# baram-term 기능 명세

펌웨어 CLI 용 시리얼 터미널. minicom 의 핵심 기능 + 펌웨어 개발에 맞춘 기능. 화면은 retro-ui (기본 mono 테마).
부제: **baram-term — 펌웨어 CLI 시리얼 터미널**

## 화면 구성 (초안)

```
 포트(&P)  보기(&V)  도구(&T)  도움말(&H)                               baram-term
┌┤ /dev/tty.usbmodem1 ├──────────────────────────────────────────────────────────┐
│[OK] uartInit()                                                                 │
│[E_] canOpen()                                        ← 태그 색상 규칙          │
│cli# help                                                                       │
│---------- cmd list ---------                                                   │
│cli# █                                                                          │
└────────────────────────────────────────────────────────────────────────────────┘
 (그래프 패널: 보기 메뉴로 켜고 끔, key=value 자동 추출)
 [F1 boot] [F2 reset] [F3 info] ...                                  ← 매크로 막대
 ● tty.usbmodem1 │ 115200 8N1 │ TX● RX● │ 1.2kB/s ▁▂▄ │ ECHO TS LOG │ Ctrl-A Z 도움말
```

## minicom 대응

| minicom | baram-term |
|---|---|
| `Ctrl-A O` 포트 설정 | 포트 메뉴 → 대화상자 (포트 목록 ComboBox + 새로고침) |
| `Ctrl-A P` 속도/데이터/패리티/정지 비트, 흐름 제어 | 같은 대화상자 |
| 하단 상태줄 | 포트, `115200 8N1`, TX/RX 표시등, 전송률, 모드 표시 |
| `Ctrl-A E` 로컬 에코 | 보기 메뉴 체크 (기본 끔: 펌웨어가 에코함) |
| CR/LF 변환 | 보기 메뉴 (보내는 Enter, 받은 LF 처리) |
| `Ctrl-A L` 로그 저장 | 체크 + 파일 이름 대화상자 |
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

1. **로그 태그 색상**: `[OK]` 초록, `[E_]` 빨강, `WARN`/`[W_]` 노랑, 프롬프트 `cli# ` 강조. 사용자 정규식 추가.
   mono 테마에서도 이 강조만 컬러. 펌웨어가 보낸 ANSI 색이 있으면 그것을 우선한다.
2. **key=value 그래프**: 수신 줄에서 `temp=42.5 rpm=1200` 같은 값을 뽑아 LivePlot 에 시리즈별로 그린다 (최대 8개).
3. **HEX 분할 보기**: 수신 바이트 `00 1A FF |..?|`.
4. **매크로**: F1~F12 에 명령 등록, 매크로 막대 클릭 전송.
5. **TX/RX 표시등 + 전송률 미니 그래프**.

## 구조

```
[시리얼 수신 스레드] ─bytes─▶ 버퍼 ─(app.call_soon, 프레임당 1회로 합침)─▶ UTF-8 증분 디코더 ─▶ Terminal.feed
                                                                         ├─▶ key=value 추출 ─▶ LivePlot
                                                                         └─▶ HEX 보기 / 로그 파일
[Terminal.send / 매크로 / 입력창] ─bytes─▶ 송신 큐 ─▶ [시리얼 송신]
```

- 수신 스레드는 버퍼에만 쓴다. 1Mbps 로 쏟아져도 UI 가 멈추지 않게 파싱은 메인 스레드에서 묶어서.
- 포트 URL: 실제 장치 경로, pyserial `loop://`, `socket://host:port`, 가짜 펌웨어 `demo://`.
- 문자열은 전부 `tr("key")` (ko 기본, en).

## 패키지 구성

```
baram-term/
├── pyproject.toml          의존: retro-ui, pyserial / 실행: baram-term
├── tests/                  i18n, 가짜 펌웨어 바이트, 헤드리스 앱
└── src/baram_term/
    ├── __main__.py         인자: 포트, -b, --demo, --list, --theme, --font-size, --size, --lang
    ├── app.py              메인 화면, 메뉴, Ctrl-A, 상태줄, 포트 설정 대화상자
    ├── serial_port.py      PortSettings, 수신/송신 스레드, 통계, 끊김 감지, list_ports
    ├── fake_device.py      demo:// 가짜 펌웨어 CLI (공개 펌웨어 cli.c 와 같은 바이트)
    ├── logo.py             시작 로고 (BARAM 블록 문자)
    ├── highlight.py        태그 색상 규칙 ([OK] [E_] WARN, 프롬프트 `...# `)
    ├── i18n.py             tr(), 언어 선택
    ├── locales/ko.json, en.json
    └── (예정) settings.py  설정 저장
```

프롬프트 강조는 특정 문자열이 아니라 "줄 처음의 공백 없는 단어 + `# `" 패턴으로 한다.

## 기본값

- 115200 8N1, 흐름 제어 없음, 로컬 에코 끔, 보내는 Enter = `\r`, Backspace = `0x08`, 받은 LF 는 줄 처음으로.
- 스크롤백 5000 줄, 테마 mono, 글자 크기 14.
