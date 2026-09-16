"""Describe the bytes picked in the HEX view (one info line)."""

from __future__ import annotations

CONTROL_NAMES = {
    0x00: "NUL", 0x07: "BEL", 0x08: "BS", 0x09: "TAB", 0x0A: "LF", 0x0B: "VT",
    0x0C: "FF", 0x0D: "CR", 0x1B: "ESC", 0x7F: "DEL",
}
# 한 줄에 다 넣을 수 없으니 앞의 몇 바이트만 보여준다
MAX_HEX = 8
MAX_TEXT = 24
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
    if len(data) == 1:
        byte = data[0]
        parts = [f"@{start:08X}", f"{byte:02X}", str(byte), char_note(byte)]
    else:
        end = start + len(data) - 1
        shown = " ".join(f"{b:02X}" for b in data[:MAX_HEX])
        if len(data) > MAX_HEX:
            shown += " …"
        text = printable(data[:MAX_TEXT]) + ("…" if len(data) > MAX_TEXT else "")
        parts = [f"@{start:08X}..{end:08X}", f"{len(data)} bytes", shown, f'"{text}"']
        if len(data) in (2, 4):
            # 바이너리 프로토콜의 길이/CRC 필드를 볼 때: 리틀/빅엔디안 정수
            le = int.from_bytes(data, "little")
            be = int.from_bytes(data, "big")
            digits = len(data) * 2
            parts.append(f"LE 0x{le:0{digits}X} ({le})  BE 0x{be:0{digits}X} ({be})")
    if width is None or len(SEP.join(parts)) <= width:
        return SEP.join(parts)
    if len(data) > 1:
        parts[0] = f"@{start:08X}+{len(data)}"  # 끝 오프셋 대신 개수로 (9칸 절약)
    while len(parts) > 2 and len(SEP.join(parts)) > width:
        parts.pop()  # 뒤쪽(정수 → 글자 → 16진수)부터 덜어낸다
    return SEP.join(parts)


def as_hex(data: bytes) -> str:
    """복사용 16진수 문자열."""
    return " ".join(f"{b:02X}" for b in data)
