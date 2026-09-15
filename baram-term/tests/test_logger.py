import time

from baram_term.logger import LineCleaner, SessionLog, log_filename


def clean(text):
    c = LineCleaner()
    lines = c.feed(text)
    partial = c.flush()
    return lines + ([partial] if partial is not None else [])


def test_plain_lines_and_crlf():
    assert clean("a\r\nb\n") == ["a", "b"]


def test_color_sequences_are_removed():
    assert clean("\x1b[32m[OK]\x1b[0m uartInit()\r\n") == ["[OK] uartInit()"]


def test_firmware_line_editing_is_applied():
    # 백스페이스 지우기, 줄 다시 그리기(CR + ESC[K), 커서 이동 후 끼워 넣기
    assert clean("cli# hex\b \bl\r\n") == ["cli# hel"]
    assert clean("cli# old command\r\x1b[Kcli# new\r\n") == ["cli# new"]
    assert clean("cli# hlp\x1b[2D\x1b[1@e\r\n") == ["cli# help"]
    assert clean("cli# abcd\x1b[3D\x1b[2P\r\n") == ["cli# ad"]


def test_partial_prompt_is_flushed_and_broken_escape_does_not_swallow_text():
    c = LineCleaner()
    assert c.feed("cli# ") == []
    assert c.flush() == "cli#"
    # 너무 긴 시퀀스는 버리고 이어지는 글자는 살린다
    assert clean("\x1b[" + "1" * 40 + "tail\n")[0].endswith("tail")


def test_filename_uses_time_and_port():
    now = time.mktime((2026, 9, 15, 14, 3, 12, 0, 0, -1))
    assert log_filename("/dev/cu.usbmodem1101", now) == "20260915-140312_cu.usbmodem1101.log"
    assert log_filename("socket://192.168.0.10:7000", now) == "20260915-140312_192.168.0.10_7000.log"
    assert log_filename("COM3", now) == "20260915-140312_COM3.log"
    assert log_filename("", now) == "20260915-140312_log.log"


def test_session_log_timestamps_notes_and_append(tmp_path):
    path = tmp_path / "logs" / "a.log"
    now = time.mktime((2026, 9, 15, 14, 3, 12, 0, 0, -1)) + 0.25
    log = SessionLog(path, timestamps=True, header="--- start", clock=lambda: now)
    log.feed("hello\r\ncli# ")
    log.note("disconnected")
    log.close()
    assert path.read_text().splitlines() == [
        "--- start",
        "[14:03:12.250] hello",
        "[14:03:12.250] cli#",
        "[14:03:12.250] --- disconnected",
    ]
    assert log.lines == 3 and log.closed

    again = SessionLog(path)
    again.feed("more\n")
    again.close()
    assert path.read_text().splitlines()[-1] == "more"
