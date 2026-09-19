"""Local control socket: lets other tools send lines through the port baram-term holds.

창마다 자기 소켓(~/.baram-term/ctl/<pid>.sock, Windows 는 <pid>.json 에 적힌 TCP 포트)을 연다.
여러 창 중 하나를 고르는 일은 클라이언트(ctl.py)가 status 로 받은 포트/USB 정보를 보고 한다.

포트를 넘겨주지 않고, 외부 도구(`baram-term ctl`, 다른 Claude 세션 등)가 baram-term 을 거쳐 명령을 보내고
받은 내용을 읽는다. 보낸 명령과 장치의 응답은 평소처럼 터미널에도 보인다.

- 수신 기록(RxHistory)은 UI 스레드가 `_on_rx` 에서 채우고, 연결 스레드는 조건 변수로 기다린다.
  기다리는 동안 UI 를 막지 않는다.
- 포트에 쓰기·상태 읽기·닫고 열기는 UI 스레드에서 한다 (`run_on_ui`). 앱 상태를 한 스레드만 만진다.
- 연결 하나에 JSON 한 줄 요청을 여러 개 보내도 되지만, `baram-term ctl` 은 요청마다 새로 붙는다.

마크(mark)는 지금까지 받은 글자 수다. 응답마다 현재 마크를 돌려주므로 `read --since`, `wait --since` 로
그 뒤에 받은 것만 볼 수 있다 (보드를 리셋하기 전에 마크를 잡아 두면 부팅 메시지를 놓치지 않는다).
"""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import threading
import time
from typing import Any, Callable

from baram_term.ctl import USE_TCP, clean, ctl_dir, endpoint_file, endpoints, pid_alive

# 수신 기록에 남기는 글자 수. 넘으면 오래된 것부터 버린다 (한 번에 절반씩 잘라 매번 복사하지 않는다)
HISTORY_CHARS = 1_000_000
MAX_REQUEST_BYTES = 1 << 20
MAX_TIMEOUT_S = 600.0
# ctl 은 요청마다 붙었다 끊긴다. 끊긴 뒤에도 잠시 상태줄 표시를 남겨야 사용자가 알아챈다
ACTIVE_HOLD_S = 3.0
# USB 정보(list_ports)는 포트를 훑느라 수십 ms 걸린다. ctl 은 명령마다 status 로 창을 고르므로 잠시 기억한다
USB_INFO_TTL_S = 5.0


class CtlError(Exception):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code
        self.message = message


class RxHistory:
    """받은 글자를 그대로 모아 둔다. 위치(마크)는 처음부터 센 글자 수라 잘라내도 변하지 않는다."""

    def __init__(self, limit: int = HISTORY_CHARS):
        self.limit = limit
        self._cv = threading.Condition()
        self._text = ""
        self._start = 0  # _text[0] 의 마크

    @property
    def end(self) -> int:
        with self._cv:
            return self._start + len(self._text)

    def feed(self, text: str) -> None:
        if not text:
            return
        with self._cv:
            self._text += text
            if len(self._text) > 2 * self.limit:
                cut = len(self._text) - self.limit
                self._text = self._text[cut:]
                self._start += cut
            self._cv.notify_all()

    def since(self, mark: int) -> tuple[str, int, bool]:
        """(mark 뒤의 글자, 현재 끝 마크, 잘려서 앞부분이 빠졌는지)."""
        with self._cv:
            return self._since(mark)

    def _since(self, mark: int) -> tuple[str, int, bool]:
        end = self._start + len(self._text)
        truncated = mark < self._start
        mark = min(max(mark, self._start), end)
        return self._text[mark - self._start :], end, truncated

    def last_lines(self, n: int) -> tuple[str, int]:
        with self._cv:
            text = self._text
            end = self._start + len(text)
        if n <= 0:
            return "", end
        pos = len(text)
        if text.endswith("\n"):
            pos -= 1
        for _ in range(n):
            pos = text.rfind("\n", 0, pos)
            if pos < 0:
                return text, end
        return text[pos + 1 :], end

    def wait_for(
        self, pattern: re.Pattern[str], mark: int, timeout: float, stop: threading.Event | None = None
    ) -> tuple[bool, str, int, bool]:
        """mark 뒤에 받은 글자(ANSI/CR 을 뺀 것)에서 pattern 을 찾을 때까지 기다린다.

        (찾았는지, mark 뒤의 글자 원본, 끝 마크, 잘렸는지).
        """
        deadline = time.monotonic() + timeout
        with self._cv:
            while True:
                text, end, truncated = self._since(mark)
                if pattern.search(clean(text)):
                    return True, text, end, truncated
                remaining = deadline - time.monotonic()
                if remaining <= 0 or (stop is not None and stop.is_set()):
                    return False, text, end, truncated
                self._cv.wait(min(remaining, 0.5))

    def wake(self) -> None:
        with self._cv:
            self._cv.notify_all()


