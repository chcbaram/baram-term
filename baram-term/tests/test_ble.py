"""BLE 전송 (ble.py) 과 앱 연동. 실제 블루투스 없이 가짜 bleak 으로 돈다."""

import time
import types

import pytest

from baram_term import app as app_module
from baram_term import ble
from baram_term import i18n
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings, open_device
from baram_term.settings import Settings

NUS = ble.NUS_SERVICE
MAC = "AA:BB:CC:DD:EE:FF"
CB_UUID = "6C1F0A72-3B54-4D9E-8A11-2F7C5E90B4D3"


# ---- 주소 읽기 ---------------------------------------------------------------


def test_parse_target_tells_name_tag_and_address_apart():
    assert ble.parse_target("ble://CLI-BOARD") == ble.Target(name="CLI-BOARD")
    assert ble.parse_target("ble://CLI-BOARD#1A2B3C4D") == ble.Target(name="CLI-BOARD", tag="1a2b3c4d")
    assert ble.parse_target(f"ble://{MAC}") == ble.Target(address=MAC)
    assert ble.parse_target(f"ble://{CB_UUID}") == ble.Target(address=CB_UUID)


def test_target_matches_by_name_tag_or_address():
    found = ble.BleFound(name="CLI-BOARD", address=CB_UUID, rssi=-60, tag="1a2b3c4d")
    assert ble.Target(name="CLI-BOARD").matches(found)
    assert ble.Target(name="CLI-BOARD", tag="1a2b3c4d").matches(found)
    assert not ble.Target(name="CLI-BOARD", tag="deadbeef").matches(found)
    assert not ble.Target(name="other").matches(found)
    assert ble.Target(address=CB_UUID.lower()).matches(found)


def test_url_keeps_the_name_because_addresses_differ_per_pc():
    found = ble.BleFound(name="CLI-BOARD", address=CB_UUID, rssi=-60, tag="1a2b3c4d")
    assert found.url() == "ble://CLI-BOARD#1a2b3c4d"
    assert found.url(unique=False) == "ble://CLI-BOARD"
    assert ble.BleFound(name="", address=MAC).url() == f"ble://{MAC}"
    assert "CLI-BOARD" in found.label() and "1a2b3c4d" in found.label()
    assert ble.display_name("ble://CLI-BOARD#1a2b3c4d") == "CLI-BOARD"


# ---- 가짜 bleak --------------------------------------------------------------


class FakeAdv:
    def __init__(self, name, rssi=-50, uuids=(NUS,), manufacturer=None):
        self.local_name = name
        self.rssi = rssi
        self.service_uuids = list(uuids)
        self.manufacturer_data = manufacturer or {}


class FakeDev:
    def __init__(self, address, name=""):
        self.address = address
        self.name = name


class FakeClient:
    """NUS 를 흉내 낸다: 쓴 글자를 그대로 에코하고, 명령 줄에는 프롬프트를 붙인다."""

    instances: list["FakeClient"] = []

    def __init__(self, device, disconnected_callback=None):
        self.device = device
        self.mtu_size = 247
        self.written: list[bytes] = []
        self._handler = None
        self._on_disconnect = disconnected_callback
        self.notifying = False
        FakeClient.instances.append(self)

    async def connect(self):
        self.connected = True

    async def start_notify(self, uuid, handler):
        assert uuid == ble.NUS_TX
        self._handler = handler
        self.notifying = True
        handler(None, bytearray(b"\n\rcli# "))  # 구독을 켜면 보드가 프롬프트를 한 번 찍는다

    async def write_gatt_char(self, uuid, data, response=False):
        assert uuid == ble.NUS_RX and response is False
        self.written.append(bytes(data))
        self._handler(None, bytearray(data))

    async def disconnect(self):
        self.notifying = False
        if self._on_disconnect is not None:
            self._on_disconnect(self)

    def drop(self):
        """보드가 멀어져 끊긴 상황."""
        if self._on_disconnect is not None:
            self._on_disconnect(self)


@pytest.fixture
def fake_bleak(monkeypatch):
    devices = {
        "a": (FakeDev(CB_UUID, "CLI-BOARD"), FakeAdv("CLI-BOARD", -60, manufacturer={0xFFFF: bytes.fromhex("0102001a2b3c4d")})),
        "b": (FakeDev(MAC, "Speaker"), FakeAdv("Speaker", -80, uuids=())),
    }
    FakeClient.instances.clear()
    scanner = types.SimpleNamespace(discover=_discover(devices), find_device_by_filter=_find_one(devices))
    monkeypatch.setattr(ble, "_bleak", lambda: types.SimpleNamespace(BleakScanner=scanner, BleakClient=FakeClient))
    monkeypatch.setattr(ble, "available", lambda: True)
    return devices


