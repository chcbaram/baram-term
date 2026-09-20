"""BLE 장치를 시리얼 포트처럼 쓰는 전송 (Nordic UART Service).

`ble://이름` 을 포트로 주면 그 이름을 광고하는 장치에 붙어 NUS 로 주고받는다. 앱 입장에서는 장치 객체가
pyserial 과 같은 최소 인터페이스(read, write, in_waiting, close, is_open)만 있으면 되므로
(fake_device.py 와 같다), 터미널·그래프·HEX·로그·자동완성·외부 제어가 그대로 동작한다.

주소가 아니라 **이름**을 기본으로 저장한다: macOS 는 장치 주소 대신 PC 마다 다른 CoreBluetooth UUID 를
주기 때문에, 주소로 저장하면 다른 PC 에서 같은 보드를 못 찾는다. 같은 이름이 여럿이면 광고의 제조사
데이터 끝 4바이트를 꼬리표로 덧붙인다 (`ble://이름#1a2b3c4d`).

bleak 은 선택 설치(`baram-term[ble]`)라 여기서만, 그것도 함수 안에서 늦게 불러온다: 없는 PC 에서
baram-term 이 못 뜨면 안 되고, BLE 를 끄고 쓰는 사람은 macOS 블루투스 권한 대화상자도 볼 이유가 없다.
bleak 은 asyncio 전용이므로 장치마다 백그라운드 스레드에서 이벤트 루프를 돌리고, 앱의 수신/송신
스레드는 평소처럼 블로킹 호출만 한다.
"""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass, field
from typing import Any

BLE_SCHEME = "ble://"
# Nordic UART Service. RX 는 장치가 받는 쪽(우리가 쓴다), TX 는 장치가 보내는 쪽(우리가 구독한다)
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"

SCAN_TIMEOUT_S = 5.0
CONNECT_TIMEOUT_S = 20.0
WRITE_TIMEOUT_S = 5.0
CLOSE_TIMEOUT_S = 5.0
READ_TIMEOUT_S = 0.05  # pyserial 의 timeout 과 같은 자리: 이 시간만 기다리고 빈 손으로 돌아온다
# 광고 제조사 데이터에서 꼬리표로 쓸 바이트 수 (보드가 칩 고유 ID 하위 4바이트를 싣는다)
TAG_BYTES = 4
# 장치 주소로 볼 글자: MAC (AA:BB:..) 또는 macOS 의 CoreBluetooth UUID
_ADDRESS = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$|^[0-9A-Fa-f]{8}-(?:[0-9A-Fa-f]{4}-){3}[0-9A-Fa-f]{12}$")

INSTALL_HINT = "BLE needs the bleak package: pip install 'baram-term[ble]'"


def available() -> bool:
    """bleak 이 설치돼 있는지 (실제로 불러오지는 않는다)."""
    import importlib.util

    return importlib.util.find_spec("bleak") is not None


def _bleak() -> Any:
    try:
        import bleak
    except ImportError as e:
        raise OSError(INSTALL_HINT) from e
    return bleak


@dataclass
class BleFound:
    """스캔에서 본 장치 하나."""

    name: str
    address: str
    rssi: int = 0
    tag: str = ""  # 제조사 데이터 끝 TAG_BYTES 바이트 (같은 이름을 구별하는 데 쓴다)

    def url(self, unique: bool = True) -> str:
        """포트로 저장할 주소. 이름이 없으면 장치 주소로 떨어진다."""
        if not self.name:
            return BLE_SCHEME + self.address
        return BLE_SCHEME + self.name + (f"#{self.tag}" if unique and self.tag else "")

    def label(self) -> str:
        name = self.name or self.address
        parts = [f"{self.rssi}dBm"] if self.rssi else []
        if self.tag:
            parts.append(self.tag)
        return f"{name} ({', '.join(parts)})" if parts else name


@dataclass
class Target:
    """`ble://...` 을 무엇으로 찾을지."""

    name: str = ""
    tag: str = ""
    address: str = ""

    def matches(self, found: BleFound) -> bool:
        if self.address:
            return found.address.lower() == self.address.lower()
        if found.name != self.name:
            return False
        return not self.tag or found.tag == self.tag


def parse_target(port: str) -> Target:
    text = port[len(BLE_SCHEME) :] if port.startswith(BLE_SCHEME) else port
    text, _, tag = text.partition("#")
    if _ADDRESS.match(text):
        return Target(address=text)
    return Target(name=text, tag=tag.lower())


def _tag_of(manufacturer_data: dict[int, bytes]) -> str:
    """제조사 데이터의 끝 TAG_BYTES 바이트. 보드 고유 ID 자리라 같은 이름을 구별한다."""
    for value in manufacturer_data.values():
        if len(value) >= TAG_BYTES:
            return bytes(value[-TAG_BYTES:]).hex()
    return ""


def _found(device: Any, adv: Any) -> BleFound:
    name = adv.local_name or getattr(device, "name", "") or ""
    return BleFound(name=name, address=device.address, rssi=adv.rssi or 0, tag=_tag_of(dict(adv.manufacturer_data)))


def _serves_nus(adv: Any) -> bool:
    return any(str(u).lower() == NUS_SERVICE for u in adv.service_uuids)


async def _discover(timeout: float) -> list[tuple[Any, Any]]:
    found = await _bleak().BleakScanner.discover(timeout=timeout, return_adv=True)
    return list(found.values())


