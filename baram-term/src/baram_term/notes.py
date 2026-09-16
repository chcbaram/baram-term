"""Memo pages (right panel tabs): load/save, and export/import as .txt or .json.

설정과 따로 둔다 (`notes.json`): 메모는 길어질 수 있고, 설정 파일은 자주 통째로 다시 쓴다.
저장 위치는 설정 폴더 (settings.config_dir) 라서 저장소에는 올라가지 않는다.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from baram_term.settings import config_dir

MAX_NOTES = 8
MAX_TITLE = 20
FORMAT_VERSION = 1


@dataclass
class Note:
    title: str
    text: str = ""


def default_path() -> Path:
    return config_dir() / "notes.json"


def clean_title(title: str, fallback: str = "memo") -> str:
    title = " ".join(str(title).split())[:MAX_TITLE]
    return title or fallback


def unique_title(title: str, existing: list[str]) -> str:
    """같은 제목이 있으면 "boot (2)" 처럼 번호를 붙인다 (덮어쓰지 않는다)."""
    title = clean_title(title)
    if title not in existing:
        return title
    for n in range(2, 100):
        candidate = clean_title(f"{title} ({n})")
        if candidate not in existing:
            return candidate
    return title


def _notes_from(raw: object) -> list[Note]:
    notes = []
    if isinstance(raw, dict):
        raw = raw.get("notes")
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("title"), str) and isinstance(item.get("text"), str):
                notes.append(Note(clean_title(item["title"]), item["text"]))
    return notes[:MAX_NOTES]


def load(path: Path | str) -> tuple[list[Note], str | None]:
    """(메모 목록, 오류 메시지). 파일이 없으면 빈 목록."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], None
    except (OSError, ValueError) as e:
        return [], str(e)
    return _notes_from(raw), None


def save(notes: list[Note], path: Path | str) -> None:
    """설정 파일과 같은 방식: 임시 파일에 쓰고 바꿔 끼운다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": FORMAT_VERSION, "notes": [asdict(n) for n in notes[:MAX_NOTES]]}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".notes-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def export_text(note: Note, path: Path | str) -> None:
    Path(path).write_text(note.text if note.text.endswith("\n") or not note.text else note.text + "\n", encoding="utf-8")


def export_all(notes: list[Note], path: Path | str) -> None:
    save(notes, path)


def import_file(path: Path | str) -> list[Note]:
    """.json 이면 여러 메모, 그 밖의 파일은 글자 그대로 한 메모 (제목은 파일 이름)."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            notes = _notes_from(json.loads(text))
        except ValueError:
            notes = []
        if notes:
            return notes
    return [Note(clean_title(path.stem), text.replace("\r\n", "\n").rstrip("\n"))]
