"""Built-in strings of library widgets (dialog buttons, file dialog).

앱이 set_language("ko" | "en") 로 고른다. 고르지 않으면 환경 locale(LC_ALL/LC_MESSAGES/LANG) 이
ko 로 시작할 때 한국어, 아니면 영어. 위젯마다 buttons=/text= 로 따로 넘기면 그 글자가 우선한다.
"""

from __future__ import annotations

import locale
import os

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "ok": "OK",
        "cancel": "Cancel",
        "yes": "Yes",
        "no": "No",
        "close": "Close",
        "filedialog.folder": "Folder",
        "filedialog.file": "File",
        "filedialog.name": "Name",
        "filedialog.up": "▲ Up",
        "filedialog.new_folder": "New folder",
        "filedialog.save": "Save",
        "filedialog.open": "Open",
        "filedialog.cannot_read": "cannot read folder: {error}",
        "filedialog.not_found": "not found: {path}",
        "filedialog.no_name": "enter a file name",
        "filedialog.mkdir_failed": "could not create folder: {error}",
    },
    "ko": {
        "ok": "확인",
        "cancel": "취소",
        "yes": "예",
        "no": "아니오",
        "close": "닫기",
        "filedialog.folder": "폴더",
        "filedialog.file": "파일",
        "filedialog.name": "이름",
        "filedialog.up": "▲ 위로",
        "filedialog.new_folder": "새 폴더",
        "filedialog.save": "저장",
        "filedialog.open": "열기",
        "filedialog.cannot_read": "폴더를 읽을 수 없습니다: {error}",
        "filedialog.not_found": "찾을 수 없습니다: {path}",
        "filedialog.no_name": "파일 이름을 입력하세요",
        "filedialog.mkdir_failed": "폴더를 만들지 못했습니다: {error}",
    },
}
LANGUAGES = tuple(STRINGS)

_language: str | None = None


def detect_language() -> str:
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var)
        if value:
            return "ko" if value.lower().startswith("ko") else "en"
    try:
        name = locale.getlocale()[0] or ""
    except ValueError:
        name = ""
    return "ko" if name.lower().startswith("ko") else "en"


def set_language(lang: str | None) -> None:
    """ko | en. 그 밖의 값이나 None 이면 환경 locale 로 정한다."""
    global _language
    _language = lang if lang in STRINGS else detect_language()


def language() -> str:
    if _language is None:
        set_language(None)
    return _language  # type: ignore[return-value]


def text(key: str) -> str:
    return STRINGS[language()].get(key) or STRINGS["en"].get(key, key)


def texts(prefix: str) -> dict[str, str]:
    """prefix.* 글자를 prefix 를 뗀 키로 (예: texts("filedialog")["save"])."""
    head = prefix + "."
    return {key[len(head) :]: text(key) for key in STRINGS["en"] if key.startswith(head)}
