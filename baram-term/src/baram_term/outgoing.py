"""Filter bytes typed or pasted at the firmware CLI prompt.

펌웨어 cli.c 는 줄 편집 키(Enter/Backspace/Delete/ESC 시퀀스)가 아닌 바이트를 제어 문자까지 전부 줄 버퍼에
넣고 그대로 에코한다. Tab(0x09)을 받으면 터미널은 커서를 다음 탭 위치(최대 8칸)로 옮기는데 펌웨어는 1칸으로
세서, 이후 Backspace/화살표 화면 갱신이 어긋나 줄이 깨진다. 프롬프트 줄에서는 이런 바이트를 보내지 않는다.
명령 실행 중(프롬프트가 아닐 때)에는 Ctrl+C 같은 키가 의미가 있으므로 그대로 보낸다.
"""

from __future__ import annotations

# 펌웨어가 줄 편집에 쓰는 제어 문자: Backspace, Enter(CR, 설정에 따라 LF/CRLF), Delete
_LINE_EDIT = {0x08, 0x0A, 0x0D, 0x7F}
_TAB = 0x09
_ESC = 0x1B


def outgoing_bytes(data: bytes, *, at_prompt: bool, guard: bool) -> bytes:
    if not guard or not at_prompt or not data:
        return data
    if data[0] == _ESC:
        return data  # 방향키/Home/End 등 키 시퀀스는 펌웨어가 처리한다
    single_key = len(data) == 1
    out = bytearray()
    for b in data:
        if b == _TAB:
            if not single_key:
                out.append(0x20)  # 붙여넣은 글자 속 Tab 은 공백으로
        elif b < 0x20 and b not in _LINE_EDIT:
            continue
        else:
            out.append(b)
    return bytes(out)
