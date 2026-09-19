# baram-term 작업 문서

다른 PC나 새 세션에서 작업을 이어가기 위한 기준 문서입니다. 코드와 어긋나면 코드가 맞고, 이 문서를 고칩니다.

## 저장소 한눈에 보기

```
baram-term/                 GitHub: https://github.com/chcbaram/baram-term
├── retro-ui/               라이브러리 (배포 이름 retro-ui, import retroui) — 나중에 별도 저장소로 분리 가능
│   ├── src/retroui/
│   ├── tests/              pytest (헤드리스 포함). tests/fixtures/local/ 은 git 제외 (장치 기록)
│   ├── tools/              record_cli_session.py (실제 장치 CLI 기록)
│   └── examples/           hello / live_plot / menu_demo / spike_*
├── baram-term/             앱 (import baram_term, 실행 명령 baram-term)
│   ├── src/baram_term/
│   └── tests/
└── docs/                   이 문서들
```

- **retro-ui**: 겉보기는 TUI(글자 격자, 박스 문자)인데 그래프는 실제 픽셀로 그리는 파이썬 GUI 라이브러리. pygame-ce 기반, Qt 없음.
- **baram-term**: retro-ui 로 만든 펌웨어 CLI 시리얼 터미널 (minicom 대체).

## 현재 상태 (2026-09-16 기준, `0b2e34f`, [v0.1.1](https://github.com/chcbaram/baram-term/releases/tag/v0.1.1))

