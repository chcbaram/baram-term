"""워크스페이스: 폴더 나누기, 잠금, 전역 값 병합, 창 메뉴와 관리 창."""

import json
import os
import sys
from pathlib import Path

import pytest

from baram_term import __main__ as entry
from baram_term import i18n, workspaces
from baram_term import settings as store
from baram_term.app import DEFAULT_WORKSPACE, BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.workspaces import Workspace


def make_ws(root, *names):
    workspaces.ensure(root)
    for name in names:
        workspaces.create(root, name)


def open_term(root, name):
    ws = Workspace(root, name)
    assert ws.acquire()
    config, _ = ws.load()
    config.workspace = name  # main() 처럼
    i18n.set_language("en")
    try:
        return BaramTerm(PortSettings(port="demo://"), headless=True, size=(100, 32), config=config, workspace=ws)
    except (FileNotFoundError, ValueError) as e:
        ws.release()
        pytest.skip(str(e))


def close_term(term):
    term.port.close()
    term.app.close()
    if term.ws is not None:
        term.ws.release()


@pytest.fixture
def bt(tmp_path):
    make_ws(tmp_path, "motor", "ble")
    term = open_term(tmp_path, "motor")
    yield term
    close_term(term)


def submenu(term):
    term.menu.menus[0].about_to_show.emit()  # 파일 메뉴를 열 때처럼
    return [(i.text or "---", i.checked) for i in term.item_workspace.submenu]


def screen(term):
    term.app.step()
    return "\n".join(term.app.screen_text())


# ---- 폴더와 설정 ------------------------------------------------------------


def test_first_run_copies_old_settings_into_default(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"port": "/dev/ttyX", "baud": 9600, "lang": "ko"}))
    (tmp_path / "notes.json").write_text("[]")
    workspaces.ensure(tmp_path)
    assert workspaces.names(tmp_path) == [DEFAULT_WORKSPACE]
    config, error = Workspace(tmp_path, DEFAULT_WORKSPACE).load()
    assert error is None and (config.port, config.baud, config.lang) == ("/dev/ttyX", 9600, "ko")
    assert (tmp_path / "workspaces" / "default" / "notes.json").exists()
    assert (tmp_path / "settings.json").exists()  # 원본은 남긴다 (예전 버전용)


def test_names_put_default_first(tmp_path):
    make_ws(tmp_path, "zeta", "Alpha")
    assert workspaces.names(tmp_path) == ["default", "Alpha", "zeta"]


def test_each_workspace_keeps_its_own_port_but_shares_the_language(tmp_path):
    make_ws(tmp_path, "motor")
    a, b = Workspace(tmp_path, "default"), Workspace(tmp_path, "motor")
    ca, _ = a.load()
    cb, _ = b.load()
    ca.port, ca.lang = "/dev/A", "ko"
    a.save(ca)
    cb.port = "/dev/B"
    b.save(cb)  # b 는 언어를 바꾸지 않았다: a 가 바꾼 ko 를 되돌리면 안 된다
    assert Workspace(tmp_path, "default").load()[0].port == "/dev/A"
    motor, _ = Workspace(tmp_path, "motor").load()
    assert motor.port == "/dev/B" and motor.lang == "ko"
    local = json.loads((tmp_path / "workspaces" / "motor" / "settings.json").read_text())
    assert "lang" not in local and "theme" not in local and "macros" in local and "rules" in local


def test_global_save_keeps_old_keys_for_older_versions(tmp_path):
    (tmp_path / "settings.json").write_text(json.dumps({"port": "/dev/old", "lang": "en"}))
    make_ws(tmp_path)
    ws = Workspace(tmp_path, "default")
    config, _ = ws.load()
    config.lang = "ko"
    ws.save(config)
    raw = json.loads((tmp_path / "settings.json").read_text())
    assert raw["lang"] == "ko" and raw["port"] == "/dev/old"


def test_lock_blocks_a_second_open_and_frees_on_release(tmp_path):
    make_ws(tmp_path)
    a, b = Workspace(tmp_path, "default"), Workspace(tmp_path, "default")
    assert a.acquire() and workspaces.in_use(tmp_path, "default")
    assert not b.acquire()
    a.release()
    assert not workspaces.in_use(tmp_path, "default") and b.acquire()
    b.release()


