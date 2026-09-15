"""File open/save dialog drawn inside the app.

OS 기본 창을 쓰지 않는 이유: macOS 에서 SDL 과 Tk 를 한 프로세스에서 같이 돌리면 멈추거나 죽기 쉽고,
외부 명령(osascript/zenity/PowerShell)은 OS 마다 다르고 창이 떠 있는 동안 이벤트 루프(수신 화면)가 멈춘다.

결과는 on_result(Path | None) 으로 받는다 (취소는 None). Dialog 처럼 블로킹하지 않는다.
"""

from __future__ import annotations

import fnmatch
import os
import time
import unicodedata
from pathlib import Path
from typing import Callable, Sequence

from retroui.core.wcwidth import str_width
from retroui.input.events import Event, Key, KeyEvent
from retroui.widgets.base import Widget
from retroui.widgets.button import Button
from retroui.widgets.containers import HBox, Spacer, VBox
from retroui.widgets.dialog import Dialog, message_box
from retroui.widgets.label import Label
from retroui.widgets.lineedit import LineEdit
from retroui.widgets.listview import ListView

DEFAULT_TEXT = {
    "folder": "폴더",
    "file": "파일",
    "name": "이름",
    "up": "▲ 위로",
    "new_folder": "새 폴더",
    "save": "저장",
    "open": "열기",
    "ok": "확인",
    "cancel": "취소",
    "yes": "예",
    "no": "아니오",
    "cannot_read": "폴더를 읽을 수 없습니다: {error}",
    "not_found": "찾을 수 없습니다: {path}",
    "no_name": "파일 이름을 입력하세요",
    "mkdir_failed": "폴더를 만들지 못했습니다: {error}",
}


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "K", "M", "G"):
        if size < 1024 or unit == "G":
            return f"{int(size)}B" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{n}B"


def _nfc(name: str) -> str:
    # macOS Finder 가 만든 한글 이름은 NFD(자모 분리)라 그대로 그리면 글자가 풀어져 보인다
    return unicodedata.normalize("NFC", name)


def _existing_dir(path: Path) -> Path:
    path = Path(os.path.abspath(path))
    while not path.is_dir() and path.parent != path:
        path = path.parent
    return path if path.is_dir() else Path.home()


