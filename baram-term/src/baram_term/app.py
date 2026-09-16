"""baram-term main window."""

from __future__ import annotations

import codecs
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from retroui import (
    App,
    Button,
    CheckBox,
    ComboBox,
    EditableComboBox,
    Dialog,
    FileDialog,
    GroupBox,
    HSplit,
    HexView,
    HBox,
    Label,
    LineEdit,
    Link,
    ListPopup,
    LivePlot,
    PlotLegend,
    VSplit,
    Menu,
    MenuBar,
    MenuItem,
    Mod,
    Spacer,
    Terminal,
    VBox,
    message_box,
)
from retroui.core.wcwidth import str_width
from retroui.widgets.lineedit import clipboard_put
from retroui.input.events import IS_MAC, Key, KeyEvent

from baram_term import __version__
from baram_term.completion import Completer, at_prompt
from baram_term.outgoing import outgoing_bytes
from baram_term.hexinfo import as_hex, describe
from baram_term.highlight import default_rules
from baram_term.icon import make_icon
from baram_term.i18n import language, tr
from baram_term.logger import LineCleaner, SessionLog, default_log_dir, log_filename
from baram_term.plotdata import parse_line, plot_format
from baram_term.plotfilter import PlotLineFilter
from baram_term.logo import banner
from baram_term.macros import SLOTS as MACRO_SLOTS, MacroBar, free_keys, join_entry, split_entry
from baram_term.search import SearchBar
from baram_term.serial_port import DEMO_PORT, PortSettings, SerialPort, list_ports, open_device
from baram_term import settings as config_store
from baram_term.settings import Settings

BAUD_RATES = ("9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600", "1000000", "2000000")
BYTESIZES = ("8", "7", "6", "5")
PARITIES = ("N", "E", "O", "M", "S")
STOPBITS = ("1", "1.5", "2")
FLOWS = ("none", "rtscts", "xonxoff")
ENTER_CODES = {"cr": b"\r", "lf": b"\n", "crlf": b"\r\n"}
BACKSPACE_CODES = {"bs": b"\x08", "del": b"\x7f"}
RX_LF_MODES = ("crlf", "lf")
REPO_URL = "https://github.com/chcbaram/baram-term"
# 언어 이름은 각 언어로 적는다: 화면이 어느 언어여도 자기 언어를 찾을 수 있게
LANGUAGE_NAMES = {"ko": "한국어", "en": "English"}


def _baud_text_ok(text: str) -> bool:
    """속도 입력칸: 숫자만 (지우는 중인 빈 칸은 허용)."""
    return text == "" or (text.isdigit() and len(text) <= 8)


def _parse_baud(text: str) -> int | None:
    text = text.strip()
    return int(text) if text.isdigit() and int(text) > 0 else None


PLOT_WINDOWS = ("1", "5", "10", "30", "60", "300")
PLOT_WINDOW_MAX_S = 3600.0


def _seconds_text_ok(text: str) -> bool:
    return re.fullmatch(r"\d{0,5}(\.\d{0,3})?", text) is not None


def _parse_seconds(text: str) -> float | None:
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if 0 < value <= PLOT_WINDOW_MAX_S else None


