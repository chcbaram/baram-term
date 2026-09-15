import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from retroui import Terminal  # noqa: E402
from retroui.input.events import IS_MAC  # noqa: E402


def filled(lines=200, wheel_lines=3):
    term = Terminal(max_lines=500)
    term.feed("".join(f"line {i}\r\n" for i in range(lines)))
    term.wheel_lines = wheel_lines  # OS 마다 기본값이 달라서 테스트는 값을 정해 둔다
    return term


def wheel(term, deltas):
    for d in deltas:
        term._wheel(d)
    return term.scroll_offset


def test_default_follows_the_os():
    """macOS 는 휠 값에 속도와 가속이 이미 들어 있어 그대로 쓰고, 다른 OS 는 한 칸에 3줄."""
    assert Terminal().wheel_lines == (1 if IS_MAC else 3)


def test_a_mouse_notch_scrolls_wheel_lines():
    term = filled(wheel_lines=3)
    assert wheel(term, [1]) == 3


def test_accelerated_deltas_are_not_amplified_on_top():
    """빠르게 밀어 가속이 들어간 큰 값에 또 곱하지 않는다 (가속이 지나치게 셌다)."""
    term = filled(wheel_lines=1)
    assert wheel(term, [4.0]) == 4


def test_small_trackpad_deltas_are_not_rounded_up_to_a_line():
    """0.1 짜리 이벤트마다 한 줄씩 움직이면 살짝 밀어도 화면이 확 지나간다."""
    term = filled(wheel_lines=1)
    assert wheel(term, [0.1, 0.1, 0.1]) == 0


def test_small_deltas_add_up_to_whole_lines():
    term = filled(wheel_lines=1)
    assert wheel(term, [0.1] * 10) == 1  # 0.999... 로 한 줄을 잃지 않는다
    assert wheel(term, [0.1] * 10) == 2


def test_scrolling_back_down_uses_the_same_steps():
    term = filled(wheel_lines=3)
    wheel(term, [1, 1])  # 6줄 위로
    assert term.scroll_offset == 6
    assert wheel(term, [-0.5] * 4) == 0  # 0.5 x 3 x 4 = 6줄 아래로


def test_wheel_lines_is_adjustable():
    term = filled(wheel_lines=1)
    assert wheel(term, [1]) == 1


def test_wheel_event_keeps_the_os_scroll_direction():
    """SDL 값은 macOS 스크롤 방향 설정이 이미 들어간 값이다. `flipped` 라고 다시 뒤집으면 안 된다.

    뒤집던 때는 트랙패드(자연스러운 스크롤)와 마우스를 반대로 설정해도 둘이 같은 방향으로 움직였다.
    """
    import pygame

    from retroui.input.events import WheelEvent, translate

    pygame.display.init()
    pygame.display.set_mode((1, 1))
    for flipped in (False, True):
        ev = pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1, flipped=flipped, precise_x=0.0, precise_y=1.0)
        out = translate(ev, 1.0, 8, 16)
        assert isinstance(out, WheelEvent)
        assert out.dy == 1.0, flipped
