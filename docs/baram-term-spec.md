# baram-term 기능 명세

펌웨어 CLI 용 시리얼 터미널. minicom 의 핵심 기능 + 펌웨어 개발에 맞춘 기능. 화면은 retro-ui (기본 mono 테마).
부제: **baram-term — 펌웨어 CLI 시리얼 터미널**

## 화면 구성

```
 포트(P)  편집(E)  보기(V)  도움말(H)
┌──────────────────────────────────────────────────────────────┐
│[OK] uartInit()                                               │  터미널 (스크롤바, 선택/복사, 찾기)
│cli# help                                                     │
│cli# █                                                        │
└──────────────────────────────────────────────────────────────┘  ← 두 테두리 줄을 끌어 높이 조절 (비율 저장)
┌──────────────────────────────────────────────────────────────┐
│■ ax  ■ ay  □ az  ■ temp                      [지우기] [정지] │  그래프 패널 (Ctrl-A G, 보기 메뉴)
│  (LivePlot, 가로축 = 받은 시각 초)                            │  범례 클릭 = 보이기/숨기기
│                                         시간 폭 [10 ▼] 초    │
└──────────────────────────────────────────────────────────────┘
● demo:// │ 115200 8N1 │ TX· RX· │ 0B/s │ ECHO TS LOG PLOT        Ctrl-A Z 도움말 · F10 메뉴
  └ 클릭: 포트 목록   └ 클릭: 속도 목록(직접 입력) / 8N1 클릭: 포트 설정
 (예정) [F1 boot] [F2 reset] [F3 info] ...   ← 매크로 막대
```

## minicom 대응

| minicom | baram-term |
|---|---|
| `Ctrl-A O` 포트 설정 | 포트 메뉴 → 대화상자 (포트 목록 ComboBox + 새로고침) |
| `Ctrl-A P` 속도/데이터/패리티/정지 비트, 흐름 제어 | 같은 대화상자 |
| 하단 상태줄 | 포트, `115200 8N1`, TX/RX 표시등, 전송률, 모드 표시 |
| `Ctrl-A E` 로컬 에코 | 보기 메뉴 체크 (기본 끔: 펌웨어가 에코함) |
| CR/LF 변환 | 포트 설정 창 (보내는 Enter CR/LF/CRLF, Backspace BS/DEL, 받은 LF 처리) |
| `Ctrl-A L` 로그 저장 | 창 안에 그리는 파일 다이얼로그로 위치 선택, 다시 누르면 멈춤 |
| `Ctrl-A N` 타임스탬프 | 줄 앞 `HH:MM:SS.mmm` (Terminal `show_timestamps`) |
| `Ctrl-A C` 지우기, `Ctrl-A W` 줄바꿈 | 메뉴 + 키 |
| `Ctrl-A Z` 도움말, `Ctrl-A X` 종료 | 도움말 팝업, 종료 확인 |
| VT102 | Terminal 위젯 (펌웨어가 쓰는 VT100 일부) |
| 파일 전송 (xmodem 등) | 나중 |

`Ctrl-A` 접두키와 메뉴를 둘 다 제공한다 (minicom 손버릇 + 처음 쓰는 사람).

## 입력 방식

- **기본: 키 입력 바로 전송** (터미널에 포커스). 펌웨어가 줄 편집/이력을 직접 처리하기 때문.
  키 → 바이트 변환은 [firmware-cli.md](firmware-cli.md) 참고 (Backspace=0x08, Home=`ESC[1~` 등).
- 보조: 줄 단위 입력창 (한글 조합 편집, 명령 이력) — 필요할 때 켠다.

## 개성 기능

| 기능 | 상태 | 내용 |
|---|---|---|
| 로그 태그 색상 | 완료 (사용자 규칙은 예정) | `[OK]` 초록, `[E_]` 빨강, `WARN`/`[W_]` 노랑, 프롬프트 `...# ` 강조. mono 테마에서도 이 강조만 컬러 |
| 그래프 패널 | 완료 | 아래 "그래프 줄 형식" |
| Tab 명령 자동완성 | 완료 | `help` 출력에서 명령 목록을 배우고 포트별로 저장 |
| 상태줄 빠른 전환 | 완료 | 포트/속도 클릭 → 바로 위 목록. 열린 포트는 속도만 바꾼다 (다시 열면 USB CDC 보드가 리셋될 수 있어서) |
| 로그 저장, 스크롤백 찾기 | 완료 | 로그는 CR/BS/ESC 를 적용한 "보이는 줄". 찾기는 smartcase |
| HEX 분할 보기 | 예정 | 받은/보낸 바이트 16진수 + ASCII, 오른쪽 패널 |
| 매크로 막대 | 예정 | F1~F12 에 명령 등록, 클릭 전송, 설정 저장 |
| 전송률 미니 그래프 | 예정 | TX/RX 표시등은 완료 |

### 그래프 줄 형식

