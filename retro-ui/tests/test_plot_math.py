import threading
import time

import numpy as np
import pytest

from retroui.widgets.plot import AutoRange, RingBuffer, decimate, format_tick, nice_ticks


def test_ring_order_after_wrap():
    rb = RingBuffer(4)
    for v in range(6):
        rb.append(float(v))
    xs, ys, version = rb.snapshot()
    assert ys.tolist() == [2, 3, 4, 5]
    assert xs.tolist() == [2, 3, 4, 5]
    assert version == 6
    assert len(rb) == 4


def test_extend_wraps():
    rb = RingBuffer(5)
    rb.extend([1, 2, 3])
    rb.extend([4, 5, 6, 7])
    assert rb.snapshot()[1].tolist() == [3, 4, 5, 6, 7]


def test_extend_larger_than_capacity_keeps_tail():
    rb = RingBuffer(5)
    rb.append(-1.0)
    rb.extend(np.arange(12.0))
    xs, ys, _ = rb.snapshot()
    assert ys.tolist() == [7, 8, 9, 10, 11]
    assert xs.tolist() == [8, 9, 10, 11, 12]


def test_snapshot_is_a_copy_and_clear_resets():
    rb = RingBuffer(3)
    rb.extend([1, 2])
    _, ys, v1 = rb.snapshot()
    ys[0] = 99
    assert rb.snapshot()[1].tolist() == [1, 2]
    rb.clear()
    xs, ys, v2 = rb.snapshot()
    assert len(xs) == 0 and v2 > v1


def test_concurrent_writer_keeps_snapshots_consistent():
    rb = RingBuffer(1000)
    stop = threading.Event()

    def writer():
        i = 0
        while not stop.is_set():
            rb.extend(np.arange(i, i + 7, dtype=float))
            i += 7
            time.sleep(0)  # GIL 양보: 없으면 읽기 쪽이 매번 스위치 간격(5ms)을 기다려 테스트가 수 초 걸린다

    th = threading.Thread(target=writer)
    th.start()
    try:
        for _ in range(100):
            xs, ys, _ = rb.snapshot()
            if len(xs) > 1:
                assert np.all(np.diff(xs) == 1.0)
                assert np.array_equal(xs, ys)  # 자동 x 와 값이 같은 카운터라 어긋나면 잘못 섞인 것
    finally:
        stop.set()
        th.join()


def test_decimate_small_input_passthrough():
    xs = np.arange(10.0)
    px, py = decimate(xs, xs * 2, 0, 9, 100)
    assert len(px) == 10
    assert px[0] == 0 and px[-1] == pytest.approx(99)


def test_decimate_bounds_and_keeps_extremes():
    n = 100_000
    xs = np.arange(n, dtype=float)
    ys = np.random.default_rng(1).normal(size=n)
    ys[12345] = 50.0
    ys[67890] = -50.0
    px, py = decimate(xs, ys, 0, n - 1, 300)
    assert len(px) <= 2 * 300 + 4
    assert py.max() == 50.0
    assert py.min() == -50.0
    assert np.all(np.diff(px) >= 0)


def test_decimate_only_visible_window():
    xs = np.arange(1000, dtype=float)
    ys = np.where(xs < 500, 100.0, 0.0)
    _, py = decimate(xs, ys, 600, 999, 50)
    assert py.max() == 0.0


def test_decimate_keeps_direction_inside_columns():
    xs = np.arange(10_000, dtype=float)
    _, py = decimate(xs, -xs, 0, 9999, 10)
    assert np.all(np.diff(py) <= 0)


def test_nice_ticks():
    assert nice_ticks(0, 1, 5) == pytest.approx([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    assert nice_ticks(-3.7, 12.2, 4) == pytest.approx([0, 5, 10])
    assert nice_ticks(1, 1, 5) == [1]


def test_format_tick():
    assert format_tick(0.2, 0.2) == "0.2"
    assert format_tick(1000.0, 500) == "1000"
    assert format_tick(-1e-17, 0.5) == "0.0"
    assert format_tick(0.05, 0.05) == "0.05"


def test_autorange_expands_now_and_shrinks_after_hold():
    ar = AutoRange(hold_s=1.0, pad=0.0)
    assert ar.update(0, 10, 0.0) == (0, 10)
    assert ar.update(-5, 10, 0.1) == (-5, 10)
    assert ar.update(0, 1, 0.2) == (-5, 10)
    assert ar.update(0, 1, 0.9) == (-5, 10)
    assert ar.update(0, 1, 1.3) == (0, 1)
