"""Overlay layer base: pull-down menus, combo lists, dialogs.

App.open_popup() 으로 화면 위 레이어에 올린다. 레이어는 스택으로 쌓이고, 위 레이어가
입력과 포커스를 먼저 받는다. 셀은 아래 레이어 위에 덮어 그리고, 픽셀 위젯(플롯)은
팝업 영역을 빼고 합성해서 팝업을 덮지 않는다.
"""

from __future__ import annotations

from retroui.core.geometry import Rect
from retroui.widgets.base import Widget


class Popup(Widget):
    # True 면 아래 레이어로 입력이 가지 않고, 바깥 클릭도 무시한다 (대화상자)
    modal = False
    # 비모달 팝업은 바깥을 클릭하면 닫히고, 그 클릭은 아래 위젯으로 그대로 전달된다
    close_on_outside_click = True

    def __init__(self, *, shadow: bool | None = None, **kw):
        super().__init__(**kw)
        self.shadow = shadow
        # 팝업을 연 위젯. 이 위젯을 클릭하면 바깥 클릭으로 보지 않는다 (메뉴 제목 클릭으로 토글)
        self.owner: Widget | None = None
        self._prev_focus: Widget | None = None

    @property
    def has_shadow(self) -> bool:
        return self.theme.shadow if self.shadow is None else self.shadow

    def outer_rect(self) -> Rect:
        """그림자까지 포함한 영역 (오른쪽 2칸, 아래 1줄)."""
        r = self.rect
        if self.has_shadow:
            return Rect(r.x, r.y, r.w + 2, r.h + 1)
        return r

    @property
    def is_open(self) -> bool:
        app = self._app
        return app is not None and any(p is self for p in app.popups)

    def close(self) -> None:
        app = self._app
        if app is not None:
            app.close_popup(self)

    def on_close(self) -> None:
        pass
