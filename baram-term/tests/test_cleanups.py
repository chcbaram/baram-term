import webbrowser

import pytest
from retroui import i18n as retroui_i18n
from retroui.input.events import Key, KeyEvent, Mod

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import REPO_URL, BaramTerm
from baram_term.outgoing import outgoing_bytes
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(settings=None, **kw):
    i18n.set_language("en")
    try:
        return BaramTerm(settings or PortSettings(port="demo://"), headless=True, size=(80, 30), **kw)
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt():
    term = make()
    yield term
    term.port.close()
    term.app.close()


def test_line_codes_apply_and_persist(tmp_path):
    path = tmp_path / "settings.json"
    term = make(config=Settings(), config_path=path)
    try:
        t = term.terminal
        assert (t.enter, t.backspace, t.screen.lf_implies_cr) == (b"\r", b"\x08", True)  # 기본: 공개 cli.c
        d = term.open_port_dialog()
        d.enter_combo.set_index(2)
        d.backspace_combo.set_index(1)
        d.rx_lf_combo.set_index(1)
        d.finish(0)
        assert (t.enter, t.backspace, t.screen.lf_implies_cr) == (b"\r\n", b"\x7f", False)
        assert t.key_bytes(KeyEvent(Key.RETURN, Mod.NONE, "")) == b"\r\n"
        assert t.key_bytes(KeyEvent(Key.BACKSPACE, Mod.NONE, "")) == b"\x7f"
    finally:
        term.port.close()
        term.app.close()

    saved = store.load(path)[0]
    assert (saved.enter, saved.backspace, saved.rx_lf) == ("crlf", "del", "lf")
    again = make(saved.port_settings(), config=saved, config_path=path)
    try:
        assert again.terminal.enter == b"\r\n" and not again.terminal.screen.lf_implies_cr
        d = again.open_port_dialog()
        assert d.enter_combo.text == "CRLF" and d.backspace_combo.index == 1 and d.rx_lf_combo.index == 1
    finally:
        again.port.close()
        again.app.close()


def test_lf_enter_passes_prompt_guard():
    assert outgoing_bytes(b"\n", at_prompt=True, guard=True) == b"\n"
    assert outgoing_bytes(b"\r\n", at_prompt=True, guard=True) == b"\r\n"
    assert outgoing_bytes(b"\x03", at_prompt=True, guard=True) == b""


def test_status_separator_only_when_a_mode_is_on(bt):
    bt._update_status()
    bt.app.step()
    before = bt.app.screen_text()[-1]
    assert not bt.st_flags_sep.visible
    bt._apply_echo(True)
    bt._update_status()
    bt.app.step()
    after = bt.app.screen_text()[-1]
    assert bt.st_flags_sep.visible and "│ ECHO" in after
    assert after.count("│") == before.count("│") + 1


def test_terminal_frame_has_no_port_title(bt):
    bt.connect()
    bt.app.step()
    assert bt.frame.title == ""
    assert "demo://" not in bt.app.screen_text()[1]  # 테두리 윗줄
    assert "demo://" in bt.app.screen_text()[-1]  # 포트는 상태줄에


def test_about_has_clickable_repo_link(bt, monkeypatch):
    opened = []
    monkeypatch.setattr(webbrowser, "open", lambda url, *a, **k: opened.append(url) or True)
    d = bt.show_about()
    assert bt.app.focus is d.buttons[0]
    assert d.link.url == REPO_URL and REPO_URL in "\n".join(bt.app.screen_text())
    d.link.activate()
    assert opened == [REPO_URL]
    bt.app.dispatch(KeyEvent(Key.RETURN, Mod.NONE, ""))
    assert not d.is_open


def test_language_is_shared_with_retroui():
    i18n.set_language("ko")
    assert retroui_i18n.language() == "ko"
    i18n.set_language("en")
    assert retroui_i18n.language() == "en"