def _discover(devices):
    async def discover(timeout=0.0, return_adv=True):
        return devices
    return discover


def _find_one(devices):
    """연결할 때 쓰는 쪽: 맞는 것을 보는 즉시 돌려준다 (실제 bleak 과 같게)."""
    async def find_device_by_filter(filterfunc, timeout=0.0, **kw):
        for device, adv in devices.values():
            if filterfunc(device, adv):
                return device
        return None
    return find_device_by_filter


# ---- 스캔 --------------------------------------------------------------------


def test_scan_shows_only_nus_devices_by_default(fake_bleak):
    found = ble.scan(timeout=0.1)
    assert [d.name for d in found] == ["CLI-BOARD"]
    assert found[0].tag == "1a2b3c4d" and found[0].rssi == -60
    assert [d.name for d in ble.scan(timeout=0.1, nus_only=False)] == ["CLI-BOARD", "Speaker"]


def test_scan_sorts_the_closest_first(fake_bleak):
    fake_bleak["c"] = (FakeDev("11:22:33:44:55:66", "Near"), FakeAdv("Near", -30))  # 스캔이 보는 dict 그대로
    assert [d.name for d in ble.scan(timeout=0.1)] == ["Near", "CLI-BOARD"]


# ---- 장치 --------------------------------------------------------------------


def read_all(device, seconds=0.5):
    out, end = bytearray(), time.monotonic() + seconds
    while time.monotonic() < end:
        out += device.read(device.in_waiting or 1)
    return bytes(out)


def test_device_connects_writes_and_reads(fake_bleak):
    device = ble.open_ble("ble://CLI-BOARD")
    try:
        assert device.is_open and device.mtu == 247 and device.address == CB_UUID
        assert read_all(device, 0.3) == b"\n\rcli# "  # 구독 직후의 프롬프트
        device.write(b"led info\r")
        assert read_all(device, 0.3) == b"led info\r"
        assert FakeClient.instances[-1].written == [b"led info\r"]
    finally:
        device.close()
    assert not device.is_open


def test_device_splits_writes_by_mtu(fake_bleak):
    device = ble.open_ble("ble://CLI-BOARD")
    try:
        device.mtu = 23  # 협상이 안 된 최소 MTU
        device.write(b"x" * 50)
        assert [len(w) for w in FakeClient.instances[-1].written] == [20, 20, 10]
    finally:
        device.close()


def test_disconnect_raises_so_the_app_can_reconnect(fake_bleak):
    device = ble.open_ble("ble://CLI-BOARD")
    try:
        read_all(device, 0.2)
        FakeClient.instances[-1].drop()
        with pytest.raises(OSError):
            read_all(device, 0.3)
        with pytest.raises(OSError):
            device.write(b"x")
    finally:
        device.close()


def test_unknown_device_fails_with_its_name(fake_bleak):
    with pytest.raises(OSError, match="NOT-THERE"):
        ble.open_ble("ble://NOT-THERE", scan_timeout=0.1)


def test_open_device_routes_ble(monkeypatch):
    opened = []
    monkeypatch.setattr(ble, "open_ble", lambda port, **kw: opened.append(port) or "device")
    assert open_device(PortSettings(port="ble://CLI-BOARD")) == "device"
    assert opened == ["ble://CLI-BOARD"]


def test_settings_have_no_baud_for_ble():
    assert PortSettings(port="ble://x").is_ble and PortSettings(port="ble://x").summary == "BLE"
    assert not PortSettings(port="/dev/cu.a").is_ble


# ---- 앱 ----------------------------------------------------------------------