def test_renaming_an_open_workspace_keeps_it_locked(tmp_path):
    make_ws(tmp_path)
    ws = Workspace(tmp_path, "default")
    assert ws.acquire()
    ws.rename("bench")
    assert ws.name == "bench" and workspaces.names(tmp_path) == ["bench"]
    assert workspaces.in_use(tmp_path, "bench")
    ws.release()


def test_duplicate_does_not_copy_the_lock(tmp_path):
    make_ws(tmp_path)
    ws = Workspace(tmp_path, "default")
    assert ws.acquire()
    workspaces.duplicate(tmp_path, "default", "copy")
    assert not (tmp_path / "workspaces" / "copy" / ".lock").exists()
    assert not workspaces.in_use(tmp_path, "copy")
    ws.release()


@pytest.mark.parametrize("name, ok", [
    ("bench 2", True), ("모터보드", True), ("", False), ("a/b", False), ("a:b", False), (".hidden", False),
    ("trail.", False), (" pad", False), ("x" * 33, False), ("tab\there", False),
])
def test_name_rules(name, ok):
    assert workspaces.valid_name(name) is ok


def test_launch_command_runs_this_python_from_a_terminal(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("__CFBundleIdentifier", "com.microsoft.VSCode")  # 터미널 앱의 ID 는 우리 것이 아니다
    assert workspaces.launch_command("motor") == [sys.executable, "-m", "baram_term", "--workspace", "motor"]


def test_launch_command_uses_open_for_the_dev_bundle(monkeypatch):
    """Dock 에서 띄운 개발용 번들: open 으로 띄워야 새 창이 앞으로 나오고 Dock 에 baram-term 으로 뜬다."""
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setenv("__CFBundleIdentifier", "com.chcbaram.baram-term-dev")
    monkeypatch.setenv("BARAM_TERM_CONFIG_DIR", "/tmp/cfg")
    assert workspaces.launch_command("motor") == [
        "open", "-n", "-b", "com.chcbaram.baram-term-dev", "--env", "BARAM_TERM_CONFIG_DIR=/tmp/cfg",
        "--args", "--workspace", "motor",
    ]


def test_launch_command_reopens_the_mac_bundle(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", "/Applications/baram-term.app/Contents/MacOS/baram-term")
    monkeypatch.delenv("BARAM_TERM_CONFIG_DIR", raising=False)
    # Path 로 만든다: 이 테스트를 Windows 에서 돌리면 경로가 \ 로 바뀐다 (실제 macOS 에서는 / 그대로)
    bundle = str(Path("/Applications/baram-term.app"))
    assert workspaces.launch_command("motor") == ["open", "-n", bundle, "--args", "--workspace", "motor"]


# ---- 실행할 때 고르기 --------------------------------------------------------


def test_start_opens_the_last_workspace(tmp_path):
    make_ws(tmp_path, "motor")
    ws, _ = entry._pick_workspace(tmp_path, None, "motor")
    assert ws.name == "motor"
    ws.release()


def test_start_skips_a_workspace_open_elsewhere(tmp_path):
    make_ws(tmp_path, "motor")
    held = Workspace(tmp_path, "motor")
    assert held.acquire()
    ws, _ = entry._pick_workspace(tmp_path, None, "motor")
    assert ws.name == "default"
    other, _ = entry._pick_workspace(tmp_path, None, "motor")  # 둘 다 열려 있으면 새로 만든다
    assert other.name == "default 2"
    for w in (held, ws, other):
        w.release()


def test_start_with_a_name_creates_it_or_refuses_a_second_window(tmp_path):
    ws, _ = entry._pick_workspace(tmp_path, "bench", None)
    assert ws.name == "bench" and "bench" in workspaces.names(tmp_path)
    again, problem = entry._pick_workspace(tmp_path, "BENCH", None)  # 대소문자만 달라도 같은 것
    assert again is None and "already open" in problem
    ws.release()
    bad, problem = entry._pick_workspace(tmp_path, "a/b", None)
    assert bad is None and "a/b" in problem


# ---- 창 메뉴 -----------------------------------------------------------------


def test_menu_lists_workspaces_in_two_levels(bt):
    assert submenu(bt) == [
        ("default", False), ("ble", False), ("motor  (this window)", True),
        ("---", None), ("New workspace...", None), ("Manage...", None),
    ]
    assert not any(i.submenu for i in bt.item_workspace.submenu)  # 3단은 없다


def test_menu_marks_a_workspace_open_in_another_window(bt, tmp_path):
    other = Workspace(tmp_path, "ble")
    assert other.acquire()
    assert ("ble", True) in submenu(bt)  # 체크는 "열려 있음": 다른 창이 연 것도
    other.release()
    assert ("ble", False) in submenu(bt)  # 메뉴를 열 때마다 다시 본다


def test_clicking_another_workspace_launches_it(bt, monkeypatch):
    launched = []
    monkeypatch.setattr(workspaces, "launch", launched.append)
    submenu(bt)
    for item in bt.item_workspace.submenu[:3]:
        item.checked = not item.checked  # 메뉴가 실행 전에 뒤집는다
        item.action()
    assert launched == ["default", "ble"]
    assert [c for _, c in submenu(bt)[:3]] == [False, False, True]  # 띄운 것은 가짜라 열리지 않았다


def test_picking_another_workspace_closes_the_menu(bt, monkeypatch):
    monkeypatch.setattr(workspaces, "launch", lambda name: None)
    bt.menu.open_menu(0)
    bt.app.popups[-1].open_submenu(0)
    item = next(i for i in bt.item_workspace.submenu if i.text == "ble")
    bt.menu.activate(item)  # 체크 항목이지만 새 창이 뜨니 메뉴는 닫는다
    assert bt.menu._popup is None and not bt.app.popups


def test_title_shows_workspace_and_port(bt):
    bt._update_status()
    assert bt._window_title() == "baram-term - motor - demo://"
    bt.settings = bt.settings.__class__(port="")
    assert bt._window_title() == "baram-term - motor"


def test_clicking_a_workspace_open_elsewhere_does_not_launch(bt, monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(workspaces, "launch", launched.append)
    monkeypatch.setattr(workspaces, "bring_to_front", lambda root, name: False)  # Windows/Linux 처럼
    other = Workspace(tmp_path, "ble")
    assert other.acquire()
    bt.open_workspace("ble")
    assert launched == [] and "already open in another window" in screen(bt)
    other.release()


def test_clicking_a_workspace_open_elsewhere_brings_that_window_forward(bt, monkeypatch, tmp_path):
    launched, raised = [], []
    monkeypatch.setattr(workspaces, "launch", launched.append)
    monkeypatch.setattr(workspaces, "bring_to_front", lambda root, name: raised.append(name) or True)
    other = Workspace(tmp_path, "ble")
    assert other.acquire()
    bt.open_workspace("ble")
    assert raised == ["ble"] and launched == []
    assert "already open" not in screen(bt)  # 가져왔으면 알릴 것이 없다
    other.release()


def test_holder_pid_reads_the_lock(tmp_path):
    make_ws(tmp_path)
    ws = Workspace(tmp_path, "default")
    assert workspaces.holder_pid(tmp_path, "default") is None
    assert ws.acquire()
    assert workspaces.holder_pid(tmp_path, "default") == os.getpid()
    assert not workspaces.bring_to_front(tmp_path, "default")  # 자기 자신은 가져올 것이 없다
    ws.release()


def test_without_workspaces_the_menu_is_off():
    i18n.set_language("en")
    term = BaramTerm(PortSettings(port="demo://"), headless=True, size=(100, 32))
    try:
        assert not term.item_workspace.enabled
    finally:
        close_term(term)


def test_ampersand_is_shown_as_is(bt, tmp_path):
    workspaces.create(tmp_path, "A&B")
    assert submenu(bt)[0] == ("A&B", False) or ("A&B", False) in submenu(bt)


def test_settings_go_to_the_workspace_folder(bt, tmp_path):
    bt.local_echo = True
    bt._save()
    saved = json.loads((tmp_path / "workspaces" / "motor" / "settings.json").read_text())
    assert saved["local_echo"] is True
    assert bt.notes_path == tmp_path / "workspaces" / "motor" / "notes.json"
    assert json.loads((tmp_path / "settings.json").read_text())["workspace"] == "motor"


# ---- 새로 만들기와 관리 창 -------------------------------------------------------


def test_new_workspace_creates_it_and_opens_a_window(bt, tmp_path, monkeypatch):
    launched = []
    monkeypatch.setattr(workspaces, "launch", launched.append)
    dialog = bt.new_workspace()
    dialog.edit.set_text("bench")
    assert dialog.error.text == ""
    dialog.finish(0)
    assert "bench" in workspaces.names(tmp_path) and ("bench", False) in submenu(bt)  # 띄운 것은 가짜
    assert launched == ["bench"]  # 만들었으면 바로 연다


def test_new_workspace_rejects_a_duplicate(bt, tmp_path):
    dialog = bt.new_workspace()
    dialog.edit.set_text("Motor")
    assert "already exists" in dialog.error.text
    dialog.finish(0)
    assert workspaces.names(tmp_path) == ["default", "ble", "motor"]


def test_manage_cannot_open_or_delete_this_window(bt):
    dialog = bt.open_workspace_dialog()
    assert dialog.listing.items[dialog.listing.selected] == "motor  (this window)"
    assert not dialog.delete_button.enabled and not dialog.open_button.enabled
    assert dialog.rename_button.enabled
    dialog.listing.select(1)
    assert dialog.delete_button.enabled and dialog.open_button.enabled


def test_manage_cannot_touch_a_workspace_open_elsewhere(bt, tmp_path):
    other = Workspace(tmp_path, "ble")
    assert other.acquire()
    dialog = bt.open_workspace_dialog()
    dialog.listing.select(1)
    assert dialog.listing.items[1] == "ble  (open)"
    assert not (dialog.delete_button.enabled or dialog.rename_button.enabled or dialog.open_button.enabled)
    other.release()


def test_manage_delete_asks_first(bt, tmp_path):
    dialog = bt.open_workspace_dialog()
    dialog.listing.select(1)
    dialog.delete_button.clicked.emit()
    assert "Delete workspace 'ble'" in screen(bt)
    assert "ble" in workspaces.names(tmp_path)  # 확인 전에는 그대로
    bt.app.popups[-1].finish(0)
    assert workspaces.names(tmp_path) == ["default", "motor"]
    assert dialog.listing.items == ["default", "motor  (this window)"]


def test_renaming_this_window_moves_its_files(bt, tmp_path):
    dialog = bt.open_workspace_dialog()
    dialog.rename_button.clicked.emit()
    ask = bt.app.popups[-1]
    ask.edit.set_text("motor-v2")
    ask.finish(0)
    assert bt.workspace == "motor-v2" and "motor-v2  (this window)" in dialog.listing.items
    assert bt.notes_path == tmp_path / "workspaces" / "motor-v2" / "notes.json"
    assert workspaces.in_use(tmp_path, "motor-v2")
    bt._save()
    assert (tmp_path / "workspaces" / "motor-v2" / "settings.json").exists()
    assert not (tmp_path / "workspaces" / "motor").exists()


def test_duplicate_suggests_a_free_name(bt, tmp_path):
    dialog = bt.open_workspace_dialog()
    dialog.listing.select(0)
    dialog.copy_button.clicked.emit()
    ask = bt.app.popups[-1]
    assert ask.edit.text == "default 2"
    ask.finish(0)
    assert "default 2" in workspaces.names(tmp_path)


def test_manage_open_launches(bt, monkeypatch):
    launched = []
    monkeypatch.setattr(workspaces, "launch", launched.append)
    dialog = bt.open_workspace_dialog()
    dialog.listing.select(1)
    dialog.open_button.clicked.emit()
    assert launched == ["ble"]
