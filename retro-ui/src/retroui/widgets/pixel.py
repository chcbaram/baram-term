"""Base for widgets that draw real pixels inside their cell area.

셀 격자(글자)와 별도로, pixel_rect() 셀 영역을 오프스크린 서피스에 픽셀로 그린다.
App 이 셀 렌더링 뒤에 이 서피스를 화면에 합성한다. 다시 그리는 시점은 두 가지다.
- invalidate_pixels(): 크기/설정 변경 등으로 즉시 다시 그려야 할 때
- frame_deadline()/poll_frame(): 스트리밍 데이터처럼 주기적으로 확인해야 할 때
"""

from __future__ import annotations

import pygame

from retroui.core.geometry import Rect
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.widgets.base import Widget


class PixelWidget(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self._surface: pygame.Surface | None = None
        self._pixels_dirty = True

    def pixel_rect(self) -> Rect:
        """픽셀로 그릴 영역 (절대 셀 좌표)."""
        return self.rect

    def frame_deadline(self) -> float | None:
        """다음에 poll_frame() 을 불러야 할 monotonic 시각. None 이면 폴링하지 않는다."""
        return None

    def poll_frame(self, now: float) -> bool:
        """deadline 에 도달했을 때 호출된다. True 를 돌려주면 render_pixels() 가 호출된다."""
        return False

    def render_pixels(self, surf: pygame.Surface, scale: float) -> None:
        pass

    def invalidate_pixels(self) -> None:
        self._pixels_dirty = True

    def paint(self, p: Painter) -> None:
        local = self.pixel_rect().translate(-self.rect.x, -self.rect.y)
        # PIXEL 셀은 셀 렌더러가 건너뛰므로 합성된 픽셀을 덮어쓰지 않는다
        p.fill(local, " ", self.palette.fg, self.palette.plot_bg, Attr.PIXEL)

    def _do_layout(self, rect: Rect) -> None:
        if rect != self.rect:
            self._pixels_dirty = True
        super()._do_layout(rect)
