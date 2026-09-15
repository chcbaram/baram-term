"""Minimal signal/slot with main-thread handoff.

워커 스레드(시리얼/소켓/EtherCAT)에서 emit 해도 슬롯은 메인(UI) 스레드에서 실행된다.
App 이 set_dispatcher() 로 call_soon 을 등록하며, 등록 전에는 호출 스레드에서 바로 실행한다.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

_dispatch: Callable[..., None] | None = None
_owner_ident: int | None = None


def set_dispatcher(dispatch: Callable[..., None] | None, owner_ident: int | None = None) -> None:
    """dispatch(fn, *args) 는 fn(*args) 를 owner 스레드에서 실행되도록 넘기는 함수."""
    global _dispatch, _owner_ident
    _dispatch = dispatch
    _owner_ident = threading.get_ident() if owner_ident is None else owner_ident


class Signal:
    __slots__ = ("_slots", "_lock")

    def __init__(self) -> None:
        self._slots: list[Callable[..., Any]] = []
        self._lock = threading.Lock()

    def connect(self, slot: Callable[..., Any]) -> Callable[..., Any]:
        with self._lock:
            if slot not in self._slots:
                self._slots.append(slot)
        return slot

    def disconnect(self, slot: Callable[..., Any]) -> bool:
        with self._lock:
            try:
                self._slots.remove(slot)
            except ValueError:
                return False
        return True

    def __len__(self) -> int:
        """연결된 슬롯 수."""
        return len(self._slots)

    def emit(self, *args: Any) -> None:
        with self._lock:
            slots = tuple(self._slots)
        dispatch = _dispatch
        if dispatch is not None and threading.get_ident() != _owner_ident:
            for slot in slots:
                dispatch(slot, *args)
            return
        for slot in slots:
            slot(*args)