class FileDialog(Dialog):
    def __init__(
        self,
        title: str,
        *,
        mode: str = "save",
        directory: str | Path | None = None,
        filename: str = "",
        patterns: Sequence[str] | None = None,
        show_hidden: bool = False,
        extra: Widget | None = None,
        confirm_existing: str | None = None,
        text: dict[str, str] | None = None,
        on_result: Callable[[Path | None], None] | None = None,
    ):
        if mode not in ("save", "open"):
            raise ValueError(f"mode must be 'save' or 'open': {mode!r}")
        t = self.text = {**DEFAULT_TEXT, **(text or {})}
        self.mode = mode
        self.patterns = [p.lower() for p in patterns] if patterns else None
        self.show_hidden = show_hidden
        # 저장 모드에서 이미 있는 파일을 고르면 물어볼 문장 ({name} 자리에 파일 이름). None 이면 묻지 않는다
        self.confirm_existing = confirm_existing
        self.on_path = on_result
        self.path: Path | None = None
        self.directory = _existing_dir(Path(os.path.expanduser(str(directory))) if directory else Path.cwd())
        self.entries: list[tuple[str, bool]] = []  # (실제 이름, 폴더 여부)

        self.path_edit = LineEdit(str(self.directory), on_submit=self._on_path_submit, min_size=(36, 1))
        self.up_button = Button(t["up"], on_click=self.go_up, style="fill")
        self.new_folder_button = Button(t["new_folder"], on_click=self.ask_new_folder, style="fill")
        self.list = ListView(on_activate=self._activate, on_select=self._on_select, min_size=(64, 14))
        self.name_edit = LineEdit(filename, min_size=(36, 1))
        self.message = Label("", fg="error")
        label_w = max(str_width(t["folder"]), str_width(t["file"]))
        rows: list[Widget] = [
            HBox(Label(t["folder"], min_size=(label_w, 1)), self.path_edit, self.up_button, self.new_folder_button, spacing=1),
            Spacer(1, stretch=0),
            self.list,
            Spacer(1, stretch=0),  # 목록과 입력칸 배경색이 비슷해서 붙으면 한 덩어리로 보인다
            HBox(Label(t["file"], min_size=(label_w, 1)), self.name_edit, spacing=1),
        ]
        if extra is not None:
            rows.append(extra)
        rows.append(self.message)
        super().__init__(title, VBox(*rows), (t["save"] if mode == "save" else t["open"], t["cancel"]))
        self.refresh()

    # ---- directory -----------------------------------------------------

    def refresh(self, select: str | None = None) -> None:
        """현재 폴더를 다시 읽는다. select 이름이 있으면 그 항목을 고른다."""
        t = self.text
        error = ""
        try:
            with os.scandir(self.directory) as it:
                raw = list(it)
        except OSError as e:
            raw = []
            error = t["cannot_read"].format(error=e.strerror or e)
        dirs: list[str] = []
        files: list[tuple[str, os.stat_result | None]] = []
        for entry in raw:
            if not self.show_hidden and entry.name.startswith("."):
                continue
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            if is_dir:
                dirs.append(entry.name)
                continue
            if self.patterns and not any(fnmatch.fnmatchcase(entry.name.lower(), p) for p in self.patterns):
                continue
            try:
                st = entry.stat()
            except OSError:
                st = None
            files.append((entry.name, st))
        dirs.sort(key=str.lower)
        files.sort(key=lambda f: f[0].lower())

        self.entries = []
        items: list[str] = []
        details: list[str] = []
        if self.directory.parent != self.directory:
            self.entries.append(("..", True))
            items.append("../")
            details.append("")
        for name in dirs:
            self.entries.append((name, True))
            items.append(_nfc(name) + "/")
            details.append("")
        for name, st in files:
            self.entries.append((name, False))
            items.append(_nfc(name))
            details.append(
                f"{human_size(st.st_size)}  {time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))}" if st else ""
            )
        index = 0
        if select is not None:
            index = next((i for i, (name, _) in enumerate(self.entries) if name == select), 0)
        self.list.set_items(items, details, index)
        self.path_edit.set_text(str(self.directory), emit=False)
        self.show_message(error)

    def navigate(self, path: str | Path, select: str | None = None) -> bool:
        path = Path(os.path.expanduser(str(path)))
        if not path.is_absolute():
            path = self.directory / path
        path = Path(os.path.normpath(path))
        if not path.is_dir():
            self.show_message(self.text["not_found"].format(path=path))
            return False
        self.directory = path
        self.refresh(select)
        return True

    def go_up(self) -> None:
        if self.directory.parent != self.directory:
            self.navigate(self.directory.parent, select=self.directory.name)

    def ask_new_folder(self) -> Dialog | None:
        app = self._app
        if app is None:
            return None
        t = self.text
        edit = LineEdit("", min_size=(32, 1))

        def done(index: int) -> None:
            name = edit.text.strip()
            if index != 0 or not name:
                return
            try:
                (self.directory / name).mkdir()
            except OSError as e:
                self.show_message(t["mkdir_failed"].format(error=e.strerror or e))
                return
            self.refresh(select=name)
            app.set_focus(self.list)

        dialog = Dialog(t["new_folder"], HBox(Label(t["name"]), edit, spacing=1), (t["ok"], t["cancel"]), on_result=done)
        dialog.open(app)
        app.set_focus(edit)
        return dialog

    def show_message(self, text: str) -> None:
        self.message.set_text(text)

    # ---- dialog --------------------------------------------------------

    def open(self, app) -> None:
        super().open(app)
        if self.mode == "save" and self.name_edit.text:
            # 이름만 바로 고쳐 쓸 수 있게 확장자 앞까지 골라 둔다
            app.set_focus(self.name_edit)
            self.name_edit.move(0)
            self.name_edit.move(len(Path(self.name_edit.text).stem), extend=True)
        else:
            app.set_focus(self.list)

    def finish(self, index: int) -> None:
        if not self.is_open:
            return
        if index != self.default:
            super().finish(index)
            if self.on_path is not None:
                self.on_path(None)
            return
        t = self.text
        name = self.name_edit.text.strip()
        if not name:
            sel = self.list.selected
            if 0 <= sel < len(self.entries) and self.entries[sel][1]:
                self._activate(sel)  # 폴더를 고른 채 확인: 그 폴더로 들어간다
            else:
                self.show_message(t["no_name"])
            return
        target = Path(os.path.expanduser(name))
        if not target.is_absolute():
            target = self.directory / target
        target = Path(os.path.normpath(target))
        if target.is_dir():
            # 파일 이름 칸에 폴더 경로를 치고 Enter: 저장하지 않고 그 폴더로 간다
            self.name_edit.set_text("")
            self.navigate(target)
            return
        if self.mode == "open" and not target.is_file():
            self.show_message(t["not_found"].format(path=target))
            return
        if self.mode == "save" and not target.parent.is_dir():
            self.show_message(t["not_found"].format(path=target.parent))
            return
        if self.mode == "save" and self.confirm_existing and target.exists():
            message_box(
                self._app,
                self.title,
                self.confirm_existing.format(name=_nfc(target.name)),
                (t["yes"], t["no"]),
                on_result=lambda i: self._accept(target) if i == 0 else None,
            )
            return
        self._accept(target)

    def _accept(self, target: Path) -> None:
        self.path = target
        super().finish(self.default)
        if self.on_path is not None:
            self.on_path(target)

    def _on_path_submit(self, text: str) -> None:
        if self.navigate(text.strip() or ".") and self._app is not None:
            self._app.set_focus(self.list)

    def _activate(self, index: int) -> None:
        if not 0 <= index < len(self.entries):
            return
        name, is_dir = self.entries[index]
        if name == "..":
            self.go_up()
        elif is_dir:
            self.navigate(self.directory / name)
        else:
            self.name_edit.set_text(_nfc(name))
            self.finish(self.default)

    def _on_select(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            name, is_dir = self.entries[index]
            if not is_dir:
                self.name_edit.set_text(_nfc(name))

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent) and ev.key == Key.BACKSPACE and not ev.mod:
            # 입력칸이 처리하지 않은 Backspace (목록에 포커스): 위 폴더로
            self.go_up()
            return True
        return super().on_event(ev)
