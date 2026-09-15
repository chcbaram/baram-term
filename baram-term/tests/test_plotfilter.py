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
    assert f.feed("\r\n12") == ("\r\n", [])
    assert f.flush(force=True) == "12"


def test_non_plot_line_that_looked_like_plot_passes_whole():
    f, _ = make()
    assert f.feed("ax") == ("", [])
    assert f.feed(" is ok!\r\n") == ("ax is ok!\r\n", [])


def test_echo_after_prompt_is_not_held():
    # 프롬프트 뒤에 치는 글자의 에코는 줄 처음이 아니라서 바로 보낸다 (입력이 늦게 보이지 않게)
    f, _ = make()
    assert f.feed("\r\ncli# ") == ("\r\ncli# ", [])
    for ch in "plot":
        assert f.feed(ch) == (ch, [])
    assert f.feed("\r\n") == ("\r\n", [])
    assert f.feed("te") == ("", [])  # 새 줄 처음은 다시 기다린다


def test_continuation_of_shown_text_is_never_a_plot_line():
    f, _ = make()
    assert f.feed("cli# ") == ("cli# ", [])
    assert f.feed("12 34\r\n") == ("12 34\r\n", [])


def test_carriage_return_after_prompt_starts_a_new_line():
    # 프롬프트가 보인 뒤 펌웨어가 줄을 지우고(\r\x1b[K) 값을 찍고 프롬프트를 다시 그린다
    f, _ = make()
    assert f.feed("cli# ") == ("cli# ", [])
    assert f.feed("\r\x1b[K>ax:1\r\ncli# ") == ("\r\x1b[Kcli# ", [">ax:1"])
    assert f.feed("\r\x1b[K>a") == ("", [])  # 지운 뒤 줄 처음이라 기다린다
    assert f.feed("y:2\r\n") == ("\r\x1b[K", [">ay:2"])


def test_expected_format_limits_what_is_held_and_accepted():
    fmt = ["tele"]
    f = PlotLineFilter(
        clock=lambda: 0.0,
        accept=lambda line: line.startswith(">"),
        expected_format=lambda: fmt[0],
    )
    assert f.feed("p:34") == ("p:34", [])  # > 없는 조각은 기다리지 않는다
    assert f.feed("\r\n>ax:1\r\np:34\r\n") == ("\r\np:34\r\n", [">ax:1"])


def test_echo_before_the_value_is_still_a_plot_line():
    """방금 친 글자의 에코가 값 앞에 붙어 와도 값은 터미널에 안 보인다.

    펌웨어가 `"n\\r\\x1b[K>ax:949\\r\\n"` 처럼 보낸다: 에코 뒤 CR 로 커서가 0열로 돌아가고
    지운 다음 값을 찍는다. 줄 *앞*의 CR 만 보던 때는 이 줄을 놓쳐 값이 그대로 찍혔다.
    """
    f = PlotLineFilter()
    f._line_start = False  # 프롬프트 뒤, 입력 중
    shown, plots = f.feed("n\r\x1b[K>ax:949\r\n")
    assert plots == [">ax:949"]
    assert ">ax" not in shown
    assert shown.startswith("n\r")  # 에코와 지우는 코드는 넘긴다 (프롬프트가 겹치지 않게)


def test_typed_line_echo_is_not_eaten_as_a_plot_line():
    """반대로, 사용자가 친 `1,2,3` 의 에코는 그래프 줄로 먹으면 안 된다 (끝 CR 은 CRLF 일 뿐)."""
    f = PlotLineFilter()
    f._line_start = False
    shown, plots = f.feed("1,2,3\r\n")
    assert plots == []
    assert "1,2,3" in shown


def test_escape_split_across_chunks_still_hides_the_value():
    """수신이 ESC 시퀀스 중간에서 잘려도 다음 조각의 값을 놓치지 않는다."""
    burst = "\r\x1b[K>ax:639\r\n"
    for cut in range(1, len(burst)):
        f = PlotLineFilter()
        f._line_start = False
        shown = f.feed(burst[:cut])[0] + f.feed(burst[cut:])[0] + f.flush(force=True)
        assert ">ax" not in shown, cut


def test_chunk_ending_inside_an_escape_does_not_raise():
    """ESC 시퀀스 중간에서 끊긴 조각에 줄 정리를 돌리면 줄이 하나도 안 나온다 (예전에 IndexError)."""
    f = PlotLineFilter()
    assert f.feed("\r\x1b") == ("\r", [])