- Teleplot: `>ax:-15`, `>ax:1234:-15` (시각:값, 시각은 쓰지 않고 받은 시각을 쓴다), `>volt:3.3§V|np`
- Arduino IDE 시리얼 플로터: `10 20 30`, `10,20,30`, `ax:-15,ay:-70`, `temp=34 rpm=1200` (이름 없으면 `value 1` ...)
- 숫자가 아닌 조각이 있으면 그래프 줄이 아니다 (`[OK] sensor temp=42` 는 로그로 둔다).
- 이름에 깨진 글자(U+FFFD), 제어 문자, 공백, `>`, 구분자가 있으면 버린다 (잘린 수신 버퍼가 두 줄을 붙인 경우).
- 한 세션의 형식은 처음 받은 줄로 고정하고 지우기로 푼다 (잘린 `>temp:34` 가 `p:34` 로 와도 새 시리즈를 만들지 않게).
- 시리즈 최대 12개, 시리즈당 16384 샘플.
- "그래프 줄은 터미널에 표시하지 않음" (기본 끔): 켜면 그래프 줄을 터미널에서 빼고 상태줄에 `PLOT`.
  줄 앞 CR/ESC 코드는 남기고(프롬프트 다시 그리기 유지), 줄 처음에서 시작한 조각만 최대 0.2초 붙잡는다
  (프롬프트 뒤 입력 에코는 바로 보인다). 로그 파일에는 모두 남는다.
- 데모 장치 `plot` / `plot arduino` / `plot off` 로 확인한다.

## 구조

```
[수신 스레드] ─bytes─▶ 버퍼 ─(call_soon, 한 번에 합침)─▶ UTF-8 증분 디코더 ─┬─▶ PlotLineFilter (숨기기 켰을 때) ─▶ Terminal.feed
                                                                           ├─▶ plotdata.parse_line ─▶ LivePlot
                                                                           ├─▶ SessionLog (받은 그대로)
                                                                           └─▶ Completer (help 목록 학습)
[Terminal.send / 자동완성 / 붙여넣기] ─▶ outgoing (프롬프트에서 제어 문자 거르기) ─▶ 송신 큐 ─▶ [송신 스레드]
```

- 수신 스레드는 버퍼에만 쓴다. 1Mbps 로 쏟아져도 UI 가 멈추지 않게 파싱은 메인 스레드에서 묶어서.
- 포트 URL: 실제 장치 경로, pyserial `loop://`, `socket://host:port`, 가짜 펌웨어 `demo://`.
- 문자열은 전부 `tr("key")` (ko, en). retro-ui 위젯 기본 글자도 같은 언어로 (`retroui.set_language`).

## 패키지 구성

```
baram-term/
├── pyproject.toml          의존: retro-ui, pyserial / 실행: baram-term
├── tests/
└── src/baram_term/
    ├── __main__.py         인자 + 설정 파일 병합 (--config, 인자가 우선)
    ├── app.py              메인 화면, 메뉴, Ctrl-A, 상태줄, 대화상자, 그래프 패널
    ├── serial_port.py      PortSettings(줄끝 코드 포함), 수신/송신 스레드, set_baud, list_ports
    ├── settings.py         settings.json (OS 사용자 설정 폴더, BARAM_TERM_CONFIG_DIR)
    ├── completion.py       Tab 자동완성
    ├── outgoing.py         프롬프트에서 제어 문자 거르기
    ├── logger.py           로그 파일, LineCleaner (CR/BS/ESC 를 적용한 줄)
    ├── search.py           스크롤백 찾기 상자
    ├── plotdata.py         그래프 줄 파싱 (Teleplot / Arduino)
    ├── plotfilter.py       그래프 줄을 터미널에서 빼기
    ├── fake_device.py      demo:// 가짜 펌웨어 (help info log sensor status reset plot)
    ├── logo.py, icon.py, highlight.py, i18n.py
    └── locales/ko.json, en.json
```

프롬프트 강조는 특정 문자열이 아니라 "줄 처음의 공백 없는 단어 + `# `" 패턴으로 한다.

## 단축키

| 키 | 동작 |
|---|---|
| `Ctrl-A O` / `P` | 포트 설정 |
| `Ctrl-A R` / `D` | 연결 / 끊기 |
| `Ctrl-A E` / `N` | 로컬 에코 / 타임스탬프 |
| `Ctrl-A L` | 로그 저장 시작/중지 |
| `Ctrl-A /` (macOS `Cmd+F`) | 스크롤백 찾기 |
| `Ctrl-A G` | 그래프 패널 |
| `Ctrl-A C` | 화면 지우기 |
| `Ctrl-A X` / `Q` | 끝내기 |
| `Ctrl-A Z` | 도움말 |
| `Ctrl-A Ctrl-A` | Ctrl-A 문자 보내기 |
| 복사/붙여넣기 | macOS `Cmd+C/V`, 그 외 `Ctrl+Shift+C/V` (Ctrl+C 는 장치로 가는 제어 문자) |

## 기본값

- 115200 8N1, 흐름 제어 없음, 로컬 에코 끔, 보내는 Enter = `\r`, Backspace = `0x08`, 받은 LF 는 줄 처음으로.
- 스크롤백 5000 줄, 테마 mono, 글자 크기 14.
- 자동 재연결 켬, Tab 자동완성 켬, 프롬프트 제어 문자 거르기 켬.
- 그래프 패널 끔, 그래프 줄 숨기기 끔, 시간 폭 10초, 터미널 : 그래프 = 2 : 1.
