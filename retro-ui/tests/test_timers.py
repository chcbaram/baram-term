import pytest

from retroui.core.timers import TimerQueue


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


def test_interval_has_no_drift(clock):
    q = TimerQueue(clock)
    calls = []
    q.set_interval(100, lambda: calls.append(clock.t))
    clock.t = 0.1
    assert q.run_due() == 1
    clock.t = 0.25  # 늦게 처리돼도
    assert q.run_due() == 1
    assert q.next_deadline() == pytest.approx(0.3)  # 다음 예약은 0.35 가 아니라 0.3


def test_missed_periods_are_skipped(clock):
    q = TimerQueue(clock)
    calls = []
    q.set_interval(100, lambda: calls.append(clock.t))
    clock.t = 1.05
    assert q.run_due() == 1
    assert q.next_deadline() == pytest.approx(1.1)


def test_timeout_fires_once(clock):
    q = TimerQueue(clock)
    calls = []
    t = q.set_timeout(50, lambda: calls.append(1))
    clock.t = 0.1
    assert q.run_due() == 1
    clock.t = 1.0
    assert q.run_due() == 0
    assert not t.active
    assert q.next_deadline() is None


def test_stop_inside_callback(clock):
    q = TimerQueue(clock)
    holder = {}
    calls = []

    def cb():
        calls.append(clock.t)
        holder["t"].stop()

    holder["t"] = q.set_interval(10, cb)
    clock.t = 1.0
    q.run_due()
    clock.t = 2.0
    q.run_due()
    assert len(calls) == 1
    assert q.next_deadline() is None


def test_restart_replaces_old_schedule(clock):
    q = TimerQueue(clock)
    calls = []
    t = q.set_interval(100, lambda: calls.append(clock.t))
    clock.t = 0.05
    t.start(500)
    clock.t = 0.2
    assert q.run_due() == 0
    clock.t = 0.55
    assert q.run_due() == 1


def test_callback_exception_does_not_break_queue(clock, caplog):
    q = TimerQueue(clock)
    calls = []
    q.set_interval(10, lambda: 1 / 0)
    q.set_interval(10, lambda: calls.append(1))
    clock.t = 0.01
    assert q.run_due() == 2
    assert calls == [1]
    assert "timer callback failed" in caplog.text
