"""Default highlight rules for firmware logs."""

from __future__ import annotations

from retroui import HighlightRule
from retroui.theme import LIGHT_CYAN, LIGHT_GREEN, LIGHT_RED, YELLOW


def default_rules() -> list[HighlightRule]:
    return [
        HighlightRule.of(r"\[OK\]", LIGHT_GREEN, bold=True),
        HighlightRule.of(r"\[E_\]|\bERROR\b|\bFAIL(?:ED)?\b", LIGHT_RED, bold=True),
        HighlightRule.of(r"\[W_\]|\bWARN(?:ING)?\b", YELLOW),
        # 프롬프트: 줄 처음의 공백 없는 단어 + "# " (cli# 등)
        HighlightRule.of(r"^\S*# ", LIGHT_CYAN),
    ]
