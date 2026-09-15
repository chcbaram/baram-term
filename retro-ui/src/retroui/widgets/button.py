"""Push button with optional &mnemonic.

style:
  fill : 배경색을 채운 한 줄 버튼 (Turbo Vision 스타일)
  box  : 테두리 박스 3줄 버튼
  solid: color 로 채운 한 줄 버튼 (시작/정지처럼 눈에 띄어야 하는 버튼)
  None : 테마의 button_style 을 따른다
"""

from __future__ import annotations

from typing import Callable

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, FocusEvent, Key, KeyEvent, MouseEvent
from retroui.render.boxdraw import EDGE_HEAVY, EDGE_LIGHT
from retroui.render.cellbuffer import Attr, fill_attr
from retroui.render.painter import Painter
from retroui.theme import lighten
from retroui.widgets.base import RGB, SizeHint, Widget


def parse_mnemonic(label: str) -> tuple[str, int | None]:
    """'&Save' -> ('Save', 0). '&&' 는 '&' 문자 그대로."""
    out: list[str] = []
    idx = None
    i = 0
    while i < len(label):
        c = label[i]
        if c == "&" and i + 1 < len(label):
            if label[i + 1] == "&":
                out.append("&")
            else:
                if idx is None:
                    idx = len(out)
                out.append(label[i + 1])
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out), idx


def draw_mnemonic(p: Painter, x: int, y: int, text: str, idx: int | None, fg: RGB, bg: RGB, attr: int = 0) -> int:
    """니모닉 글자에 밑줄을 그어 text 를 쓰고 끝 열을 돌려준다."""
    if idx is None:
        return p.text(x, y, text, fg, bg, attr)
    x = p.text(x, y, text[:idx], fg, bg, attr)
    x = p.text(x, y, text[idx], fg, bg, attr | Attr.UNDERLINE)
    return p.text(x, y, text[idx + 1 :], fg, bg, attr)


