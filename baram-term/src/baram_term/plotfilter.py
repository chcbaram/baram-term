"""Keep plot lines out of the terminal (Arduino IDE shows monitor and plotter separately).

받은 글자를 줄 단위로 보고 그래프 값으로 읽히는 줄은 터미널에 넘기지 않는다.
- 줄 앞의 CR/ESC 코드는 남긴다: 펌웨어가 "\\r\\x1b[K" 로 프롬프트 줄을 지우고 값을 찍은 뒤 프롬프트를
  다시 그리는데, 지우는 코드까지 버리면 프롬프트가 "cli# cli# " 처럼 두 번 찍힌다.
- 아직 줄바꿈이 오지 않은 끝 조각은 그래프 줄이 될 수 있는 글자로만 되어 있을 때만 잠깐(HOLD_S) 붙잡는다.
  "cli# " 같은 프롬프트는 바로 넘어가서 입력 반응이 늦어지지 않는다.
"""

from __future__ import annotations

import re
import time
from typing import Callable

from baram_term.logger import LineCleaner
from baram_term.plotdata import parse_line, plot_format

# 줄 앞의 CR 과 ESC 시퀀스 (CSI 또는 두 글자 ESC)
_LEAD = re.compile(r"(?:\r|\x1b\[[0-9;?]*[@-~]|\x1b[@-Z\\-_])*")
# 그래프 줄에 나올 수 있는 글자만으로 된 조각 (Teleplot ">", 이름, 숫자, 구분자)
_PLOT_CHARS = re.compile(r"[>\w.:=,;+\-§| \t]*")
# 끝에서 잘린 ESC 시퀀스 ("\x1b", "\x1b[", "\x1b[0;3" ...)
_INCOMPLETE_ESC = re.compile(r"\x1b(?:\[[0-9;?]*)?$")
_MAX_HOLD_LEN = 256


def _clean(raw: str) -> str:
    # 수신이 ESC 시퀀스 중간에서 잘리면 붙인 "\n" 까지 그 시퀀스에 먹혀 줄이 하나도 안 나온다
    lines = LineCleaner().feed(raw + "\n")
    return lines[0] if lines else ""


def _column_reset(raw: str, partial: bool = False) -> bool:
    """줄 도중에 CR 이 있으면 커서가 0열로 돌아간다: 앞에 찍힌 글자는 지워지고 뒤엣것만 남는다.

    펌웨어가 프롬프트 줄을 지우고 값을 찍을 때 앞에 방금 친 글자의 에코가 붙어 오기도 한다
    (`"n\r\x1b[K>ax:949"`). 줄 앞 CR 만 보면 이런 줄을 놓쳐 값이 터미널에 찍혔다.
    맨 끝 CR 은 CRLF 의 일부라 뺀다: `"1,2,3\r\n"` 같은 입력 에코까지 그래프 줄로 보면 안 된다.
    다만 아직 줄바꿈이 오지 않은 조각(partial)에서는 맨 끝 CR 도 커서를 0열로 보낸 것이 맞다.
    """
    return "\r" in (raw if partial else raw.rstrip("\r"))


class PlotLineFilter:
    HOLD_S = 0.2

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        accept: Callable[[str], bool] | None = None,
        expected_format: Callable[[], str | None] | None = None,
    ):
        self.clock = clock
        # accept(line): 그래프로 받을 줄인지 (앱이 형식 고정 등을 판단). 없으면 parse_line 으로만
        self.accept = accept or (lambda line: parse_line(line) is not None)
        self.expected_format = expected_format or (lambda: None)
        self._partial = ""
        self._since = 0.0
        self._line_start = True  # 지금까지 넘긴 글자가 줄바꿈으로 끝났는가 (수신 흐름 기준)

    @property
    def holding(self) -> bool:
        return bool(self._partial)

    def feed(self, text: str) -> tuple[str, list[str]]:
        """(터미널에 보낼 글자, 그래프 줄 목록)."""
        start = self._line_start  # 붙잡은 조각은 늘 줄 처음에서 시작했다
        data = self._partial + text
        self._partial = ""
        shown: list[str] = []
        plots: list[str] = []
        parts = data.split("\n")
        for i, raw in enumerate(parts[:-1]):
            line = _clean(raw)
            # 줄 중간부터 이어진 조각(프롬프트 뒤 에코 등)은 그래프 줄로 보지 않는다
            if (start or i > 0 or _column_reset(raw)) and self.accept(line):
                plots.append(line)
                # 값 글자만 빼고 앞의 코드는 그대로 넘긴다 (지우는 코드까지 버리면 프롬프트가 겹친다).
                # 값 앞에 에코가 붙어 온 경우 그 에코도 넘긴다 — 뒤따르는 CR/지우기가 알아서 지운다
                at = raw.rfind(line) if line else -1
                shown.append(raw[:at] if at > 0 else _LEAD.match(raw).group(0))  # type: ignore[union-attr]
            else:
                shown.append(raw + "\n")
        tail = parts[-1]
        # 끝이 잘린 ESC 시퀀스는 그 부분만 다음 조각까지 들고 있는다. 그냥 흘려보내면 다음 조각의
        # "[K>ax:1" 이 ESC 없는 보통 글자로 읽혀 그래프 줄을 놓치고 터미널에 찍혔다
        esc = _INCOMPLETE_ESC.search(tail)
        pending_esc = tail[esc.start() :] if esc else ""
        tail = tail[: esc.start()] if esc else tail
        tail_at_start = (start if len(parts) == 1 else True) or _column_reset(tail or pending_esc, partial=True)
        if tail and tail_at_start and self._could_be_plot(tail):
            self._partial = tail + pending_esc
            self._since = self.clock()
            self._line_start = True
        else:
            shown.append(tail)
            self._partial = pending_esc
            if pending_esc:
                self._since = self.clock()
            # 커서 코드만 있는 조각(프롬프트를 지우는 "\r\x1b[K" 등)은 글자를 찍지 않았으니
            # 다음 조각도 줄 처음이다. 여기서 False 로 두면 수신 조각이 그 코드와 값 사이에서
            # 잘렸을 때 다음 값 줄을 줄 중간으로 보고 터미널에 흘려보냈다
            self._line_start = tail_at_start and not _clean(tail).strip()
        return "".join(shown), plots

    def flush(self, force: bool = False) -> str:
        """오래 붙잡은 끝 조각을 터미널로 돌려준다 (줄바꿈 없이 끝나는 출력이 멈춰 보이지 않게)."""
        if not self._partial or (not force and self.clock() - self._since < self.HOLD_S):
            return ""
        text, self._partial = self._partial, ""
        self._line_start = not _clean(text).strip()  # 커서 코드만이면 여전히 줄 처음이다
        return text

    def _could_be_plot(self, tail: str) -> bool:
        if len(tail) > _MAX_HOLD_LEN:
            return False
        text = _clean(tail)
        if not text.strip() or _PLOT_CHARS.fullmatch(text) is None:
            return False
        expected = self.expected_format()
        # 형식이 정해졌으면 그 형식으로 시작하는 조각만 기다린다 (> 없는 글자로 시작하는 조각은 바로 보낸다)
        return expected is None or plot_format(text) == expected
