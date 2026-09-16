import pytest
from retroui import Dialog
from retroui.input.events import Key, KeyEvent, Mod, MouseEvent

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


def test_refresh_works_by_mouse_without_stealing_focus(tmp_path, ports):
    """실제로 눌러 보는 경로.

    위의 새로고침 테스트는 clicked.emit() 으로 신호를 직접 쏴서, 마우스로 누르는 경로
    (hit-test -> down -> up)가 한 번도 검증되지 않았다. 버튼이 포커스를 가져가면 ►◄ 가
    붙어 눌린 것처럼 보이지도 않는다 - 이 앱의 마우스용 버튼은 모두 포커스를 받지 않는다.
    """
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        term.app.step()
        button = dialog.refresh_button
        assert button.focusable is False

        ports.insert(0, "/dev/cu.usbmodem0")
        cx, cy = button.rect.x + button.rect.w // 2, button.rect.y + button.rect.h // 2
        term.app.dispatch(MouseEvent("down", 1, cx, cy, 0, 0, Mod.NONE))
        assert term.app.focus is not button
        term.app.dispatch(MouseEvent("up", 1, cx, cy, 0, 0, Mod.NONE))
        term.app.step()

        assert dialog.port_combo.items == ["/dev/cu.usbmodem0", "/dev/cu.usbmodem1", "demo://"]
        assert "►" not in "\n".join(term.app.screen_text())
    finally:
        close(term)


def test_refresh_falls_back_to_the_first_found_port(tmp_path, ports, monkeypatch):
    """고르던 포트가 목록에서 빠지면 찾은 포트 중 첫 번째로 옮기고 주소도 맞춘다.

    없는 포트를 그대로 두면 고를 수 없는 것을 가리키고, 비워 두면 고장난 것처럼 보인다.
    """
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        assert dialog.address.text == "/dev/cu.usbmodem1"

        monkeypatch.setattr(term, "_port_choices", lambda: ["demo://"])  # 뽑혔다
        dialog.refresh_button.clicked.emit()

        assert dialog.port_combo.text == "demo://"
        assert dialog.address.text == "demo://"
    finally:
        close(term)


def test_unplugged_devices_leave_the_list_but_urls_stay(tmp_path, ports):
    """꽂혀 있지 않은 장치는 고를 수 없으니 목록에 두지 않는다.

    전에는 연결 중이던 포트와 최근 포트를 무조건 끼워 넣어서, 장치를 뽑고 새로고침해도
    목록이 그대로였다 - 새로고침이 안 먹는 것처럼 보이던 진짜 원인. 반대로 socket:// 처럼
    스캔에 잡히지 않는 주소는 최근 목록이 유일한 재사용 수단이라 남겨야 한다.
    """
    config = Settings()
    config.recent_ports = ["/dev/cu.gone", "socket://127.0.0.1:7000"]
    term = make(tmp_path, [], port="/dev/cu.gone", config=config)
    try:
        dialog = term.open_port_dialog()
        # 설정된 /dev/cu.gone 은 꽂혀 있지 않으므로 고를 수 없다
        assert dialog.port_combo.items == ["/dev/cu.usbmodem1", "socket://127.0.0.1:7000", "demo://"]

        ports.remove("/dev/cu.usbmodem1")  # 이것도 뽑았다
        dialog.refresh_button.clicked.emit()
        assert dialog.port_combo.items == ["socket://127.0.0.1:7000", "demo://"]
    finally:
        close(term)


def test_status_bar_port_menu_uses_the_same_list(tmp_path, ports):
    """상태줄 포트 메뉴도 같은 함수를 쓴다. 한쪽만 고쳐지면 안 된다."""
    config = Settings()
    config.recent_ports = ["/dev/cu.gone"]
    term = make(tmp_path, [], config=config)
    try:
        assert "/dev/cu.gone" not in term._port_choices()
        assert term._port_choices() == ["/dev/cu.usbmodem1", "demo://"]
    finally:
        close(term)


def test_list_and_address_never_disagree_on_open(tmp_path, ports):
    """설정된 포트가 뽑혀 있으면 찾은 포트 중 첫 번째로 옮긴다.

    없는 포트를 목록에서 빼고 나니, 콤보는 목록 첫 항목을 가리키는데 주소 칸에는 없는
    포트가 남아 둘이 다른 말을 했다. 어느 쪽도 거짓이 되지 않게 같은 값으로 맞춘다.
    """
    ports.insert(0, "/dev/cu.Bluetooth-Incoming-Port")
    term = make(tmp_path, [], port="/dev/cu.usbmodem104")  # 쓰던 장치를 뽑았다
    try:
        dialog = term.open_port_dialog()
        assert "/dev/cu.usbmodem104" not in dialog.port_combo.items
        assert dialog.port_combo.text == "/dev/cu.Bluetooth-Incoming-Port"
        assert dialog.address.text == dialog.port_combo.text

        dialog.port_combo.set_index(0)  # 목록에서 고르면 주소가 따라온다
        assert dialog.address.text == "/dev/cu.Bluetooth-Incoming-Port"
    finally:
        close(term)


