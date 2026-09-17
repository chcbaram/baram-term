from baram_term.hexinfo import as_hex, char_note, describe, printable


def test_single_byte_shows_value_and_char():
    assert describe(0x4C, b"l") == "@0000004C  6C  108  'l'"
    assert describe(0, b"\r") == "@00000000  0D  13  CR"
    assert describe(0, b"\x81") == "@00000000  81  129  <81>"


def test_range_shows_count_hex_and_text():
    out = describe(0x4A, b"cli# hel")
    assert out.startswith("@0000004A..00000051  8 bytes  63 6C 69 23 20 68 65 6C  ")
    assert out.endswith('"cli# hel"')


def test_long_selection_is_shortened():
    out = describe(0, bytes(range(0x20, 0x40)))
    assert " …  " in out and out.endswith('…"')
    assert out.count(" ") < 40


def test_up_to_four_bytes_add_integers():
    """1~4 바이트는 한 덩어리 값으로 읽는다. 그보다 길면 조합 값이 의미가 없어 빼다."""
    assert describe(0, b"\x69\x23").endswith("LE 0x2369 (9065)  BE 0x6923 (26915)")
    assert "LE 0x04030201 (67305985)" in describe(0, b"\x01\x02\x03\x04")
    assert "LE 0x636261 (6513249)" in describe(0, b"abc")
    assert "LE" not in describe(0, b"abcde")  # 5 바이트부터는 안 붙인다


def test_helpers():
    assert char_note(0x20) == "' '" and char_note(0x1B) == "ESC"
    assert printable(b"a\x00b") == "a.b"
    assert as_hex(b"\x01\xab") == "01 AB"
    assert describe(0, b"") == ""


def test_value_line_keeps_hex_and_text_longest():
    """좁아지면 오프셋 > 빅엔디안 > 10진수 순으로 덜어내고, 16진수와 글자를 끝까지 남긴다."""
    data = b"\x69\x23\x20\x68"
    full = describe(2, data)
    assert full.endswith("BE 0x69232068 (1763909736)") and len(full) > 60

    for width, keep, drop in [
        (80, "LE 0x68202369 (1746936681)  BE 0x69232068", "(1763909736)"),
        (50, "LE 0x68202369", "BE"),
        (30, '69 23 20 68  "i# h"', "LE"),
    ]:
        out = describe(2, data, width)
        assert len(out) <= width, out
        assert keep in out and drop not in out, out

    assert describe(2, b"l", 40) == "@00000002  6C  108  'l'"  # 짧으면 그대로


def test_block_line_ellipsizes_to_fit():
    """5 바이트 이상은 바이트 수와 글자를 폭에 맞춰 말줄임으로 줄인다."""
    data = bytes(range(0x61, 0x61 + 16))
    for width in (70, 50, 40, 30):
        out = describe(0, data, width)
        assert len(out) <= width, out
        assert "16 bytes" in out and "…" in out, out
