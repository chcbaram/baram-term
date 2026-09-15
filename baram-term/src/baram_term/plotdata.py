"""Pick plot values out of received lines.

지원하는 형식:
- Teleplot:  ">ax:-15", ">temp:34.2", ">ax:1234:-15" (시각:값), 뒤에 붙는 "§단위" 와 "|옵션" 은 무시
- Arduino IDE Serial Plotter:  "10 20 30", "10,20,30", "ax:-15,ay:-70", "temp=34 rpm=1200"
  (쉼표/탭/공백으로 나누고, 이름이 없으면 Arduino IDE 2 처럼 "value 1", "value 2")

숫자로 읽을 수 없는 조각이 하나라도 있으면 그래프 줄이 아니다: "[OK] sensor temp=42" 같은 로그는 건너뛴다.
이름도 검사한다: 연결 전에 쌓였던 수신 버퍼가 잘리거나 UTF-8 이 깨지면 "gz��>ax:12" 처럼 두 줄이 붙어 오는데,
이것을 "gz��>ax" 라는 새 시리즈로 만들지 않게 깨진 글자(U+FFFD), 제어 문자, 공백, '>' 와 구분자가 든 이름은 버린다.
"""

from __future__ import annotations

import math
import re

_NUMBER = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
_SPLIT = re.compile(r"[,\t ]+")
_AROUND_SEP = re.compile(r"\s*([:=])\s*")
_NAME = re.compile(r"[^\s:=,;>§|\ufffd\x00-\x1f\x7f]+")


def _name_ok(name: str) -> bool:
    return _NAME.fullmatch(name) is not None


def _number(text: str) -> float | None:
    text = text.strip()
    if not _NUMBER.fullmatch(text):
        return None
    value = float(text)
    return value if math.isfinite(value) else None


def plot_format(line: str) -> str:
    """'tele' (>name:value) 또는 'arduino'."""
    return "tele" if line.lstrip().startswith(">") else "arduino"


def parse_line(line: str) -> list[tuple[str, float]] | None:
    """그래프 값 목록 [(이름, 값)], 그래프 줄이 아니면 None."""
    line = line.strip()
    if not line:
        return None
    if line.startswith(">"):
        return _parse_teleplot(line[1:])
    return _parse_arduino(line)


def _parse_teleplot(body: str) -> list[tuple[str, float]] | None:
    body = body.split("|", 1)[0].split("§", 1)[0]
    name, sep, rest = body.partition(":")
    name = name.strip()
    if not sep or not _name_ok(name):
        return None
    point = rest.split(";")[-1]  # ">name:t1:v1;t2:v2" 처럼 여러 점이면 마지막 값
    parts = point.split(":")
    if len(parts) > 2:
        return None
    value = _number(parts[-1])
    return None if value is None else [(name, value)]


def _parse_arduino(line: str) -> list[tuple[str, float]] | None:
    out: list[tuple[str, float]] = []
    line = _AROUND_SEP.sub(r"\1", line)  # "temp: 34" 도 "temp:34" 로
    for index, token in enumerate((t for t in _SPLIT.split(line) if t), start=1):
        name, value_text = "", token
        for sep in (":", "="):
            if sep in token:
                name, _, value_text = token.partition(sep)
                if not _name_ok(name):
                    return None
                break
        value = _number(value_text)
        if value is None:
            return None
        out.append((name or f"value {index}", value))
    return out or None
