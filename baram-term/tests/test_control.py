import os
import re
import shutil
import tempfile
import threading
import time

import pytest

from baram_term import app as app_module
from baram_term import ctl
from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.control import RxHistory
from baram_term.fake_device import FakeCliDevice
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


# ---- pure parts --------------------------------------------------------------


def test_clean_drops_ansi_cr_and_applies_backspace():
    assert ctl.clean("\x1b[32mok\x1b[0m\r\ncli# ") == "ok\ncli# "
    assert ctl.clean("helx\x08p\r\n") == "help\n"
    assert ctl.clean("a\x07b\tc") == "ab\tc"


def test_history_marks_survive_trimming():
    h = RxHistory(limit=10)
    h.feed("0123456789")
    assert h.end == 10
    h.feed("abcdefghijk")  # 21 > 2 * limit: 앞을 잘라낸다
    assert h.end == 21
    text, end, truncated = h.since(15)
    assert (text, end, truncated) == ("fghijk", 21, False)
    text, end, truncated = h.since(0)
    assert truncated and end == 21 and text.endswith("fghijk")


def test_history_last_lines():
    h = RxHistory()
    h.feed("a\nb\nc\ncli# ")
    assert h.last_lines(2)[0] == "c\ncli# "
    h2 = RxHistory()
    h2.feed("a\nb\nc\n")
    assert h2.last_lines(2)[0] == "b\nc\n"
    assert h2.last_lines(10)[0] == "a\nb\nc\n"


def test_history_wait_for_sees_later_data():
    h = RxHistory()
    h.feed("old cli# ")
    mark = h.end
    threading.Timer(0.05, lambda: h.feed("\x1b[1mboot\x1b[0m\r\ncli# ")).start()
    found, text, end, _ = h.wait_for(re.compile(r"^cli# ", re.M), mark, 2.0)
    assert found and "boot" in text and end == h.end
    found, text, _, _ = h.wait_for(re.compile("never"), h.end, 0.05)
    assert not found and text == ""


# ---- through the socket and the app -----------------------------------------


@pytest.fixture
def ctl_dir(monkeypatch):
    # 유닉스 소켓 경로는 100 자 남짓이 한계라 pytest 의 긴 tmp_path 대신 짧은 폴더를 쓴다
    path = tempfile.mkdtemp(prefix="btctl")
    monkeypatch.setenv("BARAM_TERM_CTL_DIR", path)
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def term(ctl_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "list_ports", lambda: ["/dev/cu.a"])
    i18n.set_language("en")
    devices = []

    def opener(settings):
        dev = FakeCliDevice(log_interval=0)
        devices.append(dev)
        return dev

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
    t.devices = devices
    yield t
    t.stop_control()
    t.port.close()
    t.app.close()


def call(term, fn, *args, timeout=5.0):
    """클라이언트는 다른 스레드에서, 이 스레드는 앱 루프를 돌린다 (실제 앱과 같은 배치)."""
    box = {}

    def run():
        try:
            box["value"] = fn(*args)
        except BaseException as e:  # noqa: BLE001
            box["error"] = e

    th = threading.Thread(target=run)
    th.start()
    deadline = time.monotonic() + timeout
    while th.is_alive() and time.monotonic() < deadline:
        term.app.step()
        time.sleep(0.005)
    th.join(0.1)
    assert not th.is_alive(), "client did not finish"
    if "error" in box:
        raise box["error"]
    return box["value"]


def only_endpoint():
    eps = ctl.endpoints()
    assert len(eps) == 1, eps
    return eps[0]


def req(term, **kw):
    return call(term, only_endpoint().request, kw, 10.0)


def settle(term, seconds=0.3):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        term.app.step()
        time.sleep(0.005)


def test_socket_is_private_and_named_by_pid(term, ctl_dir):
    assert term.start_control()
    path = only_endpoint().path
    assert path.stem == str(os.getpid())
    if os.name != "nt":
        assert oct(os.stat(path).st_mode & 0o777) == "0o600"
        assert oct(os.stat(ctl.ctl_dir()).st_mode & 0o777) == "0o700"
        assert oct(os.stat(ctl_dir).st_mode & 0o777) == "0o700"
    term.stop_control()
    assert ctl.endpoints() == []


