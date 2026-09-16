import time

import pytest

from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(tmp_path, **kw):
    i18n.set_language("en")
    try:
        return BaramTerm(
            PortSettings(port="demo://"),
            headless=True,
            size=(120, 36),
            config=Settings(**kw),
            config_path=tmp_path / "settings.json",
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt(tmp_path):
    term = make(tmp_path, note_wait="delay", note_delay_ms=1)
    term._apply_hex(True)
    term.app.step()
    yield term
    term.stop_note_send(quiet=True)
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


def add_note(term, text):
    dialog = term.add_note()
    dialog.edit.set_text("boot")
    dialog.finish(0)
    term.note_area.set_text(text)
    return term.notes[-1]


def device_lines(term):
    return [line for line in term.port.device.history]


def test_send_line_sends_one_line_and_moves_down(bt):
    add_note(bt, "info\nstatus")
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")

    bt.note_area.move_to(0, 0)
    bt.send_note_line()
    assert pump(bt, lambda: "info" in device_lines(bt))
    assert bt.note_area.row == 1  # 다음 줄로 내려간다


def test_send_all_skips_blanks_and_comments(bt):
    add_note(bt, "info\n\n# 설명\nstatus")
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")

    bt.send_note_block()
    assert pump(bt, lambda: device_lines(bt)[-2:] == ["info", "status"], timeout=5.0)
    assert bt.note_all_button.visible and not bt.note_stop_button.visible  # 끝나면 되돌아온다


def test_send_selection_only(bt):
    add_note(bt, "one\ntwo\nthree")
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")

    bt.note_area.move_to(1, 0)
    bt.note_area.move_to(2, 3, extend=True)  # 둘째~셋째 줄
    assert bt.note_area.selected_rows() == (1, 2)
    bt.send_note_block()
    assert pump(bt, lambda: device_lines(bt)[-2:] == ["two", "three"], timeout=5.0)
    assert "one" not in device_lines(bt)


def test_wait_line_delays_without_sending(bt):
    add_note(bt, "info\n#wait 300\nstatus")
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")

    started = time.monotonic()
    bt.send_note_block()
    assert pump(bt, lambda: device_lines(bt)[-2:] == ["info", "status"], timeout=5.0)
    assert time.monotonic() - started >= 0.3
    assert "#wait 300" not in device_lines(bt)


def test_stop_button_cancels_the_rest(bt):
    add_note(bt, "\n".join(f"cmd{i}" for i in range(20)))
    bt.connect()
    assert pump(bt, lambda: bt.terminal.screen.line_text(bt.terminal.screen.cy) == "cli#")

    bt.config.note_delay_ms = 200
    bt.send_note_block()
    assert pump(bt, lambda: "cmd0" in device_lines(bt))
    assert bt.note_stop_button.visible and not bt.note_all_button.visible
    bt.stop_note_send()
    sent = len([line for line in device_lines(bt) if line.startswith("cmd")])
    time.sleep(0.4)
    bt.app.step()
    assert len([line for line in device_lines(bt) if line.startswith("cmd")]) == sent
    assert "stopped sending" in "\n".join(bt.app.screen_text())


def test_prompt_wait_mode_sends_every_line(tmp_path):
    term = make(tmp_path, note_wait="prompt")
    try:
        term._apply_hex(True)
        add_note(term, "info\nstatus\nlog")
        term.connect()
        assert pump(term, lambda: term.terminal.screen.line_text(term.terminal.screen.cy) == "cli#")
        term.send_note_block()
        assert pump(term, lambda: device_lines(term)[-3:] == ["info", "status", "log"], timeout=6.0)
    finally:
        term.stop_note_send(quiet=True)
        term.port.close()
        term.app.close()


def test_wait_and_delay_settings_are_saved(bt, tmp_path):
    bt.note_wait_combo.set_index(0)
    bt.note_delay_combo.set_text("200")
    assert bt.config.note_wait == "prompt" and bt.config.note_delay_ms == 200
