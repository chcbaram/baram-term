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

## 현재 상태 (2026-09-15 기준)

| 영역 | 상태 |
|---|---|
| retro-ui 코어/위젯 (렌더러, 이벤트 루프, 레이아웃, 테마, HiDPI, 한글 IME, 메뉴/팝업/대화상자) | 완료 |
| retro-ui 추가 위젯 (Terminal, LivePlot + PlotLegend, ListView, FileDialog, EditableComboBox, Link, VSplit, 기본 문자열 ko/en) | 완료 |
| baram-term 기본기 (연결/자동 재연결, 설정 저장, 포트 설정 + 상태줄 빠른 전환, 로그 저장, 스크롤백 찾기, Tab 자동완성, 줄끝 코드) | 완료, 실제 보드 확인 |
| baram-term 그래프 패널 (`>name:value` / Arduino 플로터 형식, 범례, STOP/지우기, 시간 폭, 경계 끌기) | 완료, 실제 보드 확인 |
| baram-term 매크로 막대 (F 키/클릭 전송, 오른쪽 클릭 수정/삭제, 키 선택, hover 툴팁, 설정 저장) | 완료, 실제 창 확인 |
| 다음 | HEX 분할 보기, 배포 |
| 테스트 | retro-ui 244개, baram-term 193개 (+ 로컬 장치 기록이 있으면 재생 테스트) |

## 마지막 작업 지점 (2026-09-15)

- 저장소 루트에 **README.md** 를 새로 만들었다 (소개 · 기능 · 설치 · 구조 · 개발).
  그림 두 장은 손으로 찍은 캡쳐가 아니라 스크립트로 만든다:
  `docs/images/make_screenshot.py`, `docs/images/make_architecture.py` (헤드리스로 앱을 돌려 저장).
  화면이 바뀌면 다시 돌려서 `docs/images/*.png` 를 갱신한다.
- **매크로 막대를 먼저** 하기로 정하고 만들었다 (`baram_term/macros.py`, 보기 메뉴, `Ctrl-A M`).
  등록된 칸은 F 키로도 보낸다. F10 은 메뉴 키라 막대에서 눌러서만 보낸다.
  테스트 14개 추가 (`baram-term/tests/test_macros.py`). 두 패키지 모두 통과.
- 매크로 막대에 이어서 넣은 것 (모양은 확인받음)
  - 이름이 길면 버튼에서 `F1 nvs set wifi_…` 로 줄이고, 보내는 명령은 그대로
  - 폭이 모자라면 거기서 멈추고 오른쪽에 `+3` 으로 숨은 칸 수 표시 (F 키는 그대로 동작)
  - **오른쪽 클릭 = 수정/지우기** (왼쪽 클릭은 전송, 빈 칸은 왼쪽 클릭으로도 등록 창)
  - 버튼에 마우스를 올리면 0.6초 뒤 **툴팁**으로 보낼 명령 전체를 보여준다
    → retro-ui 에 일반 기능으로 넣었다 (`Widget.tooltip`, `App.tooltip_delay`, `widgets/tooltip.py`)
- 배너 로고를 원본 이미지(`assets/baram-logo.png`)에서 뽑은 도트로 바꿨다.
  왼쪽 마크는 도트로 줄이면 선이 끊겨 깨지므로 **"BARAM" 글자만** 쓴다 (2배 축소, 64칸 x 7줄).
  크기를 바꾸려면 `baram-term/tools/logo_from_image.py <축소 배율>` 을 돌려 `LOGO_DOTS` 를 갈아 끼운다.
  배율은 정수만 쓴다 — 어중간하게 줄이면 A, M 의 좌우 대칭이 깨진다.
- 매크로 버튼 좌우 여백을 1칸으로 (retro-ui `Button(padding=...)` 추가, 기본값 2는 그대로).
- 칸이 많아 좁아지면 **숨기지 않고 이름부터 줄여** 다 보여준다. 이름을 4칸도 못 줄 정도면 번호만
  (`F1 F2 …`), 번호만으로도 모자랄 때만 `+N` 으로 접는다.
- 오른쪽 클릭 = 수정/삭제 팝업 메뉴, 맨 끝 `+` 로 등록.
- **F 번호는 등록 창에서 고른다** (이미 쓰는 번호와 F10 은 목록에서 빠진다 — F10 은 메뉴 키라 최대 11개). 번호를 매크로가 들고 있어서
  (`"F5|이름=명령"`) 가운데를 지워도 남은 매크로의 번호는 그대로다. 막대는 번호 순으로 그린다.
  메뉴가 떠 있는 동안에는 툴팁이 뜨지 않는다 (겹쳐 보이던 것 수정).
