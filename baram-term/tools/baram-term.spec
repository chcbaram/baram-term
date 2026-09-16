# -*- mode: python ; coding: utf-8 -*-
"""baram-term 을 단독 실행 파일로 묶는다.

    uvx pyinstaller --noconfirm baram-term/tools/baram-term.spec

정한 것과 그 이유:
- **onedir** (COLLECT). onefile 은 실행할 때마다 8.1MB D2Coding 을 임시 폴더에 풀어서
  시작이 눈에 띄게 느려진다. 폴더째 배포하고 압축은 릴리스에서 한다.
- **console=False**. 자체 창을 띄우는 앱이라 뒤에 검은 콘솔이 따라다니면 지저분하다.
  대신 셸에서 실행했을 때의 --list/--version 출력은 __main__._attach_console() 이 살린다
  (윈도우는 부모 콘솔에 붙고, 붙을 콘솔이 없으면 조용히 버린다).
- **데이터 두 가지는 반드시 넣는다.** 런타임에 파일로 읽는 것은 이 둘뿐이다
  (retroui/render/fonts.py 의 _asset_dir, baram_term/i18n.py 의 importlib.resources).
  로고 PNG 는 도트가 logo.py 에 값으로 박혀 있어 넣지 않아도 된다.
"""

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).resolve().parents[1]  # baram-term/tools -> 저장소 루트

# 번들 폰트: sys._MEIPASS/retroui/assets/fonts 에 풀려야 한다 (fonts._asset_dir 가 그 경로를 본다)
datas = collect_data_files("retroui", includes=["assets/fonts/*"])
# 메시지 카탈로그: importlib.resources.files("baram_term") / "locales" 로 읽는다
datas += collect_data_files("baram_term", includes=["locales/*.json"])

# pyserial 은 백엔드와 URL 핸들러를 이름으로 import 해서 정적 분석이 따라가지 못한다.
# 빠지면 --list 가 포트를 못 찾고 demo:// socket:// 같은 URL 이 열리지 않는다.
hiddenimports = [
    "serial.tools.list_ports",
    "serial.urlhandler.protocol_alt",
    "serial.urlhandler.protocol_hwgrep",
    "serial.urlhandler.protocol_loop",
    "serial.urlhandler.protocol_rfc2217",
    "serial.urlhandler.protocol_socket",
    "serial.urlhandler.protocol_spy",
]

a = Analysis(
    [str(ROOT / "baram-term" / "src" / "baram_term" / "__main__.py")],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],  # 쓰지 않는다. 넣으면 용량만 커진다
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="baram-term",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX 는 압축 실행 파일을 백신이 자주 오탐한다
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="baram-term",
)

if sys.platform == "darwin":
    # .app 번들. 서명은 하지 않는다 - 받는 쪽은 처음 한 번 우클릭 > 열기 로 연다
    app = BUNDLE(
        coll,
        name="baram-term.app",
        icon=None,
        bundle_identifier="com.chcbaram.baram-term",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,  # 없으면 Retina 에서 2배 확대돼 흐려진다
        },
    )
