"""demo:// — fake firmware CLI for trying baram-term without a board.

공개 펌웨어(weact-h750-mini, common/hw/src/cli.c)의 입력 처리와 출력 바이트를 흉내 낸다.
한 글자씩 받아 줄 편집과 이력을 처리하고, 화면 갱신은 펌웨어와 같은 VT100 코드로 보낸다.
pyserial Serial 과 같은 최소 인터페이스(read, write, in_waiting, close, is_open)만 제공한다.
"""

from __future__ import annotations

import math
import random
import threading
import time
from typing import Callable

PROMPT = "cli# "
_KEY_ENTER = 0x0D
_KEY_BACK = 0x08
_KEY_DEL = 0x7F
_KEY_ESC = 0x1B


class FakeCliDevice:
    def __init__(
        self,
        *,
        log_interval: float = 3.0,
        boot: bool = True,
        seed: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.clock = clock
        self.timeout = 0.05
        self.is_open = True
        self.log_interval = log_interval
        self.line = ""
        self.cursor = 0
        self.history: list[str] = []
        self._hist_pos: int | None = None
        self._esc = b""
        self._out = bytearray()
        self._cv = threading.Condition()
        self._rng = random.Random(seed)
        self._t0 = clock()
        self._last_log = self._t0
        self.commands: dict[str, Callable[[list[str]], str]] = {
            "HELP": self._cmd_help,
            "INFO": self._cmd_info,
            "LOG": self._cmd_log,
            "SENSOR": self._cmd_sensor,
            "RESET": self._cmd_reset,
        }
        if boot:
            self._emit(self._boot_log() + "\n\r" + PROMPT)

    # ---- pyserial-like interface --------------------------------------

    @property
    def in_waiting(self) -> int:
        self._tick()
        with self._cv:
            return len(self._out)

    def read(self, size: int = 1) -> bytes:
        if not self.is_open:
            raise OSError("device disconnected")
        self._tick()
        with self._cv:
            if not self._out:
                self._cv.wait(self.timeout)
            if not self.is_open:
                raise OSError("device disconnected")
            data = bytes(self._out[:size])
            del self._out[:size]
            return data

    def write(self, data: bytes) -> int:
        if not self.is_open:
            raise OSError("device disconnected")
        for b in data:
            self._key(b)
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        with self._cv:
            self.is_open = False
            self._cv.notify_all()

    # ---- firmware behaviour --------------------------------------------

    def _emit(self, text: str) -> None:
        with self._cv:
            self._out.extend(text.encode("utf-8"))
            self._cv.notify_all()

    def _uptime_ms(self) -> int:
        return int((self.clock() - self._t0) * 1000)

    def _boot_log(self) -> str:
        return (
            "\r\n[ Demo Firmware Begin... ]\r\n"
            "Booting..Name \t\t: baram-demo\r\n"
            "Booting..Ver  \t\t: V0.1.0\r\n"
            "[OK] uartInit()\r\n"
            "[OK] cliInit()\r\n"
            "[E_] canOpen()\r\n"
            f"[  ] boot confirmed ({self._uptime_ms()} ms)\r\n"
        )

    def _tick(self) -> None:
        if not self.log_interval:
            return
        now = self.clock()
        if now - self._last_log < self.log_interval:
            return
        self._last_log = now
        t = now - self._t0
        temp = 42.0 + 3.0 * math.sin(t / 5.0) + self._rng.uniform(-0.2, 0.2)
        rpm = int(1200 + 300 * math.sin(t / 3.0))
        tag = "[E_]" if self._rng.random() < 0.1 else "[OK]"
        log = f"{tag} sensor temp={temp:.1f} rpm={rpm}"
        # 입력 중인 줄을 지우고 로그를 찍은 뒤 프롬프트와 입력 중이던 글자를 다시 그린다
        redraw = PROMPT + self.line
        if self.cursor < len(self.line):
            redraw += f"\x1b[{len(self.line) - self.cursor}D"
        self._emit("\r\x1b[K" + log + "\r\n" + redraw)

    def _key(self, b: int) -> None:
        if self._esc:
            self._escape(b)
            return
        if b == _KEY_ESC:
            self._esc = b"\x1b"
        elif b == _KEY_ENTER:
            self._enter()
        elif b == _KEY_BACK:
            if self.cursor > 0:
                self.line = self.line[: self.cursor - 1] + self.line[self.cursor :]
                self.cursor -= 1
                self._emit("\b \b\x1b[1P")
        elif b == _KEY_DEL:
            if self.cursor < len(self.line):
                self.line = self.line[: self.cursor] + self.line[self.cursor + 1 :]
                self._emit("\x1b[1P")
        elif 0x20 <= b < 0x7F:
            ch = chr(b)
            if self.cursor == len(self.line):
                self.line += ch
                self._emit(ch)
            else:
                self.line = self.line[: self.cursor] + ch + self.line[self.cursor :]
                self._emit(f"\x1b[4h{ch}\x1b[4l")
            self.cursor += 1

    def _escape(self, b: int) -> None:
        self._esc += bytes([b])
        seq = self._esc
        if len(seq) < 3:
            return
        code = seq[2:3]
        if code in (b"1", b"4") and len(seq) < 4:
            return  # Home/End 는 ESC [ 1 ~ / ESC [ 4 ~ (4바이트)
        self._esc = b""
        if code == b"D" and self.cursor > 0:
            self.cursor -= 1
            self._emit("\x1b[D")
        elif code == b"C" and self.cursor < len(self.line):
            self.cursor += 1
            self._emit("\x1b[C")
        elif code in (b"A", b"B"):
            self._recall(-1 if code == b"A" else 1)
        elif code == b"1":
            if self.cursor:
                self._emit(f"\x1b[{self.cursor}D")
            self.cursor = 0
        elif code == b"4":
            if self.cursor < len(self.line):
                self._emit(f"\x1b[{len(self.line) - self.cursor}C")
            self.cursor = len(self.line)

    def _recall(self, delta: int) -> None:
        if not self.history:
            return
        pos = len(self.history) if self._hist_pos is None else self._hist_pos
        pos = max(0, min(len(self.history) - 1, pos + delta))
        self._hist_pos = pos
        clear = ""
        if self.cursor:
            clear += f"\x1b[{self.cursor}D"
        if self.line:
            clear += f"\x1b[{len(self.line)}P"
        self.line = self.history[pos]
        self.cursor = len(self.line)
        self._emit(clear + self.line)

    def _enter(self) -> None:
        line = self.line.strip()
        self.line = ""
        self.cursor = 0
        self._hist_pos = None
        out = ""
        if line:
            if not self.history or self.history[-1] != line:
                self.history.append(line)
            args = line.split()
            handler = self.commands.get(args[0].upper())
            out = "\r\n" + (handler(args[1:]) if handler else "")
        self._emit(out + "\n\r" + PROMPT)

    # ---- commands ------------------------------------------------------

    def _cmd_help(self, args: list[str]) -> str:
        body = "".join(f"{name}\r\n" for name in self.commands)
        return "\r\n---------- cmd list ---------\r\n" + body + "-----------------------------\r\n"

    def _cmd_info(self, args: list[str]) -> str:
        return f"Board  : baram-demo\r\nUptime : {self._uptime_ms()} ms\r\nPrompt : {PROMPT.strip()}\r\n"

    def _cmd_log(self, args: list[str]) -> str:
        return self._boot_log()

    def _cmd_sensor(self, args: list[str]) -> str:
        lines = []
        for i in range(5):
            lines.append(f"temp={42.0 + self._rng.uniform(-1, 1):.1f} rpm={1200 + self._rng.randint(-50, 50)}\r\n")
        return "".join(lines)

    def _cmd_reset(self, args: list[str]) -> str:
        self._t0 = self.clock()
        return self._boot_log()
