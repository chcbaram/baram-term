import json

from baram_term import notes as store
from baram_term.notes import Note


def test_default_path_is_in_the_config_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("BARAM_TERM_CONFIG_DIR", str(tmp_path))
    assert store.default_path() == tmp_path / "notes.json"


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "sub" / "notes.json"
    pages = [Note("boot", "reset\nlog on"), Note("sensor", "sensor start")]
    store.save(pages, path)
    loaded, error = store.load(path)
    assert error is None and loaded == pages
    assert json.loads(path.read_text())["version"] == store.FORMAT_VERSION
    assert not list(path.parent.glob(".notes-*"))


def test_missing_file_and_broken_file(tmp_path):
    assert store.load(tmp_path / "nope.json") == ([], None)
    broken = tmp_path / "notes.json"
    broken.write_text("{ not json")
    pages, error = store.load(broken)
    assert pages == [] and error


def test_bad_entries_are_skipped_and_count_is_capped(tmp_path):
    path = tmp_path / "notes.json"
    items = [{"title": "ok", "text": "a"}, {"title": 1, "text": "b"}, {"text": "c"}]
    items += [{"title": f"t{i}", "text": ""} for i in range(20)]
    path.write_text(json.dumps({"notes": items}), encoding="utf-8")
    pages, error = store.load(path)
    assert error is None and len(pages) == store.MAX_NOTES
    assert pages[0] == Note("ok", "a") and pages[1].title == "t0"


def test_titles_are_cleaned_and_made_unique():
    assert store.clean_title("  boot   sequence  ") == "boot sequence"
    assert store.clean_title("") == "memo"
    assert store.clean_title("x" * 40) == "x" * store.MAX_TITLE
    assert store.unique_title("boot", ["boot"]) == "boot (2)"
    assert store.unique_title("boot", ["boot", "boot (2)"]) == "boot (3)"
    assert store.unique_title("fresh", ["boot"]) == "fresh"


def test_export_and_import_text(tmp_path):
    path = tmp_path / "boot steps.txt"
    store.export_text(Note("boot", "reset\nlog on"), path)
    assert path.read_text() == "reset\nlog on\n"

    pages = store.import_file(path)
    assert pages == [Note("boot steps", "reset\nlog on")]  # 제목은 파일 이름


def test_export_and_import_all(tmp_path):
    path = tmp_path / "all.json"
    pages = [Note("boot", "reset"), Note("sensor", "start")]
    store.export_all(pages, path)
    assert store.import_file(path) == pages


def test_import_json_without_notes_falls_back_to_text(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"other": 1}', encoding="utf-8")
    pages = store.import_file(path)
    assert pages == [Note("data", '{"other": 1}')]
