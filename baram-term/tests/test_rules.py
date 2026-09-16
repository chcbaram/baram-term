from retroui.theme import LIGHT_RED, YELLOW

from baram_term.rules import COLORS, compile_rules, entry_label, format_entry, parse_entry, pattern_error


def test_format_and_parse_round_trip():
    assert format_entry("red", True, r"\bTIMEOUT\b") == r"red bold|\bTIMEOUT\b"
    assert format_entry("cyan", False, "^\\d+ ms") == "cyan|^\\d+ ms"
    assert parse_entry(r"red bold|\bTIMEOUT\b") == ("red", True, r"\bTIMEOUT\b")
    assert parse_entry("cyan|^ok") == ("cyan", False, "^ok")
    assert parse_entry("cyan|a|b") == ("cyan", False, "a|b")  # 정규식 안의 | 는 그대로


def test_bad_entries_are_ignored():
    for entry in ("", "red", "|abc", "pink|abc", "red|", "bold|abc"):
        assert parse_entry(entry) is None
    assert compile_rules(["red", "pink|x", r"red|\bOK\b"]) and len(compile_rules(["red", "pink|x", r"red|\bOK\b"])) == 1


def test_compile_uses_colors_and_bold():
    rules = compile_rules([r"red bold|\bFAIL\b", "yellow|retry=\\d+"])
    assert [r.fg for r in rules] == [LIGHT_RED, YELLOW]
    assert [r.bold for r in rules] == [True, False]
    assert rules[0].pattern.search("boot FAIL now")
    assert compile_rules(["red|("]) == []  # 잘못된 정규식은 건너뛴다


def test_pattern_error_explains():
    assert pattern_error("(") and "unterminated" in pattern_error("(")
    assert pattern_error(r"\bok\b") is None


def test_entry_label_lines_up():
    assert entry_label(r"red bold|\bTIMEOUT\b") == r"red      bold  \bTIMEOUT\b"
    assert entry_label("cyan|^ok") == "cyan           ^ok"
    assert entry_label("nonsense") == "nonsense"


def test_color_names():
    assert list(COLORS) == ["green", "red", "yellow", "cyan", "magenta", "blue", "white", "gray"]
