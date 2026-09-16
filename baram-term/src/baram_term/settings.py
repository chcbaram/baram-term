"""User settings stored as JSON in the OS user config folder.

위치: macOS ~/Library/Application Support/baram-term, Windows %APPDATA%\\baram-term,
Linux $XDG_CONFIG_HOME/baram-term (없으면 ~/.config/baram-term). BARAM_TERM_CONFIG_DIR 로 바꿀 수 있다.
파일이 없거나 깨졌으면 기본값으로 시작하고, 형식이 틀린 값은 그 값만 기본값으로 쓴다.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from baram_term.serial_port import PortSettings

APP_NAME = "baram-term"
FORMAT_VERSION = 1


@dataclass
class Settings:
    port: str = ""
    baud: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1.0
    flow: str = "none"
    enter: str = "cr"
    backspace: str = "bs"
    rx_lf: str = "crlf"
    theme: str = "mono"
    font_size: int = 14
    cols: int = 100
    rows: int = 32
    lang: str = ""
    local_echo: bool = False
    timestamps: bool = False
    completion: bool = True
    guard_controls: bool = True
    auto_reconnect: bool = True
    plot: bool = False
    # 그래프 패널이 켜져 있을 때 그래프 값 줄을 터미널에 넘기지 않기. 기본은 끔: 받은 글자를 빠짐없이 보는 것이 터미널의 기본
    plot_hide_lines: bool = False
    plot_window: float = 10.0  # 그래프 가로 폭 (초)
    plot_split: float = 2 / 3  # 터미널 : 그래프 높이 비율 (터미널 몫)
    # HEX 보기: 받은/보낸 바이트를 16진수로 보여주는 오른쪽 패널
    hex: bool = False
    hex_split: float = 0.6  # 터미널 : HEX 폭 비율 (터미널 몫). 0.6 이면 폭 120칸에서 한 줄 8바이트가 들어간다
    # 포트 설정 창에서 고른 포트/직접 입력한 주소 (최근 것이 앞)
    recent_ports: list[str] = field(default_factory=list)
    # F1~F12 매크로 막대: 보이기와 슬롯 12개 ("이름=명령", 빈 문자열이면 빈 칸)
    macro_bar: bool = False
    macros: list[str] = field(default_factory=list)
    # 터미널 입력은 입력 언어(한글)와 무관하게 영문으로. 검색창·대화상자는 그대로 한글 입력.
    # 기본 켜짐: 펌웨어 CLI 명령은 영문이라, 한글로 쓰다 터미널에 올 때마다 한/영을 바꾸는 게 불편했다
    ascii_input: bool = True
    # 로그 저장 창의 마지막 폴더와 타임스탬프 선택
    log_dir: str = ""
    log_timestamps: bool = True
    # 포트별로 help 출력에서 배운 명령 목록 (Tab 자동완성)
    commands: dict[str, list[str]] = field(default_factory=dict)

    def port_settings(self) -> PortSettings:
        return PortSettings(
            self.port, self.baud, self.bytesize, self.parity, self.stopbits, self.flow,
            enter=self.enter, backspace=self.backspace, rx_lf=self.rx_lf,
        )


def config_dir() -> Path:
    env = os.environ.get("BARAM_TERM_CONFIG_DIR")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / APP_NAME


def default_path() -> Path:
    return config_dir() / "settings.json"


def _valid(default: object, value: object) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, (int, float)):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        return isinstance(value, list) and all(isinstance(v, str) for v in value)
    if isinstance(default, dict):
        return isinstance(value, dict) and all(
            isinstance(k, str) and isinstance(v, list) and all(isinstance(c, str) for c in v) for k, v in value.items()
        )
    return False


def load(path: Path | str) -> tuple[Settings, str | None]:
    """(설정, 오류 메시지). 파일이 없으면 오류 없이 기본값."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings(), None
    except (OSError, ValueError) as e:
        return Settings(), str(e)
    if not isinstance(raw, dict):
        return Settings(), "settings file is not a JSON object"

    defaults = Settings()
    values = {}
    for f in fields(Settings):
        if f.name not in raw:
            continue
        default = getattr(defaults, f.name)
        value = raw[f.name]
        if not _valid(default, value):
            continue
        if isinstance(default, (int, float)) and not isinstance(default, bool):
            value = type(default)(value)
        values[f.name] = value
    return Settings(**values), None


def save(settings: Settings, path: Path | str) -> None:
    """임시 파일에 쓰고 바꿔 끼운다: 저장 중에 꺼져도 기존 파일이 깨지지 않는다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"version": FORMAT_VERSION, **asdict(settings)}
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
