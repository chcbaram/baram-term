# 로드맵

## 완료

| 단계 | 내용 |
|---|---|
| P0 스파이크 | HiDPI 2x, 폰트 셀 메트릭, 스레드 깨우기, 플롯 CPU, macOS 한글 IME 이벤트 기록 |
| P1 코어 | 셀 버퍼(변경 셀만 렌더), 박스/블록 문자 도형 렌더, 글리프 캐시, 이벤트 루프, 타이머, Signal, 레이아웃, 포커스/마우스, 테마 |
| P1 위젯 | Label, Button(fill/box, 니모닉), CheckBox, GroupBox/Frame, HBox/VBox/Spacer |
| P2 플롯 | LivePlot (링버퍼, min/max 축약, 자동 범위, 일시정지, pglive 호환 이름) |
| 레이어/메뉴 | 팝업 레이어(그림자, 플롯 가림 처리), MenuBar/Menu/MenuItem |
| P3 입력 | LineEdit(선택, 클립보드, 이력), ComboBox/ListPopup, Dialog/message_box, ImeFilter |
| 테마 | mono(기본, 검정 흑백 + 박스 버튼 + 컬러 그래프), dos_blue, amber, green_phosphor, mono_dark |
| 기타 | D2Coding 폰트 포함(OFL), `App.set_font_size`, 한글 입력 상태 키 이름 복원 |
| 터미널 | Terminal/TerminalScreen (VT100 일부, 스크롤백, 타임스탬프, 강조 규칙, 펌웨어 키 매핑), 장치 기록 도구와 재생 테스트 |
| baram-term 뼈대 | 패키지/실행 명령, 다국어(`tr`, ko/en), 시리얼 계층(수신 스레드/송신 큐/통계/끊김 감지), 가짜 펌웨어 `demo://` |
| baram-term 화면 | BARAM 블록 로고, 메뉴(포트/보기/도움말), 터미널, 상태줄(연결, 포트, 8N1, TX/RX, 전송률, 모드), 포트 설정 대화상자, Ctrl-A 명령(O P R D E N C X Z), 로컬 에코, 타임스탬프, 글자 크기 |
| baram-term 편의 | 7x7 도트 로고 + 그림자, 창 여백, 터미널 아이콘, 포트 이름 오른쪽 정렬, 스크롤바(1/8칸), 드래그/더블클릭 선택과 복사·붙여넣기(편집 메뉴), Tab 명령 자동완성(help 출력 목록 학습, 입력에 따라 목록 갱신) |
| baram-term 설정 | 설정 저장/불러오기(OS 사용자 설정 폴더 `settings.json`, 실행 인자 우선, 인자 없으면 마지막 포트), 자동 재연결(1초 주기, 보기 메뉴 A), 포트별 Tab 명령 목록 저장, 포트 설정 창 새로고침 버튼/주소 직접 입력/최근 포트 8개, Enter/Backspace/받은 LF 코드 설정, 상태줄 모드 칸 정리, 터미널 테두리 제목 제거, About 링크, 상태줄 포트/속도 클릭으로 바로 전환(열린 포트는 속도만 변경), 속도 직접 입력, 로그 파일 저장(`Ctrl-A L`, 파일 다이얼로그로 위치 선택, 화면에 보이는 줄 그대로, 타임스탬프 선택), 스크롤백 찾기(`Ctrl-A /`, macOS Cmd+F, smartcase, 새 줄이 와도 위치 유지) |
| baram-term 그래프 | 그래프 패널(`Ctrl-A G`): `>name:value`(Teleplot)와 Arduino 시리얼 플로터 형식, 범례 클릭으로 보이기/숨기기, STOP/START, 시간 폭(초), 터미널/그래프 경계 끌기(비율 저장), 그래프 줄 터미널에서 숨기기 옵션(기본 끔, 켜면 상태줄 PLOT, 형식은 세션마다 고정), CLEAR 버튼, 데모 `plot` 명령 |
| baram-term HEX | HEX 보기(`Ctrl-A H`, 터미널 오른쪽 패널): 받은/보낸 바이트를 오프셋 + RX/TX + 16진수 + ASCII 로, 폭에 따라 한 줄 4/8/16 바이트, 바이트 선택(클릭·드래그·Shift, 16진수/ASCII 동시 강조)과 설명 줄·복사, 정지/지우기, 좌우 경계 끌기(비율 저장) |
| baram-term 메모 탭 | 오른쪽 패널을 탭으로 (HEX + 메모 최대 8개): 여러 줄 편집, 자동 저장(`notes.json`), 탭 추가/이름 바꾸기/삭제, 줄·선택·전체 보내기(프롬프트 대기 또는 고정 간격, `#wait 밀리초`, 중지), .txt/.json 내보내기·가져오기(형식 콤보, 확장자가 형식을 정함), 보기 메뉴 `오른쪽 패널 ▸ HEX / 메모`(각각 따로 켜고 끔, HEX 가 늘 맨 앞, 체크해도 메뉴가 닫히지 않음), 파일 메뉴 `메모 ▸ 가져오기 / 내보내기`(메모가 하나도 없어도 가져올 수 있어야 해서 탭 메뉴에서 옮김) |
| baram-term 강조 규칙 | 사용자 규칙(보기 메뉴 → 강조 규칙): 정규식 + 색 8종 + 굵게, 목록 창에서 추가/수정/삭제, 예시 줄 미리보기, 잘못된 정규식은 이유를 보여주고 저장 안 함, 설정 저장 (`"색[ bold]|정규식"`) |
| retro-ui 추가 | MenuItem 2단 메뉴(submenu, `▸`, →/← 키와 마우스 올림으로 펼치기), TextArea(여러 줄 편집, 선택, IME), TabBar(탭 줄, `+`, 오른쪽 클릭 메뉴), HexView, HSplit(좌우 경계 끌기), VSplit(경계 끌기, 위치별 커서), PlotLegend, Button solid 스타일, LivePlot(header=False)/series_changed/clear_series, Dialog 버튼 같은 폭·가운데, EditableComboBox, 클릭 가능한 Label과 손가락 커서, Link, 기본 문자열 다국어(`retroui.set_language`), 붙여넣기 줄바꿈이 Enter 코드를 따름, ListView, FileDialog(창 안에 그리는 열기/저장, 새 폴더, 패턴, 이어쓰기 확인), App padding/icon, `App.ensure_layout`, Terminal 찾기(`set_search`/`search_matches`/`reveal`), GroupBox title_align, Box 방향별 margin, ScrollBar, 포커스 없는 팝업, 터미널 256색/트루컬러, Tooltip(위젯에 `tooltip` 만 넣으면 App 이 띄움), Button padding, Key F3~F9/F11, 휠 스크롤 누적(`Terminal.wheel_lines`) |
| baram-term 입력·메뉴 (2026-09) | 매크로 막대, 원본 이미지에서 뽑은 배너 로고, 터미널 영문 입력(기본 켜짐), 파일 메뉴 맨 앞 + 화면 언어 선택(기본 영어, 다음 실행부터), 그래프 값 줄 누출 수정, 로그 줄이 채 간 그래프 형식 되찾기 |
| retro-ui 입력·표시 (2026-09) | 입력 전환 단축키의 스페이스 버리기(`input/mac_hotkeys.py`), `KeyEvent.scancode`/`caps` + `us_ascii`, `Terminal.ascii_input`, `App.refresh_text_input`, 휠이 OS 방향(`flipped` 재반전 제거)·macOS 속도 그대로, Windows DPI 힌트, 부분 갱신 경계의 한글 유지, Tooltip, Button padding |
| 배포 (2026-09-16, v0.1.0) | pipx/pip 설치(retro-ui 를 git URL 로 의존), PyInstaller onedir 빌드 → macOS `.dmg` / Windows zip / Linux `.tar.gz`, CI(3 OS × py3.10·3.12 + 설치 경로 회귀), `v*` 태그 push 시 릴리스 자동 첨부, MIT 라이선스(폰트는 OFL 문서 동봉) |
| baram-term 포트 설정 (2026-09-16, v0.1.1) | 꽂혀 있는 포트만 목록에 (뽑은 장치는 빼고, `socket://` 류 최근 주소는 남김 — 상태줄 메뉴도 같은 목록), 목록과 주소 칸이 늘 같은 포트를 가리킴, 통신 속도는 목록 + `직접 입력...` 창(숫자 순으로 끼우고 8개까지 기억), Refresh 버튼이 포커스를 가져가지 않음 |
| retro-ui 입력 칸 (2026-09-16) | 선택 중에는 캐럿을 그리지 않음(선택 칸에 반전을 덧칠해 한 칸만 색이 튀던 문제 — LineEdit·TextArea 공통), `LineEdit(padding=…)` 옵션(기본 0, 포트 설정 Address 에만 1) |
| CI 가 드러낸 라이브러리 결함 (2026-09-16) | `App.close()` 가 프로세스 전역 SDL 을 내려 App 을 닫았다 다시 못 열던 것, 쓰지도 않는 오디오까지 켜던 `pygame.init()`(사운드 장치 없는 러너에서 호출당 8초, App 마다 지불), 폰트 경로를 App 하나당 22번 glob 하던 것, 벽시계 마진에 기대 간헐 실패하던 테스트 2개 → **윈도우 테스트 722초 → 4초, 로컬 28초 → 4.6초** |

