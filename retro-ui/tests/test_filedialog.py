import pytest

from retroui import App, CheckBox, Dialog, FileDialog, Label, VBox
from retroui.input.events import Key, KeyEvent, Mod, TextEvent
from retroui.widgets.filedialog import human_size


@pytest.fixture
def app():
    try:
        a = App(headless=True, size=(100, 32), theme="mono")
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))
    a.set_root(VBox(Label("root")))
    yield a
    a.close()


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "old.log").write_text("x" * 2048)
    (tmp_path / "Beta").mkdir()
    (tmp_path / "alpha.txt").write_text("hi")
    (tmp_path / "zeta.log").write_text("")
    (tmp_path / ".hidden").write_text("")
    return tmp_path


def open_dialog(app, directory, **kw):
    results = []
    d = FileDialog("Save", directory=directory, on_result=results.append, **kw)
    d.open(app)
    app.step()
    return d, results


def key(app, k, mod=Mod.NONE):
    app.dispatch(KeyEvent(k, mod, ""))


def test_human_size():
    assert human_size(2) == "2B"
    assert human_size(2048) == "2.0K"
    assert human_size(5 * 1024 * 1024) == "5.0M"


def test_lists_folders_then_files_and_hides_dotfiles(app, tree):
    d, _ = open_dialog(app, tree, filename="new.log")
    assert d.list.items == ["../", "Beta/", "logs/", "alpha.txt", "zeta.log"]
    assert d.list.details[3].startswith("2B")
    assert app.focus is d.name_edit and d.name_edit.selected_text() == "new"
    assert "zeta.log" in "\n".join(app.screen_text())


def test_enter_on_folder_navigates_and_backspace_goes_up(app, tree):
    d, _ = open_dialog(app, tree)
    assert app.focus is d.list
    d.list.select(2)  # logs/
    key(app, Key.RETURN)
    assert d.directory == tree / "logs" and d.list.items == ["../", "old.log"]
    assert d.list.details[1].startswith("2.0K")
    assert d.path_edit.text == str(tree / "logs")
    key(app, Key.BACKSPACE)
    assert d.directory == tree and d.list.current == "logs/"


def test_selecting_file_fills_name_and_enter_saves(app, tree):
    d, results = open_dialog(app, tree, filename="new.log")
    d.list.select(4)
    assert d.name_edit.text == "zeta.log"
    d.name_edit.set_text("fresh.log")
    app.set_focus(d.name_edit)
    key(app, Key.RETURN)
    assert results == [tree / "fresh.log"] and not d.is_open and d.path == tree / "fresh.log"


def test_folder_typed_as_name_navigates_instead_of_saving(app, tree):
    d, results = open_dialog(app, tree, filename="x.log")
    d.name_edit.set_text("logs")
    d.finish(0)
    assert d.is_open and d.directory == tree / "logs" and results == [] and d.name_edit.text == ""


def test_path_field_navigates_and_reports_missing(app, tree):
    d, _ = open_dialog(app, tree)
    app.set_focus(d.path_edit)
    d.path_edit.set_text(str(tree / "nope"))
    key(app, Key.RETURN)
    assert d.is_open and d.directory == tree and "nope" in d.message.text
    d.path_edit.set_text(str(tree / "Beta"))
    key(app, Key.RETURN)
    assert d.directory == tree / "Beta" and d.message.text == "" and app.focus is d.list


def test_existing_file_asks_before_accepting(app, tree):
    d, results = open_dialog(app, tree, filename="zeta.log", confirm_existing="{name} exists. Append?")
    d.finish(0)
    confirm = app.popups[-1]
    assert isinstance(confirm, Dialog) and confirm is not d and results == []
    assert "zeta.log exists. Append?" in "\n".join(app.screen_text())
    confirm.finish(1)
    assert d.is_open and results == []
    d.finish(0)
    app.popups[-1].finish(0)
    assert results == [tree / "zeta.log"] and not d.is_open


def test_open_mode_needs_existing_file_and_escape_cancels(app, tree):
    d, results = open_dialog(app, tree, mode="open")
    d.name_edit.set_text("missing.txt")
    d.finish(0)
    assert d.is_open and "missing.txt" in d.message.text
    key(app, Key.ESCAPE)
    assert results == [None] and not d.is_open


def test_activating_file_in_open_mode_accepts(app, tree):
    d, results = open_dialog(app, tree, mode="open")
    d.list.select(3)  # alpha.txt
    key(app, Key.RETURN)
    assert results == [tree / "alpha.txt"]


def test_new_folder_is_created_and_selected(app, tree):
    d, _ = open_dialog(app, tree)
    d.ask_new_folder()
    for ch in "새폴더":
        app.dispatch(TextEvent(ch))
    key(app, Key.RETURN)
    assert (tree / "새폴더").is_dir()
    assert d.is_open and d.list.current == "새폴더/" and app.focus is d.list


def test_patterns_filter_files_but_keep_folders(app, tree):
    d, _ = open_dialog(app, tree, patterns=["*.LOG"])
    assert d.list.items == ["../", "Beta/", "logs/", "zeta.log"]


def test_missing_start_folder_falls_back_to_existing_parent(app, tree):
    d, _ = open_dialog(app, tree / "a" / "b")
    assert d.directory == tree


def test_extra_widget_and_custom_text(app, tree):
    box = CheckBox("Timestamp each line", checked=True)
    d, _ = open_dialog(app, tree, extra=box, text={"save": "Start", "folder": "Folder"})
    text = "\n".join(app.screen_text())
    assert "Timestamp each line" in text and "Start" in text and "Folder" in text
