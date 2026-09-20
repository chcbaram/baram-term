"""`baram-term ctl ...` — 실행 중인 baram-term 에 붙어 포트로 명령을 보내고 받은 내용을 읽는다.

포트는 baram-term 이 계속 쥐고 있고, 이 명령은 로컬 제어 소켓으로 요청만 한다 (서버는 control.py).
창(인스턴스)마다 자기 소켓을 연다:
- macOS/Linux: ~/.baram-term/ctl/<pid>.sock (유닉스 소켓, 권한 0600, 폴더 0700)
- Windows: 127.0.0.1 의 TCP 포트. 포트 번호와 토큰은 ~/.baram-term/ctl/<pid>.json 에 있다

여러 창이 떠 있으면 --pid / --port / --match 로 하나를 고른다. 하나로 좁혀지지 않으면 아무것도 보내지 않고
후보를 보여준 뒤 실패한다 (엉뚱한 보드에 명령이 가지 않게). 창이 하나뿐이면 고르지 않아도 된다.

프로토콜은 JSON 한 줄 요청 → JSON 한 줄 응답이다. 표준 라이브러리만 쓴다: pygame 을 올리지 않아야
빠르고, 창 없는 셸에서도 돈다. 이 파일만 따로 `python3 ctl.py ...` 로 실행해도 된다 (플러그인의 bin/baram-ctl).

종료 코드: 0 성공, 1 오류, 2 인자 오류, 3 시간 초과, 4 baram-term 이 없거나 외부 제어가 꺼져 있음,
5 대상 창을 하나로 고르지 못함.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_TIMEOUT = 3
EXIT_NOT_RUNNING = 4
EXIT_TARGET = 5

USE_TCP = os.name == "nt"
DEFAULT_TIMEOUT_S = 5.0
DEFAULT_READ_LINES = 50
PROBE_TIMEOUT_S = 1.0

# 받은 글자를 사람이/정규식이 읽기 좋게: ANSI 코드와 CR 을 빼고, Backspace 는 앞 글자를 지운다
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?|\x1b[@-Z\\-_]")
_CONTROL = re.compile(r"[\x00-\x07\x0b-\x1f\x7f]")
_ENDPOINT_NAME = re.compile(r"^(\d+)(?:-(\d+))?$")

NOT_RUNNING_MESSAGE = "baram-term is not running, or external control is off (Port menu > Allow external control)."


def ctl_dir() -> Path:
    env = os.environ.get("BARAM_TERM_CTL_DIR")
    return (Path(env) if env else Path.home() / ".baram-term") / "ctl"


def clean(text: str) -> str:
    text = _ANSI.sub("", text).replace("\r", "")
    if "\x08" in text:
        out: list[str] = []
        for ch in text:
            if ch == "\x08":
                if out and out[-1] != "\n":
                    out.pop()
            else:
                out.append(ch)
        text = "".join(out)
    return _CONTROL.sub("", text)


# ---- finding running instances ----------------------------------------------


@dataclass
class Endpoint:
    """창 하나의 제어 소켓. path 는 유닉스 소켓, 또는 (Windows) 포트/토큰이 적힌 파일."""

    pid: int
    path: Path

    def connect(self, timeout: float) -> tuple[socket.socket, str]:
        """(연결된 소켓, 요청에 붙일 토큰)."""
        if USE_TCP:
            info = json.loads(self.path.read_text(encoding="utf-8"))
            sock = socket.create_connection(("127.0.0.1", int(info["port"])), timeout=timeout)
            return sock, str(info.get("token", ""))
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(str(self.path))
        except OSError:
            sock.close()
            raise
        return sock, ""

    def request(self, req: dict[str, Any], timeout: float) -> dict[str, Any]:
        sock, token = self.connect(timeout)
        if token:
            req = {**req, "token": token}
        with sock:
            sock.sendall(json.dumps(req, ensure_ascii=False).encode("utf-8") + b"\n")
            data = bytearray()
            while not data.endswith(b"\n"):
                chunk = sock.recv(65536)
                if not chunk:
                    break
                data.extend(chunk)
        if not data:
            raise OSError("baram-term closed the connection without a reply")
        return json.loads(data.decode("utf-8"))


def endpoint_file(pid: int, n: int = 0) -> Path:
    name = str(pid) if n == 0 else f"{pid}-{n}"
    return ctl_dir() / (name + (".json" if USE_TCP else ".sock"))


def pid_alive(pid: int) -> bool | None:
    """살아 있으면 True, 없으면 False, 알 수 없으면 None (Windows: 신호 0 이 CTRL_C 라 쓰지 않는다)."""
    if USE_TCP:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None
    return True


def endpoints() -> list[Endpoint]:
    suffix = ".json" if USE_TCP else ".sock"
    try:
        entries = sorted(ctl_dir().iterdir())
    except OSError:
        return []
    found = []
    for path in entries:
        m = _ENDPOINT_NAME.match(path.stem)
        if path.suffix == suffix and m:
            found.append(Endpoint(int(m.group(1)), path))
    return found


def remove_stale(endpoint: Endpoint) -> bool:
    """응답하지 않는 소켓을 주인 프로세스가 없으면 지운다 (비정상 종료로 남은 것).

    Windows 는 pid 를 확인하지 않는다: 적힌 TCP 포트에 붙지 못했다면 주인이 없는 것이다.
    유닉스에서 프로세스가 살아 있으면 막 켜지는 중일 수 있어 둔다.
    """
    if pid_alive(endpoint.pid):
        return False
    try:
        endpoint.path.unlink()
    except OSError:
        return False
    return True


@dataclass
class Instance:
    endpoint: Endpoint
    status: dict[str, Any]

    @property
    def pid(self) -> int:
        return int(self.status.get("pid") or self.endpoint.pid)

    @property
    def port(self) -> str:
        return str(self.status.get("port") or "")

    def haystack(self) -> str:
        """--match 로 찾을 글자: 포트 경로, USB 설명/제조사/제품/시리얼/VID:PID, 창 제목."""
        usb = self.status.get("usb") or {}
        parts = [self.port, self.status.get("title", "")] + [str(v) for v in usb.values() if v]
        return "\n".join(str(p) for p in parts).lower()


def discover(timeout: float = PROBE_TIMEOUT_S) -> list[Instance]:
    """떠 있는 창을 모두 찾는다. 응답하지 않는 소켓은 주인 프로세스가 없으면 지운다."""
    found = []
    for ep in endpoints():
        try:
            status = ep.request({"cmd": "status"}, timeout)
        except (OSError, ValueError):
            remove_stale(ep)
            continue
        if status.get("ok"):
            found.append(Instance(ep, status))
    return found


def select(instances: list[Instance], pid: int | None, port: str | None, match: str | None) -> list[Instance]:
    chosen = instances
    if pid is not None:
        chosen = [i for i in chosen if i.pid == pid]
    if port is not None:
        chosen = [i for i in chosen if i.port == port]
    if match is not None:
        needle = match.lower()
        chosen = [i for i in chosen if needle in i.haystack()]
    return chosen


def describe(instance: Instance) -> str:
    s = instance.status
    usb = s.get("usb") or {}
    if s.get("connected"):
        state = "connected"
    elif s.get("connecting"):
        state = "connecting"  # BLE 는 장치를 찾는 중일 수 있다
    elif s.get("released"):
        state = "released"
    else:
        state = "closed"
    port = instance.port or "(no port)"
    # BLE 포트에는 속도도 8N1 도 없다. 그 자리에 붙은 뒤 정해지는 MTU 를 쓴다
    if s.get("kind") == "ble":
        link = "BLE" + (f" MTU {s['mtu']}" if s.get("mtu") else "")
    else:
        link = f"{s.get('baud', '')} {s.get('framing', '')}".strip()
    line = f"pid {instance.pid}  {port}  {link}  {state}"
    extra = [usb.get("description"), usb.get("serial_number") and f"SER={usb['serial_number']}", usb.get("vid_pid")]
    extra = [e for e in extra if e]
    return line + (f"  [{' · '.join(extra)}]" if extra else "")


# ---- command line --------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    # 공통 옵션은 명령 앞뒤 어디에나 둘 수 있다. 하위 명령 쪽 기본값이 앞에 준 값을 덮지 않게 SUPPRESS
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="print the raw JSON reply")
    target = common.add_argument_group("choosing a window (needed when several baram-term windows run)")
    target.add_argument("--pid", type=int, default=argparse.SUPPRESS, help="baram-term process id")
    target.add_argument("--port", default=argparse.SUPPRESS, metavar="PATH", help="serial port path, exact")
    target.add_argument(
        "--match", default=argparse.SUPPRESS, metavar="TEXT",
        help="substring of port path, USB description/serial/VID:PID or window title (case-insensitive)",
    )

    parser = argparse.ArgumentParser(
        prog="baram-term ctl",
        description="control a running baram-term: send lines to its serial port and read what came back",
        parents=[common],
        epilog="exit codes: 0 ok, 1 error, 2 usage, 3 timeout, 4 baram-term not running / control off, "
        "5 no single window matches (candidates are listed)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="COMMAND")

    sub.add_parser("list", parents=[common], help="running baram-term windows and their ports")
    sub.add_parser("status", parents=[common], help="port, baud, connection and control state")

    p = sub.add_parser("send", parents=[common], help="send one line (and optionally wait for a reply)")
    p.add_argument("text")
    p.add_argument("--until", metavar="REGEX", help="return what arrives until REGEX matches")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, metavar="S", help="seconds (default 5)")
    p.add_argument("--eol", choices=("cr", "lf", "crlf", "none"), help="line ending (default: baram-term setting)")
    p.add_argument("--raw", action="store_true", help="keep ANSI codes and CR in the output")

    p = sub.add_parser("read", parents=[common], help="read recently received text")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--since", type=int, metavar="MARK", help="everything received after MARK")
    g.add_argument("--last", type=int, metavar="N", help=f"last N lines (default {DEFAULT_READ_LINES})")
    p.add_argument("--raw", action="store_true", help="keep ANSI codes and CR in the output")

    p = sub.add_parser("wait", parents=[common], help="wait for output without sending anything")
    p.add_argument("--until", required=True, metavar="REGEX")
    p.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, metavar="S", help="seconds (default 5)")
    p.add_argument("--since", type=int, metavar="MARK", help="also search text received after MARK (default: now)")
    p.add_argument("--raw", action="store_true", help="keep ANSI codes and CR in the output")

    sub.add_parser("release", parents=[common], help="close the port so another tool can open it")
    sub.add_parser("resume", parents=[common], help="open the port again after release")
    return parser


def _build_request(args: argparse.Namespace) -> tuple[dict[str, Any], float]:
    req: dict[str, Any] = {"cmd": args.cmd}
    wait_s = 0.0
    if args.cmd == "send":
        req.update(text=args.text, until=args.until, timeout=args.timeout, eol=args.eol, raw=args.raw)
        wait_s = args.timeout if args.until else 0.0
    elif args.cmd == "read":
        req.update(since=args.since, last=args.last, raw=args.raw)
    elif args.cmd == "wait":
        req.update(until=args.until, timeout=args.timeout, since=args.since, raw=args.raw)
        wait_s = args.timeout
    return {k: v for k, v in req.items() if v is not None}, wait_s


STATUS_KEYS = (
    "pid", "port", "kind", "baud", "framing", "mtu", "enter", "connected", "connecting", "released", "control",
    "clients", "title", "mark", "version",
)


def _print_status(reply: dict[str, Any]) -> None:
    for key in STATUS_KEYS:
        if reply.get(key) is not None:
            value = reply[key]
            if isinstance(value, bool):
                value = "yes" if value else "no"
            print(f"{key}: {value}")
    usb = reply.get("usb") or {}
    for key in ("description", "manufacturer", "product", "serial_number", "vid_pid"):
        if usb.get(key):
            print(f"usb.{key}: {usb[key]}")


def _print_text(reply: dict[str, Any]) -> None:
    if reply.get("cmd") in ("status", "release", "resume") and "port" in reply:
        _print_status(reply)
        return
    output = reply.get("output")
    if output:
        sys.stdout.write(output if output.endswith("\n") else output + "\n")
    sys.stdout.flush()  # stderr 의 마크가 출력보다 먼저 찍히지 않게
    if reply.get("truncated"):
        print("[baram-term ctl] older text was dropped from the buffer", file=sys.stderr)
    if "mark" in reply:
        # 다음 `read --since` / `wait --since` 에 쓸 위치. 출력과 섞이지 않게 stderr 로
        print(f"[mark {reply['mark']}]", file=sys.stderr)


def _fail(args: argparse.Namespace, code: int, error: str, message: str, candidates: list[Instance] = ()) -> int:
    if args.json:
        out: dict[str, Any] = {"ok": False, "error": error, "message": message}
        if candidates:
            out["candidates"] = [i.status for i in candidates]
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(f"baram-term ctl: {message}", file=sys.stderr)
        for instance in candidates:
            print(f"  {describe(instance)}", file=sys.stderr)
    return code


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    for name in ("json", "pid", "port", "match"):
        if not hasattr(args, name):
            setattr(args, name, False if name == "json" else None)
    filtering = args.pid is not None or args.port is not None or args.match is not None

    instances = discover()
    if args.cmd == "list":
        shown = select(instances, args.pid, args.port, args.match)
        if args.json:
            print(json.dumps({"ok": True, "cmd": "list", "instances": [i.status for i in shown]}, ensure_ascii=False))
        elif not shown:
            print(f"baram-term ctl: {NOT_RUNNING_MESSAGE if not instances else 'no window matches'}", file=sys.stderr)
        else:
            for instance in shown:
                print(describe(instance))
        return EXIT_OK if shown else (EXIT_NOT_RUNNING if not instances else EXIT_TARGET)

    if not instances:
        return _fail(args, EXIT_NOT_RUNNING, "not_running", NOT_RUNNING_MESSAGE)
    chosen = select(instances, args.pid, args.port, args.match)
    if len(chosen) != 1:
        if not chosen:
            message = "no baram-term window matches --pid/--port/--match. Nothing was sent. Running windows:"
            return _fail(args, EXIT_TARGET, "no_match", message, instances)
        how = "matches" if filtering else "is running; pick one with --port, --match or --pid"
        message = f"more than one baram-term window {how}. Nothing was sent. Candidates:"
        return _fail(args, EXIT_TARGET, "ambiguous", message, chosen)

    req, wait_s = _build_request(args)
    try:
        reply = chosen[0].endpoint.request(req, timeout=wait_s + DEFAULT_TIMEOUT_S)
    except (OSError, ValueError) as e:
        return _fail(args, EXIT_ERROR, "io", str(e))

    if args.json:
        print(json.dumps(reply, ensure_ascii=False))
    else:
        _print_text(reply)
        if not reply.get("ok"):
            print(f"baram-term ctl: {reply.get('error')}: {reply.get('message', '')}".rstrip(": "), file=sys.stderr)
    if reply.get("ok"):
        return EXIT_OK
    return EXIT_TIMEOUT if reply.get("error") == "timeout" else EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
