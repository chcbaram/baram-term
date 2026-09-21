"""Command line entry: baram-term [PORT] [-b BAUD] [--demo] [--list] ... | baram-term ctl COMMAND ...

실행 인자가 저장된 설정보다 우선하고, 준 값은 다시 저장된다. 인자 없이 실행하면 마지막 포트로 연결한다.
설정은 워크스페이스별로 둔다 (workspaces.py). --workspace 없이 실행하면 마지막에 연 워크스페이스를,
그게 이미 다른 창에 열려 있으면 비어 있는 다음 것을 연다. --config 를 주면 예전처럼 파일 하나만 쓴다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from baram_term import __version__
from baram_term import settings as config_store
from baram_term import workspaces
from baram_term.i18n import LANGUAGES, set_language, tr
from baram_term.serial_port import DEMO_PORT, list_ports


def _attach_console() -> None:
    """콘솔 없이 묶은 실행 파일에서도 글자를 낼 곳을 마련한다.

    윈도우는 콘솔 없이(`--windowed`) 빌드하면 sys.stdout 이 None 이라 `--list` 의 print 도,
    argparse 의 오류/도움말도 AttributeError 로 죽는다. 셸에서 실행했다면 그 셸의 콘솔에
    붙어 거기에 출력하고, 탐색기에서 더블클릭했다면 붙을 콘솔이 없으므로 조용히 버린다
    (창만 뜨는 것이 맞다). 어느 쪽이든 print 가 예외를 내지 않는 상태로 만든다.
    """
    if os.name == "nt" and sys.stdout is None:
        try:
            import ctypes

            if ctypes.windll.kernel32.AttachConsole(-1):  # -1 = 부모 프로세스의 콘솔
                sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
                sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        except (OSError, AttributeError):
            pass
    for name in ("stdout", "stderr"):
        if getattr(sys, name, None) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))


def _report_fatal(message: str) -> None:
    """시작하다 죽었을 때 알린다. 콘솔이 없으면 이것 말고는 알릴 방법이 없다."""
    try:
        import pygame

        pygame.display.message_box("baram-term", message, message_type="error")
    except Exception:  # 상자도 못 띄우는 상황이면 더 할 수 있는 것이 없다
        pass


def _pick_workspace(config_dir: Path, requested: str | None, last: object) -> tuple[workspaces.Workspace | None, str]:
    """(연 워크스페이스, 못 열었을 때의 이유). 연 것은 잠겨 있다."""
    try:
        workspaces.ensure(config_dir)
        existing = workspaces.names(config_dir)
        if requested:
            # 창 메뉴가 띄운 것이든 사람이 친 것이든: 없으면 만들고, 다른 창이 열고 있으면 두 번 열지 않는다
            if not workspaces.valid_name(requested):
                return None, tr("fatal.workspace_name", name=requested, chars=workspaces.BAD_CHARS)
            name = next((n for n in existing if n.casefold() == requested.casefold()), requested)
            if name not in existing:
                workspaces.create(config_dir, name)
            ws = workspaces.Workspace(config_dir, name)
            return (ws, "") if ws.acquire() else (None, tr("fatal.workspace_open", name=name))
        candidates = [last] if isinstance(last, str) and last in existing else []
        candidates += [n for n in existing if n not in candidates]
        for name in candidates:
            ws = workspaces.Workspace(config_dir, name)
            if ws.acquire():
                return ws, ""
        # 전부 다른 창에 열려 있다: 빈 워크스페이스를 하나 만든다 (실행을 거절하는 것보다 낫다)
        ws = workspaces.create(config_dir, workspaces.unique_name(config_dir, workspaces.DEFAULT))
        return (ws, "") if ws.acquire() else (None, tr("fatal.workspace_open", name=ws.name))
    except OSError as e:
        return None, tr("fatal.workspace_failed", error=e)


def main(argv: list[str] | None = None) -> int:
    _attach_console()
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["ctl"]:
        # 실행 중인 baram-term 에 붙는 제어 명령 (ctl.py). 창을 띄우지 않고 pygame 도 올리지 않는다
        from baram_term import ctl

        return ctl.main(argv[1:])
    parser = argparse.ArgumentParser(
        prog="baram-term",
        description="firmware CLI serial terminal",
        epilog="baram-term ctl --help: control a running baram-term from another program",
    )
    parser.add_argument("port", nargs="?", help="serial port or pyserial URL (loop://, socket://host:port)")
    parser.add_argument("-b", "--baud", type=int)
    parser.add_argument("--demo", action="store_true", help=f"connect to the built-in fake firmware ({DEMO_PORT})")
    parser.add_argument("--list", action="store_true", help="list serial ports and exit")
    parser.add_argument("--theme")
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--size", help="window size in cells, COLSxROWS")
    parser.add_argument("--lang", choices=LANGUAGES)
    parser.add_argument("-w", "--workspace", help="workspace to open (created if it does not exist)")
    parser.add_argument("--config", type=Path, help="use this one settings file instead of workspaces")
    parser.add_argument("--version", action="version", version=f"baram-term {__version__}")
    args = parser.parse_args(argv)

    if args.list:
        for port in list_ports():
            print(port)
        return 0

    workspace = None
    if args.config:
        config_path = args.config
        config, load_error = config_store.load(config_path)
        set_language(args.lang or config.lang or None)
    else:
        config_path = None
        config_dir = config_store.config_dir()
        global_raw = config_store.read_raw(config_dir / "settings.json")[0]
        lang = global_raw.get("lang")
        set_language(args.lang or (lang if isinstance(lang, str) and lang else None))
        workspace, problem = _pick_workspace(config_dir, args.workspace, global_raw.get("workspace"))
        if workspace is None:
            _report_fatal(problem)
            print(problem, file=sys.stderr)
            return 1
        config, load_error = workspace.load()
        config.workspace = workspace.name  # 다음에 이름 없이 실행하면 이것을 연다
    if args.lang:
        config.lang = args.lang

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

    try:
        term = BaramTerm(
            config.port_settings(),
            theme=config.theme,
            font_size=config.font_size,
            size=(config.cols, config.rows),
            config=config,
            config_path=config_path,
            workspace=workspace,
        )
        if load_error:
            term.notice(tr("notice.settings_load_failed", error=load_error), error=True)
        term.run()
    except Exception as e:
        # 콘솔 없이 실행하면 여기서 죽어도 화면에 아무것도 남지 않는다 (폰트 못 찾음 등).
        # 상자로 알리고, 콘솔이 있으면 트레이스백도 그대로 보이도록 다시 올린다
        _report_fatal(f"{type(e).__name__}: {e}")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
