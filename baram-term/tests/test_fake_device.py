"""가짜 펌웨어가 공개 펌웨어 cli.c 와 같은 바이트를 보내는지 확인한다."""

from retroui import TerminalScreen

from baram_term.fake_device import PROMPT, FakeCliDevice


def drain(dev):
    out = b""
    while dev.in_waiting:
        out += dev.read(dev.in_waiting)
    return out


def send(dev, data):
    dev.write(data)
    return drain(dev)


def test_line_editing_bytes_match_firmware():
    dev = FakeCliDevice(log_interval=0, boot=False)
    assert send(dev, b"\r") == b"\n\rcli# "
    assert send(dev, b"hel") == b"hel"
    assert send(dev, b"\x1b[D") == b"\x1b[D"
    assert send(dev, b"X") == b"\x1b[4hX\x1b[4l"
    assert send(dev, b"\x08") == b"\x08 \x08\x1b[1P"
    assert dev.line == "hel" and dev.cursor == 2
    assert send(dev, b"\x1b[1~") == b"\x1b[2D"
    assert send(dev, b"\x1b[4~") == b"\x1b[3C"
    send(dev, b"\x08\x08\x08")
    assert dev.line == ""


def test_commands_history_and_case_insensitive():
    dev = FakeCliDevice(log_interval=0, boot=False)
    out = send(dev, b"HeLp\r")
    assert b"---------- cmd list ---------" in out
    assert out.endswith(b"\n\r" + PROMPT.encode())
    assert send(dev, b"\x1b[A") == b"HeLp"
    assert dev.line == "HeLp"


def test_replay_into_terminal_screen():
    dev = FakeCliDevice(log_interval=0, boot=True)
    screen = TerminalScreen(80, 24)
    screen.feed(drain(dev).decode())
    for data in (b"hel", b"\x1b[D", b"X", b"\x08", b"\x1b[1~", b"\x1b[4~"):
        screen.feed(send(dev, data).decode())
    assert screen.line_text(screen.cy) == "cli# hel"
    assert screen.cx == len(PROMPT) + 3
    assert any(screen.line_text(i).startswith("[E_] canOpen()") for i in range(len(screen.lines)))


def test_periodic_log_redraws_prompt_and_line():
    now = [0.0]
    dev = FakeCliDevice(log_interval=1.0, boot=False, seed=1, clock=lambda: now[0])
    send(dev, b"\rab")
    now[0] = 1.5
    out = drain(dev).decode()
    assert "temp=" in out and out.endswith(PROMPT + "ab")


def test_closed_device_raises():
    dev = FakeCliDevice(log_interval=0, boot=False)
    dev.close()
    try:
        dev.read(1)
    except OSError:
        pass
    else:
        raise AssertionError("read on closed device must raise")
