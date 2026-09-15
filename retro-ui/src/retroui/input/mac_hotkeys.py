"""macOS input source switch shortcuts that use the Space key.

사용자가 입력 소스 전환(한/영)을 Shift+Space 처럼 스페이스 조합으로 설정해 두면, macOS 기본 앱에서는
그 키가 전환에만 쓰이고 글자가 입력되지 않는다. 그런데 SDL 은 전환과 함께 TEXTINPUT " " 도 보내서
터미널에 스페이스가 찍혔다 (tests/fixtures/ime_macos_2set.json 에 실제 기록이 있다).

여기서는 그 단축키 설정을 읽어 "어떤 수정키 + 스페이스" 가 입력 전환인지 알려 준다. ImeFilter 가 이
조합 바로 뒤의 스페이스 글자를 버린다. 설정은 앱 시작 때 한 번 읽는다.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys

from retroui.input.events import Mod

# com.apple.symbolichotkeys 의 입력 소스 전환 항목: 60 이전 소스, 61 다음 소스
INPUT_SOURCE_IDS = ("60", "61")
KEYCODE_SPACE = 49  # macOS 가상 키코드 kVK_Space

# NSEvent 수정키 비트 -> Mod
_NS_MODS = {
    1 << 17: Mod.SHIFT,
    1 << 18: Mod.CTRL,
    1 << 19: Mod.ALT,
    1 << 20: Mod.META,  # Command
}
_NS_KNOWN = sum(_NS_MODS)


def parse_hotkeys(data: dict) -> set[Mod]:
    """symbolichotkeys 설정에서 스페이스를 쓰는 입력 전환 조합의 수정키 집합.

    알 수 없는 수정키(fn 등)가 섞인 조합은 뺀다: SDL 은 그 키를 알려주지 않아서, 섞인 채로 맞추면
    수정키가 덜 눌린 평범한 입력까지 버리게 된다.
    """
    out: set[Mod] = set()
    hotkeys = data.get("AppleSymbolicHotKeys", {})
    for hid in INPUT_SOURCE_IDS:
        entry = hotkeys.get(hid)
        if not isinstance(entry, dict) or not entry.get("enabled"):
            continue
        params = (entry.get("value") or {}).get("parameters") or []
        if len(params) < 3 or params[1] != KEYCODE_SPACE:
            continue
        flags = int(params[2])
        if flags & ~_NS_KNOWN & 0xFFFF0000:  # 장치별 하위 비트는 무시하고, 모르는 수정키가 있으면 뺀다
            continue
        mods = Mod.NONE
        for bit, mod in _NS_MODS.items():
            if flags & bit:
                mods |= mod
        out.add(mods)
    return out


def input_source_space_mods() -> set[Mod]:
    """이 Mac 에서 입력 전환으로 쓰는 "수정키 + 스페이스" 조합들. macOS 가 아니거나 못 읽으면 빈 집합."""
    if sys.platform != "darwin":
        return set()
    try:
        result = subprocess.run(
            ["defaults", "export", "com.apple.symbolichotkeys", "-"],
            capture_output=True, timeout=2, check=True,
        )
        return parse_hotkeys(plistlib.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, ValueError, plistlib.InvalidFileException):
        return set()  # 못 읽으면 아무것도 버리지 않는다
