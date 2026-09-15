"""Application: window, event loop, focus, layers, damage-driven painting.

- 할 일이 없으면 다음 타이머/플롯 폴링 시각까지 event.wait 으로 블록한다 (idle CPU ~0%).
- 그릴 것(damage/layout/픽셀 위젯)이 있을 때만 fps 상한 안에서 페인트한다.
- 워커 스레드는 call_soon() 또는 Signal.emit() 으로만 UI 를 건드린다.
- 화면은 root 레이어 위에 팝업 레이어(메뉴/대화상자)가 스택으로 쌓인다.
"""

from __future__ import annotations

import logging
import math
import os
import queue
import threading
import time
from typing import Any, Callable

import pygame

from retroui.core.geometry import Rect
from retroui.core.signal import set_dispatcher
from retroui.core.timers import Timer, TimerQueue
from retroui.core.wcwidth import char_width
from retroui.input.events import (
    IS_MAC,
    CompositionEvent,
    Event,
    FocusEvent,
    Key,
    KeyEvent,
    Mod,
    MouseEvent,
    TextEvent,
    WheelEvent,
    translate,
)
from retroui.input.ime import ImeFilter
from retroui.render.cellbuffer import WIDE_CONT, CellBuffer
from retroui.render.fonts import FontSet
from retroui.render.painter import Painter
from retroui.render.renderer import Renderer
from retroui.theme import DARK_GRAY, Theme, get_theme
from retroui.widgets.base import Widget
from retroui.widgets.pixel import PixelWidget
from retroui.widgets.popup import Popup

log = logging.getLogger(__name__)

_DOUBLE_CLICK_S = 0.4
# 타이머가 없어도 이 주기로는 깨어나 창 상태 변화를 놓치지 않게 한다
_MAX_IDLE_WAIT_S = 0.5
_MOD_MASK = Mod.SHIFT | Mod.CTRL | Mod.ALT | Mod.META
_SHADOW_FG = DARK_GRAY
_SHADOW_BG = (0, 0, 0)


def parse_shortcut(spec: str) -> tuple[Mod, int]:
    """'Ctrl+Q', 'Primary+S' (macOS Cmd / 그 외 Ctrl), 'Alt+Shift+F2' 형식."""
    mods = Mod.NONE
    key = None
    for part in spec.split("+"):
        p = part.strip().lower()
        if p in ("ctrl", "control"):
            mods |= Mod.CTRL
        elif p in ("cmd", "meta", "super"):
            mods |= Mod.META
        elif p in ("alt", "option"):
            mods |= Mod.ALT
        elif p == "shift":
            mods |= Mod.SHIFT
        elif p == "primary":
            mods |= Mod.META if IS_MAC else Mod.CTRL
        else:
            key = pygame.key.key_code(p)
    if key is None:
        raise ValueError(f"shortcut {spec!r} has no key")
    return mods, key


