# baram-term 작업 문서

다른 PC나 새 세션에서 작업을 이어가기 위한 기준 문서입니다. 코드와 어긋나면 코드가 맞고, 이 문서를 고칩니다.

## 저장소 한눈에 보기

```
baram-term/                 GitHub: https://github.com/chcbaram/baram-term
├── retro-ui/               라이브러리 (배포 이름 retro-ui, import retroui) — 나중에 별도 저장소로 분리 가능
│   ├── src/retroui/
│   ├── tests/              pytest (헤드리스 포함)
│   └── examples/           hello / live_plot / menu_demo / spike_*
├── baram-term/             앱 (import baram_term) — 아직 없음, 다음 단계에서 추가
└── docs/                   이 문서들
```

- **retro-ui**: 겉보기는 TUI(글자 격자, 박스 문자)인데 그래프는 실제 픽셀로 그리는 파이썬 GUI 라이브러리. pygame-ce 기반, Qt 없음.
- **baram-term**: retro-ui 로 만드는 펌웨어 CLI 시리얼 터미널 (minicom 대체).

## 현재 상태 (2026-09-15 기준)

| 영역 | 상태 |
|---|---|
| 코어 (격자 렌더러, 이벤트 루프, 레이아웃, 테마, HiDPI) | 완료 |
| 기본 위젯 (Label, Button, CheckBox, GroupBox, HBox/VBox) | 완료 |
| LivePlot (실시간 그래프) | 완료 |
| 팝업 레이어, 풀다운 메뉴 | 완료 |
| 입력 위젯 (LineEdit, ComboBox, Dialog), 한글 IME 보정 | 완료 |
| Terminal 위젯 (VT100 일부 + 스크롤백) | 완료 |
| baram-term 앱 | **다음 단계** |
| 테스트 | 150개 통과 (`retro-ui/` 에서 `pytest`) |

## 문서 목록

| 문서 | 내용 |
|---|---|
| [dev-setup.md](dev-setup.md) | 새 PC 환경 구축, 테스트/예제 실행, git 계정 설정 |
| [roadmap.md](roadmap.md) | 완료한 것, 다음에 할 일 (순서대로) |
| [architecture.md](architecture.md) | retro-ui 내부 구조 |
| [decisions.md](decisions.md) | 주요 결정과 이유 (실측값 포함) |
| [baram-term-spec.md](baram-term-spec.md) | baram-term 기능 명세와 화면 구성 |
| [firmware-cli.md](firmware-cli.md) | 대상 펌웨어 CLI 프로토콜 |

## 새 PC 에서 이어서 하기

1. [dev-setup.md](dev-setup.md) 대로 저장소를 받고 환경을 만든다.
2. `cd retro-ui && ../.venv/bin/python -m pytest -q` 로 전부 통과하는지 확인한다.
3. [roadmap.md](roadmap.md) 의 "다음 할 일" 첫 항목부터 진행한다.
4. Claude Code 를 쓴다면 첫 메시지에 "docs/README.md 부터 읽고 roadmap 다음 항목 진행" 이라고 알려준다.
   (Claude 의 메모리는 PC 마다 따로라서 다른 PC 에서는 이 문서가 유일한 기준이다.)
