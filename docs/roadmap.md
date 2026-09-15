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
| retro-ui 추가 | VSplit(경계 끌기, 위치별 커서), PlotLegend, Button solid 스타일, LivePlot(header=False)/series_changed/clear_series, Dialog 버튼 같은 폭·가운데, EditableComboBox, 클릭 가능한 Label과 손가락 커서, Link, 기본 문자열 다국어(`retroui.set_language`), 붙여넣기 줄바꿈이 Enter 코드를 따름, ListView, FileDialog(창 안에 그리는 열기/저장, 새 폴더, 패턴, 이어쓰기 확인), App padding/icon, `App.ensure_layout`, Terminal 찾기(`set_search`/`search_matches`/`reveal`), GroupBox title_align, Box 방향별 margin, ScrollBar, 포커스 없는 팝업, 터미널 256색/트루컬러, Tooltip(위젯에 `tooltip` 만 넣으면 App 이 띄움), Button padding, Key F3~F9/F11 |

## 다음 할 일 (이 순서로)

### 1. baram-term 개성 기능

> 순서 결정: **매크로 막대를 먼저** 하기로 했다 (2026-09-15). 텍스트 CLI 에서는 매크로를 매일 쓰고 HEX 는 진단용.

- [x] 매크로 막대 (F1~F12, 왼쪽 클릭 전송 / 오른쪽 클릭 수정, 이름 줄임 + `+N`, hover 툴팁, 설정 저장)
      — 막대 모양은 확인받음. **실제 창에서 클릭/툴팁 확인 대기**
- [ ] HEX 분할 보기
- [ ] 강조 규칙 사용자 추가 (정규식 + 색)
- [ ] 전송률 미니 그래프(`▁▂▄▆█`)
- [ ] 줄 단위 입력창 모드 (보조)

### 2. 배포
- [ ] `pipx install git+https://github.com/chcbaram/baram-term#subdirectory=baram-term` (retro-ui 의존성 해결 방법 포함)
- [ ] PyInstaller 단독 실행 파일 (macOS .app/.dmg, Windows .exe, Linux AppImage)
- [ ] GitHub Actions: 두 패키지 테스트(3 OS) + 태그 push 시 릴리스 빌드

## 찾아 둔 문제 (고치기 전)

작업하다 발견했고 아직 고치지 않았다. 셋 다 실제로 재현했다.

1. **부분 갱신에서 줄 끝 한글이 빠진다** (retro-ui, 렌더). 화면 일부만 다시 그릴 때
   `CellBuffer.put` 이 2칸 글자를 **클립 경계**에서 공백으로 바꾼다 (`x + 1 >= area.right`).
   그 클립은 화면 끝이 아니라 그때 다시 그리는 영역의 끝이라, 경계에 걸린 한글이 사라진다.
   증상: 상태줄 오른쪽 `… F10 메뉴` 가 `… F10 메` 로 보인다 (폭은 충분한데도).
   전체를 다시 그리면 정상 → 문서 그림 스크립트는 저장 전에 `app.invalidate()` 를 한 번 한다.
   고칠 자리: 다시 그릴 영역을 2칸 글자 단위로 넓히거나, 진짜 버퍼 끝에서만 공백으로 바꾸기.
2. **평범한 로그 줄이 그래프 형식을 채 간다**. `sensor` 의 `temp=42.0 rpm=1200`,
   `status` 의 `History : 3` 이 Arduino 플로터 줄로 받아들여져 그 세션 형식이 Arduino 로 고정된다.
   그 뒤 진짜 `>ax:-15` 는 형식이 다르다고 버려져서 그래프가 비고, 숨기기도 걸리지 않는다.
   (`[OK] sensor temp=42` 는 규칙대로 잘 걸러진다. 앞에 태그가 없는 줄이 문제.)
3. **숨기기를 켜도 그래프 줄이 가끔 새어 나온다**. 사용자가 입력하는 동안 값이 오면
   한두 줄이 터미널에 찍힌다 (`_emit_above_prompt` 처럼 줄 앞에 `\r\x1b[K` 가 붙어 올 때).

## 개선 메모 (급하지 않음)

- 상태줄이 좁을 때 오른쪽 안내(`Ctrl-A Z 도움말 · F10 메뉴`)가 잘린다. 모드 표시(ECHO/TS/LOG/PLOT)가 늘수록 심해짐 → 공간이 모자라면 안내를 먼저 줄이거나 숨기기

## 라이브러리 남은 항목 (필요해질 때)

- SpinBox, Table/Tree(가상화, 칸 편집), ScrollArea, Tabs
- 플롯 확대/이동/십자선
- Windows/Linux 확인: 한글 IME 이벤트 기록, Windows DPI 설정(`SDL_WINDOWS_DPI_AWARENESS`), Linux IME(IBus/Fcitx)
- 둥근모 폰트 포함 여부 (라이선스 출처 확인 후)