def _format_seconds(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


# 복사/붙여넣기 단축키: macOS 는 Cmd, 그 외는 Ctrl+Shift (Ctrl+C/V 는 장치로 보내는 제어 문자라서)
COPY_KEYS, PASTE_KEYS, SELECT_ALL_KEYS = (
    ("Primary+C", "Primary+V", "Primary+A") if IS_MAC else ("Ctrl+Shift+C", "Ctrl+Shift+V", "Ctrl+Shift+A")
)
# 창 가장자리 여백 (point). 메뉴/테두리/상태줄이 창에 딱 붙으면 답답해 보인다
WINDOW_PADDING = 8
# TX/RX 표시등을 켜 두는 시간. 상태줄 갱신 주기(100ms)보다 길어야 짧은 전송도 보인다
_LED_HOLD_S = 0.15
_NOT_CONNECTED_NOTICE_S = 2.0


def _human_rate(bps: float) -> str:
    if bps >= 1024 * 1024:
        return f"{bps / 1024 / 1024:.1f}MB/s"
    if bps >= 1024:
        return f"{bps / 1024:.1f}kB/s"
    return f"{bps:.0f}B/s"


class BaramTerm:
    def __init__(
        self,
        settings: PortSettings,
        *,
        theme: str = "mono",
        font_size: int = 14,
        size: tuple[int, int] = (100, 32),
        headless: bool = False,
        opener: Callable[[PortSettings], Any] = open_device,
        config: Settings | None = None,
        config_path: Path | None = None,
    ):
        self.settings = settings
        # config_path 가 없으면 설정을 파일에 쓰지 않는다 (테스트, 일회성 실행)
        self.config = config if config is not None else Settings()
        self.config_path = config_path
        self._save_error_shown = False
        self.app = App(
            title="baram-term",
            size=size,
            theme=theme,
            font_size=font_size,
            headless=headless,
            padding=WINDOW_PADDING,
            icon=make_icon(),
        )
        self.port = SerialPort(
            notify=lambda: self.app.call_soon(self._on_rx),
            on_error=lambda msg: self.app.call_soon(self._on_port_error, msg),
            opener=opener,
        )
        self.decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self.log: SessionLog | None = None
        self.search: SearchBar | None = None
        self.last_search = ""
        self.local_echo = self.config.local_echo
        self.guard_controls = self.config.guard_controls
        self.auto_reconnect = self.config.auto_reconnect
        self._reconnect_timer = None
        self._prefix = False
        self._last_not_connected = 0.0
        self._rate_prev = (time.monotonic(), 0, 0)
        self._rx_rate = 0.0

        self.terminal = Terminal(max_lines=5000, scrollbar=True)
        self.terminal.rules = default_rules()
        self.terminal.ascii_input = self.config.ascii_input  # set_focus 전에: IME 켜기 여부를 이 값으로 정한다
        self.terminal.send.connect(self.send)
        self._apply_line_codes()
        self.completer = Completer(self)
        self.completer.enabled = self.config.completion
        self.completer.on_learned = self._on_commands_learned
        if self.config.timestamps:
            self.terminal.set_show_timestamps(True)
        # 포트 이름은 상태줄에 있어서 테두리 제목은 두지 않는다
        self.frame = GroupBox("", self.terminal, stretch=2)
        # 받은 줄의 그래프 값 (>name:value, Arduino 플로터 형식). 가로축은 받은 시각(초), 폭은 plot_window 초
        self.plot = LivePlot(window=self.config.plot_window, update_hz=30, header=False)
        self.plot.focusable = False  # 그래프를 눌러도 키보드 입력은 터미널에 남는다
        # 윗줄: 왼쪽 범례(누르면 보이기/숨기기), 오른쪽 시작/정지 (Arduino IDE 플로터 배치)
        self.plot_legend = PlotLegend(self.plot)
        run_w = max(str_width(tr("plot.stop")), str_width(tr("plot.start"))) + 4  # 글자가 바뀌어도 폭 그대로
        self.plot_run_button = Button(
            tr("plot.stop"), on_click=self.toggle_plot_pause, style="solid", color="error", min_size=(run_w, 1)
        )
        self.plot_clear_button = Button(tr("plot.clear"), on_click=self.clear_plot, style="solid", color="dim")
        # 누르는 동안 포커스(►◄ 표시)를 가져가지 않는다: 마우스용 버튼이고 입력은 터미널에 남아야 한다
        self.plot_run_button.focusable = False
        self.plot_clear_button.focusable = False
        plot_toolbar = HBox(self.plot_legend, self.plot_clear_button, self.plot_run_button, spacing=1)
        # 아랫줄 오른쪽: 시간 폭 (Arduino IDE 플로터에서 설정 칸이 아래 오른쪽에 있는 배치)
        self.plot_window_combo = EditableComboBox(
            PLOT_WINDOWS,
            _format_seconds(self.config.plot_window),
            validator=_seconds_text_ok,
            min_size=(8, 1),
            on_change=self._plot_window_typed,
            on_submit=self._plot_window_submitted,
        )
        self.plot_window_combo.chosen.connect(lambda _text: self.app.set_focus(self.terminal))
        plot_footer = HBox(
            Spacer(),
            Label(tr("plot.window"), fg="dim"),
            self.plot_window_combo,
            Label(tr("dialog.plot_window.unit"), fg="dim"),
            spacing=1,
        )
        self.plot_frame = GroupBox("", VBox(plot_toolbar, self.plot, plot_footer), stretch=1, visible=self.config.plot)
        # HEX 보기: 받은/보낸 바이트 그대로 (터미널 오른쪽). 줄바꿈 코드나 안 보이는 제어 문자를 확인할 때
        self.hex_view = HexView(max_rows=5000)
        hex_run_w = max(str_width(tr("hex.stop")), str_width(tr("hex.start"))) + 4
        self.hex_run_button = Button(
            tr("hex.stop"), on_click=self.toggle_hex_pause, style="solid", color="error", min_size=(hex_run_w, 1)
        )
        self.hex_clear_button = Button(tr("hex.clear"), on_click=self.clear_hex, style="solid", color="dim")
        self.hex_run_button.focusable = False
        self.hex_clear_button.focusable = False
        hex_toolbar = HBox(
            Label(tr("hex.title"), fg="accent", bold=True), Spacer(), self.hex_clear_button, self.hex_run_button, spacing=1
        )
        # 고른 바이트 설명 줄 (없으면 빈 줄로 둔다: 줄이 생겼다 없어지면 내용이 밀린다)
        self.hex_info = Label("", fg="dim")
        self.hex_copy_button = Button(tr("hex.copy"), on_click=self.copy_hex_selection, style="solid", color="dim", enabled=False)
        self.hex_copy_button.focusable = False
        self.hex_view.selection_changed.connect(self._on_hex_selection)
        hex_footer = HBox(self.hex_info, Spacer(), self.hex_copy_button, spacing=1)
        self.hex_frame = GroupBox("", VBox(hex_toolbar, self.hex_view, hex_footer), stretch=1, visible=self.config.hex)
        # 터미널과 HEX 를 좌우로 나눈다 (경계를 끌어 폭 조절, 비율 저장)
        self.terminal_split = HSplit(
            self.frame,
            self.hex_frame,
            ratio=self.config.hex_split,
            default_ratio=Settings().hex_split,
            min_left=20,
            min_right=30,  # 오프셋 + 4바이트 + ASCII 칸이 들어가는 최소 폭
            on_change=self._on_hex_split_changed,
        )
        self._plot_lines = LineCleaner()
        # 한 세션의 그래프 형식 (>name:value 또는 Arduino). 처음 받은 줄로 정하고 지우기로 푼다:
        # 시작 직후 잘린 ">temp:34" 가 "p:34" 로 와도 새 시리즈를 만들지 않게
        self._plot_format: str | None = None
        self.plot_filter = PlotLineFilter(accept=self._plot_line_ok, expected_format=lambda: self._plot_format)
        self.plot_hide_lines = self.config.plot_hide_lines
        self._plot_series: dict[str, Any] = {}
        self.plot_clock: Callable[[], float] = time.monotonic
        self._plot_t0 = self.plot_clock()

        self.st_led = Label("○", bold=True)
        # 포트/속도는 누르면 바로 위에 목록이 열린다. 8N1 은 설정 항목이 여러 개라 포트 설정 창을 연다
        self._status_popup: ListPopup | None = None
        self.st_port = Label("", on_click=self.open_port_menu)
        self.st_baud = Label("", fg="dim", on_click=self.open_baud_menu)
        self.st_framing = Label("", fg="dim", on_click=self.open_port_dialog)
        self.st_txrx = Label("TX· RX·")
        self.st_rate = Label("", fg="dim", min_size=(9, 1))
        # 켜진 모드가 없으면 칸과 앞 구분선을 함께 숨긴다 (빈 칸 뒤에 │ 만 남지 않게)
        self.st_flags = Label("", fg="accent", visible=False)
        self.st_flags_sep = Label("│", fg="dim", visible=False)
        self.st_hint = Label(tr("status.hint"), fg="dim", align="right")

        def sep() -> Label:
            return Label("│", fg="dim")

        status = HBox(
            self.st_led, self.st_port, sep(), self.st_baud, self.st_framing, sep(), self.st_txrx, sep(), self.st_rate, self.st_flags_sep,
            self.st_flags, Spacer(), self.st_hint, spacing=1,
        )
        # 매크로 막대: 상태줄 바로 위 한 줄. 등록된 칸은 F 키로도 보낸다
        self.macro_bar = MacroBar(
            self.config.macros, on_run=self.run_macro, on_edit=self.ask_macro,
            on_menu=self.open_macro_menu, visible=self.config.macro_bar,
        )
        self.menu = self._build_menu()
        # 터미널과 그래프 사이 경계(두 테두리 줄)를 마우스로 끌어 높이를 나눈다. 더블클릭은 기본 비율로
        self.split = VSplit(
            self.terminal_split,
            self.plot_frame,
            ratio=self.config.plot_split,
            default_ratio=Settings().plot_split,
            min_top=5,
            min_bottom=8,  # 범례 줄 + 가로축 눈금 줄 + 시간 폭 줄 + 테두리를 빼고도 그래프가 보이게
            on_change=self._on_split_changed,
        )
        self.app.set_root(VBox(self.menu, self.split, self.macro_bar, status))
        self.app.set_focus(self.terminal)
        self.app.add_key_filter(self._key_filter)
        self.app.add_shortcut("Primary+=", lambda: self.zoom(+1))
        self.app.add_shortcut("Primary+-", lambda: self.zoom(-1))
        if IS_MAC:
            # Windows/Linux 의 Ctrl+F 는 장치로 보내는 제어 문자라 Ctrl-A / 만 쓴다
            self.app.add_shortcut("Primary+F", self.open_search)
        self.app.set_interval(100, self._update_status)

        self.terminal.feed(banner(__version__, self._banner_info()))
        self._update_status()

    # ---- UI construction -----------------------------------------------

    def _build_menu(self) -> MenuBar:
        self.item_echo = MenuItem(tr("menu.view.echo"), lambda: self._apply_echo(self.item_echo.checked), key="E", checked=self.local_echo)
        self.item_ts = MenuItem(tr("menu.view.timestamps"), lambda: self._apply_timestamps(self.item_ts.checked), key="N", checked=self.terminal.show_timestamps)
        self.item_complete = MenuItem(tr("menu.view.complete"), lambda: self._apply_complete(self.item_complete.checked), key="T", checked=self.completer.enabled)
        self.item_guard = MenuItem(tr("menu.view.guard"), lambda: self._apply_guard(self.item_guard.checked), key="G", checked=self.guard_controls)
        self.item_plot = MenuItem(
            tr("menu.view.plot"), lambda: self._apply_plot(self.item_plot.checked), shortcut="Ctrl-A G", key="P", checked=self.config.plot
        )
        self.item_hex = MenuItem(
            tr("menu.view.hex"), lambda: self._apply_hex(self.item_hex.checked),
            shortcut="Ctrl-A H", key="H", checked=self.config.hex,
        )
        self.item_plot_hide = MenuItem(
            tr("menu.view.plot_hide"), lambda: self._apply_plot_hide(self.item_plot_hide.checked), checked=self.plot_hide_lines
        )
        self.item_ascii = MenuItem(
            tr("menu.view.ascii_input"), lambda: self._apply_ascii_input(self.item_ascii.checked),
            key="I", checked=self.config.ascii_input,
        )
        self.item_macro = MenuItem(
            tr("menu.view.macro"), lambda: self._apply_macro_bar(self.item_macro.checked),
            shortcut="Ctrl-A M", key="M", checked=self.config.macro_bar,
        )
        self.item_reconnect = MenuItem(tr("menu.view.reconnect"), lambda: self._apply_reconnect(self.item_reconnect.checked), key="A", checked=self.auto_reconnect)
        # 체크는 "다음 실행부터 쓸 언어" (고르면 저장만 하고 화면은 다시 켤 때 바뀐다)
        chosen = self.config.lang or language()
        self.item_lang_ko = MenuItem(LANGUAGE_NAMES["ko"], lambda: self._choose_language("ko"), checked=chosen == "ko")
        self.item_lang_en = MenuItem(LANGUAGE_NAMES["en"], lambda: self._choose_language("en"), checked=chosen == "en")
        return MenuBar(
            [
                # 파일을 맨 앞에: 로그 저장·끝은 포트가 아니라 파일 메뉴에 있을 항목이고, 언어 선택도 여기에 둔다
                Menu(
                    tr("menu.file"),
                    [
                        MenuItem(tr("menu.file.log"), self.toggle_log, shortcut="Ctrl-A L", key="L"),
                        MenuItem.sep(),
                        self.item_lang_ko,
                        self.item_lang_en,
                        MenuItem.sep(),
                        MenuItem(tr("menu.file.quit"), self.quit, shortcut="Ctrl-A X", key="X"),
                    ],
                ),
                Menu(
                    tr("menu.port"),
                    [
                        MenuItem(tr("menu.port.connect"), self.connect, shortcut="Ctrl-A R", key="R"),
                        MenuItem(tr("menu.port.disconnect"), self.disconnect, shortcut="Ctrl-A D", key="D"),
                        MenuItem(tr("menu.port.settings"), self.open_port_dialog, shortcut="Ctrl-A O", key="O"),
                    ],
                ),
                Menu(
                    tr("menu.edit"),
                    [
                        MenuItem(tr("menu.edit.copy"), self.terminal.copy_selection, shortcut=COPY_KEYS),
                        MenuItem(tr("menu.edit.paste"), self.terminal.paste, shortcut=PASTE_KEYS),
                        MenuItem(tr("menu.edit.select_all"), self.terminal.select_all, shortcut=SELECT_ALL_KEYS),
                        MenuItem.sep(),
                        MenuItem(tr("menu.edit.find"), self.open_search, shortcut="Ctrl-A /", key="F"),
                    ],
                ),
                Menu(
                    tr("menu.view"),
                    [
                        self.item_echo,
                        self.item_ts,
                        self.item_complete,
                        self.item_guard,
                        self.item_reconnect,
                        self.item_macro,
                        self.item_ascii,
                        MenuItem.sep(),
                        self.item_plot,
                        self.item_plot_hide,
                        self.item_hex,
                        MenuItem(tr("menu.view.clear"), self.clear, shortcut="Ctrl-A C", key="C"),
                        MenuItem.sep(),
                        MenuItem(tr("menu.view.bigger"), lambda: self.zoom(+1), shortcut="Primary+="),
                        MenuItem(tr("menu.view.smaller"), lambda: self.zoom(-1), shortcut="Primary+-"),
                    ],
                ),
                Menu(
                    tr("menu.help"),
                    [
                        MenuItem(tr("menu.help.keys"), self.show_help, shortcut="Ctrl-A Z", key="Z"),
                        MenuItem(tr("menu.help.about"), self.show_about),
                    ],
                ),
            ]
        )

    def _banner_info(self) -> list[str]:
        if self.settings.port:
            first = tr("banner.port", port=self.settings.port, serial=self.settings.summary)
        else:
            first = tr("banner.no_port")
        return [first + " · " + time.strftime("%H:%M:%S"), tr("banner.keys")]

    # ---- actions -------------------------------------------------------

    def notice(self, text: str, error: bool = False) -> None:
        """장치로 보내지 않고 터미널에만 보여주는 안내."""
        color = "91" if error else "96"
        lead = "\r\n" if self.terminal.screen.cx else ""
        self.terminal.feed(f"{lead}\x1b[{color}m[baram-term] {text}\x1b[0m\r\n")
        if self.log is not None:
            self._log_call(self.log.note, text)

    def connect(self) -> None:
        if not self.settings.port:
            self.open_port_dialog()
            return
        self._stop_reconnect()
        if not self._open_port():
            # 보드가 아직 안 꽂혔거나 리셋 중이면 기다렸다가 붙는다
            if self.auto_reconnect:
                self._start_reconnect()
            return
        self.notice(tr("notice.connected", port=self.settings.port, serial=self.settings.summary))
        self._update_status()

    def _open_port(self, quiet: bool = False) -> bool:
        try:
            self.port.open(self.settings)
        except Exception as e:
            if not quiet:
                self.notice(tr("notice.open_failed", port=self.settings.port, error=e), error=True)
            self._update_status()
            return False
        self.decoder.reset()
        self._load_commands()
        self._save()
        return True

    # 재연결 시도 주기. USB CDC 장치가 리셋 후 다시 나타나는 데 보통 1초 안팎이 걸린다
    RECONNECT_INTERVAL_MS = 1000

    def _start_reconnect(self) -> None:
        if self._reconnect_timer is not None:
            return
        self.notice(tr("notice.reconnecting", port=self.settings.port))
        self._reconnect_timer = self.app.set_interval(self.RECONNECT_INTERVAL_MS, self._try_reconnect)
        self._update_status()

    def _stop_reconnect(self) -> None:
        if self._reconnect_timer is not None:
            self._reconnect_timer.stop()
            self._reconnect_timer = None
            self._update_status()

    def _try_reconnect(self) -> None:
        if self.port.is_open or not self.settings.port:
            self._stop_reconnect()
            return
        if self._open_port(quiet=True):
            self._stop_reconnect()
            self.notice(tr("notice.reconnected", port=self.settings.port, serial=self.settings.summary))
            self._update_status()

    def disconnect(self) -> None:
        self._stop_reconnect()
        if self.port.is_open:
            self.completer.close()
            self.port.close()
            self.notice(tr("notice.disconnected"))
        self._update_status()

    def send(self, data: bytes, raw: bool = False) -> None:
        """장치로 보낸다. raw=False 면 프롬프트 줄에서 펌웨어가 줄에 넣어 버리는 제어 문자를 거른다 (outgoing.py)."""
        if not raw:
            data = outgoing_bytes(data, at_prompt=at_prompt(self.terminal), guard=self.guard_controls)
            if not data:
                return
        if not self.port.is_open:
            now = time.monotonic()
            if now - self._last_not_connected > _NOT_CONNECTED_NOTICE_S:
                self._last_not_connected = now
                self.notice(tr("notice.not_connected"), error=True)
            return
        self.port.write(data)
        if self.hex_frame.visible:
            self.hex_view.append(data, "tx")
        if self.local_echo:
            self.terminal.feed(data.decode("utf-8", errors="replace").replace("\r", "\r\n"))

    def clear(self) -> None:
        self.completer.close()
        self.terminal.clear()

    def _apply_guard(self, on: bool) -> None:
        self.item_guard.checked = on
        self.guard_controls = on
        self._save()

    def _apply_complete(self, on: bool) -> None:
        self.item_complete.checked = on
        self.completer.enabled = on
        self._save()
        if not on:
            self.completer.close()

    def zoom(self, delta: int) -> None:
        self.app.set_font_size(max(8, min(40, self.app.fonts.size + delta)))
        self._save()

    def quit(self) -> None:
        self.stop_log(notify=False)
        self._stop_reconnect()
        self._save()
        self.port.close()
        self.app.quit()

    # ---- plot ----------------------------------------------------------

    # 시리즈마다 보관하는 샘플 수: 1kHz 로 10초를 받아도 폭 안의 점이 잘리지 않게
    PLOT_CAPACITY = 16384
    # 이름이 계속 바뀌는 데이터(카운터를 이름에 넣는 등)가 와도 범례와 색이 끝없이 늘지 않게
    PLOT_MAX_SERIES = 12

    # ---- 매크로 막대 ----------------------------------------------------

    def _choose_language(self, lang: str) -> None:
        """화면 언어를 고른다. 메뉴와 라벨은 만들 때 번역되므로 저장만 하고 다음 실행부터 적용한다.

        (바로 바꾸려면 스크롤백·연결·그래프 상태를 옮겨 담아 화면을 다시 만들어야 해서 하지 않았다)
        """
        # 체크 항목은 누를 때 먼저 뒤집히므로 둘 다 직접 맞춘다: 이미 고른 쪽을 다시 눌러도 꺼지지 않게
        self.item_lang_ko.checked = lang == "ko"
        self.item_lang_en.checked = lang == "en"
        changed = lang != (self.config.lang or language())
        self.config.lang = lang
        self._save()
        if changed and lang != language():
            self.notice(tr("notice.lang_next_start", name=LANGUAGE_NAMES[lang]))

    def _apply_ascii_input(self, on: bool) -> None:
        """터미널 입력을 입력 언어와 무관하게 영문으로 (미국 배열 물리 키 기준). 한글로 쓰다 와도 바로 명령을 친다."""
        self.item_ascii.checked = on
        self.terminal.ascii_input = on
        self.app.refresh_text_input()  # 포커스가 터미널에 그대로 있어도 IME 를 바로 끄고 켠다
        self._save()

    def _apply_macro_bar(self, on: bool) -> None:
        self.item_macro.checked = on
        self.macro_bar.visible = on
        self._save()

    def run_macro(self, index: int) -> None:
        """등록된 명령을 줄끝 코드와 함께 보낸다 (터미널에 직접 친 것과 같게)."""
        if index >= len(self.macro_bar.macros):
            self.notice(tr("notice.macro_empty", n=index + 1), error=True)
            return
        command = split_entry(self.macro_bar.macros[index])[2]
        self.send(command.encode("utf-8", "replace") + ENTER_CODES[self.settings.enter], raw=True)

    def open_macro_menu(self, index: int, x: int, y: int) -> ListPopup | None:
        """매크로 칸 오른쪽 클릭: 수정 / 지우기 중에 고른다."""
        if index >= len(self.macro_bar.macros):
            self.ask_macro(index)  # [+] 는 지울 것이 없으니 바로 등록 창
            return None
        items = [tr("macro.menu.edit"), tr("macro.menu.delete")]

        def chosen(choice: int) -> None:
            if choice == 0:
                self.ask_macro(index)
            else:
                self._set_macro(index, "")

        popup = ListPopup(items, 0, on_choose=chosen)
        popup._app = self.app
        self.app.ensure_layout()
        # 막대가 화면 맨 아래라 위로 연다 (칸 왼쪽 끝에 맞춰서)
        self.app.open_popup(popup, x, y - popup.effective_hint().pref_h)
        return popup

    def ask_macro(self, index: int) -> Dialog:
        """칸 하나의 키/이름/명령을 고친다 (목록 끝 번호면 새로 더한다). 명령을 비우면 지운다."""
        macros = self.macro_bar.macros
        adding = index >= len(macros)
        key, name, command = (None, "", "") if adding else split_entry(macros[index])
        keys = free_keys(macros, keep=key)
        if not keys:
            self.notice(tr("notice.macro_full", n=MACRO_SLOTS), error=True)
            keys = [key or 1]
        key_combo = ComboBox([f"F{k}" for k in keys], max(0, keys.index(key) if key in keys else 0))
        name_edit = LineEdit(name, min_size=(16, 1))
        cmd_edit = LineEdit(command, min_size=(28, 1))

        def done(result: int) -> None:
            if result == 2:  # 삭제
                self._set_macro(index, "")
                return
            if result != 0:
                return
            self._set_macro(index, join_entry(keys[key_combo.index], name_edit.text, cmd_edit.text))

        # 라벨 폭을 가장 긴 것에 맞춘다: 언어마다 길이가 달라서(en 은 Command/Name/Key)
        # 그냥 두면 입력칸 시작 위치가 어긋난다
        label_keys = ("dialog.macro.command", "dialog.macro.name", "dialog.macro.key")
        label_w = max(str_width(tr(k)) for k in label_keys)

        def row(label_key: str, widget) -> HBox:
            return HBox(Label(tr(label_key), min_size=(label_w, 1)), widget, spacing=1)

        dialog = Dialog(
            tr("dialog.macro.title", n=key or keys[0]),
            VBox(
                row("dialog.macro.command", cmd_edit),
                row("dialog.macro.name", name_edit),
                row("dialog.macro.key", HBox(key_combo, Spacer(), spacing=0)),
                spacing=0,
            ),
            # 새로 더하는 중이면 지울 것이 없다
            (tr("button.ok"), tr("button.cancel"))
            if adding
            else (tr("button.ok"), tr("button.cancel"), tr("dialog.macro.delete")),
            on_result=done,
        )
        dialog.open(self.app)
        self.app.set_focus(cmd_edit)
        cmd_edit.select_all()
        return dialog

    # F10 은 메뉴바 키라 매크로로 가로채지 않는다 (macros.MENU_KEY: 고를 수도 없다)
    MACRO_KEYS = (Key.F1, Key.F2, Key.F3, Key.F4, Key.F5, Key.F6, Key.F7, Key.F8, Key.F9, None, Key.F11, Key.F12)

    def _macro_slot(self, key: int) -> int | None:
        """눌린 키의 F 번호 (F1 -> 1). 매크로로 쓰지 않는 키면 None."""
        for i, k in enumerate(self.MACRO_KEYS):
            if k is not None and key == k:
                return i + 1
        return None

    def _set_macro(self, index: int, entry: str) -> None:
        """비우면 그 칸을 뺀다 (남은 매크로의 F 번호는 그대로). 목록 끝 번호면 새로 더한다.

        키가 겹치면 `normalize` 가 남는 번호로 옮긴다 (고르는 목록에서 이미 뺐으니 드문 경우다).
        """
        macros = list(self.macro_bar.macros)
        if not entry:
            if index < len(macros):
                del macros[index]
        elif index < len(macros):
            macros[index] = entry
        elif len(macros) < MACRO_SLOTS:
            macros.append(entry)
        self.macro_bar.set_macros(macros)
        self.app.set_focus(self.terminal)
        self._save()

    def _apply_plot(self, on: bool) -> None:
        self.item_plot.checked = on
        self.plot_frame.visible = on
        self._release_plot_partial()
        self._plot_lines = LineCleaner()  # 꺼져 있는 동안 받은 반쪽 줄을 이어 붙이지 않게
        self._save()

    def _plot_line_ok(self, line: str) -> bool:
        """이 줄을 그래프 값으로 받을지. 세션의 형식을 여기서 정한다."""
        if parse_line(line) is None:
            return False
        fmt = plot_format(line)
        if fmt == self._plot_format:
            return True
        if self._plot_format is None:
            self._plot_format = fmt
            return True
        if fmt == "tele":
            # Arduino 형식은 평범한 로그와 구별이 안 된다: `temp=42.0 rpm=1200`(sensor),
            # `History : 3`(status) 같은 줄이 형식을 채 가면 그 뒤 진짜 `>ax:-15` 가 전부 버려졌다.
            # `>이름:값` 은 우연히 나오지 않으니 이쪽을 믿고 갈아탄다 (잘못 잡힌 시리즈는 버린다)
            self._reset_plot_series()
            self._plot_format = fmt
            return True
        return False

    def _feed_plot(self, text: str) -> None:
        self._add_plot_lines([line for line in self._plot_lines.feed(text) if self._plot_line_ok(line)])

    def _add_plot_lines(self, lines: list[str]) -> None:
        for line in lines:
            # 한 묶음 안에서 형식이 바뀌었을 수 있다 (로그 줄이 채 간 형식을 진짜 그래프 줄이 되찾은 경우).
            # 받기로 한 형식이 아닌 앞줄은 여기서 버린다
            if plot_format(line) != self._plot_format:
                continue
            values = parse_line(line)
            if not values:
                continue
            # Teleplot 의 장치 시각은 쓰지 않는다: 형식마다 단위가 달라 받은 시각으로 통일한다
            now = self.plot_clock() - self._plot_t0
            for name, value in values:
                series = self._plot_series.get(name)
                if series is None:
                    if len(self._plot_series) >= self.PLOT_MAX_SERIES:
                        continue
                    series = self.plot.add_series(name, capacity=self.PLOT_CAPACITY)
                    self._plot_series[name] = series
                series.append(value, now)

    def _apply_plot_hide(self, on: bool) -> None:
        self.item_plot_hide.checked = on
        self.plot_hide_lines = on
        self._release_plot_partial()
        self._save()
        self._update_status()

    def _release_plot_partial(self, force: bool = True) -> None:
        """필터가 붙잡고 있던 끝 조각을 터미널로 (숨기기를 끄거나 오래 기다렸을 때)."""
        text = self.plot_filter.flush(force=force)
        if text:
            self.terminal.feed(text)

    def _on_split_changed(self, ratio: float) -> None:
        self.config.plot_split = round(ratio, 4)
        self._save()

    # ---- hex view ------------------------------------------------------

    def _apply_hex(self, on: bool) -> None:
        self.item_hex.checked = on
        self.hex_frame.visible = on
        if not on:
            self.hex_view.clear()  # 꺼 두는 동안 받은 바이트는 모으지 않으므로 오프셋이 이어지지 않는다
        self._save()
        self._update_status()

    def _on_hex_split_changed(self, ratio: float) -> None:
        self.app.ensure_layout()
        self._on_hex_selection()  # 폭이 바뀌면 설명을 다시 맞춘다
        self.config.hex_split = round(ratio, 4)
        self._save()

    def toggle_hex_pause(self) -> None:
        paused = not self.hex_view.paused
        self.hex_view.set_paused(paused)
        self.hex_run_button.set_text(tr("hex.start") if paused else tr("hex.stop"))
        self.hex_run_button.set_color("ok" if paused else "error")
        self.app.set_focus(self.terminal)

    def _on_hex_selection(self) -> None:
        data = self.hex_view.selected_bytes()
        start = self.hex_view.selection[0] if self.hex_view.selection else 0
        self.hex_info.set_text(describe(start, data, self.hex_info.rect.w or None))
        self.hex_copy_button.enabled = bool(data)

    def copy_hex_selection(self) -> None:
        data = self.hex_view.selected_bytes()
        if data:
            clipboard_put(as_hex(data))
            self.notice(tr("notice.hex_copied", count=len(data)))
        self.app.set_focus(self.terminal)

    def clear_hex(self) -> None:
        self.hex_view.clear()
        self.app.set_focus(self.terminal)

    def toggle_plot_pause(self) -> None:
        paused = not self.plot.paused
        self.plot.set_paused(paused)
        self.plot_run_button.set_text(tr("plot.start") if paused else tr("plot.stop"))
        self.plot_run_button.set_color("ok" if paused else "error")
        self.app.set_focus(self.terminal)  # 버튼을 눌러도 입력은 터미널로

    def _reset_plot_series(self) -> None:
        self.plot.clear_series()
        self._plot_series.clear()

    def clear_plot(self) -> None:
        self._reset_plot_series()
        self._plot_format = None
        self._plot_t0 = self.plot_clock()
        self.app.set_focus(self.terminal)

    def set_plot_window(self, seconds: float) -> None:
        self.plot.window = seconds
        self.plot.invalidate_pixels()
        self.config.plot_window = seconds
        # 메뉴 대화상자로 바꿨을 때 아래 칸도 맞춘다 (칸에서 입력 중인 "2." 같은 글자는 건드리지 않게 값으로 비교)
        if _parse_seconds(self.plot_window_combo.text) != seconds:
            self.plot_window_combo.set_text(_format_seconds(seconds), emit=False)
        self._save()

    def _plot_window_typed(self, text: str) -> None:
        seconds = _parse_seconds(text)
        if seconds is not None and seconds != self.plot.window:
            self.set_plot_window(seconds)

    def _plot_window_submitted(self, text: str) -> None:
        if _parse_seconds(text) is None:
            self.notice(tr("notice.bad_plot_window", text=text), error=True)
            self.plot_window_combo.set_text(_format_seconds(self.plot.window), emit=False)
        self.app.set_focus(self.terminal)

    def open_search(self) -> None:
        if self.search is not None and self.search.is_open:
            self.app.set_focus(self.search.edit)
            self.search.edit.select_all()
            return
        self.completer.close()
        self.search = SearchBar(self)
        self.search.open()

    # ---- log file ------------------------------------------------------

    def toggle_log(self) -> None:
        if self.log is not None:
            self.stop_log()
        else:
            self.open_log_dialog()

    def open_log_dialog(self) -> FileDialog:
        if self.config.log_dir:
            folder = Path(self.config.log_dir)
        else:
            folder = default_log_dir()
            try:
                folder.mkdir(parents=True, exist_ok=True)  # 처음 한 번: 문서 폴더 아래 baram-term 폴더
            except OSError:
                pass
        timestamps_box = CheckBox(tr("dialog.log.timestamps"), checked=self.config.log_timestamps)

        def on_result(path: Path | None) -> None:
            if path is not None:
                self.start_log(str(path), timestamps_box.checked)

        dialog = FileDialog(
            tr("dialog.log.title"),
            mode="save",
            directory=folder,
            filename=log_filename(self.settings.port),
            extra=timestamps_box,
            confirm_existing=tr("dialog.log.exists"),
            text={"save": tr("button.start")},  # 로그는 저장이 아니라 기록 시작
            on_result=on_result,
        )
        dialog.timestamps_box = timestamps_box
        dialog.open(self.app)
        return dialog

    def start_log(self, path: str, timestamps: bool) -> bool:
        path = path.strip()
        if not path:
            return False
        file = Path(path).expanduser()
        s = self.settings
        header = f"--- baram-term {__version__} · {s.port or '-'} {s.summary} · {time.strftime('%Y-%m-%d %H:%M:%S')}"
        self.stop_log(notify=False)
        try:
            log = SessionLog(file, timestamps=timestamps, header=header)
        except OSError as e:
            self.notice(tr("notice.log_open_failed", error=e), error=True)
            return False
        self.config.log_dir = str(file.parent)
        self.config.log_timestamps = timestamps
        self._save()
        self.log = log
        self.notice(tr("notice.log_started", path=file))
        self._update_status()
        return True

    def stop_log(self, notify: bool = True) -> None:
        log, self.log = self.log, None
        if log is None:
            return
        try:
            log.close()
        except (OSError, ValueError):
            pass
        if notify:
            self.notice(tr("notice.log_stopped", path=log.path, lines=log.lines))
            self._update_status()

    def _log_call(self, write: Callable[[str], None], text: str) -> None:
        try:
            write(text)
        except (OSError, ValueError) as e:
            # 디스크가 차거나 USB 저장장치가 빠지면 기록을 멈추고 알린다 (터미널은 계속 동작)
            log, self.log = self.log, None
            if log is not None:
                try:
                    log.close()
                except (OSError, ValueError):
                    pass
            self.notice(tr("notice.log_failed", error=e), error=True)
            self._update_status()

    def _apply_echo(self, on: bool) -> None:
        self.local_echo = on
        self.item_echo.checked = on
        self._save()
        self.notice(tr("notice.echo", state=tr("state.on" if on else "state.off")))
        self._update_status()

    def _apply_timestamps(self, on: bool) -> None:
        self.item_ts.checked = on
        self.terminal.set_show_timestamps(on)
        self._save()
        self.notice(tr("notice.timestamps", state=tr("state.on" if on else "state.off")))
        self._update_status()

    def _apply_line_codes(self) -> None:
        s = self.settings
        self.terminal.enter = ENTER_CODES.get(s.enter, b"\r")
        self.terminal.backspace = BACKSPACE_CODES.get(s.backspace, b"\x08")
        self.terminal.screen.lf_implies_cr = s.rx_lf != "lf"

    def _apply_reconnect(self, on: bool) -> None:
        self.item_reconnect.checked = on
        self.auto_reconnect = on
        if not on:
            self._stop_reconnect()
        self._save()

    def _save(self) -> None:
        c = self.config
        s = self.settings
        # demo:// 는 마지막 포트로 남기지 않는다: --demo 한 번 뒤 다음 실행이 demo 에 붙으면 헷갈린다
        if s.port and s.port != DEMO_PORT:
            c.port, c.baud, c.bytesize, c.parity, c.stopbits, c.flow = (
                s.port, s.baud, s.bytesize, s.parity, float(s.stopbits), s.flow
            )
        c.enter, c.backspace, c.rx_lf = s.enter, s.backspace, s.rx_lf
        c.plot = self.plot_frame.visible
        c.hex = self.hex_frame.visible
        c.plot_hide_lines = self.plot_hide_lines
        c.local_echo = self.local_echo
        c.timestamps = self.terminal.show_timestamps
        c.completion = self.completer.enabled
        c.guard_controls = self.guard_controls
        c.auto_reconnect = self.auto_reconnect
        c.macro_bar = self.macro_bar.visible
        c.ascii_input = self.terminal.ascii_input
        c.macros = list(self.macro_bar.macros)
        c.font_size = self.app.fonts.size
        c.cols, c.rows = self.app.cols, self.app.rows
        if self.config_path is None:
            return
        try:
            config_store.save(c, self.config_path)
        except OSError as e:
            if not self._save_error_shown:
                self._save_error_shown = True
                self.notice(tr("notice.settings_save_failed", error=e), error=True)

    def _load_commands(self) -> None:
        commands = self.config.commands.get(self.settings.port)
        if commands:
            self.completer.catalog.commands = list(commands)

    def _on_commands_learned(self, commands: list[str]) -> None:
        if self.settings.port:
            self.config.commands[self.settings.port] = list(commands)
            self._save()

    # ---- status bar quick switch ---------------------------------------

    def open_port_menu(self) -> ListPopup | None:
        return self._open_status_popup(self.st_port, self._port_choices(), self.settings.port, self.switch_port)

    def open_baud_menu(self) -> ListPopup | None:
        current = str(self.settings.baud)
        rates = sorted({*BAUD_RATES, current}, key=int)
        items = [*rates, tr("status.custom_baud")]

        def choose(item: str) -> None:
            if item in rates:
                self.switch_baud(int(item))
            else:
                self.ask_custom_baud()

        return self._open_status_popup(self.st_baud, items, current, choose)

    def _open_status_popup(
        self, anchor: Label, items: list[str], current: str, choose: Callable[[str], None]
    ) -> ListPopup | None:
        popup = self._status_popup
        if popup is not None and popup.is_open:
            popup.close()
            self._status_popup = None
            if popup.owner is anchor:
                return None  # 같은 글자를 다시 누르면 닫기만
        app = self.app
        app.ensure_layout()
        popup = ListPopup(items, items.index(current) if current in items else 0, on_choose=lambda i: choose(items[i]), visible_rows=12)
        popup.owner = anchor
        popup._app = app
        hint = popup.effective_hint()
        # 목록 글자가 상태줄 글자와 같은 열에서 시작하게 (상자 테두리 + 여백 2칸), 상태줄 바로 위에
        app.open_popup(popup, anchor.rect.x - 2, anchor.rect.y - hint.pref_h)
        self._status_popup = popup
        return popup

    def switch_port(self, port: str) -> None:
        if port == self.settings.port and self.port.is_open:
            return
        self._remember_port(port)
        self.settings = replace(self.settings, port=port)
        self._stop_reconnect()
        self.completer.close()
        self.port.close()
        self._save()
        self.connect()

    def switch_baud(self, baud: int) -> None:
        if baud <= 0 or baud == self.settings.baud:
            return
        self.settings = replace(self.settings, baud=baud)
        if self.port.is_open:
            try:
                self.port.set_baud(baud)
            except Exception:
                self.port.close()  # 열린 채 속도를 바꾸지 못하는 장치: 새 속도로 다시 연다
                self.connect()
            else:
                self.notice(tr("notice.baud_changed", port=self.settings.port, serial=self.settings.summary))
        self._save()
        self._update_status()

    def ask_custom_baud(self) -> Dialog:
        edit = LineEdit(str(self.settings.baud), validator=_baud_text_ok, min_size=(12, 1))

        def done(index: int) -> None:
            if index != 0:
                return
            baud = _parse_baud(edit.text)
            if baud is None:
                self.notice(tr("notice.bad_baud", text=edit.text), error=True)
                return
            self.switch_baud(baud)

        dialog = Dialog(
            tr("dialog.baud.title"),
            HBox(Label(tr("dialog.port.baud")), edit, spacing=1),
            (tr("button.ok"), tr("button.cancel")),
            on_result=done,
        )
        dialog.edit = edit
        dialog.open(self.app)
        self.app.set_focus(edit)
        edit.select_all()
        return dialog

    RECENT_PORTS_MAX = 8

    def _port_choices(self) -> list[str]:
        """현재 포트(목록에 없으면 맨 앞), 찾은 포트, 최근에 쓴 포트/주소, demo 순."""
        detected = list_ports()
        current = self.settings.port
        head = [current] if current and current not in detected else []
        choices: list[str] = []
        for port in (*head, *detected, *self.config.recent_ports, DEMO_PORT):
            if port and port not in choices:
                choices.append(port)
        return choices

    def _remember_port(self, port: str) -> None:
        if not port or port == DEMO_PORT:
            return
        recent = [p for p in self.config.recent_ports if p != port]
        self.config.recent_ports = [port, *recent][: self.RECENT_PORTS_MAX]

    def open_port_dialog(self) -> Dialog:
        ports = self._port_choices()
        current = self.settings.port

        def combo(items, value) -> ComboBox:
            items = list(items)
            return ComboBox(items, index=items.index(value) if value in items else 0)

        s = self.settings
        stop = str(int(s.stopbits)) if float(s.stopbits).is_integer() else str(s.stopbits)
        port_cb = combo(ports, current)
        # 목록에서 고르면 주소 칸에 채우고, 확인은 주소 칸 값으로 연결한다 (socket://, rfc2217:// 직접 입력)
        address = LineEdit(current or port_cb.text, placeholder="socket://host:port", min_size=(32, 1))
        port_cb.changed.connect(lambda _index, text: address.set_text(text))

        def refresh() -> None:
            port_cb.set_items(self._port_choices())

        # 박스 버튼은 3줄이라 한 줄짜리로: 포트 줄 높이를 늘리지 않는다
        refresh_button = Button(tr("dialog.port.refresh"), on_click=refresh, style="fill")
        # 목록에 없는 속도(250000 등)는 직접 입력한다
        baud_cb = EditableComboBox(BAUD_RATES, str(s.baud), validator=_baud_text_ok, min_size=(12, 1))
        bits_cb = combo(BYTESIZES, str(s.bytesize))
        parity_cb = combo(PARITIES, s.parity)
        stop_cb = combo(STOPBITS, stop)
        flow_cb = combo(FLOWS, s.flow)
        enter_keys, backspace_keys = tuple(ENTER_CODES), tuple(BACKSPACE_CODES)
        enter_cb = ComboBox([k.upper() for k in enter_keys], index=enter_keys.index(s.enter) if s.enter in enter_keys else 0)
        backspace_cb = ComboBox(
            ["BS (0x08)", "DEL (0x7F)"], index=backspace_keys.index(s.backspace) if s.backspace in backspace_keys else 0
        )
        rx_lf_cb = ComboBox(
            [tr("dialog.port.rx_lf.crlf"), tr("dialog.port.rx_lf.lf")],
            index=RX_LF_MODES.index(s.rx_lf) if s.rx_lf in RX_LF_MODES else 0,
        )

        def row(label_key: str, widget) -> HBox:
            return HBox(Label(tr(label_key), min_size=(12, 1)), widget, Spacer(), spacing=1)

        body = VBox(
            HBox(Label(tr("dialog.port.port"), min_size=(12, 1)), port_cb, refresh_button, Spacer(), spacing=1),
            HBox(Label(tr("dialog.port.address"), min_size=(12, 1)), address, spacing=1),
            row("dialog.port.baud", baud_cb),
            row("dialog.port.bytesize", bits_cb),
            row("dialog.port.parity", parity_cb),
            row("dialog.port.stopbits", stop_cb),
            row("dialog.port.flow", flow_cb),
            row("dialog.port.enter", enter_cb),
            row("dialog.port.backspace", backspace_cb),
            row("dialog.port.rx_lf", rx_lf_cb),
        )

        def on_result(index: int) -> None:
            if index != 0:
                return
            baud = _parse_baud(baud_cb.text)
            if baud is None:
                self.notice(tr("notice.bad_baud", text=baud_cb.text), error=True)
                return
            port = address.text.strip()
            self._remember_port(port)
            self.settings = PortSettings(
                port=port,
                baud=baud,
                bytesize=int(bits_cb.text),
                parity=parity_cb.text,
                stopbits=float(stop_cb.text),
                flow=flow_cb.text,
                enter=enter_keys[enter_cb.index],
                backspace=backspace_keys[backspace_cb.index],
                rx_lf=RX_LF_MODES[rx_lf_cb.index],
            )
            self._apply_line_codes()
            self._save()
            self.connect()

        dialog = Dialog(tr("dialog.port.title"), body, (tr("button.ok"), tr("button.cancel")), on_result=on_result)
        dialog.port_combo, dialog.address, dialog.refresh_button = port_cb, address, refresh_button
        dialog.enter_combo, dialog.backspace_combo, dialog.rx_lf_combo = enter_cb, backspace_cb, rx_lf_cb
        dialog.baud_combo = baud_cb
        dialog.open(self.app)
        return dialog

    def show_help(self) -> None:
        copy = COPY_KEYS.replace("Primary", "Cmd")
        paste = PASTE_KEYS.replace("Primary", "Cmd")
        message_box(self.app, tr("help.title"), tr("help.body", copy=copy, paste=paste), (tr("button.close"),))

    def show_about(self) -> Dialog:
        link = Link(REPO_URL)
        body = VBox(*[Label(line) for line in tr("about.body", version=__version__).split("\n")], Label(""), link)
        dialog = Dialog(tr("about.title"), body, (tr("button.close"),))
        dialog.link = link
        dialog.open(self.app)
        # 링크가 첫 포커스면 Enter 가 창을 닫지 않고 브라우저를 연다: 닫기 버튼에서 시작
        self.app.set_focus(dialog.buttons[0])
        return dialog

    # ---- events --------------------------------------------------------

    def _key_filter(self, ev: KeyEvent) -> bool:
        name = ev.name.lower()
        if self._prefix:
            if any(m in name for m in ("shift", "ctrl", "alt", "meta", "gui")) and len(name) > 1:
                return True  # 수정자 키만 누른 것은 명령으로 보지 않는다
            self._prefix = False
            self._update_status()
            if ev.key == Key.ESCAPE:
                return True
            if ev.mod & Mod.CTRL and name == "a":
                self.send(b"\x01", raw=True)  # 사용자가 명시적으로 보내는 제어 문자는 거르지 않는다
                return True
            action = {
                "o": self.open_port_dialog,
                "p": self.open_port_dialog,
                "r": self.connect,
                "d": self.disconnect,
                "e": lambda: self._apply_echo(not self.local_echo),
                "n": lambda: self._apply_timestamps(not self.terminal.show_timestamps),
                "c": self.clear,
                "x": self.quit,
                "q": self.quit,
                "z": self.show_help,
                "l": self.toggle_log,
                "/": self.open_search,
                "g": lambda: self._apply_plot(not self.plot_frame.visible),
                "h": lambda: self._apply_hex(not self.hex_frame.visible),
                "m": lambda: self._apply_macro_bar(not self.macro_bar.visible),
                "f": self.open_search,
            }.get(name)
            if action is not None:
                action()
            return True
        if ev.mod & Mod.CTRL and not ev.mod & (Mod.META | Mod.ALT) and name == "a":
            self._prefix = True
            self._update_status()
            return True
        if self.macro_bar.visible and not ev.mod:
            fkey = self._macro_slot(ev.key)
            index = None if fkey is None else self.macro_bar.index_of_key(fkey)
            if index is not None:
                self.run_macro(index)
                return True
        if self.search is not None and self.search.is_open:
            return False  # 찾기 칸에 입력 중: Tab 자동완성을 끼우지 않는다
        return self.completer.handle_key(ev)

    def _on_rx(self) -> None:
        data = self.port.take()
        if data:
            if self.hex_frame.visible:
                self.hex_view.append(data, "rx")  # 디코딩 전 바이트 그대로
            text = self.decoder.decode(data)
            if self.plot_frame.visible and self.plot_hide_lines:
                shown, plot_lines = self.plot_filter.feed(text)
                if shown:
                    self.terminal.feed(shown)
                self._add_plot_lines(plot_lines)
            else:
                self.terminal.feed(text)
                if self.plot_frame.visible:
                    self._feed_plot(text)
            if self.log is not None:
                self._log_call(self.log.feed, text)  # 로그에는 그래프 줄까지 받은 그대로
            self.completer.on_text(text)

    def _on_port_error(self, message: str) -> None:
        self.completer.close()
        self.port.close()
        self.notice(tr("notice.port_error", error=message), error=True)
        if self.auto_reconnect:
            self._start_reconnect()
        self._update_status()

    def _update_status(self) -> None:
        now = time.monotonic()
        p = self.port
        connected = p.is_open
        self.st_led.set_text("●" if connected else "○")
        led_fg = "ok" if connected else "error"
        if self.st_led.fg != led_fg:
            self.st_led.fg = led_fg
            self.st_led.invalidate()
        self.st_port.set_text(self.settings.port or tr("status.no_port"))
        self.st_baud.set_text(str(self.settings.baud))
        self.st_framing.set_text(self.settings.framing)
        tx = "●" if now - p.last_tx < _LED_HOLD_S else "·"
        rx = "●" if now - p.last_rx < _LED_HOLD_S else "·"
        self.st_txrx.set_text(f"TX{tx} RX{rx}")
        t0, rx0, _ = self._rate_prev
        if now - t0 >= 1.0:
            self._rx_rate = (p.rx_bytes - rx0) / (now - t0)
            self._rate_prev = (now, p.rx_bytes, p.tx_bytes)
        self.st_rate.set_text(_human_rate(self._rx_rate))
        flags = []
        if self._prefix:
            flags.append(tr("status.prefix"))
        if self.local_echo:
            flags.append("ECHO")
        if self.terminal.show_timestamps:
            flags.append("TS")
        if getattr(self, "log", None) is not None:
            flags.append("LOG")
        if self.plot_frame.visible and self.plot_hide_lines:
            flags.append("PLOT")
        if self.hex_frame.visible:
            flags.append("HEX")  # 그래프 줄이 터미널에서 빠지고 있다는 표시
            self._release_plot_partial(force=False)
        if getattr(self, "_reconnect_timer", None) is not None:
            flags.append(tr("status.reconnecting"))
        self.st_flags.set_text(" ".join(flags))
        self.st_flags.visible = self.st_flags_sep.visible = bool(flags)
        search = getattr(self, "search", None)
        if search is not None and search.is_open:
            search.tick()

    def run(self) -> None:
        if self.settings.port:
            self.connect()
        try:
            self.app.run()
        finally:
            self.stop_log(notify=False)
            self.port.close()
