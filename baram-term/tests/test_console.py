"""콘솔 없이 묶은 실행 파일에서 글자를 낼 곳을 마련하는 경로.

윈도우에서 --windowed 로 묶으면 sys.stdout 이 None 이라, --list 의 print 도 argparse 의
오류 출력도 AttributeError 로 죽는다. _attach_console() 이 그 상태를 없애 준다.
"""

import os
import sys

from baram_term.__main__ import _attach_console, _report_fatal


def test_leaves_a_working_stdout_alone():
    before_out, before_err = sys.stdout, sys.stderr
    _attach_console()
    assert sys.stdout is before_out and sys.stderr is before_err


def test_replaces_a_missing_stdout_so_print_cannot_crash(monkeypatch):
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    _attach_console()

    assert sys.stdout is not None and sys.stderr is not None
    print("이 줄이 예외를 내면 --list 가 콘솔 없는 빌드에서 죽는다")
    print("stderr 도 마찬가지", file=sys.stderr)
    sys.stdout.close()
    sys.stderr.close()


def test_devnull_fallback_is_used_off_windows(monkeypatch):
    if os.name == "nt":
        return  # 윈도우는 부모 콘솔에 붙을 수 있어 devnull 이 아닐 수 있다
    monkeypatch.setattr(sys, "stdout", None)
    _attach_console()
    assert sys.stdout.name == os.devnull
    sys.stdout.close()


def test_report_fatal_never_raises(monkeypatch):
    """알림 자체가 죽으면 원래 오류까지 가려진다. 무슨 일이 있어도 조용히 넘어가야 한다."""
    import pygame

    def boom(*args, **kwargs):
        raise RuntimeError("상자를 못 띄우는 상황")

    monkeypatch.setattr(pygame.display, "message_box", boom)
    _report_fatal("시작 실패")  # 예외가 새어 나오면 이 테스트가 실패한다
