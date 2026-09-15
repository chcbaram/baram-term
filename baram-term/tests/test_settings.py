import json
import sys

from baram_term import settings as store
from baram_term.settings import Settings


def test_config_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("BARAM_TERM_CONFIG_DIR", str(tmp_path))
    assert store.default_path() == tmp_path / "settings.json"


def test_platform_config_dir(monkeypatch):
    monkeypatch.delenv("BARAM_TERM_CONFIG_DIR", raising=False)
    path = str(store.config_dir())
    if sys.platform == "darwin":
        assert path.endswith("Library/Application Support/baram-term")
    assert path.endswith("baram-term")


def test_missing_file_gives_defaults_without_error(tmp_path):
    config, error = store.load(tmp_path / "nope.json")
    assert config == Settings() and error is None


def test_roundtrip(tmp_path):
    path = tmp_path / "sub" / "settings.json"
    config = Settings(port="/dev/ttyUSB0", baud=921600, stopbits=1.5, local_echo=True, commands={"/dev/ttyUSB0": ["help", "md"]})
    store.save(config, path)
    loaded, error = store.load(path)
    assert error is None and loaded == config
    assert json.loads(path.read_text())["version"] == store.FORMAT_VERSION
    assert not list(path.parent.glob(".settings-*"))  # 임시 파일이 남지 않는다


def test_corrupt_file_reports_error(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ not json")
    config, error = store.load(path)
    assert config == Settings() and error


def test_wrong_types_fall_back_per_value(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "baud": "fast",
        "local_echo": "yes",
        "font_size": 18,
        "stopbits": 2,
        "commands": {"x": [1]},
        "unknown": True,
    }))
    config, error = store.load(path)
    assert error is None
    assert config.baud == 115200 and config.local_echo is False
    assert config.font_size == 18 and config.stopbits == 2.0
    assert config.commands == {}
