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
| 다음 | 개성 기능 (HEX 보기 또는 매크로 막대부터, 아래 "마지막 작업 지점" 참고), 배포 |
| 테스트 | retro-ui 224개, baram-term 144개 (+ 로컬 장치 기록이 있으면 재생 테스트) |

## 마지막 작업 지점 (2026-09-15)

- 마지막으로 푸시한 커밋: `71dba03` (그래프 줄 숨기기 입력 지연 수정, 그래프 형식 세션 고정, 숨기기 기본 끔)
- **결정 대기**: 로드맵 순서상 다음은 HEX 분할 보기인데, **매크로 막대를 먼저** 하자는 제안을 해 둔 상태다.
  - 이유: 대상 장치가 텍스트 CLI 라서 HEX 보기는 문제가 있을 때만 쓰는 진단용이고, 매크로(F1~F12 명령 전송)는 매일 쓴다.
  - 사용자가 아직 고르지 않았다. 새 세션에서는 두 화면 스케치를 보여 주고 먼저 고르게 한다.
- 아직 실제로 확인하지 못한 것
  - 실제 창에서 손가락 커서(링크/상태줄 항목)와 ↕ 커서(터미널/그래프 경계) 모양
  - 연결된 상태에서 상태줄로 속도만 바꿀 때 실제 보드가 끊기지 않는지
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
