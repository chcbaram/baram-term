"""Modal dialog on the popup layer.

Enter 는 기본 버튼, Esc 는 취소 버튼으로 끝낸다. 결과는 on_result(버튼 인덱스) 콜백으로 받는다.
Qt 의 exec() 처럼 블로킹하지 않는다: 이벤트 루프가 계속 돌아야 워커 스레드 데이터와 화면 갱신이 멈추지 않는다.
"""

from __future__ import annotations

from functools import partial
from typing import Callable, Sequence

from retroui.core.geometry import Rect
from retroui.core.wcwidth import str_width
from retroui.input.events import Event, Key, KeyEvent
from retroui.render.painter import Painter
from retroui.widgets.base import SizeHint, Widget
from retroui.widgets.button import Button
from retroui.widgets.containers import HBox, Spacer, VBox
from retroui.widgets.label import Label
from retroui.widgets.popup import Popup


class Dialog(Popup):
    modal = True
    close_on_outside_click = False

    def __init__(
        self,
        title: str,
        body: Widget,
        buttons: Sequence[str] = ("확인", "취소"),
        *,
        default: int = 0,
        cancel: int | None = None,
        on_result: Callable[[int], None] | None = None,
        **kw,
    ):
        super().__init__(**kw)
        self.title = title
        self.body = body
        self.default = default
        self.cancel = len(buttons) - 1 if cancel is None else cancel
        self.on_result = on_result
        self.result: int | None = None
        self.buttons = [Button(text, on_click=partial(self.finish, i)) for i, text in enumerate(buttons)]
        self.add(VBox(body, HBox(Spacer(), *self.buttons, spacing=2), spacing=1, margin=1))

    def _fit_margins(self) -> None:
        # 박스 버튼은 테두리 선을 셀 안쪽으로 당겨 그려(boxdraw.EDGE_INSET) 버튼 아래 칸이 이미 비어 보인다.
        # 여기에 아래 여백 줄까지 두면 버튼 아래(약 2.2줄)가 위(1.7줄)보다 넓어 버튼이 떠 보인다.
        # 한 줄 버튼은 아래 여백 1줄일 때 위아래(1.5줄)가 대칭이다
        box_buttons = bool(self.buttons) and self.buttons[0].effective_style == "box"
        self.children[0].margin = (1, 1, 1, 0) if box_buttons else 1

    def size_hint(self) -> SizeHint:
        self._fit_margins()
        h = self.children[0].effective_hint()
        title_w = str_width(self.title) + 8
        return SizeHint(max(h.min_w + 2, title_w), h.min_h + 2, max(h.pref_w + 2, title_w), h.pref_h + 2)

    def layout_children(self) -> None:
        self._fit_margins()
        self.children[0]._do_layout(self.rect.inset(1))

    def open(self, app) -> None:
        # 크기 계산 전에 앱에 붙여야 한다. 안 붙으면 버튼이 기본 테마(한 줄 버튼) 기준으로 크기를 잡고,
        # 그리기는 앱 테마(mono 박스 버튼)로 해서 버튼이 잘리고 클릭 위치가 어긋난다
        self._app = app
        hint = self.effective_hint()
        w = min(hint.pref_w, app.cols)
        h = min(hint.pref_h, app.rows)
        app.open_popup(self, (app.cols - w) // 2, (app.rows - h) // 2, w, h)

    def finish(self, index: int) -> None:
        if not self.is_open:
            return
        self.result = index
        self.close()
        if self.on_result is not None:
            self.on_result(index)

    def paint(self, p: Painter) -> None:
        theme = self.theme
        pal = theme.palette
        p.box(Rect(0, 0, self.rect.w, self.rect.h), theme.box, pal.border_focus, pal.bg, title=self.title, title_fg=pal.accent)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent) and not ev.mod:
            if ev.key == Key.ESCAPE:
                self.finish(self.cancel)
                return True
            if ev.is_enter:
                self.finish(self.default)
                return True
        return False


def message_box(
    app,
    title: str,
    text: str,
    buttons: Sequence[str] = ("확인",),
    *,
    on_result: Callable[[int], None] | None = None,
    default: int = 0,
) -> Dialog:
    body = VBox(*[Label(line) for line in text.split("\n")])
    dialog = Dialog(title, body, buttons, default=default, on_result=on_result)
    dialog.open(app)
    return dialog
