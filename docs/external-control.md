# 외부 제어 (`baram-term ctl`)

baram-term 이 포트를 쥔 채로, 다른 프로그램이 그 포트로 명령을 보내고 받은 내용을 읽게 한다.
Claude Code 같은 도구가 보드 CLI 를 시험할 때 사용자가 쓰던 창을 닫지 않아도 되고,
보낸 명령과 응답은 사용자 화면에도 그대로 보인다.

- 켜고 끄기: **포트 메뉴 > 외부 제어 허용 (baram-term ctl)**. 기본은 켜짐 (설정 `"control": true`).
- 외부 연결이 있으면 상태줄에 `CTL` 이 뜬다 (요청이 끝나도 3초 동안 남는다).
- 창 제목에 포트 경로가 붙는다 (`baram-term - /dev/cu.usbmodem1234`): 창을 여러 개 띄웠을 때 구별용.

## 명령

```bash
baram-term ctl list                                   # 떠 있는 창 (포트, 속도, 연결 상태, USB 정보)
baram-term ctl status                                 # 포트, 속도, 줄끝, 연결 여부, 외부 제어 상태, mark
baram-term ctl send "info"                            # 한 줄 보내기 (줄끝은 설정을 따름, --eol 로 지정)
baram-term ctl send "info" --until 'cli# $' --timeout 5   # 보내고, 정규식이 나올 때까지 받은 것을 출력
baram-term ctl read --last 20                         # 최근 받은 20줄
baram-term ctl read --since 18231                     # mark 뒤에 받은 전부
baram-term ctl wait --until 'cli# $' --timeout 10     # 보내지 않고 기다리기 (--since 로 앞서 받은 것도 포함)
baram-term ctl release                                # 포트를 잠시 닫기 (자동 재연결도 멈춤, 업데이트 도구용)
baram-term ctl resume                                 # 다시 열기
```

- 공통 옵션: `--json` (응답 JSON 그대로), `--pid`, `--port 경로`, `--match 글자` (대상 창 고르기).
- 출력은 ANSI 코드와 CR 을 뺀 글자다. `--raw` 면 받은 그대로.
- `--until` 정규식은 정리된 글자에 여러 줄 모드(`re.MULTILINE`)로 맞춘다.
- **mark**: 창이 켜진 뒤 받은 글자 수. 응답마다 현재 mark 가 있고, 텍스트 출력에서는 stderr 에 `[mark N]`.
  보드를 리셋하기 전에 mark 를 잡아 두고 `wait --since` / `read --since` 로 부팅 메시지를 빠짐없이 본다.
  수신 기록은 최근 100만 글자까지 둔다. 더 오래된 mark 를 주면 남은 것만 주고 `truncated` 를 붙인다.

종료 코드: 0 성공, 1 오류, 2 인자 오류, 3 시간 초과, 4 baram-term 이 없거나 외부 제어가 꺼짐,
5 대상 창을 하나로 고르지 못함 (후보 목록을 출력하고 아무것도 보내지 않는다).

## 창이 여러 개일 때

창마다 자기 소켓을 연다. `ctl` 은 소켓을 모두 훑어 각 창의 `status` 를 받고 대상을 고른다.

- 창이 하나면 대상 옵션 없이 그 창.
- 여럿이면 `--pid` / `--port` / `--match` 로 좁힌다. 옵션이 없거나, 맞는 창이 없거나, 여럿이 맞으면
  **아무것도 보내지 않고** 후보를 보여 준 뒤 종료 코드 5. 엉뚱한 보드에 명령이 가지 않게 하려는 것이다.
- `--match` 는 포트 경로, USB 설명/제조사/제품/시리얼, VID:PID, 창 제목에서 대소문자 없이 찾는다.
  포트 경로는 PC 마다 다르므로 USB 시리얼이나 설명(예: `STLink`)으로 고르는 편이 옮겨 다니기 좋다.

## 소켓과 보안

| OS | 위치 | 보호 |
|---|---|---|
| macOS / Linux | `~/.baram-term/ctl/<pid>.sock` (유닉스 소켓) | 소켓 0600, 폴더 0700: 같은 사용자만 |
| Windows | `127.0.0.1` 의 임의 TCP 포트. 포트와 토큰은 `~/.baram-term/ctl/<pid>.json` | 로컬 주소만 듣고, 요청마다 토큰을 확인 |

- 비정상 종료로 남은 소켓은 주인 pid 가 없으면 `ctl list`/연결 시, 그리고 새 창이 켜질 때 지운다.
- `BARAM_TERM_CTL_DIR` 로 `~/.baram-term` 대신 다른 폴더를 쓴다 (테스트용).

## 프로토콜

연결 하나에 JSON 한 줄 요청 → JSON 한 줄 응답 (여러 번 주고받을 수 있다). Windows 는 요청에 `"token"` 을 넣는다.

```json
{"cmd": "send", "text": "info", "until": "cli# $", "timeout": 5, "eol": "cr", "raw": false}
{"ok": true, "cmd": "send", "sent": "info\r", "output": "info\nBoard  : baram-demo\n...\ncli# ", "start": 170, "mark": 236}
```

| cmd | 요청 필드 | 응답 필드 |
|---|---|---|
| `status` | | `pid, port, kind, baud, framing, mtu, enter, connected, connecting, released, reconnecting, control, clients, title, version, usb, mark` |
| `send` | `text`, `until?`, `timeout?`, `eol?`, `raw?` | `sent, output?, start, mark` |
| `read` | `since?` 또는 `last?` (기본 50줄), `raw?` | `output, mark, truncated?` |
| `wait` | `until`, `timeout?`, `since?`, `raw?` | `output, start, mark, truncated?` |
| `release` / `resume` | | `status` 와 같음 |

실패하면 `{"ok": false, "error": "timeout|not_connected|released|no_port|open_failed|bad_regex|bad_request|busy|denied|internal", "message": ...}`.
`timeout` 일 때도 그때까지 받은 `output` 이 들어 있다. `usb` 는 USB 포트일 때만
`{vid_pid, serial_number, description, manufacturer, product, location}`.

## 구현

- `baram_term/ctl.py` — 클라이언트와 공용 경로. 표준 라이브러리만 쓴다 (pygame 을 올리지 않는다).
  플러그인의 `bin/baram-ctl` 은 이 파일을 python 으로 바로 실행한다.
- `baram_term/control.py` — 서버. 수신 기록(`RxHistory`)은 UI 스레드가 `_on_rx` 에서 채우고, 연결 스레드는
  조건 변수로 기다린다. 포트 쓰기·상태·닫고 열기는 `app.call_soon` 으로 UI 스레드에서 한다.
- `send` 는 보내기 직전의 mark 부터 찾는다. 인자(정규식, 시간)를 먼저 확인하고 보낸다: 보낸 뒤의 오류는 되돌릴 수 없다.
- BLE 포트는 여는 데 몇 초 걸린다. `resume` 은 열기를 시작만 하고 바로 답한다 (`connecting: true`).
  연결을 기다리려면 `status` 를 다시 보거나 `wait --until '프롬프트'` 를 쓴다.
- release 상태에서는 자동 재연결을 하지 않는다. 사용자가 연결(`Ctrl-A R`)하거나 `resume` 하면 풀린다.

## Claude Code 스킬

저장소가 Claude Code 플러그인 마켓플레이스를 겸한다 (`.claude-plugin/`, `skills/baram-term/SKILL.md`, `bin/baram-ctl`).
설치는 [README](../README.md#claude-code-와-함께-쓰기) 참고.