def _compile(pattern: Any) -> re.Pattern[str]:
    if not isinstance(pattern, str) or not pattern:
        raise CtlError("bad_request", "until must be a non-empty regex")
    try:
        return re.compile(pattern, re.MULTILINE)
    except re.error as e:
        raise CtlError("bad_regex", f"{pattern!r}: {e}") from e


def _timeout(req: dict[str, Any]) -> float:
    value = req.get("timeout", 5.0)
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise CtlError("bad_request", "timeout must be a non-negative number")
    return min(float(value), MAX_TIMEOUT_S)


def _mark(req: dict[str, Any], key: str) -> int | None:
    value = req.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CtlError("bad_request", f"{key} must be a non-negative integer")
    return value


class ControlServer:
    """제어 소켓을 열고 요청을 처리한다.

    ui(cmd, req) 는 UI 스레드에서 불린다 (status / send / release / resume). send 는 {"mark": 보내기 직전 마크}
    를 돌려준다. run_on_ui(fn) 은 fn 을 UI 스레드에서 돌리고 결과를 돌려준다.
    on_change() 는 연결 수가 바뀌면 (연결 스레드에서) 불린다.
    describe_port(path) 는 포트의 USB 정보(dict 또는 None)를 돌려준다 (연결 스레드에서 불린다).
    """

    def __init__(
        self,
        history: RxHistory,
        ui: Callable[[str, dict[str, Any]], dict[str, Any]],
        run_on_ui: Callable[[Callable[[], Any]], Any],
        on_change: Callable[[], None] = lambda: None,
        describe_port: Callable[[str], dict[str, Any] | None] = lambda _path: None,
    ):
        self.history = history
        self._ui = ui
        self._run_on_ui = run_on_ui
        self._on_change = on_change
        self._describe_port = describe_port
        self._usb_cache: tuple[str, float, dict[str, Any] | None] = ("", 0.0, None)
        self._path = None
        self._stop = threading.Event()
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._clients = 0
        self._last_activity = 0.0
        self.token = ""
        self.address = ""

    # ---- lifecycle ------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._sock is not None

    @property
    def clients(self) -> int:
        return self._clients

    @property
    def active(self) -> bool:
        """연결이 있거나 방금 요청이 있었다 (상태줄 표시용)."""
        return self._clients > 0 or time.monotonic() - self._last_activity < ACTIVE_HOLD_S

    def start(self) -> None:
        """소켓을 못 열면 OSError."""
        if self.running:
            return
        directory = ctl_dir()
        directory.mkdir(parents=True, exist_ok=True)
        if not USE_TCP:
            os.chmod(directory.parent, 0o700)
            os.chmod(directory, 0o700)
            for ep in endpoints():  # 비정상 종료한 창이 남긴 소켓 (Windows 는 ctl list 가 붙어 보고 지운다)
                if pid_alive(ep.pid) is False:
                    try:
                        ep.path.unlink()
                    except OSError:
                        pass
        # 한 프로세스에 창이 둘이면(테스트) <pid>-1 처럼 번호를 붙인다
        n = 0
        while endpoint_file(os.getpid(), n).exists():
            n += 1
        self._path = endpoint_file(os.getpid(), n)
        sock = self._open_tcp(self._path) if USE_TCP else self._open_unix(self._path)
        sock.settimeout(0.5)
        self._stop.clear()
        self._sock = sock
        self._thread = threading.Thread(target=self._accept_loop, name="baram-ctl", daemon=True)
        self._thread.start()

    def _open_unix(self, path) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        old_umask = os.umask(0o177)  # 만들어지는 순간부터 0600
        try:
            sock.bind(str(path))
        finally:
            os.umask(old_umask)
        os.chmod(path, 0o600)
        sock.listen(4)
        self.address = str(path)
        return sock

    def _open_tcp(self, path) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(4)
        self.token = secrets.token_hex(16)
        port = sock.getsockname()[1]
        path.write_text(json.dumps({"port": port, "token": self.token, "pid": os.getpid()}), encoding="utf-8")
        self.address = f"127.0.0.1:{port}"
        return sock

    def stop(self) -> None:
        if self._sock is None:
            return
        self._stop.set()
        self.history.wake()  # 기다리던 wait 요청을 깨운다
        try:
            self._sock.close()
        except OSError:
            pass
        if self._thread is not None and self._thread is not threading.current_thread():
            self._thread.join(timeout=1.0)
        self._sock = None
        self._thread = None
        if self._path is not None:
            try:
                self._path.unlink()
            except OSError:
                pass
            self._path = None

    # ---- connections ----------------------------------------------------

    def _accept_loop(self) -> None:
        sock = self._sock
        while not self._stop.is_set() and sock is not None:
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self._serve, args=(conn,), name="baram-ctl-conn", daemon=True).start()

    def _set_clients(self, delta: int) -> None:
        with self._lock:
            self._clients += delta
            self._last_activity = time.monotonic()
        self._on_change()

    def _serve(self, conn: socket.socket) -> None:
        self._set_clients(+1)
        try:
            conn.settimeout(None)
            reader = conn.makefile("rb")
            while not self._stop.is_set():
                line = reader.readline(MAX_REQUEST_BYTES)
                if not line:
                    return
                reply = self.handle_line(line)
                conn.sendall(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
        except OSError:
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            self._set_clients(-1)

    def handle_line(self, line: bytes) -> dict[str, Any]:
        try:
            req = json.loads(line.decode("utf-8"))
            if not isinstance(req, dict):
                raise ValueError("request must be a JSON object")
        except ValueError as e:
            return {"ok": False, "error": "bad_request", "message": str(e)}
        cmd = req.get("cmd")
        if USE_TCP and not secrets.compare_digest(str(req.get("token", "")), self.token):
            return {"ok": False, "cmd": cmd, "error": "denied", "message": "bad token"}
        try:
            reply = self.handle(req)
        except CtlError as e:
            reply = {"ok": False, "error": e.code, "message": e.message}
        except TimeoutError:
            reply = {"ok": False, "error": "busy", "message": "baram-term window did not respond"}
        except Exception as e:  # 요청 하나가 서버를 죽이지 않게
            reply = {"ok": False, "error": "internal", "message": f"{type(e).__name__}: {e}"}
        reply.setdefault("cmd", cmd)
        reply.setdefault("mark", self.history.end)
        return reply

    # ---- commands -------------------------------------------------------

    def handle(self, req: dict[str, Any]) -> dict[str, Any]:
        cmd = req.get("cmd")
        with self._lock:
            self._last_activity = time.monotonic()
        if cmd in ("status", "release", "resume"):
            result = self._run_on_ui(lambda: self._ui(cmd, req))
            return {"ok": True, "pid": os.getpid(), **result, "usb": self._usb_info(result.get("port", ""))}
        if cmd == "send":
            return self._send(req)
        if cmd == "read":
            return self._read(req)
        if cmd == "wait":
            return self._wait(req)
        raise CtlError("bad_request", f"unknown command {cmd!r}")

    def _usb_info(self, port: str) -> dict[str, Any] | None:
        if not port:
            return None
        cached_port, at, info = self._usb_cache
        if cached_port == port and time.monotonic() - at < USB_INFO_TTL_S:
            return info
        try:
            info = self._describe_port(port)
        except Exception:  # 정보를 못 얻어도 status 는 돌려준다
            info = None
        self._usb_cache = (port, time.monotonic(), info)
        return info

    def _output(self, req: dict[str, Any], text: str) -> str:
        return text if req.get("raw") else clean(text)

    def _send(self, req: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(req.get("text"), str):
            raise CtlError("bad_request", "text must be a string")
        if req.get("eol") not in (None, "cr", "lf", "crlf", "none"):
            raise CtlError("bad_request", "eol must be cr, lf, crlf or none")
        pattern = _compile(req["until"]) if req.get("until") is not None else None
        timeout = _timeout(req)  # 보내기 전에 인자를 다 확인한다: 보낸 뒤 오류가 나면 되돌릴 수 없다
        sent = self._run_on_ui(lambda: self._ui("send", req))
        mark = sent["mark"]
        if pattern is None:
            return {"ok": True, "sent": sent.get("sent", ""), "mark": self.history.end, "start": mark}
        found, text, end, truncated = self.history.wait_for(pattern, mark, timeout, self._stop)
        reply = {"ok": found, "sent": sent.get("sent", ""), "output": self._output(req, text), "mark": end, "start": mark}
        if truncated:
            reply["truncated"] = True
        if not found:
            reply.update(error="timeout", message=f"no match for {req['until']!r} within {timeout:g}s")
        return reply

    def _read(self, req: dict[str, Any]) -> dict[str, Any]:
        since = _mark(req, "since")
        if since is not None:
            text, end, truncated = self.history.since(since)
            reply = {"ok": True, "output": self._output(req, text), "mark": end}
            if truncated:
                reply["truncated"] = True
            return reply
        last = req.get("last", 50)
        if not isinstance(last, int) or isinstance(last, bool) or last < 0:
            raise CtlError("bad_request", "last must be a non-negative integer")
        text, end = self.history.last_lines(last)
        return {"ok": True, "output": self._output(req, text), "mark": end}

    def _wait(self, req: dict[str, Any]) -> dict[str, Any]:
        pattern = _compile(req.get("until"))
        timeout = _timeout(req)
        since = _mark(req, "since")
        mark = self.history.end if since is None else since
        found, text, end, truncated = self.history.wait_for(pattern, mark, timeout, self._stop)
        reply = {"ok": found, "output": self._output(req, text), "mark": end, "start": mark}
        if truncated:
            reply["truncated"] = True
        if not found:
            reply.update(error="timeout", message=f"no match for {req['until']!r} within {timeout:g}s")
        return reply
