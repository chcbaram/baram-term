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

## 다음 할 일 (이 순서로)

### 1. baram-term 기본기 마무리
- [ ] 설정 저장/불러오기 (최근 포트, 속도, 테마, 글자 크기, 언어, 에코/타임스탬프) — OS 별 사용자 설정 폴더
- [ ] 자동 재연결 (USB CDC 장치가 리셋으로 사라졌다 다시 생길 때)
- [ ] 포트 설정 대화상자: 포트 목록 새로고침 버튼, 직접 입력(`socket://` 등)
- [ ] 받은 LF 처리/보내는 Enter(CR/LF/CRLF)/Backspace 코드(0x08/0x7F) 설정
- [ ] 로그 파일 저장 (`Ctrl-A L`, 타임스탬프 포함 여부)
- [ ] 스크롤백 검색 (`Ctrl-A /`)
- [ ] 터미널 드래그 선택/복사
- [ ] retroui 기본 문자열(Dialog "확인/취소") 다국어화

### 2. baram-term 개성 기능
- [ ] 수신 줄의 `key=value` 추출 → LivePlot 실시간 그래프 패널 (보기 메뉴로 켜고 끔)
- [ ] HEX 분할 보기
- [ ] 매크로 막대 (F1~F12, 클릭 전송, 설정 저장)
- [ ] 강조 규칙 사용자 추가 (정규식 + 색)
- [ ] 전송률 미니 그래프(`▁▂▄▆█`)
- [ ] 줄 단위 입력창 모드 (보조)

### 3. 배포
- [ ] `pipx install git+https://github.com/chcbaram/baram-term#subdirectory=baram-term` (retro-ui 의존성 해결 방법 포함)
- [ ] PyInstaller 단독 실행 파일 (macOS .app/.dmg, Windows .exe, Linux AppImage)
- [ ] GitHub Actions: 두 패키지 테스트(3 OS) + 태그 push 시 릴리스 빌드

## 라이브러리 남은 항목 (필요해질 때)

- SpinBox, Table/Tree(가상화, SDO/PDO 편집), ScrollArea, Tabs, FileDialog(앱 내부 그리기)
- 플롯 확대/이동/십자선
- Windows/Linux 확인: 한글 IME 이벤트 기록, Windows DPI 설정(`SDL_WINDOWS_DPI_AWARENESS`), Linux IME(IBus/Fcitx)
- 둥근모 폰트 포함 여부 (라이선스 출처 확인 후)