- 로고 흰색을 (205,205,205) 로 살짝 낮췄다.
- 매크로 막대는 **실제 창에서 확인받았다**.
- 아직 실제로 확인하지 못한 것 (이전부터)
  - 실제 창에서 손가락 커서(링크/상태줄 항목)와 ↕ 커서(터미널/그래프 경계) 모양
  - 연결된 상태에서 상태줄로 속도만 바꿀 때 실제 보드가 끊기지 않는지
- 작업하다 찾은 문제 **셋 다 고쳤다**: 부분 갱신에서 줄 끝 한글이 빠지던 것, 평범한 로그가 그래프
  형식을 채 가던 것, 숨기기를 켜도 값 줄이 새어 나오던 것. 덤으로 수신이 ESC 시퀀스 중간에서
  잘릴 때 나던 `IndexError` 도 막았다.
- 터미널 휠 스크롤: 소수 델타를 모아 움직이고, macOS 에서는 OS 가 준 속도·가속을 그대로 쓴다
  (`Terminal.wheel_lines` macOS 1 / 그 외 3). 트랙패드가 macOS 스크롤 방향 설정을 따르지 않던 것도
  고쳤다 (SDL 의 `flipped` 를 다시 뒤집고 있었다). macOS 실제 트랙패드·마우스에서 방향과 속도 확인받음.
  Windows/Linux 휠(3줄 고정, Windows 는 시스템 설정값을 읽는 편이 맞음)은 아직 확인 못 함.
- 루트 README 에 **펌웨어에서 그래프 값 찍는 법**(printf 예시)을 넣었다.
- 설정 파일 주의: 이전 버전으로 실행한 PC 는 `plot_hide_lines` 가 `true` 로 저장돼 있을 수 있다 (예전 기본값). 보기 메뉴에서 한 번 끄면 된다.

## 작업 방식 (Claude Code 와 작업할 때)

Claude 의 메모리는 PC 마다 따로라서, 이어서 작업할 때 지킬 것을 여기에 적어 둔다.

- 화면 배치가 바뀌는 요청은 **코드 전에 글자 스케치로 먼저 확인**받는다 (배치를 만들고 바로 뒤집는 왕복을 줄이려고).
- 요청에 이상하거나 중복되는 점, 이전 결정과 부딪히는 점이 있으면 구현하면서 짧게 **피드백**하고 추천안을 낸다.
- 커밋/푸시는 요청할 때만. 커밋 메시지는 영어, Claude 서명(Co-Authored-By) 없음.
- 커밋 전에 회사 식별자 검색과 `retro-ui/tests/fixtures/local/` 무시 여부를 확인한다 (아래 ⚠).
- 화면 확인은 창을 띄우지 않고 헤드리스로 그린다: `SDL_VIDEODRIVER=dummy` 로 앱을 만들고 `pygame.image.save(app.surface, ...)`.
- 두 패키지 테스트를 동시에(병렬로) 돌리면 결과 출력이 섞여 보인 적이 있다. 한 명령에서 순서대로 돌린다.

## 문서 목록

| 문서 | 내용 |
|---|---|
| [dev-setup.md](dev-setup.md) | 새 PC 환경 구축, 실행/테스트, git 계정 설정 |
| [roadmap.md](roadmap.md) | 완료한 것, 다음에 할 일 (순서대로) |
| [architecture.md](architecture.md) | retro-ui 내부 구조 |
| [decisions.md](decisions.md) | 주요 결정과 이유 (실측값 포함) |
| [baram-term-spec.md](baram-term-spec.md) | baram-term 기능 명세와 화면 구성 |
| [firmware-cli.md](firmware-cli.md) | 대상 펌웨어 CLI 프로토콜 (공개 펌웨어 기준) |
| [device-testing.md](device-testing.md) | 실제 장치 CLI 기록과 재생 테스트, **장치 정보 비공개 규칙** |

## 새 PC 에서 이어서 하기

1. [dev-setup.md](dev-setup.md) 대로 저장소를 받고 환경을 만든다.
2. 두 패키지 테스트가 모두 통과하는지 확인한다.
3. `baram-term --demo` 로 보드 없이 실행해 본다.
4. 위 "마지막 작업 지점"의 결정 대기 항목을 먼저 정하고, [roadmap.md](roadmap.md) 의 "다음 할 일"을 진행한다.
5. Claude Code 를 쓴다면 첫 메시지에 "docs/README.md 부터 읽고 roadmap 다음 항목 진행" 이라고 알려준다.
   (Claude 의 메모리는 PC 마다 따로라서 다른 PC 에서는 이 문서가 유일한 기준이다.)

> ⚠ 이 저장소는 Public 이다. 회사 보드 이름, 프롬프트, 명령 목록, 장치 기록은 코드/테스트/문서/커밋 메시지 어디에도 넣지 않는다.