class Button(Widget):
    focusable = True

    def __init__(
        self,
        text: str,
        on_click: Callable[[], None] | None = None,
        *,
        style: str | None = None,
        color: str | RGB | None = None,
        padding: int = 2,
        **kw,
    ):
        super().__init__(**kw)
        # 글자 좌우 여백 (칸). 버튼이 여러 개 늘어서는 줄에서는 1로 줄여 폭을 아낀다
        self.padding = padding
        self.fill_color = color  # solid 버튼 배경 (팔레트 이름 또는 RGB). None 이면 accent
        self.clicked = Signal()
        if on_click is not None:
            self.clicked.connect(on_click)
        self.style = style
        self.pressed = False
        self._armed = False
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self.text, self.mnemonic = parse_mnemonic(text)
        self.relayout()
        self.invalidate()

    @property
    def mnemonic_key(self) -> str | None:
        return None if self.mnemonic is None else self.text[self.mnemonic].lower()

    @property
    def effective_style(self) -> str:
        return self.style or self.theme.button_style

    def activate(self) -> None:
        self.click()

    def click(self) -> None:
        if self.enabled:
            self.clicked.emit()

    def size_hint(self) -> SizeHint:
        w = str_width(self.text) + self.padding * 2
        h = 3 if self.effective_style == "box" else 1
        return SizeHint(w, h, w, h, max_w=w, max_h=h)

    def _fg(self) -> RGB:
        pal = self.palette
        if not self.enabled:
            return pal.disabled
        return pal.button_focus_fg if self.focused else pal.button_fg

    def _draw_label(self, p: Painter, y: int, fg: RGB, bg: RGB, attr: int) -> None:
        w = self.rect.w
        label = truncate(self.text, max(0, w - self.padding * 2))
        x = (w - str_width(label)) // 2
        if self.focused:
            attr |= Attr.BOLD
        idx = self.mnemonic if label == self.text else None
        if idx is None:
            p.text(x, y, label, fg, bg, attr)
            return
        x = p.text(x, y, label[:idx], fg, bg, attr)
        x = p.text(x, y, label[idx], fg, bg, attr | Attr.UNDERLINE)
        p.text(x, y, label[idx + 1 :], fg, bg, attr)

    def paint(self, p: Painter) -> None:
        # 공간이 3줄보다 좁게 배치되면 box 대신 한 줄 버튼으로 그린다
        if self.effective_style == "box" and self.rect.h >= 3:
            self._paint_box(p)
        elif self.effective_style == "solid":
            self._paint_solid(p)
        else:
            self._paint_fill(p)

    def set_color(self, color: str | RGB | None) -> None:
        if color != self.fill_color:
            self.fill_color = color
            self.invalidate()

    def _paint_solid(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        if not self.enabled:
            bg = pal.disabled
        else:
            bg = self.color(self.fill_color if self.fill_color is not None else "accent")
            if self.hovered and not self.pressed:
                bg = lighten(bg)
        fg = pal.bg  # 채운 배경 위에는 화면 바탕색 글자
        attr = Attr.REVERSE if self.pressed else 0
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg, attr)
        if self.focused and w >= 2:
            p.put(0, 0, "►", fg, bg, attr)
            p.put(w - 1, 0, "◄", fg, bg, attr)
        self._draw_label(p, 0, fg, bg, attr | Attr.BOLD)

    def _paint_fill(self, p: Painter) -> None:
        pal = self.palette
        w = self.rect.w
        fg = self._fg()
        bg = pal.button_bg
        if self.hovered and self.enabled and not self.pressed:
            # 마우스를 올리면 배경을 밝게 해서 클릭할 수 있는 대상임을 보여준다
            bg = lighten(bg)
        attr = Attr.REVERSE if self.pressed else 0
        p.fill(Rect(0, 0, w, self.rect.h), " ", fg, bg, attr)
        if self.focused and w >= 2:
            p.put(0, 0, "►", fg, bg, attr)
            p.put(w - 1, 0, "◄", fg, bg, attr)
        self._draw_label(p, 0, fg, bg, attr)

    def _paint_box(self, p: Painter) -> None:
        pal = self.palette
        w, h = self.rect.w, self.rect.h

        if not self.enabled:
            border, fill, fg, edges = pal.disabled, pal.button_bg, pal.disabled, EDGE_LIGHT
        elif self.pressed:
            border, fill, fg, edges = pal.border_focus, pal.sel_bg, pal.sel_fg, EDGE_HEAVY
        elif self.focused:
            border, fill, fg, edges = pal.border_focus, pal.hover_bg, pal.button_focus_fg, EDGE_HEAVY
        elif self.hovered:
            # 마우스만 올린 버튼은 테두리만 밝게: 포커스(채움)와 구분돼야 Enter 가 어디로 가는지 보인다
            border, fill, fg, edges = pal.border_focus, pal.button_bg, pal.button_fg, EDGE_LIGHT
        else:
            border, fill, fg, edges = pal.border, pal.button_bg, pal.button_fg, EDGE_LIGHT

        # 테두리 셀은 바깥=화면 배경, 선=border, 선 안쪽=채움색(attr 에 실음) 세 색으로 그린다.
        # 선을 글자 쪽으로 당겨 그려서(boxdraw.EDGE_INSET) 버튼이 글자에 비해 과하게 커 보이지 않게 한다
        tl, top, tr, left, right, bl, bottom, br = edges
        bg = pal.bg
        fa = fill_attr(fill)
        p.fill(Rect(1, 1, w - 2, h - 2), " ", fg, fill)
        p.put(0, 0, tl, border, bg, fa)
        p.hline(1, 0, w - 2, top, border, bg, fa)
        p.put(w - 1, 0, tr, border, bg, fa)
        p.vline(0, 1, h - 2, left, border, bg, fa)
        p.vline(w - 1, 1, h - 2, right, border, bg, fa)
        p.put(0, h - 1, bl, border, bg, fa)
        p.hline(1, h - 1, w - 2, bottom, border, bg, fa)
        p.put(w - 1, h - 1, br, border, bg, fa)
        self._draw_label(p, h // 2, fg, fill, 0)

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, MouseEvent):
            if ev.kind == "down" and ev.button == 1:
                self._armed = True
                self.pressed = True
                self.invalidate()
                return True
            if ev.kind == "move" and self._armed:
                # 누른 채 밖으로 나가면 눌림 표시를 풀고, 다시 들어오면 되살린다 (놓는 위치로 클릭 여부 결정)
                inside = self.rect.contains(ev.cx, ev.cy)
                if inside != self.pressed:
                    self.pressed = inside
                    self.invalidate()
                return True
            if ev.kind == "up" and ev.button == 1 and self._armed:
                inside = self.rect.contains(ev.cx, ev.cy)
                self._armed = False
                self.pressed = False
                self.invalidate()
                if inside:
                    self.click()
                return True
        elif isinstance(ev, KeyEvent):
            if (ev.key == Key.SPACE or ev.is_enter) and not ev.mod:
                self.click()
                return True
        elif isinstance(ev, FocusEvent) and not ev.gained:
            self._armed = False
            self.pressed = False
        return False
