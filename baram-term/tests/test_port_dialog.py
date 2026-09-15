import pytest
from retroui import Dialog
from retroui.input.events import Key, KeyEvent, Mod

from baram_term import app as app_module
from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.fake_device import FakeCliDevice
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


@pytest.fixture
def ports(monkeypatch):
    found = ["/dev/cu.usbmodem1"]
    monkeypatch.setattr(app_module, "list_ports", lambda: list(found))
    return found


def make(tmp_path, opened, port="", config=None):
    i18n.set_language("en")

    def opener(settings):
        opened.append(settings.port)
        return FakeCliDevice(log_interval=0)

    try:
        return BaramTerm(
            PortSettings(port=port),
            headless=True,
            size=(80, 30),
            opener=opener,
            config=config or Settings(),
            config_path=tmp_path / "settings.json",
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


def close(term):
    term.port.close()
    term.app.close()


def test_choosing_from_list_fills_address(tmp_path, ports):
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        assert dialog.port_combo.items == ["/dev/cu.usbmodem1", "demo://"]
        assert dialog.address.text == "/dev/cu.usbmodem1"
        dialog.port_combo.set_index(1)
        assert dialog.address.text == "demo://"
        assert "Address" in "\n".join(term.app.screen_text())
    finally:
        close(term)


def test_refresh_picks_up_new_ports_and_keeps_selection(tmp_path, ports):
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        dialog.port_combo.set_index(1)  # demo://
        ports.insert(0, "/dev/cu.usbmodem0")
        dialog.refresh_button.clicked.emit()
        assert dialog.port_combo.items == ["/dev/cu.usbmodem0", "/dev/cu.usbmodem1", "demo://"]
        assert dialog.port_combo.text == "demo://"
    finally:
        close(term)


def test_manual_address_connects_and_is_remembered(tmp_path, ports):
    opened = []
    term = make(tmp_path, opened)
    try:
        dialog = term.open_port_dialog()
        dialog.address.set_text("  socket://127.0.0.1:7000 ")
        term.app.set_focus(dialog.address)
        term.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))  # 주소 칸의 Enter 는 확인
        assert not term.app.popups
        assert opened == ["socket://127.0.0.1:7000"] and term.port.is_open
    finally:
        close(term)

    saved = store.load(tmp_path / "settings.json")[0]
    assert saved.port == "socket://127.0.0.1:7000"
    assert saved.recent_ports == ["socket://127.0.0.1:7000"]

    again = make(tmp_path, [], config=saved)
    try:
        dialog = again.open_port_dialog()
        assert dialog.port_combo.items == ["/dev/cu.usbmodem1", "socket://127.0.0.1:7000", "demo://"]
    finally:
        close(again)


def test_recent_ports_are_capped_and_demo_is_not_recorded(tmp_path, ports):
    term = make(tmp_path, [])
    try:
        for i in range(12):
            term._remember_port(f"socket://host:{i}")
        term._remember_port("demo://")
        term._remember_port("socket://host:5")
        recent = term.config.recent_ports
        assert len(recent) == term.RECENT_PORTS_MAX
        assert recent[0] == "socket://host:5" and recent.count("socket://host:5") == 1
        assert "demo://" not in recent
    finally:
        close(term)


def test_cancel_keeps_current_settings(tmp_path, ports):
    opened = []
    term = make(tmp_path, opened, port="/dev/cu.usbmodem1")
    try:
        dialog = term.open_port_dialog()
        dialog.address.set_text("socket://elsewhere:1")
        assert isinstance(term.app.popups[-1], Dialog)
        dialog.finish(1)
        assert term.settings.port == "/dev/cu.usbmodem1" and opened == []
    finally:
        close(term)
