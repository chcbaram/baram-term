# 대상 펌웨어 CLI 프로토콜

출처: https://github.com/chcbaram/weact-h750-mini
`firmware/weact-h750-fw/src/common/hw/src/cli.c`, `hw/driver/log.c`, `hw/hw.c`, `ap/ap.c`, `ap/modules/common/cli/cli_mgr.c`
(부트로더 `weact-h750-boot` 도 같은 구조)

## 연결

- 기본 115200 (`cli_mgr.c`). 채널은 UART / USB CDC / NET 중 전환 가능.
- 펌웨어가 **한 글자씩** 받아 줄 편집과 이력을 직접 처리하고 입력을 **에코**한다
  → 터미널은 키를 바로 보내고 로컬 에코는 끈다.

## 키 → 보낼 바이트

| 키 | 바이트 | 펌웨어 처리 |
|---|---|---|
| Enter | `0x0D` | 명령 실행 후 프롬프트 |
| Backspace | `0x08` | 앞 글자 삭제 (`\b \b\x1B[1P` 로 화면 갱신) |
| Delete | `0x7F` | **커서 위치 글자 삭제** (백스페이스 아님) |
| ← → ↑ ↓ | `ESC [ D/C/A/B` | 커서 이동 / 이력 |
| Home | `ESC [ 1 ~` | 줄 처음 |
| End | `ESC [ 4 ~` | 줄 끝 |

macOS 터미널은 보통 Backspace 에 `0x7F` 를 보내는데, 이 펌웨어에서는 삭제 동작이 달라진다. baram-term 기본값은 `0x08`.

## 펌웨어가 보내는 출력

- 프롬프트: `\n\r` + `cli# `
- 명령 결과: `cliPrintf("\r\n")` 등, `\r\n` 과 `\n\r` 이 섞인다. 로그는 `\n` 만 오기도 한다
  → 터미널은 받은 LF 를 줄 처음으로 보낸다 (`lf_implies_cr=True`).
- 쓰는 VT100 코드: `ESC[nP` (글자 삭제), `ESC[4h`/`ESC[4l` (삽입 모드), `ESC[nC`/`ESC[nD`/`ESC[nA`/`ESC[nB`,
  `ESC[?25l`/`ESC[?25h` (커서 숨김/표시, `cliShowCursor`), `\b`.
- 명령어는 대소문자 구분 없음 (argv[0] 을 대문자로 바꿔 비교). 기본 명령 `help`, `md addr [size]`, `log info|boot|list`.

## 로그 형식

코드의 형식 문자열 기준 (값은 자리 표시, 실제 보드 출력으로 확인하지 않음):

```
[ Bootloader Begin... ]                      hw.c: logPrintf("\r\n[ Bootloader Begin... ]\r\n")
Booting..Name 		: <_DEF_BOARD_NAME>        hw.c: "Booting..Name \t\t: %s\r\n"
Booting..Ver  		: <_DEF_FIRMWATRE_VERSION>
Booting..Clock		: <N> Mhz
[  ] boot confirmed (<N> ms)                 ap.c: "[  ] boot confirmed (%d ms)\n"
```

- 태그: `[  ]` 정보는 `ap.c` 에서 확인. `[OK]` 성공 / `[E_]` 실패는 사용자의 펌웨어 로그 규칙
  (초기화 함수 결과를 `logPrintf("[%s] <fn>()\n", ret ? "OK" : "E_")` 형태로 출력).
- 탭(`\t\t`)으로 정렬 → 탭 정지 8칸.
- `log list` 출력은 `%04X\t%s` (줄 번호 + 탭).

## baram-term 에서 확인할 것 (실제 보드 연결 시)

- [ ] Backspace/Delete/Home/End/방향키 동작
- [ ] 이력(↑/↓) 후 줄 다시 그리기가 깨지지 않는지
- [ ] `md` 메모리 덤프 정렬
- [ ] USB CDC 재연결 (보드 리셋 시 포트가 사라졌다 다시 생김)
