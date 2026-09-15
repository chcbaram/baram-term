from baram_term.plotfilter import PlotLineFilter


def make():
    clock = [0.0]
    f = PlotLineFilter(clock=lambda: clock[0])
    return f, clock


def test_plot_lines_are_removed_and_text_passes():
    f, _ = make()
    shown, plots = f.feed("[OK] boot\r\n>ax:1\r\n>ay:2\r\nhello\r\n")
    assert shown == "[OK] boot\r\nhello\r\n"
    assert plots == [">ax:1", ">ay:2"]


def test_arduino_lines_and_log_lines_with_values():
    f, _ = make()
    shown, plots = f.feed("temp:34,hum:50\r\n[OK] sensor temp=42 rpm=1200\r\n10 20 30\r\n")
    assert shown == "[OK] sensor temp=42 rpm=1200\r\n"
    assert plots == ["temp:34,hum:50", "10 20 30"]


def test_prompt_redraw_keeps_erase_code_but_drops_values():
    # 펌웨어: 프롬프트 줄 지우기 -> 값 출력 -> 프롬프트와 입력 중이던 글자 다시 그리기
    f, _ = make()
    shown, plots = f.feed("\r\x1b[K>ax:972\r\n>ay:-232\r\ncli# he")
    assert shown == "\r\x1b[Kcli# he" and plots == [">ax:972", ">ay:-232"]


def test_partial_plot_line_is_held_until_newline():
    f, _ = make()
    assert f.feed(">a") == ("", [])
    assert f.holding
    assert f.feed("x:1") == ("", [])
    assert f.feed("\r\n") == ("", [">ax:1"])
    assert not f.holding


def test_arduino_label_partial_is_held_so_it_never_flashes():
    f, _ = make()
    assert f.feed("te") == ("", [])
    assert f.feed("mp:34\r\n") == ("", ["temp:34"])


def test_prompt_is_not_held():
    f, _ = make()
    assert f.feed("\n\rcli# ") == ("\n\rcli# ", [])
    assert not f.holding


def test_held_text_is_released_after_timeout_or_force():
    f, clock = make()
    assert f.feed("> ") == ("", [])  # ">" 로 시작하는 프롬프트는 잠깐 붙잡힌다
    assert f.flush() == ""
    clock[0] = 0.25
    assert f.flush() == "> " and not f.holding
    f.feed("12")
    assert f.flush(force=True) == "12"


def test_non_plot_line_that_looked_like_plot_passes_whole():
    f, _ = make()
    assert f.feed("ax") == ("", [])
    assert f.feed(" is ok!\r\n") == ("ax is ok!\r\n", [])
