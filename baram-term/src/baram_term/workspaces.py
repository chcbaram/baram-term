"""Workspaces: one folder of settings per window, so several windows do not overwrite each other.

    <config_dir>/settings.json                 앱 전체에 한 벌인 값 (settings.GLOBAL_FIELDS)
    <config_dir>/workspaces/<이름>/settings.json   나머지 전부 (포트, 배치, 매크로, 강조 규칙 ...)
    <config_dir>/workspaces/<이름>/notes.json      메모 (앱이 설정 파일 옆에 둔다)
    <config_dir>/workspaces/<이름>/.lock           열려 있는 동안 잡고 있는 OS 파일 잠금

잠금은 pid 가 아니라 OS 파일 잠금이다. 프로세스가 죽으면 OS 가 풀어 주고, Windows 에서는
pid 로 살아 있는지 알 수 없다 (ctl.pid_alive 가 None).

전역 파일은 여러 창이 같이 쓴다. 통째로 다시 쓰면 A 가 읽은 뒤 B 가 바꾼 언어를 A 가 되돌리므로,
**이 창이 바꾼 값만** 파일을 다시 읽어 갈아끼운다.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import IO

from baram_term import settings as store
from baram_term.settings import GLOBAL_FIELDS, Settings

DEFAULT = "default"
NAME_MAX = 32
# 이름이 곧 폴더 이름이다: 세 OS 어디서도 파일 이름에 못 쓰는 글자
BAD_CHARS = '/\\:*?"<>|'
LOCK_NAME = ".lock"
# Windows 잠금(msvcrt)은 잠근 바이트를 다른 프로세스가 읽지도 못하게 한다. 앞쪽에 적은 pid 를
# 다른 창이 읽어야 하므로 (앞으로 가져오기) 파일 끝 너머의 바이트를 잠근다. 파일 끝 너머도 잠글 수 있다
LOCK_BYTE = 4096
# 릴리스 번들(tools/baram-term.spec)과 개발용 번들(-dev)이 이것으로 시작한다
BUNDLE_ID = "com.chcbaram.baram-term"
CONFIG_ENV = "BARAM_TERM_CONFIG_DIR"


def valid_name(name: str) -> bool:
    # 앞뒤 점·공백: 점으로 시작하면 숨김 폴더가 되고, Windows 는 끝의 점·공백을 말없이 떼어 낸다
    return (
        0 < len(name) <= NAME_MAX
        and not any(c in BAD_CHARS or ord(c) < 32 for c in name)
        and name.strip(". ") == name
    )


def root_dir(config_dir: Path) -> Path:
    return config_dir / "workspaces"


def names(config_dir: Path) -> list[str]:
    """있는 워크스페이스. default 가 맨 앞, 나머지는 이름순."""
    try:
        found = [p.name for p in root_dir(config_dir).iterdir() if p.is_dir() and valid_name(p.name)]
    except OSError:
        found = []
    return sorted(found, key=lambda n: (n != DEFAULT, n.casefold()))


def exists(config_dir: Path, name: str) -> bool:
    return name.casefold() in (n.casefold() for n in names(config_dir))


def ensure(config_dir: Path) -> None:
    """워크스페이스가 생기기 전의 설정을 default 로 옮긴다 (한 번만).

    원본은 지우지 않고 복사만 한다: 예전 버전으로 되돌려 실행해도 설정이 그대로 있다.
    """
    root = root_dir(config_dir)
    if root.exists():
        return
    target = root / DEFAULT
    target.mkdir(parents=True)
    for name in ("settings.json", "notes.json"):
        source = config_dir / name
        if source.exists():
            shutil.copy2(source, target / name)


def create(config_dir: Path, name: str) -> "Workspace":
    folder = root_dir(config_dir) / name
    folder.mkdir(parents=True)
    return Workspace(config_dir, name)


def duplicate(config_dir: Path, source: str, name: str) -> None:
    shutil.copytree(
        root_dir(config_dir) / source, root_dir(config_dir) / name, ignore=shutil.ignore_patterns(LOCK_NAME)
    )


def rename(config_dir: Path, old: str, new: str) -> None:
    os.rename(root_dir(config_dir) / old, root_dir(config_dir) / new)


def delete(config_dir: Path, name: str) -> None:
    shutil.rmtree(root_dir(config_dir) / name)


def unique_name(config_dir: Path, base: str) -> str:
    n = 2
    while exists(config_dir, f"{base} {n}"):
        n += 1
    return f"{base} {n}"


# ---- 잠금 ---------------------------------------------------------------


def _lock(fp: IO) -> bool:
    try:
        if os.name == "nt":
            import msvcrt

            fp.seek(LOCK_BYTE)
            msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def in_use(config_dir: Path, name: str) -> bool:
    """다른 창(또는 이 프로세스의 다른 Workspace)이 열고 있는지. 잠가 보고 바로 놓는다."""
    path = root_dir(config_dir) / name / LOCK_NAME
    try:
        fp = open(path, "a+")
    except OSError:
        return False
    try:
        return not _lock(fp)
    finally:
        fp.close()  # 닫으면 잠금도 풀린다


def holder_pid(config_dir: Path, name: str) -> int | None:
    """열고 있는 창의 pid (잠금 파일에 적어 둔 것). 모르면 None."""
    try:
        return int((root_dir(config_dir) / name / LOCK_NAME).read_text().strip())
    except (OSError, ValueError):
        return None


def bring_to_front(config_dir: Path, name: str) -> bool:
    """다른 창이 연 워크스페이스를 앞으로. 가져왔으면 True.

    macOS: 앞에 있는 앱(방금 메뉴를 누른 이 창)이 다른 앱을 활성화하는 것은 허락된다. 그래서 이쪽에서 한다.
    Windows/Linux: 창은 스스로만 앞으로 나올 수 있다. ctl 소켓으로 그 창에 부탁한다 (그 창의 외부 제어가
    꺼져 있으면 못 한다). Windows 는 앞에 있는 프로세스가 먼저 허락(AllowSetForegroundWindow)해야 통한다.
    Linux Wayland 는 다른 창이 앞으로 나오는 것 자체를 막는 경우가 많다.
    """
    pid = holder_pid(config_dir, name)
    if pid is None or pid == os.getpid():
        return False
    if sys.platform == "darwin":
        return _activate_mac(pid)
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.AllowSetForegroundWindow(pid)
        except (OSError, AttributeError):
            pass
    return _ask_to_raise(pid)


def _ask_to_raise(pid: int) -> bool:
    from baram_term import ctl

    for endpoint in ctl.endpoints():
        if endpoint.pid != pid:
            continue
        try:
            reply = endpoint.request({"cmd": "raise"}, timeout=ctl.PROBE_TIMEOUT_S)
        except (OSError, ValueError):
            return False
        return bool(reply.get("ok")) and bool(reply.get("raised"))
    return False


def _activate_mac(pid: int) -> bool:
    """NSRunningApplication(pid).activate. pyobjc 없이 objc 런타임을 ctypes 로 부른다."""
    import ctypes
    import ctypes.util

    try:
        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    except OSError:
        return False
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    # objc_msgSend 는 부르는 메서드의 모양대로 불러야 한다 (arm64 는 가변 인자로 부르면 값이 깨진다)
    address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
    lookup = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)(address)
    activate = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(address)
    running = objc.objc_getClass(b"NSRunningApplication")
    if not running:
        return False
    app = lookup(running, objc.sel_registerName(b"runningApplicationWithProcessIdentifier:"), pid)
    if not app:
        return False
    ignoring_other_apps = 1 << 1  # NSApplicationActivateIgnoringOtherApps
    return bool(activate(app, objc.sel_registerName(b"activateWithOptions:"), ignoring_other_apps))


class Workspace:
    def __init__(self, config_dir: Path, name: str):
        self.config_dir = config_dir
        self.name = name
        self._lock_fp: IO | None = None
        self._global_seen: dict[str, object] = {}

    @property
    def folder(self) -> Path:
        return root_dir(self.config_dir) / self.name

    @property
    def settings_path(self) -> Path:
        return self.folder / "settings.json"

    @property
    def global_path(self) -> Path:
        return self.config_dir / "settings.json"

    # ---- 잠금 ----

    def acquire(self) -> bool:
        """잡으면 True. 다른 창이 열고 있으면 False."""
        if self._lock_fp is not None:
            return True
        self.folder.mkdir(parents=True, exist_ok=True)
        fp = open(self.folder / LOCK_NAME, "a+")
        if not _lock(fp):
            fp.close()
            return False
        fp.seek(0)
        fp.truncate()
        fp.write(str(os.getpid()))  # 사람이 볼 때 참고용. 판단은 잠금으로만 한다
        fp.flush()
        self._lock_fp = fp
        return True

    def release(self) -> None:
        if self._lock_fp is not None:
            self._lock_fp.close()
            self._lock_fp = None

    def rename(self, new: str) -> None:
        """이 창이 연 워크스페이스의 이름 바꾸기. Windows 는 열린 파일이 있는 폴더를 못 옮겨서 잠금을 잠깐 놓는다."""
        held = self._lock_fp is not None
        self.release()
        try:
            rename(self.config_dir, self.name, new)
            self.name = new
        finally:
            if held:
                self.acquire()

    # ---- 설정 ----

    def load(self) -> tuple[Settings, str | None]:
        """전역 파일의 전역 값 + 워크스페이스 파일의 나머지."""
        global_raw, global_error = store.read_raw(self.global_path)
        local_raw, local_error = store.read_raw(self.settings_path)
        merged = {k: v for k, v in local_raw.items() if k not in GLOBAL_FIELDS}
        merged.update({k: v for k, v in global_raw.items() if k in GLOBAL_FIELDS})
        settings = store.from_dict(merged)
        self._global_seen = {k: getattr(settings, k) for k in GLOBAL_FIELDS}
        return settings, local_error or global_error

    def save(self, settings: Settings) -> None:
        values = asdict(settings)
        store.write_raw({k: v for k, v in values.items() if k not in GLOBAL_FIELDS}, self.settings_path)
        changed = {k: values[k] for k in GLOBAL_FIELDS if self._global_seen.get(k) != values[k]}
        if not changed:
            return
        # 다른 창이 그사이 바꾼 값은 두고, 이 창이 바꾼 값만 갈아끼운다.
        # 워크스페이스 전의 값들(포트 등)도 그대로 둔다: 예전 버전으로 실행해도 설정이 남아 있게
        current, _error = store.read_raw(self.global_path)
        current.update(changed)
        store.write_raw(current, self.global_path)
        self._global_seen.update(changed)


# ---- 새 인스턴스 ----------------------------------------------------------


def launch_command(name: str) -> list[str]:
    """이 워크스페이스로 baram-term 을 하나 더 띄우는 명령."""
    if sys.platform == "darwin":
        # macOS 는 open(LaunchServices)으로 띄워야 새 창이 앞으로 나오고 Dock 에 baram-term 으로 뜬다.
        # 실행 파일을 직접 부르면 다른 창 뒤에 깔리고 Dock 에는 Python 으로 떠서, 열렸는지도 알기 어렵다
        exe = Path(sys.executable)
        bundle = next((p for p in exe.parents if p.suffix == ".app"), None) if getattr(sys, "frozen", False) else None
        # Dock 에서 띄운 개발용 번들: 실행 파일은 venv 의 파이썬이라 번들을 경로로 못 찾고, 번들 ID 로 찾는다
        # (LaunchServices 가 넣어 주는 값. 터미널에서 실행하면 그 터미널 앱의 ID 라 우리 것인지 확인한다)
        bundle_id = os.environ.get("__CFBundleIdentifier", "")
        target = ["-n", str(bundle)] if bundle is not None else (
            ["-n", "-b", bundle_id] if bundle_id.startswith(BUNDLE_ID) else None
        )
        if target is not None:
            env = ["--env", f"{CONFIG_ENV}={os.environ[CONFIG_ENV]}"] if os.environ.get(CONFIG_ENV) else []
            return ["open", *target, *env, "--args", "--workspace", name]  # open 은 환경 변수를 넘기지 않는다
    if getattr(sys, "frozen", False):
        return [sys.executable, "--workspace", name]
    return [sys.executable, "-m", "baram_term", "--workspace", name]


def launch(name: str) -> None:
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        # 이 창을 닫아도 새 창이 같이 죽지 않게
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(launch_command(name), **kwargs)
