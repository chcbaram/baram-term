# 개발 환경 구축

## 필요한 것

- Python 3.12 (3.10 이상이면 동작, 개발은 3.12 기준)
- [uv](https://docs.astral.sh/uv/) — 가상환경/패키지 설치
- git, (선택) GitHub CLI `gh`

pygame-ce, numpy, pyserial 은 macOS / Windows / Linux 용 설치 파일이 있어 별도 빌드가 필요 없다.
D2Coding 폰트는 저장소에 포함돼 있어 따로 설치하지 않아도 된다.

## 저장소 받기와 가상환경

```bash
git clone https://github.com/chcbaram/baram-term.git
cd baram-term
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e "retro-ui[dev]" -e "baram-term[dev]"
```

Windows (PowerShell) 는 `.venv/bin/python` 대신 `.venv\Scripts\python.exe`, `.venv/bin/baram-term` 대신
`.venv\Scripts\baram-term.exe` 를 쓴다.

uv 가 없으면 표준 도구로 같은 환경을 만든다. 테스트까지 돌리려면 `[dev]` 를 꼭 붙인다 (빼면 pytest 가 없다).
**두 줄로 나누고 순서를 지켜야 한다** — 한 줄로 합치면 pip 이 충돌로 막는다:

```bash
python3 -m venv .venv
.venv/bin/pip install -e "baram-term[dev]"   # retro-ui 가 git URL 로 딸려온다
.venv/bin/pip install -e "retro-ui[dev]"     # 그 사본을 이 저장소 소스로 덮어쓴다
```

`baram-term` 은 retro-ui 를 git URL 로 의존한다 (PyPI 에 없는데 `pipx install` 이 되게 하려는 것).
평범한 pip 은 그 URL 과 로컬 `-e retro-ui` 를 같은 이름의 다른 소스로 보고 `ResolutionImpossible`
을 낸다. 그래서 나중 줄이 앞 줄을 덮어쓰게 나눈다. **순서를 뒤집으면 에러 없이 설치되지만**
retro-ui 가 editable 이 아니라 git 사본으로 남아, `retro-ui/src` 를 고쳐도 반영되지 않는다.
uv 는 `[tool.uv.sources]` 가 URL 을 덮어쓰므로 위쪽 명령 한 줄이면 된다.

Windows 메모 (Windows 11 에서 확인):
- `py` 런처가 없을 수 있다. 그때는 `python -m venv .venv` 로 만든다. Microsoft Store 판 Python 3.13 도 동작한다.
- 편집 가능 설치(`-e`)라서 `git pull` 만 하면 새 코드가 반영된다. `pyproject.toml` 의 의존성이 바뀌었을 때만 다시 설치한다.

> `.venv` 는 안에 절대 경로가 들어가므로 **폴더를 옮기거나 이름을 바꾸면 다시 만든다.**
> `rm -rf .venv` 후 위 설치 명령을 다시 실행.

## baram-term 실행

```bash
.venv/bin/baram-term --demo                         # 보드 없이 가짜 펌웨어(demo://)에 연결
.venv/bin/baram-term --list                         # 시리얼 포트 목록
.venv/bin/baram-term /dev/cu.usbmodemXXXX           # 실제 장치 (기본 115200)
.venv/bin/baram-term /dev/ttyUSB0 -b 921600 --lang en --font-size 16 --size 120x40
.venv/bin/baram-term                                # 포트 없이 시작 → Ctrl-A O 로 선택
```

- 같은 포트를 minicom 등 다른 프로그램이 열고 있으면 수신 데이터를 서로 나눠 가져간다. 먼저 닫는다.
- 언어: 기본은 영어. 파일 메뉴에서 한국어/English 를 고르면 저장돼 다음 실행부터 적용된다.
  `--lang ko|en` 이나 환경 변수 `BARAM_TERM_LANG` 으로도 정한다 (시스템 로케일은 보지 않는다).
- 설정 파일: macOS `~/Library/Application Support/baram-term/settings.json`, Windows `%APPDATA%\baram-term\settings.json`,
  Linux `~/.config/baram-term/settings.json`. `BARAM_TERM_CONFIG_DIR` 또는 `--config 파일` 로 바꾼다.
  동작이 이상하면 이 파일을 지우고 기본값으로 시작해 본다.
- 그래프 확인: `--demo` 로 실행 → `Ctrl-A G` (그래프 패널) → 터미널에 `plot` (Teleplot 형식), `plot arduino`, `plot off`.

## 테스트

```bash
(cd retro-ui   && ../.venv/bin/python -m pytest -q)
(cd baram-term && ../.venv/bin/python -m pytest -q)
```

- 헤드리스 테스트는 `SDL_VIDEODRIVER=dummy` 로 창 없이 돈다. CI 에서도 그대로 동작한다.
- 테스트 개수는 `python -m pytest --collect-only -q` 의 마지막 줄로 본다 ([README.md](README.md) 표를 고칠 때).
- 창 없이 확인할 수 없는 것(IME·한/영 전환, 스크롤 느낌, 화면 배율)은 실제 창에서 따로 확인한다.
- 문서 그림은 저장소 루트에서 `.venv/bin/python docs/images/make_screenshot.py docs/images/screenshot.png`,
  `.venv/bin/python docs/images/make_architecture.py docs/images/architecture.png` 로 다시 만든다.
- `retro-ui/tests/fixtures/ime_macos_2set.json` 은 실제 macOS 두벌식 입력 기록이다. IME 보정 코드를 바꾸면 이 재생 테스트가 기준이다.
- 실제 장치 CLI 재생 테스트는 로컬 기록이 있을 때만 돈다: [device-testing.md](device-testing.md).

## retro-ui 예제

```bash
cd retro-ui
../.venv/bin/python examples/hello.py              # 기본 위젯, 글자 크기 [-]/[+], Cmd/Ctrl +/-
../.venv/bin/python examples/live_plot.py          # 실시간 플롯 3개 x 시리즈 3개 (1kHz)
../.venv/bin/python examples/menu_demo.py          # 풀다운 메뉴 + 플롯 위 팝업
../.venv/bin/python examples/hello.py dos_blue     # 테마 지정: mono(기본) dos_blue amber green_phosphor mono_dark
```

### 새 OS/PC 에서 한 번씩 확인할 것

| 스크립트 | 확인 내용 |
|---|---|
| `examples/spike_hidpi.py` | 창 서피스가 실제 배율(Retina 2x 등)로 나오는지 |
| `examples/spike_font.py` | 셀 크기, 한글 폭이 영문의 2배인지 |
| `examples/spike_ime.py` | **한글 입력 이벤트 순서 기록** (수동). Windows/Linux 는 아직 기록이 없다. 결과 `_spike_out/ime_log.json` 을 `tests/fixtures/ime_<os>.json` 으로 저장해 재생 테스트를 추가한다 |
| `examples/spike_plot.py` | 플롯 렌더링 CPU 사용량 |

## 배포 파일 만들기 (PyInstaller)

파이썬을 깔지 않은 사람에게 건네는 단독 실행 파일이다. 빌드 도구는 테스트에 필요 없으므로
`[dev]` 에 넣지 않았다. 직접 만들 때만 설치한다.

```bash
uv pip install --python .venv/bin/python pyinstaller
.venv/bin/pyinstaller --noconfirm --clean baram-term/tools/baram-term.spec
```

결과는 `dist/` 에 나온다 (`.gitignore` 에 있어 커밋되지 않는다). 약 54MB 이고 대부분이 폰트다.

| OS | 결과물 | 건네는 방법 |
| --- | --- | --- |
| macOS | `dist/baram-term.app` | `.dmg` 로 묶어서 (릴리스 워크플로가 한다) |
| Windows | `dist/baram-term/` 폴더 | zip 으로 묶어서. 폴더째 풀어야 한다 |
| Linux | `dist/baram-term/` 폴더 | `.tar.gz` 로 묶어서 |

`onefile` 이 아니라 폴더로 묶는다. 한 파일로 만들면 실행할 때마다 8.1MB 폰트를 임시 폴더에
풀어서 시작이 느려진다.

**콘솔 없이 묶는다** (`console=False`). 자체 창을 띄우는 앱이라 뒤에 검은 콘솔이 따라다니면
지저분하다. 대신 셸에서 실행하면 `--list` 나 `--version` 출력이 그 셸에 나온다
(`__main__._attach_console()` 이 윈도우에서 부모 콘솔에 붙는다). 탐색기에서 더블클릭하면
붙을 콘솔이 없으므로 창만 뜬다. 시작하다 죽으면 콘솔이 없어도 알 수 있게 메시지 상자를 띄운다.

### 서명하지 않은 앱 열기

코드 서명을 하지 않는다 (Apple 계정이 연 $99). 받는 쪽에서 처음 한 번 아래처럼 연다.

- **macOS**: 더블클릭하면 "확인되지 않은 개발자" 라고 막힌다. **우클릭 > 열기** 로 한 번 열면
  그다음부터는 그냥 열린다. 안 되면 `xattr -dr com.apple.quarantine baram-term.app`.
- **Windows**: SmartScreen 이 "Windows 의 PC 보호" 를 띄운다. **추가 정보 > 실행** 을 누른다.

### 릴리스

`v` 로 시작하는 태그를 밀면 `.github/workflows/release.yml` 이 3 OS 빌드를 만들어 GitHub
릴리스에 붙인다. 태그를 만들지 않고 빌드만 시험하려면 Actions 에서 수동 실행한다
(그때는 릴리스에 올리지 않고 아티팩트로만 남는다).

```bash
git tag v0.1.0 && git push origin v0.1.0
```

## git 계정 (회사 PC 에서 개인 저장소 작업)

회사 PC 는 기본 GitHub 계정/전역 git 이메일이 회사 계정이다. **전역 설정과 `gh` 활성 계정은 바꾸지 않고**, 이 저장소에만 개인 계정을 설정한다.

```bash
# 저장소 폴더 안에서 (--local)
git config --local user.name  "Hancheol Cho"
git config --local user.email "chcbaram@gmail.com"

# gh 에 chcbaram 계정도 로그인돼 있어야 한다: gh auth login (계정 추가)
git config --local credential.https://github.com.helper ""
git config --local --add credential.https://github.com.helper \
  '!f() { test "$1" = get && echo "username=chcbaram" && echo "password=$(gh auth token -u chcbaram)"; }; f'
```

- 첫 번째 빈 helper 줄은 전역 helper 목록을 이 저장소에서만 비우는 역할이다.
- `gh auth git-credential` 은 사용자명으로 계정을 고르지 않는다 (확인함). 그래서 위처럼 토큰을 직접 넘긴다.
- `gh` 명령을 개인 계정으로 실행할 때는 전환하지 말고 `GH_TOKEN="$(gh auth token -u chcbaram)" gh ...` 처럼 명령 단위로 넘긴다.
- 확인: `printf 'protocol=https\nhost=github.com\n\n' | git credential fill` 결과의 `username=chcbaram`.

개인 PC 처럼 기본 계정이 chcbaram 이면 위 설정은 필요 없다.

## 커밋 규칙

- 커밋 메시지는 영어, 짧게 (subject + 짧은 본문). 자세한 설명은 PR 에.
- PR 설명은 한국어, 변경 전/후 대비로.
- 라이브러리(`retro-ui/`)는 앱(`baram-term/`)을 import 하지 않는다 (분리 가능 구조 유지).
- **커밋 전**: `git status --short --ignored retro-ui/tests/fixtures` 로 장치 기록(`local/`)이 무시되는지 확인한다.
