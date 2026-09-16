import pytest

from baram_term import i18n
from baram_term import settings as store
from baram_term.app import BaramTerm
from baram_term.serial_port import PortSettings
from baram_term.settings import Settings


def make(lang="en", config=None, config_path=None):
    i18n.set_language(lang)
    try:
        return BaramTerm(
            PortSettings(port="demo://"), headless=True, size=(80, 30),
            config=config if config is not None else Settings(), config_path=config_path,
        )
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))


@pytest.fixture
def bt():
    term = make()
    yield term
    term.port.close()
    term.app.close()


def click(item):
    """메뉴에서 누른 것처럼: 체크 항목은 실행 전에 먼저 뒤집힌다."""
    if item.checked is not None:
        item.checked = not item.checked
    item.action()


def screen(term):
    term.app.step()
    return "\n".join(term.app.screen_text())


def test_file_menu_comes_first(bt):
    assert [m.title for m in bt.menu.menus] == ["File", "Port", "Edit", "View", "Help"]


def test_file_menu_holds_log_language_and_quit(bt):
    items = [i.text or "---" for i in bt.menu.menus[0].items]
    assert items == ["Start/stop log...", "---", "Memo", "---", "한국어", "English", "---", "Quit"]
    memo = bt.menu.menus[0].items[2]  # 메모 파일 넣고 빼기는 한 단 아래로 묶는다
    assert [i.text for i in memo.submenu] == ["Import...", "Export..."]


def test_port_menu_keeps_only_connection_items(bt):
    assert [i.text for i in bt.menu.menus[1].items] == ["Connect", "Disconnect", "Port settings..."]


def test_language_names_are_written_in_their_own_language():
    """화면이 영어여도 한국어는 "한국어" 로 보여야 찾을 수 있다."""
    term = make("en")
    try:
        assert term.item_lang_ko.text == "한국어" and term.item_lang_en.text == "English"
    finally:
        term.port.close()
        term.app.close()


def test_current_language_is_checked(bt):
    assert bt.item_lang_en.checked and not bt.item_lang_ko.checked


def test_choosing_another_language_saves_it_for_next_start(tmp_path):
    path = tmp_path / "settings.json"
    term = make("en", config=Settings(), config_path=path)
    try:
        click(term.item_lang_ko)
        assert term.item_lang_ko.checked and not term.item_lang_en.checked
        assert store.load(path)[0].lang == "ko"
        assert "takes effect the next time" in screen(term)
        assert term.menu.menus[0].title == "File"  # 화면은 다시 켤 때 바뀐다
    finally:
        term.port.close()
        term.app.close()


def test_clicking_the_checked_language_keeps_it_checked(bt):
    click(bt.item_lang_en)
    assert bt.item_lang_en.checked and not bt.item_lang_ko.checked
    assert "takes effect the next time" not in screen(bt)


def test_switching_back_before_restart_shows_no_notice(bt):
    click(bt.item_lang_ko)
    bt.clear()
    click(bt.item_lang_en)
    assert bt.config.lang == "en"
    assert "takes effect the next time" not in screen(bt)
