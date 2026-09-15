"""Command line entry: baram-term [PORT] [-b BAUD] [--demo] [--list] ...

실행 인자가 저장된 설정보다 우선하고, 준 값은 다시 저장된다. 인자 없이 실행하면 마지막 포트로 연결한다.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from baram_term import __version__
from baram_term import settings as config_store
from baram_term.i18n import LANGUAGES, set_language, tr
from baram_term.serial_port import DEMO_PORT, list_ports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="baram-term", description="firmware CLI serial terminal")
    parser.add_argument("port", nargs="?", help="serial port or pyserial URL (loop://, socket://host:port)")
    parser.add_argument("-b", "--baud", type=int)
    parser.add_argument("--demo", action="store_true", help=f"connect to the built-in fake firmware ({DEMO_PORT})")
    parser.add_argument("--list", action="store_true", help="list serial ports and exit")
    parser.add_argument("--theme")
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--size", help="window size in cells, COLSxROWS")
    parser.add_argument("--lang", choices=LANGUAGES)
    parser.add_argument("--config", type=Path, help=f"settings file (default: {config_store.default_path()})")
    parser.add_argument("--version", action="version", version=f"baram-term {__version__}")
    args = parser.parse_args(argv)

    config_path = args.config or config_store.default_path()
    config, load_error = config_store.load(config_path)
    if args.lang:
        config.lang = args.lang
    set_language(config.lang or None)

    if args.list:
        for port in list_ports():
            print(port)
        return 0

    if args.demo:
        config.port = DEMO_PORT
    elif args.port:
        config.port = args.port
    if args.baud:
        config.baud = args.baud
    if args.theme:
        config.theme = args.theme
    if args.font_size:
        config.font_size = args.font_size
    if args.size:
        config.cols, config.rows = (int(v) for v in args.size.lower().split("x"))

    # 창을 만들기 전에 import: pygame 초기화 메시지가 --list/--version 출력에 섞이지 않게
    from baram_term.app import BaramTerm

    term = BaramTerm(
        config.port_settings(),
        theme=config.theme,
        font_size=config.font_size,
        size=(config.cols, config.rows),
        config=config,
        config_path=config_path,
    )
    if load_error:
        term.notice(tr("notice.settings_load_failed", error=load_error), error=True)
    term.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
