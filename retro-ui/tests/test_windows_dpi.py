from retroui.app import set_windows_dpi_hints


def test_windows_gets_per_monitor_dpi_and_scaling():
    """힌트가 없으면 윈도우가 100% 로 그린 화면을 늘려서 글자가 흐려진다."""
    env: dict[str, str] = {}
    set_windows_dpi_hints(env, "nt")
    assert env == {"SDL_WINDOWS_DPI_AWARENESS": "permonitorv2", "SDL_WINDOWS_DPI_SCALING": "1"}


def test_other_platforms_are_left_alone():
    for name in ("posix", "java"):
        env: dict[str, str] = {}
        set_windows_dpi_hints(env, name)
        assert env == {}


def test_values_set_by_the_user_win():
    env = {"SDL_WINDOWS_DPI_AWARENESS": "unaware"}
    set_windows_dpi_hints(env, "nt")
    assert env["SDL_WINDOWS_DPI_AWARENESS"] == "unaware"
    assert env["SDL_WINDOWS_DPI_SCALING"] == "1"
