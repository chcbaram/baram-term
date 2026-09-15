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
| baram-term 설정 | 설정 저장/불러오기(OS 사용자 설정 폴더 `settings.json`, 실행 인자 우선, 인자 없으면 마지막 포트), 자동 재연결(1초 주기, 보기 메뉴 A), 포트별 Tab 명령 목록 저장, 포트 설정 창 새로고침 버튼/주소 직접 입력/최근 포트 8개, Enter/Backspace/받은 LF 코드 설정, 상태줄 모드 칸 정리, 터미널 테두리 제목 제거, About 링크, 로그 파일 저장(`Ctrl-A L`, 파일 다이얼로그로 위치 선택, 화면에 보이는 줄 그대로, 타임스탬프 선택), 스크롤백 찾기(`Ctrl-A /`, macOS Cmd+F, smartcase, 새 줄이 와도 위치 유지) |
| retro-ui 추가 | Link, 기본 문자열 다국어(`retroui.set_language`), 붙여넣기 줄바꿈이 Enter 코드를 따름, ListView, FileDialog(창 안에 그리는 열기/저장, 새 폴더, 패턴, 이어쓰기 확인), App padding/icon, `App.ensure_layout`, Terminal 찾기(`set_search`/`search_matches`/`reveal`), GroupBox title_align, Box 방향별 margin, ScrollBar, 포커스 없는 팝업, 터미널 256색/트루컬러 |

## 다음 할 일 (이 순서로)

### 1. baram-term 개성 기능
- [ ] 수신 줄의 `key=value` 추출 → LivePlot 실시간 그래프 패널 (보기 메뉴로 켜고 끔)
- [ ] HEX 분할 보기
- [ ] 매크로 막대 (F1~F12, 클릭 전송, 설정 저장)
- [ ] 강조 규칙 사용자 추가 (정규식 + 색)
- [ ] 전송률 미니 그래프(`▁▂▄▆█`)
- [ ] 줄 단위 입력창 모드 (보조)

### 2. 배포
- [ ] `pipx install git+https://github.com/chcbaram/baram-term#subdirectory=baram-term` (retro-ui 의존성 해결 방법 포함)
- [ ] PyInstaller 단독 실행 파일 (macOS .app/.dmg, Windows .exe, Linux AppImage)
- [ ] GitHub Actions: 두 패키지 테스트(3 OS) + 태그 push 시 릴리스 빌드

## 라이브러리 남은 항목 (필요해질 때)

- SpinBox, Table/Tree(가상화, SDO/PDO 편집), ScrollArea, Tabs
- 플롯 확대/이동/십자선
- Windows/Linux 확인: 한글 IME 이벤트 기록, Windows DPI 설정(`SDL_WINDOWS_DPI_AWARENESS`), Linux IME(IBus/Fcitx)
- 둥근모 폰트 포함 여부 (라이선스 출처 확인 후)
