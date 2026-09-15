"""Live streaming plot (pyqtgraph/pglive replacement).

워커 스레드는 Series.append()/extend() 로 링버퍼에만 쓰고, UI 스레드는 update_hz 주기로
버전 번호를 확인해 바뀌었을 때만 다시 그린다. 샘플마다 이벤트 루프를 깨우지 않는다.

P0 실측 (Retina 2400px 폭 플롯 3개 x 시리즈 3개): aalines 는 CPU ~100%, 안티앨리어싱 없는
lines + 30Hz 는 ~42% (측정용 워커 스레드 10% 포함). 그래서 기본값은 antialias=False,
update_hz=30 이고, 점 축약은 물리 픽셀이 아닌 논리 픽셀 폭 기준으로 한다.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Sequence

import numpy as np
import pygame

from retroui.core.geometry import Rect
from retroui.core.signal import Signal
from retroui.core.wcwidth import str_width, truncate
from retroui.input.events import Event, Key, KeyEvent, MouseEvent
from retroui.render.cellbuffer import Attr
from retroui.render.painter import Painter
from retroui.theme import resolve_color
from retroui.widgets.base import RGB, SizeHint
from retroui.widgets.pixel import PixelWidget

# 왼쪽 Y 눈금 라벨 폭 (셀). "-1234.5" + 여백
_GUTTER = 8


class RingBuffer:
    """고정 크기 (x, y) 링버퍼. append/extend/snapshot 은 어느 스레드에서나 호출할 수 있다."""

    def __init__(self, capacity: int):
        if capacity < 2:
            raise ValueError("capacity must be >= 2")
        self._x = np.zeros(capacity, dtype=np.float64)
        self._y = np.zeros(capacity, dtype=np.float64)
        self._head = 0
        self._count = 0
        self._next_x = 0.0
        self._lock = threading.Lock()
        self.version = 0

    @property
    def capacity(self) -> int:
        return len(self._y)

    def __len__(self) -> int:
        return self._count

    def append(self, y: float, x: float | None = None) -> None:
        with self._lock:
            if x is None:
                x = self._next_x
            self._next_x = x + 1.0
            self._x[self._head] = x
            self._y[self._head] = y
            self._head = (self._head + 1) % len(self._y)
            self._count = min(self._count + 1, len(self._y))
            self.version += 1

    def extend(self, ys: Sequence[float] | np.ndarray, xs: Sequence[float] | np.ndarray | None = None) -> None:
        ys = np.asarray(ys, dtype=np.float64).ravel()
        n = len(ys)
        if n == 0:
            return
        cap = len(self._y)
        with self._lock:
            if xs is None:
                xs = self._next_x + np.arange(n, dtype=np.float64)
            else:
                xs = np.asarray(xs, dtype=np.float64).ravel()
            self._next_x = float(xs[-1]) + 1.0
            if n >= cap:
                self._x[:] = xs[-cap:]
                self._y[:] = ys[-cap:]
                self._head = 0
                self._count = cap
            else:
                idx = (self._head + np.arange(n)) % cap
                self._x[idx] = xs
                self._y[idx] = ys
                self._head = (self._head + n) % cap
                self._count = min(self._count + n, cap)
            self.version += 1

    def clear(self) -> None:
        with self._lock:
            self._head = 0
            self._count = 0
            self._next_x = 0.0
            self.version += 1

    def snapshot(self) -> tuple[np.ndarray, np.ndarray, int]:
        """오래된 순서로 정렬된 (xs, ys) 복사본과 그 시점의 버전."""
        with self._lock:
            cap = len(self._y)
            if self._count < cap:
                start = (self._head - self._count) % cap
                if start + self._count <= cap:
                    xs = self._x[start : start + self._count].copy()
                    ys = self._y[start : start + self._count].copy()
                else:
                    xs = np.concatenate((self._x[start:], self._x[: self._head]))
                    ys = np.concatenate((self._y[start:], self._y[: self._head]))
            else:
                xs = np.concatenate((self._x[self._head :], self._x[: self._head]))
                ys = np.concatenate((self._y[self._head :], self._y[: self._head]))
            return xs, ys, self.version


def decimate(xs: np.ndarray, ys: np.ndarray, x0: float, x1: float, width: int) -> tuple[np.ndarray, np.ndarray]:
    """보이는 x 구간 [x0, x1] 을 폭 width 픽셀에 맞게 줄인다.

    반환 x 는 픽셀 좌표 (0..width-1, 가장자리 밖 한 점씩 포함). 점이 많으면 픽셀 열마다
    min/max 두 점만 남겨 스파이크를 보존하고, 열 안에서 값이 내려가는 중이면 max 를 먼저 둬서
    파형이 뒤틀리지 않게 한다. 결과 점 개수는 대략 2*(width+2) 이하.
    xs 는 단조 증가해야 한다.
    """
    n_all = len(xs)
    if width < 2 or n_all == 0 or x1 <= x0:
        return np.empty(0), np.empty(0)
    # 선이 플롯 가장자리까지 이어지도록 구간 바로 밖의 한 점씩 포함
    i0 = max(0, int(np.searchsorted(xs, x0, "left")) - 1)
    i1 = min(n_all, int(np.searchsorted(xs, x1, "right")) + 1)
    xs = xs[i0:i1]
    ys = ys[i0:i1]
    n = len(xs)
    px = (xs - x0) * ((width - 1) / (x1 - x0))
    if n <= 2 * width:
        return px, ys

    cols = np.floor(px).astype(np.intp)
    starts = np.concatenate(([0], np.flatnonzero(np.diff(cols)) + 1))
    ends = np.concatenate((starts[1:], [n])) - 1
    mins = np.minimum.reduceat(ys, starts)
    maxs = np.maximum.reduceat(ys, starts)
    falling = ys[starts] > ys[ends]

    out_y = np.empty(len(starts) * 2)
    out_y[0::2] = np.where(falling, maxs, mins)
    out_y[1::2] = np.where(falling, mins, maxs)
    out_x = np.repeat(cols[starts].astype(np.float64), 2)
    return out_x, out_y


def nice_step(span: float, max_ticks: int) -> float:
    raw = span / max(1, max_ticks)
    if raw <= 0 or not math.isfinite(raw):
        return 1.0
    mag = 10.0 ** math.floor(math.log10(raw))
    for m in (1.0, 2.0, 5.0, 10.0):
        if m * mag >= raw * (1 - 1e-9):
            return m * mag
    return 10.0 * mag


def nice_ticks(lo: float, hi: float, max_ticks: int) -> list[float]:
    """1-2-5 간격의 눈금 값들."""
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo:
        return [lo] if math.isfinite(lo) else []
    step = nice_step(hi - lo, max_ticks)
    start = math.ceil(lo / step - 1e-9)
    ticks = []
    i = start
    while i * step <= hi + step * 1e-9:
        ticks.append(i * step)
        i += 1
    return ticks


def format_tick(v: float, step: float) -> str:
    if abs(v) < step * 1e-9:
        v = 0.0
    if abs(v) >= 1e6 or (0 < step < 1e-4):
        return f"{v:.3g}"
    decimals = max(0, -math.floor(math.log10(step))) if step < 1 else 0
    return f"{v:.{decimals}f}"


class AutoRange:
    """자동 Y 범위. 데이터가 벗어나면 즉시 넓히고, 좁히는 것은 hold_s 동안 유지될 때만 한다.

    매 프레임 범위를 딱 맞추면 눈금 라벨이 계속 흔들려 읽을 수가 없다.
    """

    def __init__(self, hold_s: float = 1.0, pad: float = 0.05):
        self.hold_s = hold_s
        self.pad = pad
        self.lo: float | None = None
        self.hi: float | None = None
        self._shrink_since: float | None = None

    def reset(self) -> None:
        self.lo = self.hi = None
        self._shrink_since = None

    def update(self, dmin: float, dmax: float, now: float) -> tuple[float, float]:
        if not (math.isfinite(dmin) and math.isfinite(dmax)):
            return (self.lo, self.hi) if self.lo is not None else (-1.0, 1.0)  # type: ignore[return-value]
        if dmax <= dmin:
            dmin -= 0.5
            dmax += 0.5
        span = dmax - dmin
        tlo = dmin - span * self.pad
        thi = dmax + span * self.pad
        if self.lo is None or self.hi is None:
            self.lo, self.hi = tlo, thi
        elif tlo < self.lo or thi > self.hi:
            self.lo = min(self.lo, tlo)
            self.hi = max(self.hi, thi)
            self._shrink_since = None
        elif (thi - tlo) < (self.hi - self.lo) * 0.7:
            if self._shrink_since is None:
                self._shrink_since = now
            elif now - self._shrink_since >= self.hold_s:
                self.lo, self.hi = tlo, thi
                self._shrink_since = None
        else:
            self._shrink_since = None
        return self.lo, self.hi


class Series:
    def __init__(self, name: str, color: str | RGB | None = None, width: int = 1, capacity: int = 4096):
        self.name = name
        self.color = color
        self.width = width
        self.visible = True
        self.buffer = RingBuffer(capacity)
        self._drawn_version = -1

    def append(self, y: float, x: float | None = None) -> None:
        self.buffer.append(y, x)

    def extend(self, ys: Sequence[float] | np.ndarray, xs: Sequence[float] | np.ndarray | None = None) -> None:
        self.buffer.extend(ys, xs)

    def cb_append_data_point(self, y: float, x: float | None = None) -> None:
        """pglive DataConnector 호환 이름."""
        self.buffer.append(y, x)

    def clear(self) -> None:
        self.buffer.clear()


class LivePlot(PixelWidget):
    focusable = True

    def __init__(
        self,
        title: str = "",
        *,
        window: float | None = None,
        x_range: tuple[float, float] | None = None,
        y_range: tuple[float, float] | None = None,
        update_hz: float = 30.0,
        antialias: bool = False,
        header: bool = True,
        stretch: int = 1,
        **kw,
    ):
        super().__init__(stretch=stretch, **kw)
        self.title = title
        # False 면 제목/범례 줄 없이 그래프만 그린다 (범례는 PlotLegend 로 다른 줄에)
        self.header = header
        self.series_changed = Signal()  # 시리즈가 추가/삭제되거나 보이기가 바뀔 때
        self.window = window  # x 단위 롤링 구간 (x 를 안 주면 샘플 개수)
        self.x_range = x_range
        self.y_range = y_range
        self.update_hz = update_hz
        self.antialias = antialias
        self.series: list[Series] = []
        self.paused = False
        self._frozen: list[tuple[Series, np.ndarray, np.ndarray, int]] | None = None
        self._auto = AutoRange()
        self._last_poll = 0.0
        self._y_labels: list[tuple[int, str]] = []
        self._x_labels: list[tuple[int, str]] = []

    # ---- public API ----------------------------------------------------

    def add_series(self, name: str, color: str | RGB | None = None, width: int = 1, capacity: int = 4096) -> Series:
        s = Series(name, color, width, capacity)
        self.series.append(s)
        self.invalidate()
        self.invalidate_pixels()
        self.series_changed.emit()
        return s

    def set_series_visible(self, series: Series, visible: bool) -> None:
        if series.visible == visible:
            return
        series.visible = visible
        self._auto.reset()  # 숨긴 시리즈 범위에 맞춰 넓어진 Y 축을 다시 잡는다
        self.invalidate()
        self.invalidate_pixels()
        self.series_changed.emit()

    def set_paused(self, paused: bool) -> None:
        if paused == self.paused:
            return
        self._frozen = self._take_snapshots() if paused else None
        self.paused = paused
        self.invalidate()
        self.invalidate_pixels()

    def set_y_range(self, y_range: tuple[float, float] | None) -> None:
        self.y_range = y_range
        self._auto.reset()
        self.invalidate_pixels()

    def set_x_range(self, x_range: tuple[float, float] | None) -> None:
        self.x_range = x_range
        self.invalidate_pixels()

    def clear(self) -> None:
        for s in self.series:
            s.clear()
        self._auto.reset()
        self.invalidate_pixels()

    def clear_series(self) -> None:
        """시리즈까지 모두 지운다 (데이터 원본이 바뀌어 이름 목록부터 다시 만들 때)."""
        self.series.clear()
        self._frozen = None
        self._auto.reset()
        self.invalidate()
        self.invalidate_pixels()
        self.series_changed.emit()

    # ---- layout / paint ------------------------------------------------

    def size_hint(self) -> SizeHint:
        return SizeHint(16, 5, 40, 12)

    def _has_axes(self) -> bool:
        return self.rect.h >= 5 and self.rect.w >= _GUTTER + 8

    def pixel_rect(self) -> Rect:
        r = self.rect
        top = 1 if self.header else 0
        if self._has_axes():
            return Rect(r.x + _GUTTER, r.y + top, r.w - _GUTTER, r.h - 1 - top)
        return Rect(r.x, r.y + top, r.w, max(0, r.h - top))

    def series_color(self, index: int, s: Series) -> RGB:
        pal = self.palette
        if s.color is None:
            return pal.series[index % len(pal.series)]
        return resolve_color(s.color, pal)

    def paint(self, p: Painter) -> None:
        pal = self.palette
        r = self.rect
        p.fill(Rect(0, 0, r.w, r.h), " ", pal.fg, pal.bg)

        if self.header:
            title_fg = pal.border_focus if self.focused else pal.accent
            x = p.text(0, 0, truncate(self.title, r.w), title_fg, pal.bg, Attr.BOLD)
            if self.paused:
                x = p.text(x + 1, 0, " PAUSED ", pal.bg, pal.warn)

            legend = [(i, s) for i, s in enumerate(self.series) if s.name]
            legend_w = sum(str_width(s.name) + 3 for _, s in legend)
            lx = r.w - legend_w + 1
            if legend and lx > x + 1:
                for i, s in legend:
                    color = self.series_color(i, s)
                    p.put(lx, 0, "■", color, pal.bg)
                    lx = p.text(lx + 1, 0, s.name, color if s.visible else pal.disabled, pal.bg) + 2

        super().paint(p)
        if self._has_axes():
            for row, text in self._y_labels:
                p.text(_GUTTER - 1 - str_width(text), row, text, pal.axis, pal.bg)
            for col, text in self._x_labels:
                p.text(col, r.h - 1, text, pal.axis, pal.bg)

    # ---- pixel rendering -----------------------------------------------

    def frame_deadline(self) -> float | None:
        if self.paused or self.update_hz <= 0:
            return None
        return self._last_poll + 1.0 / self.update_hz

    def poll_frame(self, now: float) -> bool:
        self._last_poll = now
        return any(s.buffer.version != s._drawn_version for s in self.series)

    def _take_snapshots(self) -> list[tuple[Series, np.ndarray, np.ndarray, int]]:
        return [(s, *s.buffer.snapshot()) for s in self.series]

    def _x_bounds(self, data) -> tuple[float, float]:
        if self.x_range is not None:
            return float(self.x_range[0]), float(self.x_range[1])
        firsts = [xs[0] for s, xs, _, _ in data if s.visible and len(xs)]
        lasts = [xs[-1] for s, xs, _, _ in data if s.visible and len(xs)]
        if not lasts:
            return 0.0, float(self.window or 1.0)
        x1 = float(max(lasts))
        x0 = x1 - self.window if self.window else float(min(firsts))
        if x1 <= x0:
            x0 = x1 - 1.0
        return x0, x1

    def _y_bounds(self, data, x0: float, x1: float) -> tuple[float, float]:
        if self.y_range is not None:
            return float(self.y_range[0]), float(self.y_range[1])
        mins, maxs = [], []
        for s, xs, ys, _ in data:
            if not s.visible or not len(xs):
                continue
            seg = ys[np.searchsorted(xs, x0, "left") : np.searchsorted(xs, x1, "right")]
            seg = seg[np.isfinite(seg)]
            if seg.size:
                mins.append(float(seg.min()))
                maxs.append(float(seg.max()))
        if not mins:
            return (self._auto.lo, self._auto.hi) if self._auto.lo is not None else (-1.0, 1.0)  # type: ignore[return-value]
        return self._auto.update(min(mins), max(maxs), time.monotonic())

    def render_pixels(self, surf: pygame.Surface, scale: float) -> None:
        pal = self.palette
        area = self.pixel_rect()
        W, H = surf.get_size()
        surf.fill(pal.plot_bg)
        if W < 2 or H < 2 or area.w <= 0 or area.h <= 0:
            return
        cw = W / area.w
        ch = H / area.h
        t = max(1, round(scale))

        data = self._frozen if self.paused and self._frozen is not None else self._take_snapshots()
        x0, x1 = self._x_bounds(data)
        lo, hi = self._y_bounds(data, x0, x1)
        if hi <= lo:
            hi = lo + 1.0

        def to_py(v: float) -> float:
            return (hi - v) * ((H - 1) / (hi - lo))

        # 격자와 눈금 라벨 위치 (라벨은 셀 텍스트라 가장 가까운 행/열에 둔다)
        y_labels: list[tuple[int, str]] = []
        rows_used: set[int] = set()
        y_step = nice_step(hi - lo, max(2, area.h // 2))
        for v in nice_ticks(lo, hi, max(2, area.h // 2)):
            py = to_py(v)
            surf.fill(pal.grid, (0, int(py), W, t))
            row = (area.y - self.rect.y) + min(area.h - 1, int(py // ch))
            if row not in rows_used:
                rows_used.add(row)
                y_labels.append((row, format_tick(v, y_step)))
        if lo < 0 < hi:
            surf.fill(pal.axis, (0, int(to_py(0.0)), W, t))

        x_labels: list[tuple[int, str]] = []
        last_end = -1
        x_ticks = max(2, area.w // 12)
        x_step = nice_step(x1 - x0, x_ticks)
        for v in nice_ticks(x0, x1, x_ticks):
            px = (v - x0) * ((W - 1) / (x1 - x0))
            surf.fill(pal.grid, (int(px), 0, t, H))
            text = format_tick(v, x_step)
            col = (area.x - self.rect.x) + int(px // cw) - str_width(text) // 2
            col = max(area.x - self.rect.x, min(col, self.rect.w - str_width(text)))
            if col > last_end:
                x_labels.append((col, text))
                last_end = col + str_width(text)

        # 시리즈: 논리 픽셀 폭으로 줄여서 그린다 (Retina 에서 점 수를 1/2 로)
        logical_w = max(2, int(W / scale))
        sx = (W - 1) / (logical_w - 1)
        for i, (s, xs, ys, version) in enumerate(data):
            s._drawn_version = version
            if not s.visible or len(xs) < 2:
                continue
            dx, dy = decimate(xs, ys, x0, x1, logical_w)
            if len(dx) < 2:
                continue
            px = dx * sx
            py = (hi - dy) * ((H - 1) / (hi - lo))
            ok = np.isfinite(py)
            if not ok.all():
                px, py = px[ok], py[ok]
                if len(px) < 2:
                    continue
            np.clip(py, -H, 2 * H, out=py)
            pts = np.column_stack((px, py)).tolist()
            color = self.series_color(i, s)
            if self.antialias and s.width == 1:
                pygame.draw.aalines(surf, color, False, pts)
            else:
                pygame.draw.lines(surf, color, False, pts, max(1, s.width * t))

        if y_labels != self._y_labels or x_labels != self._x_labels:
            self._y_labels = y_labels
            self._x_labels = x_labels
            self.invalidate()

    # ---- events --------------------------------------------------------

    def on_event(self, ev: Event) -> bool:
        if isinstance(ev, KeyEvent) and ev.key == Key.SPACE and not ev.mod:
            self.set_paused(not self.paused)
            return True
        if isinstance(ev, MouseEvent) and ev.kind == "down" and ev.button == 1:
            if ev.clicks == 2:
                self.set_paused(not self.paused)
            return True
        return False
