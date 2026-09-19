"""Serial port with a background reader, a write queue and simple stats.

수신 스레드는 버퍼에만 쓰고, 버퍼가 비어 있다가 데이터가 처음 들어올 때만 notify() 를 부른다.
UI 는 notify 로 깨어나 take() 로 쌓인 바이트를 한꺼번에 가져간다. 1Mbps 로 쏟아져도 UI 호출은
프레임당 한 번 수준으로 합쳐진다. notify/on_error 는 수신 스레드에서 불리므로 app.call_soon 으로 넘겨야 한다.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable

DEMO_PORT = "demo://"


@dataclass
class PortSettings:
    port: str = ""
    baud: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    flow: str = "none"  # none | rtscts | xonxoff
    # 줄 끝/지우기 코드: 장치 CLI 마다 다르다 (공개 cli.c 는 Enter=CR, Backspace=0x08)
    enter: str = "cr"  # cr | lf | crlf
    backspace: str = "bs"  # bs (0x08) | del (0x7F)
    rx_lf: str = "crlf"  # crlf: 받은 LF 에 CR 도 적용 (LF 만 보내는 장치) | lf: 줄만 내림

    @property
    def framing(self) -> str:
        """8N1 처럼 데이터 비트, 패리티, 정지 비트."""
        stop = str(int(self.stopbits)) if float(self.stopbits).is_integer() else str(self.stopbits)
        return f"{self.bytesize}{self.parity}{stop}"

    @property
    def summary(self) -> str:
        return f"{self.baud} {self.framing}"


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return []
    return sorted(p.device for p in lp.comports())


def usb_info(path: str) -> dict[str, Any] | None:
    """포트의 USB 정보 (외부 제어의 창 고르기용). USB 장치가 아니거나 못 찾으면 None."""
    try:
        from serial.tools import list_ports as lp
    except ImportError:
        return None
    for p in lp.comports():
        if p.device != path:
            continue
        if p.vid is None:
            return None
        return {
            "vid_pid": f"{p.vid:04X}:{p.pid:04X}",
            "serial_number": p.serial_number or "",
            "description": p.description or "",
            "manufacturer": p.manufacturer or "",
            "product": p.product or "",
            "location": p.location or "",
        }
    return None


def open_device(settings: PortSettings) -> Any:
    if settings.port.startswith(DEMO_PORT):
        from baram_term.fake_device import FakeCliDevice

        return FakeCliDevice()
    import serial

    return serial.serial_for_url(
        settings.port,
        baudrate=settings.baud,
        bytesize=settings.bytesize,
        parity=settings.parity,
        stopbits=settings.stopbits,
        rtscts=settings.flow == "rtscts",
        xonxoff=settings.flow == "xonxoff",
        timeout=0.05,
        write_timeout=2,
    )


class SerialPort:
    def __init__(
        self,
        notify: Callable[[], None],
        on_error: Callable[[str], None],
        opener: Callable[[PortSettings], Any] = open_device,
    ):
        self._notify = notify
        self._on_error = on_error
        self._opener = opener
        self._lock = threading.Lock()
        self._buf = bytearray()
        self._pending = False
        self._stop = threading.Event()
        self._txq: queue.SimpleQueue[bytes | None] = queue.SimpleQueue()
        self._reader: threading.Thread | None = None
        self._writer: threading.Thread | None = None
        self.device: Any = None
        self.settings: PortSettings | None = None
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.last_rx = 0.0
        self.last_tx = 0.0

    @property
    def is_open(self) -> bool:
        return self.device is not None and not self._stop.is_set()

    def open(self, settings: PortSettings) -> None:
        """실패하면 예외를 그대로 올린다 (호출한 UI 가 알림을 띄운다)."""
        self.close()
        device = self._opener(settings)
        self.device = device
        self.settings = settings
        self._stop.clear()
        self._txq = queue.SimpleQueue()
        self._reader = threading.Thread(target=self._read_loop, args=(device,), name="baram-rx", daemon=True)
        self._writer = threading.Thread(target=self._write_loop, args=(device,), name="baram-tx", daemon=True)
        self._reader.start()
        self._writer.start()

    def close(self) -> None:
        if self.device is None:
            return
        self._stop.set()
        self._txq.put(None)
        try:
            self.device.close()
        except Exception:
            pass
        for th in (self._reader, self._writer):
            if th is not None and th is not threading.current_thread():
                th.join(timeout=1.0)
        self.device = None
        self._reader = self._writer = None

    def set_baud(self, baud: int) -> None:
        """열린 포트의 속도만 바꾼다. 다시 열지 않는다: USB CDC 보드는 포트를 다시 열 때 리셋되거나 끊길 수 있다."""
        if self.device is None:
            raise OSError("port is not open")
        self.device.baudrate = baud  # pyserial 은 열린 포트에 바로 적용한다
        if self.settings is not None:
            self.settings = replace(self.settings, baud=baud)

    def write(self, data: bytes) -> bool:
        if not self.is_open or not data:
            return False
        self._txq.put(bytes(data))
        return True

    def take(self) -> bytes:
        with self._lock:
            data = bytes(self._buf)
            self._buf.clear()
            self._pending = False
        return data

    def _read_loop(self, device: Any) -> None:
        while not self._stop.is_set():
            try:
                data = device.read(device.in_waiting or 1)
            except Exception as e:  # 장치 제거 등
                self._fail(e)
                return
            if not data:
                continue
            with self._lock:
                self._buf.extend(data)
                self.rx_bytes += len(data)
                self.last_rx = time.monotonic()
                wake = not self._pending
                self._pending = True
            if wake:
                self._notify()

    def _write_loop(self, device: Any) -> None:
        while True:
            item = self._txq.get()
            if item is None or self._stop.is_set():
                return
            try:
                device.write(item)
            except Exception as e:
                self._fail(e)
                return
            self.tx_bytes += len(item)
            self.last_tx = time.monotonic()

    def _fail(self, error: Exception) -> None:
        if self._stop.is_set():
            return  # 사용자가 닫는 중에 난 예외는 알리지 않는다
        self._stop.set()
        self._on_error(str(error) or error.__class__.__name__)
