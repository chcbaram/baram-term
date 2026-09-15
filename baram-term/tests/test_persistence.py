import time

import pytest
from retroui.input.events import Key, KeyEvent, Mod, TextEvent

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.fake_device import FakeCliDevice
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(port="demo://", **kw):
    i18n.set_language("en")
    try:
        return BaramTerm(PortSettings(port=port), headless=True, size=(80, 30), **kw)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


def close(term):
    term.port.close()
    term.app.close()


def pump(term, cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        term.app.step()
        if cond():
            return True
        time.sleep(0.01)
    return False


def screen(term):
    return "\n".join(term.app.screen_text())


def cursor_line(term):
    scr = term.terminal.screen
    return scr.line_text(scr.cy)


# ---- settings -----------------------------------------------------------


def test_changes_are_saved_and_restored(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        term._apply_echo(True)
        term._apply_timestamps(True)
        term._apply_guard(False)
        term.settings = PortSettings("/dev/ttyUSB0", baud=921600)
        term.zoom(+2)
    finally:
        close(term)

    loaded, error = store.load(path)
    assert error is None
    assert loaded.local_echo and loaded.timestamps and not loaded.guard_controls
    assert loaded.font_size == 16
    assert (loaded.port, loaded.baud) == ("/dev/ttyUSB0", 921600)
    assert (loaded.cols, loaded.rows) == (80, 30)

    again = make(port=loaded.port, config=loaded, config_path=path)
    try:
        assert again.local_echo and again.item_echo.checked
        assert again.terminal.show_timestamps and again.item_ts.checked
        assert not again.guard_controls and not again.item_guard.checked
    finally:
        close(again)


def test_demo_port_is_not_saved_as_last_port(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(port="/dev/real"), config_path=path)
    try:
        term.connect()
        assert pump(term, lambda: term.port.is_open)
    finally:
        close(term)
    assert store.load(path)[0].port == "/dev/real"


def test_command_list_is_remembered_per_port(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        term.connect()
        assert pump(term, lambda: cursor_line(term) == "cli#")
        for ch in "help":
            term.app.dispatch(TextEvent(ch))
        term.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
        assert pump(term, lambda: bool(term.completer.catalog.commands))
    finally:
        close(term)
    saved = store.load(path)[0]
    assert "status" in saved.commands["demo://"]

    again = make(config=saved, config_path=path)
    try:
        again.connect()
        assert again.completer.catalog.commands == saved.commands["demo://"]  # help 없이 바로 사용
        assert pump(again, lambda: cursor_line(again) == "cli#")
        again.app.dispatch(TextEvent("s"))
        assert pump(again, lambda: cursor_line(again) == "cli# s")
        again.app.dispatch(KeyEvent(Key.TAB, Mod.NONE, ""))
        assert again.completer.is_open and again.completer.popup.items == ["sensor", "status"]
    finally:
        close(again)


# ---- auto reconnect -----------------------------------------------------


def test_reconnects_after_unplug():
    term = make()
    term.RECONNECT_INTERVAL_MS = 50
    try:
        term.connect()
        assert pump(term, lambda: cursor_line(term) == "cli#")
        term.port.device.close()  # 장치 제거 흉내
        assert pump(term, lambda: "port error" in screen(term))
        assert pump(term, lambda: term.port.is_open and "reconnected to demo://" in screen(term))
        assert term._reconnect_timer is None
    finally:
        close(term)


def test_waits_for_device_at_startup_and_manual_disconnect_stops_waiting():
    attempts = {"n": 0}

    def opener(settings):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise OSError("no such device")
        return FakeCliDevice(log_interval=0)

    term = make(port="/dev/board", opener=opener)
    term.RECONNECT_INTERVAL_MS = 30
    try:
        term.connect()
        text = screen(term)
        assert "failed to open /dev/board" in text and "waiting for /dev/board" in text
        assert "WAITING" in term.app.screen_text()[-1]
        assert pump(term, lambda: term.port.is_open)
        assert attempts["n"] == 3 and "reconnected to /dev/board" in screen(term)

        term.port.device.close()
        assert pump(term, lambda: term._reconnect_timer is not None)
        term.disconnect()  # 사용자가 끊으면 기다리지 않는다
        assert term._reconnect_timer is None
    finally:
        close(term)


def test_auto_reconnect_can_be_turned_off():
    term = make()
    term.RECONNECT_INTERVAL_MS = 30
    try:
        term._apply_reconnect(False)
        term.connect()
        assert pump(term, lambda: cursor_line(term) == "cli#")
        term.port.device.close()
        assert pump(term, lambda: "port error" in screen(term))
        time.sleep(0.2)
        term.app.step()
        assert not term.port.is_open and term._reconnect_timer is None
    finally:
        close(term)