class App:
    def __init__(
        self,
        title: str = "retroui",
        size: tuple[int, int] = (100, 32),
        *,
        theme: str | Theme = "mono",
        font: str = "d2coding",
        font_size: int = 14,
        fps: int = 60,
        headless: bool = False,
        resizable: bool = True,
        padding: int = 0,
        icon: "pygame.Surface | str | None" = None,
    ):
        self.headless = headless
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        # macOS 에서 비활성 창을 클릭하면 SDL 은 기본으로 창 활성화에만 쓰고 클릭을 버린다.
        # 첫 클릭이 "안 먹는" 것처럼 보이므로 클릭도 함께 전달한다
        os.environ.setdefault("SDL_MOUSE_FOCUS_CLICKTHROUGH", "1")
        pygame.init()
        self.theme = get_theme(theme)
        self.fps = fps
        self.fonts = FontSet(font, font_size, 1.0)

        # 창 가장자리와 격자 사이 여백 (창 기준 point). 글자가 창 테두리에 붙으면 답답해 보인다
        self.padding = max(0, int(padding))
        self.origin = (0, 0)
        cols, rows = size
        if headless:
            pygame.display.set_mode((1, 1))  # 이벤트 큐 사용에 비디오 초기화가 필요하다
            self.window = None
            self.scale = 1.0
            self.surface = pygame.Surface(self._surface_size_for(cols, rows))
        else:
            self.scale = 1.0
            self.window = pygame.Window(
                title, self._window_size_for(cols, rows), allow_high_dpi=True, resizable=resizable
            )
            self.surface = self.window.get_surface()
            self.scale = self.surface.get_width() / self.window.size[0]
            if self.scale != 1.0:
                # 2x 폰트의 셀 크기는 1x 의 정확히 2배가 아닐 수 있어(px 반올림) 요청한 열/행 수가 되도록 창을 다시 맞춘다
                self.fonts.reload(self.scale)
                self.window.size = self._window_size_for(cols, rows)
                self.surface = self.window.get_surface()
            if icon is not None:
                self.set_icon(icon)

        pal = self.theme.palette
        self.buf = CellBuffer(1, 1, pal.fg, pal.bg)
        self.renderer = Renderer(self.fonts, self.buf)

        self.timers = TimerQueue()
        self._calls: queue.SimpleQueue[tuple[Callable[..., Any], tuple]] = queue.SimpleQueue()
        self._wake_pending = threading.Event()
        self._wake_type = pygame.event.custom_type()
        set_dispatcher(self.call_soon, threading.get_ident())

        self.root: Widget | None = None
        self.focus: Widget | None = None
        self._popups: list[Popup] = []
        self._hover: Widget | None = None
        self._capture: Widget | None = None
        self._last_click = (0.0, -1, -1, 0, 0)  # time, cx, cy, button, clicks
        self._shortcuts: list[tuple[Mod, int, Callable[[], None]]] = []
        self._key_filters: list[Callable[[KeyEvent], bool]] = []
        self._ime = ImeFilter()
        self._text_input_active = False
        self._text_input_rect: tuple[int, int, int, int] | None = None
        self._key_hooks: list[Widget] = []
        self._damage: Rect | None = None
        self._layout_needed = True
        self._pixel_widgets: list[PixelWidget] = []
        # 화면 서피스가 지워졌을 때(리사이즈/노출) 픽셀 위젯을 다시 합성해야 한다
        self._pixels_force = True
        self._next_frame = 0.0
        self.frame_count = 0
        # 워커 스레드가 `while app.running` 으로 돌 수 있도록 run() 전부터 True
        self.running = True

        self._fit_grid()
        pygame.key.set_repeat(400, 35)
        # SDL 은 기본으로 텍스트 입력(IME)을 켜 둔다: 입력 위젯이 포커스를 받을 때만 켠다
        pygame.key.stop_text_input()

    # ---- public API ----------------------------------------------------

    @property
    def cols(self) -> int:
        return self.buf.cols

    @property
    def rows(self) -> int:
        return self.buf.rows

    @property
    def popups(self) -> list[Popup]:
        return list(self._popups)

    @property
    def top_layer(self) -> Widget | None:
        return self._popups[-1] if self._popups else self.root

    def set_root(self, widget: Widget) -> None:
        self.close_all_popups()
        if self.root is not None:
            self.root._app = None
        widget._app = self
        self.root = widget
        self.focus = None
        self._hover = None
        self._capture = None
        self.request_layout()
        self.focus_next(1)

    def open_popup(
        self, popup: Popup, x: int, y: int, w: int | None = None, h: int | None = None, *, focus: bool = True
    ) -> None:
        """팝업을 (x, y) 셀 위치에 연다. 크기는 size_hint 기준이고 화면 안으로 밀어 넣는다.

        focus=False 면 포커스를 옮기지 않는다. 입력은 계속 원래 위젯으로 가고, 팝업은 목록만 보여준다
        (자동완성 목록처럼 타이핑하면서 갱신되는 팝업).
        """
        popup._app = self
        hint = popup.effective_hint()
        w = min(w or hint.pref_w, self.cols)
        h = min(h or hint.pref_h, self.rows)
        x = max(0, min(x, self.cols - w))
        y = max(0, min(y, self.rows - h))
        popup._prev_focus = self.focus
        self._popups.append(popup)
        popup._do_layout(Rect(x, y, w, h))
        self.invalidate(popup.outer_rect())
        if focus:
            chain = [c for c in popup.iter_tree() if c.focusable and c.enabled]
            self.set_focus(chain[0] if chain else None)

    def reposition_popup(self, popup: Popup, x: int, y: int, w: int | None = None, h: int | None = None) -> None:
        """열린 팝업의 위치/크기를 바꾼다 (내용이 바뀌어 크기가 달라질 때)."""
        if not any(p is popup for p in self._popups):
            return
        hint = popup.effective_hint()
        w = min(w or hint.pref_w, self.cols)
        h = min(h or hint.pref_h, self.rows)
        x = max(0, min(x, self.cols - w))
        y = max(0, min(y, self.rows - h))
        self.invalidate(popup.outer_rect())
        popup._do_layout(Rect(x, y, w, h))
        self.invalidate(popup.outer_rect())

    def close_popup(self, popup: Popup) -> None:
        """popup 과 그 위에 쌓인 팝업들을 닫고, 열기 전 포커스로 되돌린다."""
        if not any(p is popup for p in self._popups):
            return
        while self._popups:
            p = self._popups.pop()
            self.invalidate(p.outer_rect())
            if p.is_ancestor_of(self._hover):
                self._hover = None
            if p.is_ancestor_of(self._capture):
                self._capture = None
            if self.focus is None or p.is_ancestor_of(self.focus):
                prev = p._prev_focus
                self.set_focus(prev if prev is not None and self._is_live(prev) else None)
            p.on_close()
            if p is popup:
                break

    def close_all_popups(self) -> None:
        if self._popups:
            self.close_popup(self._popups[0])

    def invalidate(self, rect: Rect | None = None) -> None:
        r = self.buf.rect if rect is None else rect
        self._damage = r if self._damage is None else self._damage.union(r)

    def request_layout(self) -> None:
        self._layout_needed = True

    def call_soon(self, fn: Callable[..., Any], *args: Any) -> None:
        """아무 스레드에서나 호출 가능. fn(*args) 는 메인 스레드에서 실행된다."""
        self._calls.put((fn, args))
        if not self._wake_pending.is_set():
            self._wake_pending.set()
            try:
                pygame.event.post(pygame.event.Event(self._wake_type))
            except pygame.error:
                pass  # 종료 중

    def set_interval(self, interval_ms: float, callback: Callable[[], None]) -> Timer:
        return self.timers.set_interval(interval_ms, callback)

    def set_timeout(self, delay_ms: float, callback: Callable[[], None]) -> Timer:
        return self.timers.set_timeout(delay_ms, callback)

    def add_shortcut(self, spec: str, callback: Callable[[], None]) -> None:
        mods, key = parse_shortcut(spec)
        self._shortcuts.append((mods, key, callback))

    def add_key_filter(self, fn: Callable[[KeyEvent], bool]) -> None:
        """포커스 위젯보다 먼저 키를 받는다. True 를 돌려주면 그 키는 소비된다 (minicom 식 Ctrl-A 접두키 등)."""
        self._key_filters.append(fn)

    def set_icon(self, icon: "pygame.Surface | str") -> None:
        """창/Dock 아이콘. 지정하지 않으면 pygame 기본 아이콘(뱀)이 보인다."""
        if self.window is None:
            return
        try:
            surface = icon if isinstance(icon, pygame.Surface) else pygame.image.load(icon)
            self.window.set_icon(surface)
        except (pygame.error, FileNotFoundError, OSError) as e:
            log.warning("set_icon failed: %s", e)

    def set_font_size(self, size: int) -> None:
        """글자 크기(pt)를 바꾼다. 열/행 수는 유지하고 창(또는 헤드리스 서피스) 크기를 새 셀 크기에 맞춘다."""
        size = max(6, int(size))
        if size == self.fonts.size:
            return
        cols, rows = self.cols, self.rows
        self.fonts.size = size
        self.fonts.reload(self.scale)
        if self.window is not None:
            # 화면보다 커지면 SDL 이 창을 줄이고, 그만큼 열/행 수가 줄어든다
            self.window.size = self._window_size_for(cols, rows)
            self.surface = self.window.get_surface()
        else:
            self.surface = pygame.Surface(self._surface_size_for(cols, rows))
        self.buf.invalidate_all()
        self._fit_grid()

    def set_focus(self, widget: Widget | None) -> None:
        if widget is self.focus:
            return
        old = self.focus
        pending = self._ime.commit_pending()
        if pending and old is not None:
            # 조합 중에 포커스가 옮겨지면 조합 중 글자를 이전 위젯에 확정한다.
            # IME 가 뒤늦게 같은 확정을 보내면 ImeFilter 가 버린다
            old.on_event(TextEvent(pending))
            old.on_event(CompositionEvent("", 0))
        self.focus = widget
        for w, gained in ((old, False), (widget, True)):
            if w is None:
                continue
            w.on_event(FocusEvent(gained))
            self.invalidate(w.rect)
            p = w.parent
            while p is not None:
                if p.repaint_on_focus_within:
                    self.invalidate(p.rect)
                p = p.parent
        self._update_text_input()

    def focus_chain(self) -> list[Widget]:
        top = self.top_layer
        if top is None:
            return []
        return [w for w in top.iter_tree() if w.focusable and w.enabled]

    def focus_next(self, delta: int = 1) -> None:
        chain = self.focus_chain()
        if not chain:
            self.set_focus(None)
            return
        try:
            i = next(i for i, w in enumerate(chain) if w is self.focus)
        except StopIteration:
            i = -1 if delta > 0 else 0
        self.set_focus(chain[(i + delta) % len(chain)])

    def dispatch(self, ev: Event) -> None:
        """정규화된 이벤트 처리. 헤드리스 테스트에서 입력 주입용으로도 쓴다."""
        # IME 보정 필터: 조합 중 편집키 순서 보정, 중복 확정 제거 (input/ime.py)
        for e in self._ime.feed(ev):
            self._dispatch_one(e)

    def _dispatch_one(self, ev: Event) -> None:
        if isinstance(ev, KeyEvent):
            self._dispatch_key(ev)
        elif isinstance(ev, (TextEvent, CompositionEvent)):
            self._bubble(self.focus, ev)
        elif isinstance(ev, MouseEvent):
            self._dispatch_mouse(ev)
        elif isinstance(ev, WheelEvent):
            self._bubble(self._hit(ev.cx, ev.cy), ev)

    def step(self, block: bool = False) -> None:
        if block:
            now = time.monotonic()
            if self._damage is not None or self._layout_needed or self._pixels_force:
                paint_at = self._next_frame
            else:
                pixel_at = self._pixel_deadline()
                # 픽셀 폴링 시각이 지났어도 fps 상한 전에는 그릴 수 없다. 그 전에 깨면 루프가 헛돈다
                # (P2 프로파일: 6초에 step() 149k 회, CPU 대부분이 이 busy spin 이었다)
                paint_at = None if pixel_at is None else max(pixel_at, self._next_frame)
            candidates = [d for d in (self.timers.next_deadline(), paint_at) if d is not None]
            wake_at = min(candidates) if candidates else now + _MAX_IDLE_WAIT_S
            timeout_s = min(wake_at - now, _MAX_IDLE_WAIT_S)
        else:
            timeout_s = 0.0

        events = []
        if timeout_s > 0:
            # pygame 의 wait(0) 은 무한 대기라서 양수일 때만 호출한다
            first = pygame.event.wait(max(1, int(timeout_s * 1000)))
            if first.type != pygame.NOEVENT:
                events.append(first)
        events.extend(pygame.event.get())
        for e in events:
            self._handle_pygame_event(e)

        self._drain_calls()
        self.timers.run_due()

        now = time.monotonic()
        if self._needs_paint(now) and (self.headless or now >= self._next_frame):
            rects = self._paint(now)
            if rects:
                self.frame_count += 1
                if self.window is not None:
                    self.window.flip()
            self._next_frame = time.monotonic() + 1.0 / self.fps
        self._update_text_input_rect()

    def run(self) -> None:
        self.running = True
        try:
            while self.running:
                self.step(block=True)
        finally:
            self.close()

    def quit(self) -> None:
        self.running = False

    def close(self) -> None:
        self.running = False
        set_dispatcher(None)
        if self.window is not None:
            self.window.destroy()
            self.window = None
        pygame.quit()

    def screen_text(self) -> list[str]:
        """현재 화면 글자 (테스트용). 그릴 것이 남아 있으면 먼저 그린다."""
        self._paint()
        return self.buf.text_lines()

    # ---- internals -----------------------------------------------------

    @property
    def padding_px(self) -> int:
        return round(self.padding * self.scale)

    def _window_size_for(self, cols: int, rows: int) -> tuple[int, int]:
        return (
            math.ceil(cols * self.fonts.cw / self.scale) + 2 * self.padding,
            math.ceil(rows * self.fonts.ch / self.scale) + 2 * self.padding,
        )

    def _surface_size_for(self, cols: int, rows: int) -> tuple[int, int]:
        pad = self.padding_px
        return cols * self.fonts.cw + 2 * pad, rows * self.fonts.ch + 2 * pad

    def _fit_grid(self) -> None:
        # 격자 크기가 바뀌면 팝업 위치가 의미 없어지므로 닫는다
        self.close_all_popups()
        pad = self.padding_px
        w, h = self.surface.get_width(), self.surface.get_height()
        cols, rows = self.renderer.grid_size(max(1, w - 2 * pad), max(1, h - 2 * pad))
        # 셀로 나누고 남는 자투리 픽셀은 양쪽에 반씩 나눠 여백을 대칭으로 맞춘다
        ox = pad + max(0, w - 2 * pad - cols * self.fonts.cw) // 2
        oy = pad + max(0, h - 2 * pad - rows * self.fonts.ch) // 2
        self.origin = (ox, oy)
        self.renderer.ox, self.renderer.oy = ox, oy
        self.buf.resize(cols, rows)
        # 셀 격자로 나누고 남는 오른쪽/아래 자투리 픽셀
        self.surface.fill(self.theme.palette.bg)
        self._pixels_force = True
        self.request_layout()
        self.invalidate()

    def _on_window_resized(self) -> None:
        assert self.window is not None
        self.surface = self.window.get_surface()
        scale = self.surface.get_width() / max(1, self.window.size[0])
        if abs(scale - self.scale) > 1e-3:
            # Retina <-> 일반 모니터 이동: 폰트를 새 px 크기로 다시 연다
            self.scale = scale
            self.fonts.reload(scale)
        self._fit_grid()

    def _handle_pygame_event(self, e: pygame.event.Event) -> None:
        t = e.type
        if t in (pygame.QUIT, pygame.WINDOWCLOSE):
            self.running = False
        elif t == self._wake_type:
            pass
        elif t in (pygame.WINDOWSIZECHANGED, pygame.WINDOWDISPLAYCHANGED):
            if self.window is not None:
                self._on_window_resized()
        elif t == pygame.WINDOWEXPOSED:
            self.surface.fill(self.theme.palette.bg)
            self.buf.invalidate_all()
            self._pixels_force = True
            self.invalidate()
        elif t == pygame.WINDOWFOCUSLOST:
            self._release_pointer()
        else:
            ev = translate(e, self.scale, self.fonts.cw, self.fonts.ch, *self.origin)
            if ev is not None:
                self.dispatch(ev)

    def _update_text_input(self) -> None:
        """입력 위젯에 포커스가 있을 때만 IME 를 켠다. 켜 두면 일반 위젯의 글자 키를 IME 가 가로챈다."""
        want = self.focus is not None and getattr(self.focus, "wants_text_input", False)
        if want == self._text_input_active:
            return
        self._text_input_active = want
        self._text_input_rect = None
        try:
            if want:
                pygame.key.start_text_input()
            else:
                pygame.key.stop_text_input()
        except pygame.error:
            pass

    def _update_text_input_rect(self) -> None:
        # IME 후보창을 캐럿 위치에 붙인다. 좌표는 point 단위이고, 매번 부르면 macOS 에서 후보창이 깜박여 바뀔 때만 부른다
        if not self._text_input_active or self.focus is None:
            return
        caret_cell = getattr(self.focus, "caret_cell", None)
        pos = caret_cell() if callable(caret_cell) else None
        if pos is None:
            return
        cx, cy = pos
        s = self.scale
        ox, oy = self.origin
        rect = (
            int((ox + cx * self.fonts.cw) / s),
            int((oy + cy * self.fonts.ch) / s),
            int(2 * self.fonts.cw / s),
            int(self.fonts.ch / s),
        )
        if rect != self._text_input_rect:
            self._text_input_rect = rect
            try:
                pygame.key.set_text_input_rect(pygame.Rect(rect))
            except pygame.error:
                pass

    def _drain_calls(self) -> None:
        # 비우기 전에 플래그를 내려야, 비우는 도중 들어온 항목이 다음 WAKE 로 깨운다
        self._wake_pending.clear()
        while True:
            try:
                fn, args = self._calls.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception:
                log.exception("call_soon callback failed")

    def _is_live(self, widget: Widget) -> bool:
        top = widget
        while top.parent is not None:
            top = top.parent
        return top is self.root or any(p is top for p in self._popups)

    def _hit(self, cx: int, cy: int) -> Widget | None:
        """위 레이어부터 (cx, cy) 에 있는 가장 깊은 위젯. 모달 팝업 밖이면 None."""
        for popup in reversed(self._popups):
            hit = popup.child_at(cx, cy)
            if hit is not None:
                return hit
            if popup.modal:
                return None
        return self.root.child_at(cx, cy) if self.root is not None else None

    @staticmethod
    def _bubble(widget: Widget | None, ev: Event) -> Widget | None:
        w = widget
        while w is not None:
            if w.enabled and w.visible and w.on_event(ev):
                return w
            w = w.parent
        return None

    def _dispatch_key(self, ev: KeyEvent) -> None:
        for key_filter in list(self._key_filters):
            if key_filter(ev):
                return
        if self._bubble(self.focus, ev) is not None:
            return
        mods = ev.mod & _MOD_MASK
        modal = bool(self._popups) and self._popups[-1].modal
        if not modal:
            for w in self._key_hooks:
                if w.visible and w.enabled and w.global_key(ev):  # type: ignore[attr-defined]
                    return
            for sc_mods, sc_key, callback in self._shortcuts:
                if ev.key == sc_key and mods == sc_mods:
                    callback()
                    return
        top = self.top_layer
        if ev.alt and top is not None:
            name = ev.name.lower()
            for w in top.iter_tree():
                if w.enabled and getattr(w, "mnemonic_key", None) == name and callable(getattr(w, "activate", None)):
                    if w.focusable:
                        self.set_focus(w)
                    w.activate()  # type: ignore[attr-defined]
                    return
        if ev.key == Key.TAB and not (mods & (Mod.CTRL | Mod.META | Mod.ALT)):
            self.focus_next(-1 if ev.shift else 1)

    def _dispatch_mouse(self, ev: MouseEvent) -> None:
        under = self._hit(ev.cx, ev.cy)
        if ev.kind == "move":
            if under is not self._hover:
                for w, state in ((self._hover, False), (under, True)):
                    if w is not None:
                        w.hovered = state
                        w.invalidate()
                self._hover = under
            if self._capture is not None:
                self._capture.on_event(ev)
            else:
                self._bubble(under, ev)
            return

        if ev.kind == "down":
            pending = self._ime.commit_pending()
            if pending and self.focus is not None:
                # 조합 중 클릭: 커서 이동/포커스 변경 전에 조합 중 글자를 현재 위젯에 확정한다
                self.focus.on_event(TextEvent(pending))
                self.focus.on_event(CompositionEvent("", 0))
            now = time.monotonic()
            t, cx, cy, button, clicks = self._last_click
            same = now - t <= _DOUBLE_CLICK_S and (cx, cy, button) == (ev.cx, ev.cy, ev.button)
            ev.clicks = clicks + 1 if same else 1
            self._last_click = (now, ev.cx, ev.cy, ev.button, ev.clicks)

            top = self._popups[-1] if self._popups else None
            if top is not None and not top.is_ancestor_of(under):
                if top.modal:
                    return
                # 바깥 클릭: 비모달 팝업을 닫고 클릭은 아래 위젯으로 전달한다.
                # 팝업을 연 위젯(메뉴 제목)을 누른 경우는 그 위젯이 열기/닫기를 직접 처리한다
                for p in reversed(list(self._popups)):
                    if p.is_ancestor_of(under) or (p.owner is not None and p.owner.is_ancestor_of(under)):
                        break
                    if not p.close_on_outside_click:
                        break
                    self.close_popup(p)
                under = self._hit(ev.cx, ev.cy)

            target = under
            while target is not None and not (target.focusable and target.enabled):
                target = target.parent
            if target is not None:
                self.set_focus(target)
            consumer = self._bubble(under, ev)
            if consumer is not None:
                self._capture = consumer
            return

        # up
        captured = self._capture
        self._capture = None
        if captured is not None:
            captured.on_event(ev)
        else:
            self._bubble(under, ev)

    def _release_pointer(self) -> None:
        if self._capture is not None:
            self._capture.on_event(FocusEvent(False))
            self._capture = None

    def _forget(self, widget: Widget) -> None:
        if widget.is_ancestor_of(self.focus):
            self.set_focus(None)
        if widget.is_ancestor_of(self._hover):
            self._hover = None
        if widget.is_ancestor_of(self._capture):
            self._capture = None

    @property
    def _frame_slack(self) -> float:
        # 반 프레임 안에 몰린 폴링은 한 프레임에 같이 처리한다. 플롯마다 위상이 달라
        # 프레임이 잘게 쪼개지는 것을 막는다 (30Hz 플롯 3개가 90회 페인트가 되지 않게)
        return 0.5 / self.fps

    def _pixel_deadline(self) -> float | None:
        deadline = None
        for w in self._pixel_widgets:
            d = 0.0 if w._pixels_dirty else w.frame_deadline()
            if d is None:
                continue
            d -= self._frame_slack
            if deadline is None or d < deadline:
                deadline = d
        return deadline

    def _needs_paint(self, now: float) -> bool:
        if self._damage is not None or self._layout_needed or self._pixels_force:
            return True
        deadline = self._pixel_deadline()
        return deadline is not None and now >= deadline

    def ensure_layout(self) -> None:
        """밀린 레이아웃을 지금 한다. 그리기 전에 위젯 위치(rect)로 팝업 자리를 잡을 때 쓴다."""
        if not self._layout_needed:
            return
        self._layout_needed = False
        if self.root is not None:
            self.root._do_layout(self.buf.rect)
            tree = list(self.root.iter_tree())
            self._pixel_widgets = [w for w in tree if isinstance(w, PixelWidget)]
            self._key_hooks = [w for w in tree if callable(getattr(w, "global_key", None))]
        else:
            self._pixel_widgets = []
            self._key_hooks = []
        self._pixels_force = True
        self.invalidate()

    def _paint(self, now: float | None = None) -> list[pygame.Rect]:
        if now is None:
            now = time.monotonic()
        self.ensure_layout()

        rects: list[pygame.Rect] = []
        if self._damage is not None:
            clip = self._damage.intersect(self.buf.rect)
            self._damage = None
            if not clip.empty:
                pal = self.theme.palette
                self.buf.fill(clip, " ", pal.fg, pal.bg)
                if self.root is not None:
                    self._paint_widget(self.root, clip)
                for popup in self._popups:
                    if popup.has_shadow:
                        self._paint_shadow(popup.rect, clip)
                    self._paint_widget(popup, clip)
            rects = self.renderer.render(self.surface)
        rects.extend(self._composite_pixels(now, rects))
        return rects

    def _paint_widget(self, widget: Widget, clip: Rect) -> None:
        if not widget.visible:
            return
        area = clip.intersect(widget.rect)
        if area.empty:
            return
        widget.paint(Painter(self.buf, (widget.rect.x, widget.rect.y), area))
        for child in widget.children:
            self._paint_widget(child, area)

    def _paint_shadow(self, r: Rect, clip: Rect) -> None:
        # 아래 레이어 글자는 남기고 어둡게 칠한다 (Turbo Vision 그림자). 와이드 문자는 반쪽만 걸리므로 공백으로
        for shadow in (Rect(r.right, r.y + 1, 2, r.h), Rect(r.x + 2, r.bottom, r.w, 1)):
            area = shadow.intersect(clip).intersect(self.buf.rect)
            for y in range(area.y, area.bottom):
                for x in range(area.x, area.right):
                    ch = self.buf.get(x, y)[0]
                    if ch == WIDE_CONT or char_width(ch) != 1:
                        ch = " "
                    self.buf.put(x, y, ch, _SHADOW_FG, _SHADOW_BG)

    def _composite_pixels(self, now: float, cell_dirty: list[pygame.Rect]) -> list[pygame.Rect]:
        force = self._pixels_force
        self._pixels_force = False
        cw, ch = self.fonts.cw, self.fonts.ch
        ox, oy = self.origin
        occluders = [p.outer_rect() for p in self._popups]
        out = []
        for w in self._pixel_widgets:
            area = w.pixel_rect().intersect(self.buf.rect)
            if area.empty:
                continue
            size = (area.w * cw, area.h * ch)
            dest = pygame.Rect(ox + area.x * cw, oy + area.y * ch, *size)

            redraw = w._pixels_dirty
            if w._surface is None or w._surface.get_size() != size:
                w._surface = pygame.Surface(size)
                redraw = True
            deadline = w.frame_deadline()
            if deadline is not None and now + self._frame_slack >= deadline and w.poll_frame(now):
                redraw = True
            if redraw:
                w.render_pixels(w._surface, self.scale)
                w._pixels_dirty = False
            # 셀 렌더러가 같은 영역을 다시 칠했으면(레이아웃 변경, 위를 덮던 팝업이 닫힘) 픽셀도 다시 올린다
            if not (redraw or force or dest.collidelist(cell_dirty) != -1):
                continue

            # 팝업(그림자 포함)이 덮은 영역은 빼고 올려야 플롯이 메뉴를 덮어쓰지 않는다
            parts = [area]
            for occ in occluders:
                parts = [q for part in parts for q in part.subtract(occ)]
            for part in parts:
                src = pygame.Rect((part.x - area.x) * cw, (part.y - area.y) * ch, part.w * cw, part.h * ch)
                self.surface.blit(w._surface, (ox + part.x * cw, oy + part.y * ch), src)
                out.append(pygame.Rect(ox + part.x * cw, oy + part.y * ch, src.w, src.h))
        return out
