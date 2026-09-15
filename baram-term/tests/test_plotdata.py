import pytest

from baram_term.plotdata import parse_line


@pytest.mark.parametrize(
    "line, expected",
    [
        (">ax:-15", [("ax", -15.0)]),
        (">temp:34.5\r", [("temp", 34.5)]),
        (">ax:1234:-15", [("ax", -15.0)]),  # 시각:값
        (">volt:3.3§V|np", [("volt", 3.3)]),  # 단위, 옵션
        (">ax:1:2;3:4", [("ax", 4.0)]),
    ],
)
def test_teleplot(line, expected):
    assert parse_line(line) == expected


@pytest.mark.parametrize(
    "line, expected",
    [
        ("10 20 30", [("value 1", 10.0), ("value 2", 20.0), ("value 3", 30.0)]),
        ("10,20,-.5", [("value 1", 10.0), ("value 2", 20.0), ("value 3", -0.5)]),
        ("1e3\t2", [("value 1", 1000.0), ("value 2", 2.0)]),
        ("ax:-15,ay:-70,az:2055", [("ax", -15.0), ("ay", -70.0), ("az", 2055.0)]),
        ("temp=42.1 rpm=1200", [("temp", 42.1), ("rpm", 1200.0)]),
        ("temp: 34, hum: 50", [("temp", 34.0), ("hum", 50.0)]),
    ],
)
def test_arduino_plotter(line, expected):
    assert parse_line(line) == expected


@pytest.mark.parametrize(
    "line",
    ["", "   ", "cli# help", "[OK] sensor temp=42 rpm=1200", "Uptime  : 12 ms", ">ax", ">:1", ">ax:abc", "nan", "inf 1", ":5", "a:b:c"],
)
def test_non_plot_lines_are_ignored(line):
    assert parse_line(line) is None