## 다음 할 일 (이 순서로)

### 1. baram-term 개성 기능

> 순서 결정: **매크로 막대를 먼저** 하기로 했다 (2026-09-15). 텍스트 CLI 에서는 매크로를 매일 쓰고 HEX 는 진단용.

- [x] 매크로 막대 (F 키 선택·전송, 오른쪽 클릭 수정/삭제, `+` 등록, 이름 줄임, hover 툴팁, 설정 저장) — macOS 실제 창 확인
- [ ] 줄 단위 입력창 모드 (보조)
- [x] 메모 탭 (오른쪽 패널 탭: 명령을 적어 두고 줄/선택/전체 보내기, `#wait`, 내보내기/가져오기)

### 2. 배포 — 끝 (2026-09-16, [v0.1.1](https://github.com/chcbaram/baram-term/releases/tag/v0.1.1))

- [x] `pipx install "git+https://github.com/chcbaram/baram-term#subdirectory=baram-term"`
      — retro-ui 가 PyPI 에 없어서 git URL 로 의존한다 (hatchling `allow-direct-references`).
      로컬 개발은 `[tool.uv.sources]` 가 그 줄을 덮어써 editable 로 남고, 평범한 pip 은
      두 줄로 나눠 설치해야 한다 (`docs/dev-setup.md`). PyPI 에 올리려면 retro-ui 를 먼저 올리고
      이 의존성을 버전으로 바꿔야 한다 — PyPI 는 직접 URL 참조를 거부한다