def test_status_send_until_and_read(term):
    term.start_control()
    term.connect()
    settle(term)
    status = req(term, cmd="status")
    assert status["ok"] and status["connected"] and status["port"] == "/dev/cu.a" and status["baud"] == 115200
    assert status["control"] and status["framing"] == "8N1"
    assert status["pid"] == os.getpid() and status["title"] == "baram-term - /dev/cu.a"

    reply = req(term, cmd="send", text="info", until=r"cli# $", timeout=3)
    assert reply["ok"], reply
    assert reply["output"].startswith("info\n") and reply["output"].endswith("cli# ")
    # 보낸 명령과 응답이 터미널에도 보인다
    assert any("cli# info" in line for line in term.app.screen_text())

    again = req(term, cmd="read", since=reply["start"])
    assert again["output"] == reply["output"] and again["mark"] == reply["mark"]
    assert req(term, cmd="read", last=1)["output"] == "cli# "


def test_send_timeout_returns_partial_output(term):
    term.start_control()
    term.connect()
    settle(term)
    reply = req(term, cmd="send", text="info", until="NEVER-PRINTED", timeout=0.3)
    assert not reply["ok"] and reply["error"] == "timeout" and "info" in reply["output"]


def test_wait_since_mark_catches_output_sent_before_waiting(term):
    term.start_control()
    term.connect()
    settle(term)
    mark = req(term, cmd="status")["mark"]
    req(term, cmd="send", text="help")
    settle(term)
    reply = req(term, cmd="wait", until="cmd list", since=mark, timeout=1)
    assert reply["ok"], reply


def test_bad_requests_do_not_send(term):
    term.start_control()
    term.connect()
    settle(term)
    sent = term.port.tx_bytes
    assert req(term, cmd="send", text="info", until="(")["error"] == "bad_regex"
    assert req(term, cmd="nope")["error"] == "bad_request"
    settle(term, 0.1)
    assert term.port.tx_bytes == sent


def test_release_and_resume(term):
    term.start_control()
    term.connect()
    settle(term)
    reply = req(term, cmd="release")
    assert reply["ok"] and not reply["connected"] and reply["released"]
    assert not term.port.is_open
    assert req(term, cmd="send", text="info")["error"] == "released"
    term._try_reconnect()  # 놓은 동안에는 자동 재연결도 하지 않는다
    assert not term.port.is_open
    reply = req(term, cmd="resume")
    assert reply["ok"] and reply["connected"] and not reply["released"]
    assert req(term, cmd="send", text="info", until=r"cli# $", timeout=3)["ok"]


def test_send_when_disconnected(term):
    term.start_control()
    reply = req(term, cmd="send", text="info")
    assert not reply["ok"] and reply["error"] == "not_connected"


def test_status_bar_shows_ctl_while_active(term):
    term.start_control()
    req(term, cmd="status")
    settle(term, 0.2)
    assert "CTL" in term.app.screen_text()[-1]


def test_menu_toggle_saves_and_stops(term):
    term.start_control()
    term.item_control.checked = False
    term._apply_control(False)
    assert not term.control.running and term.config.control is False
    assert ctl.endpoints() == []


def run_cli(apps, argv, capsys):
    """ctl.main 을 다른 스레드에서 돌리고, 이 스레드는 창들의 루프를 돌린다."""
    box = {}
    th = threading.Thread(target=lambda: box.setdefault("code", ctl.main(argv)))
    th.start()
    deadline = time.monotonic() + 10
    while th.is_alive() and time.monotonic() < deadline:
        for a in apps:
            a.app.step()
        time.sleep(0.005)
    th.join(0.1)
    out = capsys.readouterr()
    return box["code"], out.out, out.err