def scan(timeout: float = SCAN_TIMEOUT_S, nus_only: bool = True) -> list[BleFound]:
    """둘레의 장치를 찾는다 (기본은 NUS 를 광고하는 것만). 가까운 것부터."""
    pairs = asyncio.run(_discover(timeout))
    devices = [_found(d, a) for d, a in pairs if not nus_only or _serves_nus(a)]
    return sorted(devices, key=lambda d: (-d.rssi, d.name.lower()))


async def _find(target: Target, timeout: float) -> Any:
    """target 에 맞는 bleak 장치. 없으면 OSError.

    목록을 만들 때(scan)와 달리 여기서는 **찾는 즉시** 멈춘다. discover() 는 장치를 이미 봤어도
    정해진 시간을 꽉 채우기 때문에, 그대로 쓰면 연결할 때마다 몇 초씩 기다리게 된다.
    """
    device = await _bleak().BleakScanner.find_device_by_filter(
        lambda d, adv: target.matches(_found(d, adv)), timeout=timeout
    )
    if device is None:
        what = target.address or target.name + (f"#{target.tag}" if target.tag else "")
        raise OSError(f"BLE device not found: {what}")
    return device


class BleDevice:
    """pyserial 처럼 보이는 NUS 연결. 모든 bleak 호출은 자기 이벤트 루프 스레드에서 돈다."""

    def __init__(
        self,
        port: str,
        *,
        scan_timeout: float = SCAN_TIMEOUT_S,
        connect_timeout: float = CONNECT_TIMEOUT_S,
    ):
        self.timeout = READ_TIMEOUT_S
        self.port = port
        self.target = parse_target(port)
        self.is_open = False
        self.mtu = 0
        self.name = ""
        self.address = ""
        self._buf = bytearray()
        self._cv = threading.Condition()
        self._client: Any = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, name="baram-ble", daemon=True)
        self._thread.start()
        try:
            self._call(self._connect(scan_timeout), scan_timeout + connect_timeout)
        except BaseException:
            self._shutdown_loop()
            raise

    # ---- asyncio 다리 ---------------------------------------------------

    def _call(self, coro: Any, timeout: float) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except asyncio.TimeoutError as e:
            future.cancel()
            raise OSError(f"BLE timed out after {timeout:g}s") from e

    def _shutdown_loop(self) -> None:
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._loop.close()

    async def _connect(self, scan_timeout: float) -> None:
        device = await _find(self.target, scan_timeout)
        client = _bleak().BleakClient(device, disconnected_callback=self._on_disconnect)
        await client.connect()
        try:
            await client.start_notify(NUS_TX, self._on_notify)
        except Exception:
            await client.disconnect()
            raise
        self._client = client
        self.mtu = getattr(client, "mtu_size", 0) or 0
        self.name = getattr(device, "name", "") or self.target.name
        self.address = device.address
        self.is_open = True

    # ---- 콜백 (이벤트 루프 스레드) ---------------------------------------

    def _on_notify(self, _characteristic: Any, data: bytearray) -> None:
        with self._cv:
            self._buf.extend(data)
            self._cv.notify_all()

    def _on_disconnect(self, _client: Any) -> None:
        # 남은 글자는 그대로 두고 닫힘만 알린다: read 가 마지막 줄까지 넘겨준 뒤 오류를 낸다
        with self._cv:
            self.is_open = False
            self._cv.notify_all()

    # ---- pyserial 처럼 보이는 부분 ---------------------------------------

    @property
    def in_waiting(self) -> int:
        with self._cv:
            return len(self._buf)

    def read(self, size: int = 1) -> bytes:
        with self._cv:
            if not self._buf:
                if not self.is_open:
                    raise OSError("BLE disconnected")
                self._cv.wait(self.timeout)
            data = bytes(self._buf[:size])
            del self._buf[:size]
            if not data and not self.is_open:
                raise OSError("BLE disconnected")
            return data

    def write(self, data: bytes) -> int:
        if not self.is_open or self._client is None:
            raise OSError("BLE disconnected")
        # 한 번에 MTU - 3 바이트까지 (ATT 헤더 3바이트). 모르면 기본 MTU 23 을 가정한다
        chunk = max(20, (self.mtu or 23) - 3)
        for start in range(0, len(data), chunk):
            self._call(self._write(bytes(data[start : start + chunk])), WRITE_TIMEOUT_S)
        return len(data)

    async def _write(self, data: bytes) -> None:
        # response=False (write without response): 장치가 받은 대로 에코를 보내므로 응답을 기다릴 필요가 없다
        await self._client.write_gatt_char(NUS_RX, data, response=False)

    def close(self) -> None:
        was_open, self.is_open = self.is_open, False
        if self._client is not None and was_open:
            try:
                self._call(self._client.disconnect(), CLOSE_TIMEOUT_S)
            except (OSError, Exception):
                pass  # 이미 끊겼거나 끊는 중이면 그대로 둔다
        self._client = None
        with self._cv:
            self._cv.notify_all()
        if self._loop.is_running():
            self._shutdown_loop()


def open_ble(port: str, **kwargs: Any) -> BleDevice:
    if not available():
        raise OSError(INSTALL_HINT)
    return BleDevice(port, **kwargs)


# UI 가 쓰는 짧은 이름: 상태줄과 포트 설정 창에서 ble:// 주소를 사람이 읽는 꼴로
def display_name(port: str) -> str:
    target = parse_target(port)
    return target.address or target.name or port


@dataclass
class ScanResult:
    """UI 로 넘기는 스캔 결과 (오류도 같이 넘긴다: 스캔은 다른 스레드에서 돈다)."""

    devices: list[BleFound] = field(default_factory=list)
    error: str = ""
