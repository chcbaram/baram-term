import threading

import pytest

from retroui.core import signal as signal_mod
from retroui.core.signal import Signal, set_dispatcher


@pytest.fixture(autouse=True)
def reset_dispatcher():
    yield
    set_dispatcher(None)


def test_direct_emit_and_disconnect():
    s = Signal()
    got = []
    s.connect(got.append)
    s.connect(got.append)  # 중복 연결은 무시
    s.emit(1)
    assert got == [1]
    assert s.disconnect(got.append)
    assert not s.disconnect(got.append)
    s.emit(2)
    assert got == [1]


def test_emit_from_worker_thread_goes_through_dispatcher():
    queued = []
    set_dispatcher(lambda fn, *args: queued.append((fn, args)), threading.get_ident())
    s = Signal()
    got = []
    s.connect(got.append)

    th = threading.Thread(target=s.emit, args=("- DONE -",))
    th.start()
    th.join()
    assert got == []
    assert len(queued) == 1

    for fn, args in queued:
        fn(*args)
    assert got == ["- DONE -"]

    s.emit("main")  # 메인 스레드 emit 은 바로 실행
    assert got == ["- DONE -", "main"]


def test_no_dispatcher_runs_in_caller_thread():
    assert signal_mod._dispatch is None
    s = Signal()
    idents = []
    s.connect(lambda: idents.append(threading.get_ident()))
    th = threading.Thread(target=s.emit)
    th.start()
    th.join()
    assert idents == [th.ident]
