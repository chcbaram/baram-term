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


def test_two_and_four_bytes_add_integers():
    assert describe(0, b"\x69\x23").endswith("LE 0x2369 (9065)  BE 0x6923 (26915)")
    assert "LE 0x04030201 (67305985)" in describe(0, b"\x01\x02\x03\x04")
    assert "LE" not in describe(0, b"abc")


def test_helpers():
    assert char_note(0x20) == "' '" and char_note(0x1B) == "ESC"
    assert printable(b"a\x00b") == "a.b"
    assert as_hex(b"\x01\xab") == "01 AB"
    assert describe(0, b"") == ""


def test_width_shortens_from_the_end():
    data = b"\x69\x23\x20\x68"
    full = describe(2, data)
    assert full.endswith("BE 0x69232068 (1763909736)") and len(full) > 60

    fitted = describe(2, data, 42)  # 글자까지 딱 들어가는 폭
    assert len(fitted) <= 42 and fitted.startswith("@00000002+4") and '"i# h"' in fitted
    assert "LE" not in fitted  # 정수부터 덜어낸다

    assert '"i# h"' not in describe(2, data, 40)  # 한 칸이 모자라면 글자도 뺀다

    narrow = describe(2, data, 24)
    assert len(narrow) <= 24 and narrow.startswith("@00000002+4  4 bytes")

    assert describe(2, b"l", 40) == "@00000002  6C  108  'l'"  # 짧으면 그대로
