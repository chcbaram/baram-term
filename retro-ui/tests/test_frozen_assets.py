"""PyInstaller 로 묶었을 때 폰트를 찾는 경로.

동결한 실행 파일은 데이터 파일이 __file__ 옆이 아니라 sys._MEIPASS 아래에 풀린다.
이 분기가 틀어지면 묶은 앱이 D2Coding 을 못 찾아 창도 못 띄우고 죽는다 - 로컬에서는
절대 재현되지 않는 종류의 고장이라 여기서 지킨다.
"""

import os
import sys

from retroui.render import fonts


def test_normal_run_uses_the_package_folder():
    assert not hasattr(sys, "_MEIPASS")  # 동결되지 않은 상태가 기본
    path = fonts._asset_dir()
    assert path.endswith(os.path.join("retroui", "assets", "fonts"))
    assert os.path.isdir(path), "번들 폰트 폴더가 패키지 안에 있어야 한다"


def test_frozen_run_looks_under_meipass(monkeypatch):
    monkeypatch.setattr(sys, "_MEIPASS", os.path.join("tmp", "frozen"), raising=False)
    assert fonts._asset_dir() == os.path.join("tmp", "frozen", "retroui", "assets", "fonts")


def test_module_level_dir_matches_the_helper():
    # _ASSET_DIR 은 import 시점에 한 번 계산된다. 검색 경로의 첫 항목이라 어긋나면 안 된다
    assert fonts._ASSET_DIR == fonts._asset_dir()
    assert fonts._SEARCH_DIRS[0] == fonts._ASSET_DIR


def test_bundled_font_is_actually_there():
    """spec 이 넣어야 할 파일. 이름이 바뀌면 --add-data 도 같이 바뀌어야 한다."""
    names = os.listdir(fonts._ASSET_DIR)
    assert any(n.startswith("D2Coding") and n.endswith(".ttc") for n in names), names
    assert "D2Coding-OFL.txt" in names  # OFL 폰트라 라이선스 문서도 함께 배포한다
