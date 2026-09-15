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
_MAX_HOLD_LEN = 256


def _clean(raw: str) -> str:
    return LineCleaner().feed(raw + "\n")[0]


def _starts_with_cr(raw: str) -> bool:
    """줄 앞 코드에 CR 이 있으면 커서가 0열로 간다: 펌웨어가 프롬프트 줄을 지우고 새로 찍는 경우."""
    return "\r" in _LEAD.match(raw).group(0)  # type: ignore[union-attr]


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
            if (start or i > 0 or _starts_with_cr(raw)) and self.accept(line):
                plots.append(line)
                shown.append(_LEAD.match(raw).group(0))  # type: ignore[union-attr]
            else:
                shown.append(raw + "\n")
        tail = parts[-1]
        tail_at_start = (start if len(parts) == 1 else True) or _starts_with_cr(tail)
        if tail and tail_at_start and self._could_be_plot(tail):
            self._partial = tail
            self._since = self.clock()
            self._line_start = True
        else:
            shown.append(tail)
            self._line_start = tail_at_start if not tail else False
        return "".join(shown), plots

    def flush(self, force: bool = False) -> str:
        """오래 붙잡은 끝 조각을 터미널로 돌려준다 (줄바꿈 없이 끝나는 출력이 멈춰 보이지 않게)."""
        if not self._partial or (not force and self.clock() - self._since < self.HOLD_S):
            return ""
        text, self._partial = self._partial, ""
        self._line_start = False
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