- [x] PyInstaller 단독 실행 파일 — macOS `.app` → `.dmg`, Windows onedir → zip, Linux onedir → `.tar.gz`.
      **AppImage 는 하지 않았다** (개선 메모로 내림). onefile 이 아니라 폴더로 묶는다 (한 파일이면
      실행할 때마다 8.1MB 폰트를 풀어 느리다). 콘솔 없이 묶고(`console=False`), 셸에서 부른
      `--list`/`--version` 은 부모 콘솔에 붙여 살린다
- [x] GitHub Actions — `ci.yml`(3 OS × py3.10·3.12, 그리고 pipx 설치 경로가 깨지는지 보는 잡),
      `release.yml`(`v*` 태그 push 또는 수동 실행, 3 OS 빌드를 릴리스에 첨부)

## 개선 메모 (급하지 않음)

- 전송률 미니 그래프(`▁▂▄▆█`): 상태줄에 최근 전송률을 막대로. 지금도 숫자(`1.2kB/s`)는 보이므로 급하지 않다
- 상태줄이 좁을 때 오른쪽 안내(`Ctrl-A Z 도움말 · F10 메뉴`)가 잘린다. 모드 표시(ECHO/TS/LOG/PLOT)가 늘수록 심해짐 → 공간이 모자라면 안내를 먼저 줄이거나 숨기기
- 로그만 찍는 장치에서 `temp=42 rpm=1200` 같은 줄이 그래프 시리즈로 잡힌다. Arduino 형식이 평범한
  로그와 구별되지 않아서인데, 진짜 그래프 줄(`>이름:값`)이 오면 되찾으므로 급하지는 않다 (지우기로도 푼다)
- Windows 휠 한 칸의 줄 수를 시스템 설정값(`SPI_GETWHEELSCROLLLINES`)으로 읽기 (지금 3줄 고정, 사용자는 괜찮다고 함)
- Linux AppImage: 지금은 onedir 를 `.tar.gz` 로 낸다. AppImage 는 `appimagetool` + AppDir 배치 +
  `.desktop` 파일이 따로 필요해서 미뤘다. 배포판 무관하게 파일 하나로 주고 싶어지면 그때 한다
- 릴리스 산출물에 서명하지 않는다 (Apple 개발자 계정 연 $99, Windows 코드 서명은 별도 비용).
  받는 쪽은 첫 실행에서 macOS 우클릭>열기 / Windows 추가 정보>실행 로 연다 — 릴리스 노트와
  `docs/dev-setup.md` 에 적어 뒀다. 배포 대상이 넓어지면 서명을 다시 검토한다

## 장기 검토 (지금은 안 함)

### 시리얼 포트 여러 개 동시 연결

HEX 보기를 만들면서 생기는 좌우 분할(`HSplit`)은 나중에 터미널 두 개를 나란히 놓는 데 쓸 수 있다.
다만 어려운 부분은 분할이 아니라 아래에 있어서, 필요해질 때 UI 방식(좌우 분할 / 탭)부터 다시 정한다.

- 포트마다 객체·수신 스레드·자동 재연결 타이머 (지금은 `BaramTerm` 에 포트가 하나)
- 활성 패널 표시와 전환 키. `Ctrl-A` 명령과 메뉴가 "활성 패널에 적용"으로 의미가 바뀐다
- 상태줄: 패널별 상태 또는 탭에 상태 표시
- 설정: 세션/레이아웃(어느 패널에 어느 포트) 저장, 포트별 최근 설정
- 로그·찾기·자동완성은 패널마다 따로, 그래프 시리즈 이름은 포트 접두어 필요 (`A:ax`, `B:ax`)

> 지금도 프로그램을 두 번 실행하면 창 두 개로 볼 수 있다. 설정이 서로 덮어쓰지 않게 `--config` 로 파일을 나눈다:
> `baram-term /dev/cu.usbmodem1 --config ~/.baram-a.json`

## 라이브러리 남은 항목 (필요해질 때)

- SpinBox, Table/Tree(가상화, 칸 편집), ScrollArea, Tabs
- 플롯 확대/이동/십자선
- Windows/Linux 확인: 한글 IME 이벤트 기록, Linux IME(IBus/Fcitx)
  (Windows 11 에서 실행·스크롤 확인함. DPI 힌트는 넣었고 선명해졌는지 확인 대기. Linux 는 아직 실행해 보지 않음)
- 둥근모 폰트 포함 여부 (라이선스 출처 확인 후)