def test_custom_baud_dialog_adds_the_value_to_the_list(tmp_path, ports):
    """'직접 입력...' 은 상태줄과 같은 창을 띄우고, 받은 값을 목록 끝에 넣어 고른 상태로 만든다."""
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        term.app.step()
        combo = dialog.baud_combo
        assert combo.items[-1] == "Custom..." and combo.text == "115200"

        # 보이라고 넣은 항목이 스크롤해야 나오면 없는 것과 같다
        combo.open()
        term.app.step()
        assert "Custom..." in "\n".join(term.app.screen_text())
        combo.close()

        combo.set_index(len(combo.items) - 1)  # 직접 입력... 을 고른다
        ask = term.app.popups[-1]
        ask.edit.set_text("250000")
        ask.finish(0)

        # 끝에 붙이지 않고 다른 속도와 같이 숫자 순으로 낀다 (상태줄 속도 메뉴와 같은 방식)
        assert combo.items.index("250000") == combo.items.index("230400") + 1
        assert combo.items[-1] == "Custom..."
        assert combo.text == "250000"

        dialog.finish(0)
        assert term.settings.baud == 250000
    finally:
        close(term)


def test_custom_baud_cancel_leaves_the_previous_value(tmp_path, ports):
    """창을 취소하면 고르기 전 값이 남는다 (안내 문구가 골라진 채 남으면 안 된다)."""
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        combo = dialog.baud_combo
        combo.set_index(len(combo.items) - 1)
        term.app.popups[-1].finish(1)  # 취소

        assert combo.text == "115200"
        dialog.finish(0)
        assert term.settings.baud == 115200
    finally:
        close(term)


def test_saved_custom_baud_is_kept_in_the_list(tmp_path, ports):
    """저장해 둔 250000 이 목록에 없으면 combo() 가 첫 항목(9600)으로 떨어뜨린다."""
    term = make(tmp_path, [])
    try:
        term.switch_baud(250000)
        dialog = term.open_port_dialog()
        assert "250000" in dialog.baud_combo.items
        assert dialog.baud_combo.text == "250000"
    finally:
        close(term)


def test_custom_baud_is_remembered_for_next_time(tmp_path, ports):
    """포트처럼 직접 입력한 속도도 기억한다. 표준 속도는 늘 목록에 있으니 기억하지 않는다."""
    term = make(tmp_path, [])
    try:
        dialog = term.open_port_dialog()
        combo = dialog.baud_combo
        combo.set_index(len(combo.items) - 1)  # 직접 입력...
        ask = term.app.popups[-1]
        ask.edit.set_text("250000")
        ask.finish(0)
        dialog.finish(0)
        assert term.config.recent_bauds == ["250000"]

        term.switch_baud(115200)  # 표준 속도로 되돌려도 기억은 남는다
        assert term.config.recent_bauds == ["250000"]

        again = term.open_port_dialog()
        assert "250000" in again.baud_combo.items  # 다음에 열어도 고를 수 있다
        assert again.baud_combo.text == "115200"
    finally:
        close(term)


def test_remembered_bauds_are_capped_newest_first(tmp_path, ports):
    term = make(tmp_path, [])
    try:
        for i in range(12):
            term._remember_baud(250000 + i)
        recent = term.config.recent_bauds
        assert len(recent) == term.RECENT_BAUDS_MAX
        assert recent[0] == "250011"  # 최근 것이 앞

        term._remember_baud(115200)  # 표준 속도는 들어가지 않는다
        assert "115200" not in term.config.recent_bauds
    finally:
        close(term)


def test_status_bar_baud_menu_shows_remembered_rates(tmp_path, ports):
    """상태줄 속도 메뉴도 같은 목록을 쓴다. 한쪽만 고쳐지면 안 된다."""
    term = make(tmp_path, [])
    try:
        term._remember_baud(250000)
        popup = term.open_baud_menu()
        assert "250000" in popup.items
        assert popup.items[-1] == "Custom..."
    finally:
        close(term)