| 영역 | 상태 |
|---|---|
| retro-ui 코어/위젯 (렌더러, 이벤트 루프, 레이아웃, 테마, HiDPI, 한글 IME, 메뉴/팝업/대화상자, 툴팁) | 완료 |
| retro-ui 추가 위젯 (Terminal, LivePlot + PlotLegend, ListView, FileDialog, EditableComboBox, Link, VSplit, 기본 문자열 ko/en) | 완료 |
| baram-term 기본기 (연결/자동 재연결, 설정 저장, 포트 설정 + 상태줄 빠른 전환, 로그 저장, 스크롤백 찾기, Tab 자동완성, 줄끝 코드) | 완료, 실제 보드 확인 |
| baram-term 그래프 패널 (`>name:value` / Arduino 플로터 형식, 범례, STOP/지우기, 시간 폭, 경계 끌기, 값 줄 숨기기) | 완료, 실제 보드 확인 |
| baram-term HEX 보기 (`Ctrl-A H`, 오른쪽 패널, RX/TX 바이트, 바이트 선택·설명 줄·복사, 정지/지우기, 좌우 경계 끌기) | 완료, 헤드리스 확인 |
| baram-term 강조 규칙 (보기 메뉴, 정규식 + 색 + 굵게, 미리보기, 설정 저장) | 완료, 헤드리스 확인 |
| baram-term 메모 탭 (오른쪽 패널 탭, 여러 줄 편집, 줄/선택/전체 보내기, `#wait`, 내보내기/가져오기) | 완료, 헤드리스 확인 |
| baram-term 매크로 막대 (F 키 선택·전송, 오른쪽 클릭 수정/삭제, `+` 등록, 이름 줄임, hover 툴팁) | 완료, macOS 실제 창 확인 |
| 입력 (터미널 영문 입력 기본 켜짐, Shift+Space 한/영 전환 때 스페이스 안 찍힘, 휠이 OS 방향·속도를 따름) | 완료, macOS 실제 창 확인 |
| 메뉴·언어 (파일 메뉴 맨 앞, 화면 언어 기본 영어·파일 메뉴에서 선택) | 완료, 헤드리스 확인 |
| baram-term 포트 설정 (꽂힌 포트만 목록, 목록↔주소 일치, 속도 직접 입력·기억 8개) | 완료, 실제 창 확인 |
| baram-term 외부 제어 (`baram-term ctl`, 창마다 제어 소켓, 여러 창 고르기, Claude Code 플러그인·스킬) | 완료, 실제 보드(ST-LINK VCP, macOS)에서 list·status·send·리셋 후 wait/read 확인 |
| 배포 (pipx/pip 설치, PyInstaller 3 OS, GitHub Actions CI·릴리스) | 완료. [v0.1.1](https://github.com/chcbaram/baram-term/releases/tag/v0.1.1) 에 macOS `.dmg` / Windows zip / Linux `.tar.gz` |
| Windows 11 | 실행·스크롤·**파일 메뉴 언어 전환 확인 완료**. 글자 선명도(DPI)는 **확인 대기** |
| Linux | 직접 실행해 본 적 없음 (CI 에서 테스트만 통과) |
| 다음 | 줄 단위 입력창 (보조) — [roadmap.md](roadmap.md) 의 마지막 남은 항목. 전송률 미니 그래프는 뒤로 미룸 |
| 테스트 | retro-ui 323개, baram-term 295개 (+ 로컬 장치 기록이 있으면 재생 테스트) |

## 이어서 할 때 먼저 볼 것 (2026-09-16)

### 확인 대기 (사용자가 실제 창에서)

- **게시된 산출물을 아직 아무도 실행해 보지 않았다.** 로컬에서 만든 빌드는 확인했지만,
  릴리스에 붙은 `.dmg`/zip/`.tar.gz` 는 받아서 열어 본 적이 없다. 서명이 없어 첫 실행은
  macOS 우클릭>열기 / Windows 추가 정보>실행 이 필요하다.
- **Windows**: 화면 배율 125%·150% 에서 글자가 선명한지 (DPI 힌트, `03a880a`).
  (파일 메뉴 언어 전환은 확인 완료 — 2026-09-16)
- 오래전부터 남은 것: 실제 창에서 손가락 커서(링크/상태줄 항목)와 ↕ 커서(터미널/그래프 경계) 모양,
  연결된 상태에서 상태줄로 속도만 바꿀 때 실제 보드가 끊기지 않는지.

### 결정 대기

- **Windows 휠 한 칸의 줄 수**: 지금 3줄 고정 (`Terminal.wheel_lines`). Windows 는 사용자가 줄 수를 바꿀 수
  있으니 시스템 설정값(`SPI_GETWHEELSCROLLLINES`, ctypes 로 읽음)을 쓰는 편이 정확하다.
  사용자는 Windows 에서 스크롤이 괜찮다고 했으니 급하지 않다.
- **Linux AppImage**: 지금은 onedir 를 `.tar.gz` 로 낸다. AppImage 는 `appimagetool` + AppDir 배치 +
  `.desktop` 파일이 따로 필요해 미뤘다 ([roadmap.md](roadmap.md) 개선 메모).
- **커스텀 속도 관리 창**: 지금은 쓰면 자동으로 8개까지 기억만 한다. 목록이 지저분해져 지우고
  싶어지면 그때 추가/삭제 창을 만든다.
- **retro-ui 를 PyPI 에 올릴지**: 올리면 baram-term 의 git URL 의존을 버전 의존으로 바꿀 수 있고,
  그래야 baram-term 도 PyPI 에 올릴 수 있다 (PyPI 는 직접 URL 참조를 거부한다).

### 알아 둘 것

- 설정 파일은 PC 마다 따로다. 예전 버전으로 실행한 PC 는 `plot_hide_lines` 가 `true` 로 남아 있을 수 있고
  (예전 기본값), `--lang ko` 로 실행한 적이 있으면 `lang` 이 `ko` 로 저장돼 한국어로 시작한다. 메뉴에서 한 번 바꾸면 된다.
- 매크로는 `"F5|이름=명령"` 형식으로 저장된다. `F<번호>|` 없이 손으로 적어도 남는 번호를 붙여 준다. F10 은 메뉴 키라 쓰지 않는다.
- 배너 로고는 `baram-term/src/baram_term/assets/baram-logo.png` 의 "BARAM" 글자를 2배로 줄인 도트다.
  바꾸려면 `baram-term/tools/logo_from_image.py` (정수 배율만: 어중간하면 A·M 대칭이 깨진다).
- 문서 그림(`docs/images/*.png`)은 손으로 캡쳐하지 않고 `docs/images/make_*.py` 로 만든다. 화면이 바뀌면 다시 돌린다.
- 이번 작업의 결정과 이유는 [decisions.md](decisions.md) 의 "2026-09-15 매크로 막대와 저장소 소개" 이후에 있다.

## 작업 방식 (Claude Code 와 작업할 때)

Claude 의 메모리는 PC 마다 따로라서, 이어서 작업할 때 지킬 것을 여기에 적어 둔다.

- 화면 배치가 바뀌는 요청은 **코드 전에 글자 스케치로 먼저 확인**받는다 (배치를 만들고 바로 뒤집는 왕복을 줄이려고).
- 요청에 이상하거나 중복되는 점, 이전 결정과 부딪히는 점이 있으면 구현하면서 짧게 **피드백**하고 추천안을 낸다.
- 커밋/푸시는 요청할 때만. 커밋 메시지는 영어, Claude 서명(Co-Authored-By) 없음.
- 커밋 전에 회사 식별자 검색과 `retro-ui/tests/fixtures/local/` 무시 여부를 확인한다 (아래 ⚠).
- 화면 확인은 창을 띄우지 않고 헤드리스로 그린다: `SDL_VIDEODRIVER=dummy` 로 앱을 만들고 `pygame.image.save(app.surface, ...)`.
- 두 패키지 테스트를 동시에(병렬로) 돌리면 결과 출력이 섞여 보인 적이 있다. 한 명령에서 순서대로 돌린다.
- 커밋은 주제별로 나눈다. 한 파일에 두 주제가 섞이면 파일 안에서 나눠 따로 커밋한다.
- 창 없이 확인할 수 없는 것(IME·한/영 전환, 스크롤 느낌, Windows 화면 배율)은 헤드리스 테스트 뒤에
  **사용자에게 실제 창 확인을 요청**하고, 확인받기 전에는 문서에 "확인 대기" 로 적는다.
- Windows 확인은 사용자가 Windows PC 에서 `git pull` 로 받아 직접 한다. 원격 접속으로 파일을 옮기는 것은
  Claude Code 자동 권한 검사에 막혔다. PC 주소·계정·비밀번호는 문서나 메모리에 남기지 않는다.
- 테스트 개수는 `python -m pytest --collect-only -q` 로 확인해 위 표를 고친다.

## 문서 목록

| 문서 | 내용 |
|---|---|
| [dev-setup.md](dev-setup.md) | 새 PC 환경 구축, 실행/테스트, git 계정 설정 |
| [roadmap.md](roadmap.md) | 완료한 것, 다음에 할 일 (순서대로) |
| [architecture.md](architecture.md) | retro-ui 내부 구조 |
| [decisions.md](decisions.md) | 주요 결정과 이유 (실측값 포함) |
| [baram-term-spec.md](baram-term-spec.md) | baram-term 기능 명세와 화면 구성 |
| [firmware-cli.md](firmware-cli.md) | 대상 펌웨어 CLI 프로토콜 (공개 펌웨어 기준) |
| [external-control.md](external-control.md) | 외부 제어 (`baram-term ctl`, 제어 소켓, 여러 창 고르기) 와 Claude Code 플러그인 |
| [device-testing.md](device-testing.md) | 실제 장치 CLI 기록과 재생 테스트, **장치 정보 비공개 규칙** |

## 새 PC 에서 이어서 하기

1. [dev-setup.md](dev-setup.md) 대로 저장소를 받고 환경을 만든다.
2. 두 패키지 테스트가 모두 통과하는지 확인한다.
3. `baram-term --demo` 로 보드 없이 실행해 본다.
4. 위 "이어서 할 때 먼저 볼 것" 의 확인·결정 대기 항목을 보고, [roadmap.md](roadmap.md) 의 "다음 할 일"을 진행한다.
5. Claude Code 를 쓴다면 첫 메시지에 "docs/README.md 부터 읽고 roadmap 다음 항목 진행" 이라고 알려준다.
   (Claude 의 메모리는 PC 마다 따로라서 다른 PC 에서는 이 문서가 유일한 기준이다.)

> ⚠ 이 저장소는 Public 이다. 회사 보드 이름, 프롬프트, 명령 목록, 장치 기록은 코드/테스트/문서/커밋 메시지 어디에도 넣지 않는다.
