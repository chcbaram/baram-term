"""Backend-neutral input events translated from pygame events.

위젯은 pygame 을 직접 import 하지 않고 이 모듈의 이벤트와 Key 상수만 쓴다.
마우스 좌표는 SDL 이 point 단위로 주므로 scale 을 곱해 픽셀로, 셀 크기로 나눠 셀 좌표로 바꾼다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import IntFlag
from typing import Union

import pygame

IS_MAC = sys.platform == "darwin"


class Mod(IntFlag):
    NONE = 0
    SHIFT = 1
    CTRL = 2
    ALT = 4
    META = 8


def mod_from_pygame(m: int) -> Mod:
    out = Mod.NONE
    if m & pygame.KMOD_SHIFT:
        out |= Mod.SHIFT
    if m & pygame.KMOD_CTRL:
        out |= Mod.CTRL
    if m & pygame.KMOD_ALT:
        out |= Mod.ALT
    if m & pygame.KMOD_META:
        out |= Mod.META
    return out


class Key:
    RETURN = pygame.K_RETURN
    KP_ENTER = pygame.K_KP_ENTER
    ESCAPE = pygame.K_ESCAPE
    TAB = pygame.K_TAB
    BACKSPACE = pygame.K_BACKSPACE
    DELETE = pygame.K_DELETE
    INSERT = pygame.K_INSERT
    LEFT = pygame.K_LEFT
    RIGHT = pygame.K_RIGHT
    UP = pygame.K_UP
    DOWN = pygame.K_DOWN
    HOME = pygame.K_HOME
    END = pygame.K_END
    PAGEUP = pygame.K_PAGEUP
    PAGEDOWN = pygame.K_PAGEDOWN
    SPACE = pygame.K_SPACE
    F1 = pygame.K_F1
    F2 = pygame.K_F2
    F3 = pygame.K_F3
    F4 = pygame.K_F4
    F5 = pygame.K_F5
    F6 = pygame.K_F6
    F7 = pygame.K_F7
    F8 = pygame.K_F8
    F9 = pygame.K_F9
    F10 = pygame.K_F10
    F11 = pygame.K_F11
    F12 = pygame.K_F12
    A = pygame.K_a
    C = pygame.K_c
    V = pygame.K_v
    X = pygame.K_x
    Z = pygame.K_z


@dataclass(slots=True)
class KeyEvent:
    key: int
    mod: Mod
    name: str = ""

    @property
    def shift(self) -> bool:
        return bool(self.mod & Mod.SHIFT)

    @property
    def alt(self) -> bool:
        return bool(self.mod & Mod.ALT)

    @property
    def primary(self) -> bool:
        """복사/붙여넣기 등 기본 단축키 수정자: macOS 는 Cmd, 그 외는 Ctrl."""
        return bool(self.mod & (Mod.META if IS_MAC else Mod.CTRL))

    @property
    def is_enter(self) -> bool:
        return self.key in (Key.RETURN, Key.KP_ENTER)


@dataclass(slots=True)
class TextEvent:
    """확정된 입력 문자열 (IME 커밋 포함)."""

    text: str


@dataclass(slots=True)
class CompositionEvent:
    """IME 조합 중 문자열 (preedit). 빈 문자열이면 조합 종료."""

    text: str
    cursor: int


@dataclass(slots=True)
class MouseEvent:
    kind: str  # "down" | "up" | "move"
    button: int  # 1 left, 2 middle, 3 right, 0 move
    cx: int
    cy: int
    px: int
    py: int
    mod: Mod = Mod.NONE
    clicks: int = 1


@dataclass(slots=True)
class WheelEvent:
    dx: float
    dy: float  # 위로 굴리면 양수
    cx: int
    cy: int
    px: int
    py: int


@dataclass(slots=True)
class FocusEvent:
    gained: bool


Event = Union[KeyEvent, TextEvent, CompositionEvent, MouseEvent, WheelEvent, FocusEvent]


def normalize_key(key: int, name: str, scancode: int) -> tuple[int, str]:
    """한글 등 비라틴 입력 상태에서는 글자 키 이름이 빈 문자열로 온다 (tests/fixtures/ime_macos_2set.json 실측).

    물리 키 위치(USB HID scancode)로 영문 키를 복원해서 단축키, 니모닉, 메뉴 선택 문자가
    입력 언어와 무관하게 동작하게 한다.
    """
    if name and name.isascii():
        return key, name
    if 4 <= scancode <= 29:
        return pygame.K_a + scancode - 4, chr(ord("a") + scancode - 4)
    if 30 <= scancode <= 38:
        return pygame.K_1 + scancode - 30, str(scancode - 29)
    if scancode == 39:
        return pygame.K_0, "0"
    return key, name


def _to_cells(pos: tuple[float, float], scale: float, cw: int, ch: int, ox: int, oy: int) -> tuple[int, int, int, int]:
    # 여백 안쪽 격자 원점 기준. 여백을 누르면 음수 셀이 되어 어떤 위젯에도 맞지 않는다
    px = int(pos[0] * scale) - ox
    py = int(pos[1] * scale) - oy
    return px // cw, py // ch, px, py


def translate(ev: pygame.event.Event, scale: float, cw: int, ch: int, ox: int = 0, oy: int = 0) -> Event | None:
    t = ev.type
    if t == pygame.KEYDOWN:
        key, name = normalize_key(ev.key, pygame.key.name(ev.key), getattr(ev, "scancode", 0))
        return KeyEvent(key, mod_from_pygame(ev.mod), name)
    if t == pygame.TEXTINPUT:
        return TextEvent(ev.text)
    if t == pygame.TEXTEDITING:
        return CompositionEvent(ev.text, ev.start)
    if t in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        # pygame 은 휠을 버튼 4/5 로도 보낸다: MOUSEWHEEL 로만 처리
        if ev.button > 3:
            return None
        cx, cy, px, py = _to_cells(ev.pos, scale, cw, ch, ox, oy)
        kind = "down" if t == pygame.MOUSEBUTTONDOWN else "up"
        return MouseEvent(kind, ev.button, cx, cy, px, py, mod_from_pygame(pygame.key.get_mods()))
    if t == pygame.MOUSEMOTION:
        cx, cy, px, py = _to_cells(ev.pos, scale, cw, ch, ox, oy)
        return MouseEvent("move", 0, cx, cy, px, py, mod_from_pygame(pygame.key.get_mods()))
    if t == pygame.MOUSEWHEEL:
        cx, cy, px, py = _to_cells(pygame.mouse.get_pos(), scale, cw, ch, ox, oy)
        dx = getattr(ev, "precise_x", ev.x)
        dy = getattr(ev, "precise_y", ev.y)
        if getattr(ev, "flipped", False):
            dx, dy = -dx, -dy
        return WheelEvent(dx, dy, cx, cy, px, py)
    return None