@pytest.fixture
def term(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "list_ports", lambda: ["/dev/cu.a"])
    i18n.set_language("en")
    try:
        t = BaramTerm(
            PortSettings(port="/dev/cu.a"), headless=True, size=(90, 30),
            config=Settings(), config_path=tmp_path / "settings.json",
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    yield t
    t.port.close()
    t.app.close()


def test_menu_toggle_saves_ble(term):
    assert not term.config.ble
    term.item_ble.checked = True
    term._apply_ble(True)
    assert term.config.ble and term.item_ble.checked


def test_menu_toggle_explains_when_bleak_is_missing(term, monkeypatch):
    monkeypatch.setattr(app_module.ble_transport, "available", lambda: False)
    term.item_ble.checked = True
    term._apply_ble(True)
    assert not term.item_ble.checked and not term.config.ble
    assert any("bleak" in line for line in term.app.screen_text())


def test_port_dialog_hides_ble_until_it_is_on(term):
    dialog = term.open_port_dialog()
    assert not dialog.kind_cb.parent.visible  # 종류 줄
    dialog.close()
    term.config.ble = True
    dialog = term.open_port_dialog()
    assert dialog.kind_cb.parent.visible and dialog.kind_cb.index == 0
    dialog.close()


def test_port_dialog_scans_and_saves_a_ble_device(term, monkeypatch):
    term.config.ble = True
    found = ble.BleFound(name="CLI-BOARD", address=CB_UUID, rssi=-60, tag="1a2b3c4d")
    monkeypatch.setattr(app_module.ble_transport, "scan", lambda *a, **k: [found])
    dialog = term.open_port_dialog()
    dialog.kind_cb.set_index(1)  # 종류: BLE
    term.app.ensure_layout()
    # BLE 에는 속도·패리티가 없다: 그 줄은 숨는다
    baud_row = next(r for r in dialog.body.children if any(c is dialog.baud_combo for c in r.children))
    assert not baud_row.visible

    dialog.scan_button.click()
    deadline = time.monotonic() + 5
    while dialog.device_cb.text.startswith("(") and time.monotonic() < deadline:
        term.app.step()
        time.sleep(0.01)
    assert found.label() in dialog.device_cb.items
    assert dialog.address.text == "ble://CLI-BOARD#1a2b3c4d"

    dialog.buttons[0].click()  # 확인
    assert term.settings.port == "ble://CLI-BOARD#1a2b3c4d" and term.settings.is_ble


def test_status_bar_shows_ble_and_mtu(term):
    term.settings = PortSettings(port="ble://CLI-BOARD")
    term.port.settings = term.settings

    class Device:
        mtu = 247
        is_open = True

        def read(self, n=1):
            time.sleep(0.01)
            return b""

        def close(self):
            self.is_open = False

    term.port.device = Device()
    term._update_status()
    term.app.step()
    status = term.app.screen_text()[-1]
    assert "ble://CLI-BOARD" in status and "BLE" in status and "MTU 247" in status
    term.port.device = None


def test_ctl_status_reports_ble_instead_of_baud(term):
    term.settings = PortSettings(port="ble://CLI-BOARD")
    status = term._ctl_ui("status", {})
    assert status["kind"] == "ble" and status["baud"] is None and status["framing"] is None


def test_turning_ble_off_disconnects_and_blocks_reconnect(term, monkeypatch):
    """껐는데 저장된 ble:// 주소로 계속 붙어 있으면 끈 뜻이 없다 (다음 실행의 자동 연결도 막는다)."""
    opened = []
    monkeypatch.setattr(app_module, "open_device", lambda settings: opened.append(settings.port) or _FakeOpen())
    term.item_ble.checked = True
    term._apply_ble(True)
    term.settings = PortSettings(port="ble://CLI-BOARD")
    term.connect()  # BLE 는 다른 스레드에서 연다: 열릴 때까지 앱 루프를 돌린다
    deadline = time.monotonic() + 5
    while not term.port.is_open and time.monotonic() < deadline:
        term.app.step()
        time.sleep(0.01)
    assert term.port.is_open and opened == ["ble://CLI-BOARD"]

    term.item_ble.checked = False
    term._apply_ble(False)
    assert not term.port.is_open and not term.config.ble

    term.connect()  # 꺼져 있으면 다시 붙지 않고 이유를 알린다
    for _ in range(20):
        term.app.step()
        time.sleep(0.01)
    assert not term.port.is_open and opened == ["ble://CLI-BOARD"]
    assert any("is a BLE device" in line for line in term.app.screen_text())  # 안내는 폭에 맞춰 줄이 나뉜다


class _FakeOpen:
    is_open = True
    mtu = 247
    in_waiting = 0

    def read(self, n=1):
        time.sleep(0.01)
        return b""

    def write(self, data):
        return len(data)

    def close(self):
        self.is_open = False


def test_ctl_resume_does_not_block_the_window_on_ble(term, monkeypatch):
    """BLE 는 여는 데 몇 초 걸린다. resume 이 그걸 기다리면 창이 멈추고 제어 요청도 시간 초과가 난다."""
    monkeypatch.setattr(app_module, "open_device", lambda settings: _slow_open())
    term.item_ble.checked = True
    term._apply_ble(True)
    term.settings = PortSettings(port="ble://CLI-BOARD")
    term._released = True

    t0 = time.monotonic()
    status = term._ctl_ui("resume", {})
    assert time.monotonic() - t0 < 0.5, "resume 이 연결을 기다리고 있다"
    assert status["connecting"] and not status["connected"] and not status["released"]

    deadline = time.monotonic() + 5
    while not term.port.is_open and time.monotonic() < deadline:
        term.app.step()
        time.sleep(0.01)
    assert term.port.is_open and not term._ctl_ui("status", {})["connecting"]


def _slow_open():
    time.sleep(0.6)  # 실제 BLE 는 스캔·연결에 몇 초가 걸린다
    return _FakeOpen()
