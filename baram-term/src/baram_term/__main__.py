"""Command line entry: baram-term [PORT] [-b BAUD] [--demo] [--list] ..."""

from __future__ import annotations

import argparse

from baram_term import __version__
from baram_term.i18n import LANGUAGES, set_language
from baram_term.serial_port import DEMO_PORT, PortSettings, list_ports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="baram-term", description="firmware CLI serial terminal")
    parser.add_argument("port", nargs="?", default="", help="serial port or pyserial URL (loop://, socket://host:port)")
    parser.add_argument("-b", "--baud", type=int, default=115200)
    parser.add_argument("--demo", action="store_true", help=f"connect to the built-in fake firmware ({DEMO_PORT})")
    parser.add_argument("--list", action="store_true", help="list serial ports and exit")
    parser.add_argument("--theme", default="mono")
    parser.add_argument("--font-size", type=int, default=14)
    parser.add_argument("--size", default="100x32", help="window size in cells, COLSxROWS")
    parser.add_argument("--lang", choices=LANGUAGES)
    parser.add_argument("--version", action="version", version=f"baram-term {__version__}")
    args = parser.parse_args(argv)

    set_language(args.lang)
    if args.list:
        for port in list_ports():
            print(port)
        return 0

    cols, rows = (int(v) for v in args.size.lower().split("x"))
    # 창을 만들기 전에 import: pygame 초기화 메시지가 --list/--version 출력에 섞이지 않게
    from baram_term.app import BaramTerm

    settings = PortSettings(port=DEMO_PORT if args.demo else args.port, baud=args.baud)
    BaramTerm(settings, theme=args.theme, font_size=args.font_size, size=(cols, rows)).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
