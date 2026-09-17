"""Describe the bytes picked in the HEX view (one info line)."""

from __future__ import annotations

CONTROL_NAMES = {
    0x00: "NUL", 0x07: "BEL", 0x08: "BS", 0x09: "TAB", 0x0A: "LF", 0x0B: "VT",
    0x0C: "FF", 0x0D: "CR", 0x1B: "ESC", 0x7F: "DEL",
}
# 4바이트까지는 길이/CRC 같은 한 덩어리 값으로 읽는다. 그보다 길면 조합 값이 의미가 없어서
# 바이트 수와 글자만 보여 주고, 좁으면 말줄임으로 줄인다.
VALUE_MAX = 4
# 긴 선택을 한 줄에 다 넣을 수는 없으니 앞의 몇 바이트만 보여준다
MAX_HEX = 8
MAX_TEXT = 24
# 이보다 더 줄이느니 앞의 오프셋을 먼저 덜어낸다 (말줄임만 남으면 읽을 게 없다)
MIN_HEX = 4
MIN_TEXT = 8
SEP = "  "


def char_note(byte: int) -> str:
    """한 바이트의 글자 표시: 'l' 처럼 따옴표로, 제어 문자는 이름으로."""
    if 0x20 <= byte < 0x7F:
        return f"'{chr(byte)}'"
    return CONTROL_NAMES.get(byte, f"<{byte:02X}>")


def printable(data: bytes) -> str:
    return "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in data)


def describe(start: int, data: bytes, width: int | None = None) -> str:
    """고른 바이트 설명. width 를 주면 그 폭에 맞춰 줄인다 (좁은 패널에서 뒤가 잘리지 않게)."""
    if not data:
        return ""
    if len(data) <= VALUE_MAX:
        return _pick(_value_lines(start, data), width)
    return _block_line(start, data, width)


def _pick(lines: list[str], width: int | None) -> str:
    """긴 것부터 늘어놓은 후보 중 폭에 맞는 첫 줄. 다 넘치면 가장 짧은 것."""
    if width is None:
        return lines[0]
    for line in lines:
        if len(line) <= width:
            return line
    return lines[-1]


def _value_lines(start: int, data: bytes) -> list[str]:
    """1~4 바이트: 16진수 · 10진수 값 · 글자. 폭이 모자랄 때 덜어낼 순서대로 긴 것부터."""
    at_long = f"@{start:08X}..{start + len(data) - 1:08X}"
    at_short = f"@{start:08X}+{len(data)}"  # 끝 오프셋 대신 개수로 (9칸 절약)
    raw = " ".join(f"{b:02X}" for b in data)
    if len(data) == 1:
        byte = data[0]
        return [
            SEP.join([f"@{start:08X}", raw, str(byte), char_note(byte)]),
            SEP.join([raw, str(byte), char_note(byte)]),
            SEP.join([raw, str(byte)]),
        ]
    # 바이너리 프로토콜의 길이/CRC 필드를 볼 때: 리틀/빅엔디안 정수.
    # 펌웨어 쪽이 대개 리틀엔디안이라 자리가 모자라면 빅엔디안부터 덜어낸다.
    digits = len(data) * 2
    le, be = int.from_bytes(data, "little"), int.from_bytes(data, "big")
    le_hex, be_hex = f"LE 0x{le:0{digits}X}", f"BE 0x{be:0{digits}X}"
    le_full, be_full = f"{le_hex} ({le})", f"{be_hex} ({be})"
    text = f'"{printable(data)}"'
    return [
        SEP.join([at_long, raw, text, le_full, be_full]),
        SEP.join([at_short, raw, text, le_full, be_full]),
        SEP.join([at_short, raw, text, le_full, be_hex]),
        SEP.join([at_short, raw, text, le_full]),
        SEP.join([at_short, raw, text, le_hex]),
        SEP.join([raw, text, le_hex]),
        SEP.join([raw, text]),
        raw,
    ]


def _run(data: bytes, count: int, sep: str, fmt) -> str:
    shown = sep.join(fmt(b) for b in data[:count])
    return shown + (f"{sep}…" if len(data) > count else "")


def _block_line(start: int, data: bytes, width: int | None) -> str:
    """5바이트 이상: 바이트 수와 글자. 좁으면 16진수와 글자를 말줄임으로 줄인다."""
    count = f"{len(data)} bytes"
    hex_n, text_n = MAX_HEX, MAX_TEXT

    def line(head: list[str]) -> str:
        raw = _run(data, hex_n, " ", lambda b: f"{b:02X}")
        text = _run(data, text_n, "", lambda b: printable(bytes([b])))
        return SEP.join([*head, raw, f'"{text}"'])

    heads = [
        [f"@{start:08X}..{start + len(data) - 1:08X}", count],
        [f"@{start:08X}+{len(data)}", count],  # 끝 오프셋 대신 개수로 (9칸 절약)
        [count],  # 바이트 수는 끝까지 남긴다. 말줄임이 걸리면 몇 바이트인지가 유일한 단서다
    ]
    if width is None:
        return line(heads[0])

    def shrink(head: list[str], min_hex: int, min_text: int) -> None:
        nonlocal hex_n, text_n
        while len(line(head)) > width and (hex_n > min_hex or text_n > min_text):
            # 자리를 많이 먹는 쪽부터 한 바이트씩 (16진수는 한 바이트가 3칸, 글자는 1칸)
            if hex_n > min_hex and hex_n * 3 >= text_n:
                hex_n -= 1
            else:
                text_n -= 1

    for head in heads:
        shrink(head, MIN_HEX, MIN_TEXT)  # 읽을 만한 선까지만 줄이고, 모자라면 앞을 덜어낸다
        if len(line(head)) <= width:
            return line(head)
    shrink(heads[-1], 1, 1)  # 앞을 다 덜어내도 넘치면 그때 더 줄인다
    return line(heads[-1])


def as_hex(data: bytes) -> str:
    """복사용 16진수 문자열."""
    return " ".join(f"{b:02X}" for b in data)
