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
| 터미널 | Terminal/TerminalScreen (VT100 일부, 스크롤백, 타임스탬프, 강조 규칙, 펌웨어 키 매핑) |

## 다음 할 일 (이 순서로)

### 1. baram-term 뼈대
- [ ] `baram-term/pyproject.toml` (의존: `retro-ui`, `pyserial`), 실행 명령 `baram-term`
- [ ] 다국어 구조: `baram_term/i18n.py` 의 `tr(key, **fmt)`, `locales/ko.json`, `locales/en.json`
      (시스템 언어 자동 선택 + 설정으로 변경). retroui 기본 문자열(Dialog "확인/취소")도 같은 방식으로 뺀다
- [ ] 시리얼 계층 `serial_port.py`: 수신 스레드 → 버퍼 → `app.call_soon` 으로 프레임당 한 번 묶어서 전달,
      송신 큐, 통계(TX/RX 바이트, 초당 전송률), 끊김 감지. pyserial URL(`loop://`, `socket://`) 지원
- [ ] 가짜 펌웨어 `fake_device.py`: `demo://` 포트. `cli# ` 프롬프트, 줄 편집/이력, `help`/`info` 명령,
      주기적 `[OK]`/`[E_]` 로그와 `temp=42.5` 같은 값 출력. 보드 없이 데모/헤드리스 테스트용

### 2. baram-term 메인 화면 (minicom 핵심)
- [ ] 메뉴바, 터미널, 상태줄(포트, 115200 8N1, TX/RX 표시등, 전송률, ECHO/TS/LOG), 입력 모드 표시
- [ ] 포트 설정 대화상자 (포트 목록 새로고침, 속도, 데이터/패리티/정지 비트, 흐름 제어)
- [ ] 연결/끊기, 자동 재연결
- [ ] `Ctrl-A` 접두키 (`App.add_key_filter` 사용): O 포트, P 통신설정, E 에코, L 로그, N 타임스탬프, C 지우기, W 줄바꿈, Z 도움말, X 종료
- [ ] 설정 저장/불러오기 (최근 포트, 속도, 테마, 글자 크기, 언어)

### 3. minicom 부가 기능
- [ ] 로그 파일 저장 (타임스탬프 포함 여부 선택)
- [ ] 로컬 에코, 줄 끝 변환(CR/LF/CRLF), Backspace 코드(0x08/0x7F) 선택
- [ ] 검색 (스크롤백)
- [ ] 줄 단위 입력창 모드 (보조)

### 4. baram-term 개성 기능
- [ ] 펌웨어 로그 태그 색상 규칙 (`[OK]` 초록, `[E_]` 빨강, `WARN` 노랑, 사용자 정규식 추가)
- [ ] 수신 줄의 `key=value` 추출 → LivePlot 실시간 그래프 패널
- [ ] HEX 분할 보기
- [ ] 매크로 막대 (F1~F12, 클릭 전송)
- [ ] TX/RX 표시등 깜박임, 전송률 미니 그래프(`▁▂▄▆█`)

### 5. 배포
- [ ] `pipx install git+https://github.com/chcbaram/baram-term#subdirectory=baram-term`
- [ ] PyInstaller 단독 실행 파일 (macOS .app/.dmg, Windows .exe, Linux AppImage)
- [ ] GitHub Actions: 테스트(3 OS) + 태그 push 시 릴리스 빌드

## 라이브러리 남은 항목 (필요해질 때)

- SpinBox, Table/Tree(가상화, SDO/PDO 편집), ScrollArea, Tabs, FileDialog(앱 내부 그리기)
- 플롯 확대/이동/십자선
- 라이브러리 기본 문자열 다국어화
- Windows/Linux 확인: 한글 IME 이벤트 기록, Windows DPI 설정(`SDL_WINDOWS_DPI_AWARENESS`), Linux IME(IBus/Fcitx)
- 드래그 선택/복사 (Terminal)
- 둥근모 폰트 포함 여부 (라이선스 출처 확인 후)
