"""Tiny message catalog: tr("key", **fmt) with JSON files in baram_term/locales.

언어 선택 순서: set_language() > 환경 변수 BARAM_TERM_LANG > 시스템 로케일(ko* 면 ko) > en.
키가 현재 언어에 없으면 en, 그래도 없으면 키 문자열 그대로 보여준다 (빠진 번역이 화면에서 바로 보이게).
"""

from __future__ import annotations

import json
import locale
import os
from importlib import resources

from retroui import i18n as retroui_i18n

LANGUAGES = ("ko", "en")

_catalogs: dict[str, dict[str, str]] = {}
_language: str | None = None


def _catalog(lang: str) -> dict[str, str]:
    if lang not in _catalogs:
        try:
            text = (resources.files("baram_term") / "locales" / f"{lang}.json").read_text(encoding="utf-8")
            _catalogs[lang] = json.loads(text)
        except FileNotFoundError:
            _catalogs[lang] = {}
    return _catalogs[lang]


def detect_language() -> str:
    env = os.environ.get("BARAM_TERM_LANG", "").lower()
    if env in LANGUAGES:
        return env
    names = [locale.getlocale()[0] or "", os.environ.get("LC_ALL", ""), os.environ.get("LANG", "")]
    return "ko" if any(n.lower().startswith("ko") for n in names) else "en"


def set_language(lang: str | None) -> None:
    global _language
    _language = lang if lang in LANGUAGES else detect_language()
    # 라이브러리 위젯(대화상자 기본 버튼, 파일 대화상자)도 같은 언어로
    retroui_i18n.set_language(_language)


def language() -> str:
    if _language is None:
        set_language(None)
    return _language  # type: ignore[return-value]


def tr(key: str, **fmt: object) -> str:
    text = _catalog(language()).get(key) or _catalog("en").get(key) or key
    return text.format(**fmt) if fmt else text
