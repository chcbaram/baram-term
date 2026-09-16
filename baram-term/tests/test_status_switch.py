import pytest
from retroui import Dialog, ListPopup
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent, TextEvent

from baram_term import app as app_module
from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.fake_device import FakeCliDevice
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


@pytest.fixture
def term(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "list_ports", lambda: ["/dev/cu.a"])
    i18n.set_language("en")
    opened = []

    def opener(settings):
        opened.append(settings.port)
        return FakeCliDevice(log_interval=0)

    try:
        t = BaramTerm(
            PortSettings(port="/dev/cu.a"),
            headless=True,
            size=(80, 30),
            opener=opener,
            config=Settings(),
            config_path=tmp_path / "settings.json",
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    t.opened = opened
    t.config_file = tmp_path / "settings.json"
    yield t
    t.port.close()
    t.app.close()


def click(term, widget):
    term.app.ensure_layout()
    x, y = widget.rect.x, widget.rect.y
    term.app.dispatch(MouseEvent("down", 1, x, y, 0, 0))
    term.app.dispatch(MouseEvent("up", 1, x, y, 0, 0))


def status(term):
    term.app.step()
    return term.app.screen_text()[-1]


def test_port_click_opens_list_above_and_switches(term):
    term.connect()
    click(term, term.st_port)
    popup = term._status_popup
    assert isinstance(popup, ListPopup) and popup.is_open
    assert popup.items == ["/dev/cu.a", "demo://"] and popup.selected == 0
    assert popup.rect.bottom == term.st_port.rect.y and term.app.focus is popup
    assert popup.rect.x + 2 == term.st_port.rect.x  # 목록 글자가 상태줄 글자와 같은 열에서

    popup.choose(1)
    assert term.settings.port == "demo://" and term.port.is_open
    assert term.opened == ["/dev/cu.a", "demo://"]
    assert term.app.focus is term.terminal and "demo://" in status(term)


def test_same_label_toggles_and_other_label_switches_popup(term):
    click(term, term.st_port)
    assert term._status_popup.is_open
    click(term, term.st_port)
    assert term._status_popup is None and not term.app.popups

    click(term, term.st_port)
    click(term, term.st_baud)
    popup = term._status_popup
    assert popup.owner is term.st_baud and len(term.app.popups) == 1
    assert popup.rect.x + 2 == term.st_baud.rect.x


def test_baud_change_keeps_port_open(term):
    term.connect()
    device = term.port.device
    click(term, term.st_baud)
    popup = term._status_popup
    assert popup.items[popup.selected] == "115200" and popup.items[-1] == "Custom..."
    popup.choose(popup.items.index("921600"))
    assert term.port.device is device and device.baudrate == 921600
    assert term.opened == ["/dev/cu.a"] and term.settings.baud == 921600
    assert "921600 8N1" in status(term)
    assert store.load(term.config_file)[0].baud == 921600


def test_custom_baud_from_status_bar(term):
    click(term, term.st_baud)
    term._status_popup.choose(len(term._status_popup.items) - 1)
    dialog = term.app.popups[-1]
    assert isinstance(dialog, Dialog) and term.app.focus is dialog.edit
    for ch in "250x000":
        term.app.dispatch(TextEvent(ch))  # 전체 선택된 115200 을 바꿔 쓴다, 숫자가 아닌 글자는 무시
    term.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert term.settings.baud == 250000 and "250000 8N1" in status(term)

    click(term, term.st_baud)
    assert "250000" in term._status_popup.items  # 목록에 없던 현재 속도도 보인다


def test_port_dialog_baud_goes_through_the_custom_dialog(term):
    d = term.open_port_dialog()
    assert d.baud_combo.text == "115200"

    # 속도는 목록이나 '직접 입력...' 창으로만 정한다 (콤보박스에 직접 치던 방식을 걷어냈다).
    # 빈 값은 그 창에서 걸러지고, 고르기 전 값이 그대로 남아야 한다
    d.baud_combo.set_index(len(d.baud_combo.items) - 1)
    ask = term.app.popups[-1]
    ask.edit.set_text("")
    ask.finish(0)

    assert d.baud_combo.text == "115200"  # 고르기 전 값이 남는다

    # notice() 는 상태줄이 아니라 터미널에 쓴다. 대화상자가 그 위를 덮고 있으므로 닫고 본다
    d.finish(0)
    assert term.settings.baud == 115200
    assert "invalid baud rate" in "\n".join(term.app.screen_text())

    # 목록 밖 속도는 '직접 입력...' 창으로 받는다. 받은 값은 목록에 끼워 고른 상태가 된다
    d = term.open_port_dialog()
    d.baud_combo.set_index(len(d.baud_combo.items) - 1)
    ask = term.app.popups[-1]
    ask.edit.set_text("256000")
    ask.finish(0)
    assert d.baud_combo.text == "256000"

    d.finish(0)
    assert term.settings.baud == 256000 and term.port.is_open


def test_framing_click_opens_port_dialog(term):
    click(term, term.st_framing)
    assert isinstance(term.app.popups[-1], Dialog) and hasattr(term.app.popups[-1], "baud_combo")
