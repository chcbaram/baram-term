"""baram-term main window."""

from __future__ import annotations

import codecs
import time
from typing import Any, Callable

from retroui import (
    App,
    ComboBox,
    Dialog,
    GroupBox,
    HBox,
    Label,
    Menu,
    MenuBar,
    MenuItem,
    Mod,
    Spacer,
    Terminal,
    VBox,
    message_box,
)
from retroui.input.events import IS_MAC, Key, KeyEvent

from baram_term import __version__
from baram_term.completion import Completer
from baram_term.highlight import default_rules
from baram_term.icon import make_icon
from baram_term.i18n import tr
from baram_term.logo import banner
from baram_term.serial_port import DEMO_PORT, PortSettings, SerialPort, list_ports, open_device

BAUD_RATES = ("9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600", "1000000", "2000000")
BYTESIZES = ("8", "7", "6", "5")
PARITIES = ("N", "E", "O", "M", "S")
STOPBITS = ("1", "1.5", "2")
FLOWS = ("none", "rtscts", "xonxoff")

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
    ):
        self.settings = settings
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
        self.local_echo = False
        self._prefix = False
        self._last_not_connected = 0.0
        self._rate_prev = (time.monotonic(), 0, 0)
        self._rx_rate = 0.0

        self.terminal = Terminal(max_lines=5000, scrollbar=True)
        self.terminal.rules = default_rules()
        self.terminal.send.connect(self.send)
        self.completer = Completer(self)
        # 포트 이름은 오른쪽에: 왼쪽에 두면 바로 위 메뉴바와 붙어 메뉴의 일부처럼 읽힌다
        self.frame = GroupBox(self._frame_title(), self.terminal, stretch=1, title_align="right")

        self.st_led = Label("○", bold=True)
        self.st_port = Label("")
        self.st_serial = Label("", fg="dim")
        self.st_txrx = Label("TX· RX·")
        self.st_rate = Label("", fg="dim", min_size=(9, 1))
        self.st_flags = Label("", fg="accent")
        self.st_hint = Label(tr("status.hint"), fg="dim", align="right")

        def sep() -> Label:
            return Label("│", fg="dim")

        status = HBox(
            self.st_led, self.st_port, sep(), self.st_serial, sep(), self.st_txrx, sep(), self.st_rate, sep(),
            self.st_flags, Spacer(), self.st_hint, spacing=1,
        )
        self.menu = self._build_menu()
        self.app.set_root(VBox(self.menu, self.frame, status))
        self.app.set_focus(self.terminal)
        self.app.add_key_filter(self._key_filter)
        self.app.add_shortcut("Primary+=", lambda: self.zoom(+1))
        self.app.add_shortcut("Primary+-", lambda: self.zoom(-1))
        self.app.set_interval(100, self._update_status)

        self.terminal.feed(banner(__version__, self._banner_info()))
        self._update_status()

    # ---- UI construction -----------------------------------------------

    def _build_menu(self) -> MenuBar:
        self.item_echo = MenuItem(tr("menu.view.echo"), lambda: self._apply_echo(self.item_echo.checked), key="E", checked=False)
        self.item_ts = MenuItem(tr("menu.view.timestamps"), lambda: self._apply_timestamps(self.item_ts.checked), key="N", checked=False)
        self.item_complete = MenuItem(tr("menu.view.complete"), lambda: self._apply_complete(self.item_complete.checked), key="T", checked=True)
        return MenuBar(
            [
                Menu(
                    tr("menu.port"),
                    [
                        MenuItem(tr("menu.port.connect"), self.connect, shortcut="Ctrl-A R", key="R"),
                        MenuItem(tr("menu.port.disconnect"), self.disconnect, shortcut="Ctrl-A D", key="D"),
                        MenuItem(tr("menu.port.settings"), self.open_port_dialog, shortcut="Ctrl-A O", key="O"),
                        MenuItem.sep(),
                        MenuItem(tr("menu.port.quit"), self.quit, shortcut="Ctrl-A X", key="X"),
                    ],
                ),
                Menu(
                    tr("menu.edit"),
                    [
                        MenuItem(tr("menu.edit.copy"), self.terminal.copy_selection, shortcut=COPY_KEYS),
                        MenuItem(tr("menu.edit.paste"), self.terminal.paste, shortcut=PASTE_KEYS),
                        MenuItem(tr("menu.edit.select_all"), self.terminal.select_all, shortcut=SELECT_ALL_KEYS),
                    ],
                ),
                Menu(
                    tr("menu.view"),
                    [
                        self.item_echo,
                        self.item_ts,
                        self.item_complete,
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

    def _frame_title(self) -> str:
        return self.settings.port or "baram-term"

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

    def connect(self) -> None:
        if not self.settings.port:
            self.open_port_dialog()
            return
        try:
            self.port.open(self.settings)
        except Exception as e:
            self.notice(tr("notice.open_failed", port=self.settings.port, error=e), error=True)
            self._update_status()
            return
        self.decoder.reset()
        self.frame.set_title(self._frame_title())
        self.notice(tr("notice.connected", port=self.settings.port, serial=self.settings.summary))
        self._update_status()

    def disconnect(self) -> None:
        if self.port.is_open:
            self.completer.close()
            self.port.close()
            self.notice(tr("notice.disconnected"))
        self._update_status()

    def send(self, data: bytes) -> None:
        if not self.port.is_open:
            now = time.monotonic()
            if now - self._last_not_connected > _NOT_CONNECTED_NOTICE_S:
                self._last_not_connected = now
                self.notice(tr("notice.not_connected"), error=True)
            return
        self.port.write(data)
        if self.local_echo:
            self.terminal.feed(data.decode("utf-8", errors="replace").replace("\r", "\r\n"))

    def clear(self) -> None:
        self.completer.close()
        self.terminal.clear()

    def _apply_complete(self, on: bool) -> None:
        self.item_complete.checked = on
        self.completer.enabled = on
        if not on:
            self.completer.close()

    def zoom(self, delta: int) -> None:
        self.app.set_font_size(max(8, min(40, self.app.fonts.size + delta)))

    def quit(self) -> None:
        self.port.close()
        self.app.quit()

    def _apply_echo(self, on: bool) -> None:
        self.local_echo = on
        self.item_echo.checked = on
        self.notice(tr("notice.echo", state=tr("state.on" if on else "state.off")))
        self._update_status()

    def _apply_timestamps(self, on: bool) -> None:
        self.item_ts.checked = on
        self.terminal.set_show_timestamps(on)
        self.notice(tr("notice.timestamps", state=tr("state.on" if on else "state.off")))
        self._update_status()

    def open_port_dialog(self) -> None:
        ports = list_ports()
        current = self.settings.port
        if current and current not in ports:
            ports.insert(0, current)
        if DEMO_PORT not in ports:
            ports.append(DEMO_PORT)

        def combo(items, value) -> ComboBox:
            items = list(items)
            return ComboBox(items, index=items.index(value) if value in items else 0)

        s = self.settings
        stop = str(int(s.stopbits)) if float(s.stopbits).is_integer() else str(s.stopbits)
        port_cb = combo(ports, current)
        baud_cb = combo(BAUD_RATES, str(s.baud))
        bits_cb = combo(BYTESIZES, str(s.bytesize))
        parity_cb = combo(PARITIES, s.parity)
        stop_cb = combo(STOPBITS, stop)
        flow_cb = combo(FLOWS, s.flow)

        def row(label_key: str, widget) -> HBox:
            return HBox(Label(tr(label_key), min_size=(12, 1)), widget, Spacer(), spacing=1)

        body = VBox(
            row("dialog.port.port", port_cb),
            row("dialog.port.baud", baud_cb),
            row("dialog.port.bytesize", bits_cb),
            row("dialog.port.parity", parity_cb),
            row("dialog.port.stopbits", stop_cb),
            row("dialog.port.flow", flow_cb),
        )

        def on_result(index: int) -> None:
            if index != 0:
                return
            self.settings = PortSettings(
                port=port_cb.text,
                baud=int(baud_cb.text),
                bytesize=int(bits_cb.text),
                parity=parity_cb.text,
                stopbits=float(stop_cb.text),
                flow=flow_cb.text,
            )
            self.connect()

        Dialog(tr("dialog.port.title"), body, (tr("button.ok"), tr("button.cancel")), on_result=on_result).open(self.app)

    def show_help(self) -> None:
        copy = COPY_KEYS.replace("Primary", "Cmd")
        paste = PASTE_KEYS.replace("Primary", "Cmd")
        message_box(self.app, tr("help.title"), tr("help.body", copy=copy, paste=paste), (tr("button.close"),))

    def show_about(self) -> None:
        message_box(self.app, tr("about.title"), tr("about.body", version=__version__), (tr("button.close"),))

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
                self.send(b"\x01")
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
            }.get(name)
            if action is not None:
                action()
            return True
        if ev.mod & Mod.CTRL and not ev.mod & (Mod.META | Mod.ALT) and name == "a":
            self._prefix = True
            self._update_status()
            return True
        return self.completer.handle_key(ev)

    def _on_rx(self) -> None:
        data = self.port.take()
        if data:
            text = self.decoder.decode(data)
            self.terminal.feed(text)
            self.completer.on_text(text)

    def _on_port_error(self, message: str) -> None:
        self.port.close()
        self.notice(tr("notice.port_error", error=message), error=True)
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
        self.st_serial.set_text(self.settings.summary)
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
        self.st_flags.set_text(" ".join(flags))

    def run(self) -> None:
        if self.settings.port:
            self.connect()
        try:
            self.app.run()
        finally:
            self.port.close()
