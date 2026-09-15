"""Record a real device CLI session for the terminal replay test.

장치에 아래 바이트만 보내고, 보낸/받은 바이트를 시각과 함께 JSON 으로 저장한다.
기본으로는 명령을 실행하지 않는다 (빈 Enter 와 줄 편집 키만, 편집한 줄은 지운 뒤 빈 Enter).
결과는 git 에 올리지 않는 tests/fixtures/local/ 에 저장한다. 자세한 내용: docs/device-testing.md

usage: python tools/record_cli_session.py PORT [-b 115200] [-o tests/fixtures/local/cli_session.json] [--with-help]
필요: pyserial
"""

from __future__ import annotations

import argparse
import codecs
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parent / "tests" / "fixtures" / "local" / "cli_session.json"

# (단계 이름, 보낼 바이트, 응답 대기 초). 단계 이름은 tests/test_terminal_recorded_sessions.py 와 맞춘다
STEPS = [
    ("enter_prompt", b"\r", 0.5),
    ("type_h", b"h", 0.15),
    ("type_e", b"e", 0.15),
    ("type_l", b"l", 0.15),
    ("left", b"\x1b[D", 0.2),
    ("insert_x", b"X", 0.2),
    ("backspace_x", b"\x08", 0.2),
    ("home", b"\x1b[1~", 0.2),
    ("end", b"\x1b[4~", 0.2),
    ("clear_line", b"\x08\x08\x08", 0.3),
    ("history_up", b"\x1b[A", 0.3),
    ("clear_history", b"\x08" * 16, 0.3),
    ("enter_empty", b"\r", 0.5),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("port")
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("-o", "--out", type=pathlib.Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--with-help",
        action="store_true",
        help="history_up 단계용으로 help 를 먼저 실행한다 (명령 목록이 기록에 들어간다)",
    )
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("[E_] pyserial 이 필요합니다: uv pip install pyserial", file=sys.stderr)
        return 1

    steps = list(STEPS)
    if args.with_help:
        steps.insert(1, ("help", b"help\r", 1.0))

    events = []
    t0 = time.monotonic()

    def rx(ser, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            data = ser.read(ser.in_waiting or 1)
            if data:
                events.append({"t": round(time.monotonic() - t0, 4), "dir": "rx", "hex": data.hex()})

    with serial.Serial(args.port, args.baud, timeout=0.05) as ser:
        rx(ser, 0.5)
        for name, data, wait in steps:
            events.append({"t": round(time.monotonic() - t0, 4), "dir": "tx", "hex": data.hex(), "note": name})
            ser.write(data)
            ser.flush()
            rx(ser, wait)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"baud": args.baud, "events": events}, indent=1), encoding="utf-8")
    print(f"[OK] saved {args.out} ({len(events)} events)")

    sys.path.insert(0, str(HERE.parent / "src"))
    from retroui.widgets.terminal import TerminalScreen

    screen = TerminalScreen(200, 60)
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    for e in events:
        if e["dir"] == "rx":
            screen.feed(decoder.decode(bytes.fromhex(e["hex"])))
    print("--- replayed last lines ---")
    for i in range(max(0, len(screen.lines) - 5), len(screen.lines)):
        print(f"|{screen.line_text(i)}")
    print(f"cursor col {screen.cx}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
