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

> `.venv` 는 안에 절대 경로가 들어가므로 **폴더를 옮기거나 이름을 바꾸면 다시 만든다.**
> `rm -rf .venv` 후 위 두 줄을 다시 실행.

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
