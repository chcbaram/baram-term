"""Heap-based timers driven by the app event loop (QTimer replacement)."""

from __future__ import annotations

import heapq
import itertools
import logging
import math
import time
from typing import Callable

log = logging.getLogger(__name__)

# interval 0 반복 타이머가 run_due 한 번 안에서 무한히 도는 것을 막는 최소 간격
_MIN_INTERVAL_S = 0.001


class Timer:
    def __init__(self, queue: TimerQueue, interval_ms: float, callback: Callable[[], None], repeat: bool = True):
        self._queue = queue
        self.interval_ms = interval_ms
        self.callback = callback
        self.repeat = repeat
        self._gen = 0
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    @property
    def interval_s(self) -> float:
        return max(_MIN_INTERVAL_S, self.interval_ms / 1000.0)

    def start(self, interval_ms: float | None = None) -> None:
        if interval_ms is not None:
            self.interval_ms = interval_ms
        # 세대 번호를 올려 힙에 남아 있는 이전 예약을 무효화한다
        self._gen += 1
        self._active = True
        self._queue._schedule(self, self._queue.clock() + self.interval_s)

    def stop(self) -> None:
        self._gen += 1
        self._active = False


class TimerQueue:
    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.clock = clock
        self._heap: list[tuple[float, int, int, Timer]] = []
        self._seq = itertools.count()

    def set_interval(self, interval_ms: float, callback: Callable[[], None]) -> Timer:
        timer = Timer(self, interval_ms, callback, repeat=True)
        timer.start()
        return timer

    def set_timeout(self, delay_ms: float, callback: Callable[[], None]) -> Timer:
        timer = Timer(self, delay_ms, callback, repeat=False)
        timer.start()
        return timer

    def _schedule(self, timer: Timer, deadline: float) -> None:
        heapq.heappush(self._heap, (deadline, next(self._seq), timer._gen, timer))

    def _drop_stale(self) -> None:
        heap = self._heap
        while heap and (not heap[0][3]._active or heap[0][2] != heap[0][3]._gen):
            heapq.heappop(heap)

    def next_deadline(self) -> float | None:
        self._drop_stale()
        return self._heap[0][0] if self._heap else None

    def run_due(self, now: float | None = None) -> int:
        if now is None:
            now = self.clock()
        fired = 0
        heap = self._heap
        while heap and heap[0][0] <= now:
            deadline, _, gen, timer = heapq.heappop(heap)
            if not timer._active or gen != timer._gen:
                continue
            if timer.repeat:
                # 콜백 전에 다음 예약을 넣어야 콜백 안의 stop()/start() 가 세대 번호로 이를 무효화한다.
                # 다음 시각은 deadline 기준으로 잡아 누적 지연(drift)이 없고, 밀린 주기는 몰아서 실행하지 않고 건너뛴다.
                interval = timer.interval_s
                nxt = deadline + (math.floor((now - deadline) / interval) + 1) * interval
                if nxt <= now:
                    nxt += interval
                self._schedule(timer, nxt)
            else:
                timer._active = False
            fired += 1
            try:
                timer.callback()
            except Exception:
                log.exception("timer callback failed")
        return fired
