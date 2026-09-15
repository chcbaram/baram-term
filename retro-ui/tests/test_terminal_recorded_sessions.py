"""실제 장치에서 기록한 CLI 세션을 TerminalScreen 에 재생해서 줄 편집 결과를 확인한다.

기록은 tests/fixtures/local/*.json (git 에 올리지 않음). 없으면 건너뛴다.
기록 방법: docs/device-testing.md  (tools/record_cli_session.py)

프롬프트 문자열은 코드에 적지 않고 기록에서 뽑는다 (장치 식별 정보를 저장소에 남기지 않기 위해).
"""

import codecs
import json
import pathlib

import pytest

from retroui.widgets.terminal import WIDE_CONT, TerminalScreen

LOCAL = pathlib.Path(__file__).parent / "fixtures" / "local"
SESSIONS = sorted(LOCAL.glob("*.json")) if LOCAL.is_dir() else []


def line_raw(screen: TerminalScreen) -> str:
    return "".join(ch for ch, _ in screen.lines[screen.cy] if ch != WIDE_CONT)


def snapshots(events):
    """각 송신 단계 직전의 (커서 줄 글자, 커서 열). 앞 단계에 대한 장치 응답이 반영된 상태다."""
    screen = TerminalScreen(200, 60)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    snaps = {}
    for e in events:
        if e["dir"] == "rx":
            screen.feed(decoder.decode(bytes.fromhex(e["hex"])))
        else:
            snaps.setdefault(e["note"], (line_raw(screen), screen.cx))
    snaps["final"] = (line_raw(screen), screen.cx)
    return snaps


@pytest.mark.skipif(not SESSIONS, reason="no local device recordings (docs/device-testing.md)")
@pytest.mark.parametrize("path", SESSIONS, ids=lambda p: p.stem)
def test_recorded_line_editing_matches_device(path):
    snaps = snapshots(json.loads(path.read_text(encoding="utf-8"))["events"])
    prompt_line, plen = snaps["type_h"]
    prompt = prompt_line[:plen]
    assert plen > 0, "빈 Enter 뒤에 프롬프트가 보여야 한다"

    def expect(step, text, col):
        line, cx = snaps[step]
        assert line.rstrip() == (prompt + text).rstrip(), step
        assert cx == plen + col, step

    expect("left", "hel", 3)
    expect("insert_x", "hel", 2)
    expect("backspace_x", "heXl", 3)
    expect("home", "hel", 2)
    expect("end", "hel", 0)
    expect("clear_line", "hel", 3)
    expect("history_up", "", 0)
    recalled, cx = snaps["clear_history"]
    assert recalled.startswith(prompt) and cx == len(recalled.rstrip()) or cx == plen + len(recalled[plen:].rstrip())
    expect("enter_empty", "", 0)
    expect("final", "", 0)