def test_several_windows_need_a_target(term, capsys):
    term.start_control()
    term.connect()
    settle(term)
    other = BaramTerm(PortSettings(), headless=True, size=(80, 30), config=Settings())
    try:
        assert other.start_control()
        assert len(ctl.endpoints()) == 2
        apps = [term, other]

        code, out, _ = run_cli(apps, ["list"], capsys)
        assert code == 0 and "/dev/cu.a" in out and "(no port)" in out

        sent = term.port.tx_bytes
        code, _, err = run_cli(apps, ["send", "info"], capsys)
        assert code == ctl.EXIT_TARGET and "Nothing was sent" in err and "/dev/cu.a" in err
        code, _, err = run_cli(apps, ["send", "info", "--match", "nothing-like-this"], capsys)
        assert code == ctl.EXIT_TARGET and "no baram-term window matches" in err
        # 같은 프로세스라 pid 로는 둘 다 맞는다: 여러 개가 맞으면 보내지 않는다
        code, _, err = run_cli(apps, ["--pid", str(os.getpid()), "send", "info"], capsys)
        assert code == ctl.EXIT_TARGET
        settle(term, 0.1)
        assert term.port.tx_bytes == sent

        code, out, _ = run_cli(apps, ["send", "info", "--port", "/dev/cu.a", "--until", r"cli# $"], capsys)
        assert code == 0 and "Board" in out
        code, out, _ = run_cli(apps, ["--match", "CU.A", "status"], capsys)
        assert code == 0 and "port: /dev/cu.a" in out
    finally:
        other.stop_control()
        other.app.close()


@pytest.mark.skipif(os.name == "nt", reason="unix socket files")
def test_stale_socket_of_dead_process_is_removed(term, ctl_dir):
    import socket as socketlib
    import subprocess

    dead = subprocess.Popen(["true"])
    dead.wait()
    stale = ctl.endpoint_file(dead.pid)
    stale.parent.mkdir(parents=True, exist_ok=True)
    s = socketlib.socket(socketlib.AF_UNIX)
    s.bind(str(stale))
    s.close()  # 파일만 남고 듣는 쪽은 없다 (비정상 종료)
    assert stale.exists()
    assert ctl.discover() == [] and not stale.exists()

    s = socketlib.socket(socketlib.AF_UNIX)
    s.bind(str(stale))
    s.close()
    term.start_control()  # 새 창도 켜질 때 치운다
    assert not stale.exists()


def test_cli_exit_codes(term, capsys):
    assert ctl.main(["status"]) == ctl.EXIT_NOT_RUNNING
    assert "not running" in capsys.readouterr().err
    assert ctl.main(["list"]) == ctl.EXIT_NOT_RUNNING
    capsys.readouterr()
    term.start_control()
    term.connect()
    settle(term)
    code, out, err = run_cli([term], ["send", "info", "--until", r"cli# $", "--timeout", "3"], capsys)
    assert code == ctl.EXIT_OK and "info" in out and "[mark " in err
    code, out, _ = run_cli([term], ["--json", "wait", "--until", "NEVER", "--timeout", "0.2"], capsys)
    assert code == ctl.EXIT_TIMEOUT and '"error": "timeout"' in out


class FakeWindow:
    def __init__(self):
        self.title = ""
        self.calls = []

    def restore(self):
        self.calls.append("restore")

    def focus(self):
        self.calls.append("focus")


def test_raise_brings_the_window_forward(term):
    """다른 창의 워크스페이스 메뉴가 이 창을 앞으로 부탁한다 (Windows/Linux 경로)."""
    assert term._ctl_ui("raise", {}) == {"raised": False}  # 창 없는 헤드리스: 올릴 것이 없다
    term.app.window = FakeWindow()
    try:
        assert term._ctl_ui("raise", {}) == {"raised": True}
        assert term.app.window.calls == ["restore", "focus"]
    finally:
        term.app.window = None


def test_workspace_asks_the_window_by_pid_over_ctl(term):
    from baram_term import workspaces

    asked = []
    real = term._ctl_ui
    term._ctl_ui = lambda cmd, r: (asked.append(cmd) or {"raised": True}) if cmd == "raise" else real(cmd, r)
    term.start_control()
    assert call(term, workspaces._ask_to_raise, os.getpid()) is True and asked == ["raise"]
    assert call(term, workspaces._ask_to_raise, os.getpid() + 1_000_000) is False  # 그런 창은 없다
