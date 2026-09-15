"""Session log file (Ctrl-A L).

받은 글자를 화면에 보이는 줄 그대로 저장한다. 펌웨어 CLI 는 줄 편집을 CR/BS/ESC[K 로 다시 그리므로
원문 바이트를 그대로 쓰면 "cli# hel\\b \\blp" 같은 줄이 되어 읽기 어렵다. 색 등 ESC 시퀀스도 뺀다.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable

# CSI 가 이보다 길면 깨진 시퀀스로 보고 버린다 (이어지는 글자를 계속 삼키지 않게)
_MAX_ESC_LEN = 32


def default_log_dir() -> Path:
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "baram-term"


def log_filename(port: str, now: float | None = None) -> str:
    """20260915-140312_cu.usbmodem1101.log 처럼 시각 + 포트 이름."""
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    name = port.rstrip("/").split("/")[-1] if port else ""
    name = re.sub(r"[^A-Za-z0-9.-]+", "_", name).strip("_.")
    return f"{stamp}_{name or 'log'}.log"


class LineCleaner:
    """CR/BS/ESC 줄 편집을 적용해 완성된 줄을 돌려준다."""

    def __init__(self) -> None:
        self.line: list[str] = []
        self.col = 0
        self._esc = ""

    def feed(self, text: str) -> list[str]:
        out: list[str] = []
        for ch in text:
            if self._esc:
                self._esc += ch
                if len(self._esc) == 2 and ch != "[":
                    self._esc = ""  # ESC 7, ESC 8 같은 두 글자 시퀀스
                elif len(self._esc) > 2 and "\x40" <= ch <= "\x7e":
                    self._csi(self._esc[2:-1], ch)
                    self._esc = ""
                elif len(self._esc) > _MAX_ESC_LEN:
                    self._esc = ""
                continue
            if ch == "\x1b":
                self._esc = ch
            elif ch == "\n":
                out.append(self._take())
            elif ch == "\r":
                self.col = 0
            elif ch == "\b":
                self.col = max(0, self.col - 1)
            elif ch == "\t" or ch >= " " and ch != "\x7f":
                self._put(ch)
        return out

    def flush(self) -> str | None:
        """아직 줄바꿈이 오지 않은 줄 (프롬프트 등)."""
        if not self.line:
            return None
        return self._take()

    def _take(self) -> str:
        line = "".join(self.line).rstrip()
        self.line = []
        self.col = 0
        return line

    def _put(self, ch: str) -> None:
        if self.col < len(self.line):
            self.line[self.col] = ch
        else:
            self.line.extend(" " * (self.col - len(self.line)))
            self.line.append(ch)
        self.col += 1

    def _csi(self, params: str, final: str) -> None:
        nums = [int(p) for p in params.split(";") if p.isdigit()]
        n = max(1, nums[0]) if nums else 1
        if final == "K":
            mode = nums[0] if nums else 0
            if mode == 0:
                del self.line[self.col :]
            elif mode == 1:
                self.line[: self.col] = [" "] * min(self.col, len(self.line))
            elif mode == 2:
                self.line = []
        elif final == "D":
            self.col = max(0, self.col - n)
        elif final == "C":
            self.col += n
        elif final == "G":
            self.col = n - 1
        elif final == "P":
            del self.line[self.col : self.col + n]
        elif final == "@":
            if self.col < len(self.line):
                self.line[self.col : self.col] = [" "] * n
        elif final == "X":
            end = min(len(self.line), self.col + n)
            self.line[self.col : end] = [" "] * max(0, end - self.col)


class SessionLog:
    def __init__(
        self,
        path: Path | str,
        *,
        timestamps: bool = False,
        header: str = "",
        clock: Callable[[], float] = time.time,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # 같은 이름이면 이어 쓴다: 사용자가 고른 파일을 지워버리지 않게
        self._fp = open(self.path, "a", encoding="utf-8", newline="\n")
        self.timestamps = timestamps
        self.clock = clock
        self.cleaner = LineCleaner()
        self.lines = 0
        if header:
            self._fp.write(header + "\n")
            self._fp.flush()

    @property
    def closed(self) -> bool:
        return self._fp.closed

    def feed(self, text: str) -> None:
        lines = self.cleaner.feed(text)
        for line in lines:
            self._write(line)
        if lines:
            self._fp.flush()  # 실행 중에도 tail -f 로 볼 수 있고, 강제 종료돼도 남는다

    def note(self, text: str) -> None:
        """터미널 안내(연결/끊김 등). 쓰던 줄이 있으면 먼저 내보낸다."""
        partial = self.cleaner.flush()
        if partial is not None:
            self._write(partial)
        self._write(f"--- {text}")
        self._fp.flush()

    def close(self) -> None:
        if self._fp.closed:
            return
        try:
            partial = self.cleaner.flush()
            if partial is not None:
                self._write(partial)
        finally:
            self._fp.close()

    def _write(self, line: str) -> None:
        if self.timestamps:
            now = self.clock()
            ms = int(now * 1000) % 1000
            line = f"[{time.strftime('%H:%M:%S', time.localtime(now))}.{ms:03d}] {line}"
        self._fp.write(line + "\n")
        self.lines += 1
