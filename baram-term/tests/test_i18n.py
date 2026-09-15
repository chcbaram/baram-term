import string

import pytest

from baram_term import i18n


@pytest.fixture(autouse=True)
def restore_language():
    yield
    i18n.set_language("en")


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalogs_have_the_same_keys_and_placeholders():
    ko = i18n._catalog("ko")
    en = i18n._catalog("en")
    assert set(ko) == set(en)
    for key in ko:
        assert placeholders(ko[key]) == placeholders(en[key]), key


def test_tr_formats_and_falls_back_to_key():
    i18n.set_language("en")
    assert i18n.tr("notice.connected", port="demo://", serial="115200 8N1") == "connected to demo:// (115200 8N1)"
    assert i18n.tr("no.such.key") == "no.such.key"
    i18n.set_language("ko")
    assert i18n.tr("button.ok") == "확인"


def test_env_selects_language(monkeypatch):
    monkeypatch.setenv("BARAM_TERM_LANG", "ko")
    i18n.set_language(None)
    assert i18n.language() == "ko"


def test_default_is_english_even_on_a_korean_system(monkeypatch):
    """시스템 로케일이 한국어여도 기본은 영어다. 한국어는 파일 메뉴에서 골라 저장한다."""
    monkeypatch.delenv("BARAM_TERM_LANG", raising=False)
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    monkeypatch.setenv("LC_ALL", "ko_KR.UTF-8")
    i18n.set_language(None)
    assert i18n.language() == "en"
