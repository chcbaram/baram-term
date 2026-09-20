---
name: baram-term
description: Send firmware CLI commands to a board over its serial port and read the replies through a running baram-term window (baram-ctl / baram-term ctl). Use when you need to run commands on a connected board's serial CLI, check boot messages after a reset, or read recent serial output while the user keeps the port open in baram-term. Also covers choosing the right window when several baram-term windows are open, and temporarily releasing the port for a flashing tool.
---

# baram-term 으로 보드 CLI 쓰기

사용자가 baram-term 창으로 보드의 시리얼 포트를 열어 두고 있으면 그 포트를 직접 열지 않는다
(macOS 는 열리더라도 수신 데이터를 나눠 가져가 양쪽 다 깨진다). baram-term 을 거쳐 보내고 읽는다.
보낸 명령과 보드의 응답은 사용자의 baram-term 화면에도 그대로 보이고, 상태줄에 `CTL` 이 뜬다.

## 명령 이름

- `baram-ctl` — 이 플러그인이 PATH 에 넣는 명령. 아래 예시는 모두 이것을 쓴다.
- PATH 에 없으면 (스킬만 링크한 경우) `"${CLAUDE_SKILL_DIR}/../../bin/baram-ctl"`.
- `baram-term ctl ...` 도 같은 명령이다 (새 버전 baram-term 이 PATH 에 있을 때).

`--json` 을 붙이면 응답 JSON 을 그대로 찍는다. `send`/`read`/`wait` 는 stderr 에 `[mark N]` 을 찍는다
(받은 글자 수 위치. 그 뒤에 받은 것만 다시 읽을 때 쓴다).

## 1. 창 고르기 — 항상 먼저

```bash
baram-ctl list
# pid 4242  /dev/cu.usbmodem1234  115200 8N1  connected  [STM32 STLink · SER=0673FF... · VID:PID=0483:3752]
```

- 창이 하나면 그대로 쓴다. 대상 옵션 없이 명령하면 된다.
- 창이 여럿이면 어느 보드인지 대화나 프로젝트 문서(CLAUDE.md 등)로 **확실할 때만** 고른다. 아니면 목록을
  사용자에게 보여 주고 묻는다. 추측으로 고르지 않는다.
- 정한 뒤로는 **모든 명령에** `--port <경로>` 또는 `--match <글자>` 를 붙인다.
  `--match` 는 포트 경로, USB 설명/제조사/시리얼, VID:PID, 창 제목에서 대소문자 없이 찾는다.
- 포트 경로는 PC 와 USB 자리마다 다르다. 경로를 문서나 코드에 박아 두지 말고 `list`/`status` 로 확인한다.
  같은 보드를 PC 가 바뀌어도 가리키려면 USB 시리얼 번호로 `--match` 한다.
- 대상이 모호하면 ctl 은 아무것도 보내지 않고 후보를 보여 준 뒤 종료 코드 5 로 끝난다.

```bash
baram-ctl --match STLink status
```

`status` 로 `connected: yes`, 속도·프레이밍, 줄끝(`enter`)을 확인한다.

## 2. 명령 보내고 응답 받기

```bash
baram-ctl --match STLink send "help" --until 'cli# $' --timeout 5
```

- `--until` 은 응답이 끝났다고 볼 정규식이다. 보통 펌웨어 프롬프트를 줄 끝에 맞춘다 (위는 baram-term 데모
  펌웨어의 `cli# `). 프롬프트를 모르면 먼저 `baram-ctl read --last 5` 로 화면 끝을 본다.
- 정규식은 ANSI 색 코드와 CR 을 뺀 글자에 여러 줄 모드로 맞춘다 (`^`, `$` 가 줄마다 맞는다).
- 출력은 에코된 명령 줄부터 `--until` 이 맞은 곳(보통 다음 프롬프트)까지다.
- `--until` 없이 보내면 기다리지 않고 바로 돌아온다.
- 줄끝은 baram-term 설정을 따른다. 바꾸려면 `--eol cr|lf|crlf|none`.
- 한 번에 한 줄. 여러 명령은 `send` 를 여러 번.
- 보드를 지우거나 쓰거나 리셋하는 명령은 사용자에게 먼저 확인받는다.
- 사용자가 baram-term 에 치다 만 줄이 있으면 보낸 글자가 그 뒤에 붙는다. 출력이 이상하면 `read --last` 로 확인한다.

## 3. 리셋 뒤 부팅 메시지 보기

리셋하기 **전에** mark 를 잡아 두면 부팅 메시지를 놓치지 않는다.

```bash
baram-ctl --match STLink --json status          # ... "mark": 18231 ...
# (보드 리셋: 리셋 버튼, 프로그래머, 또는 CLI 명령)
baram-ctl --match STLink wait --since 18231 --until 'cli# $' --timeout 15
baram-ctl --match STLink read --since 18231     # 그 뒤에 받은 전부
```

USB CDC 보드는 리셋하면 포트가 잠시 사라진다. baram-term 의 자동 재연결이 다시 붙으니 `status` 로
`connected: yes` 를 확인한 뒤 명령을 보낸다.

## 4. 포트를 잠시 비워 주기

같은 포트를 다른 도구가 열어야 할 때 (시리얼 부트로더로 굽기 등):

```bash
baram-ctl --match STLink release   # baram-term 이 포트를 닫는다 (자동 재연결도 멈춤)
# ... 다른 도구로 작업 ...
baram-ctl --match STLink resume    # 다시 연다. 끝나면 반드시 resume
```

ST-LINK 의 SWD 로 굽는 경우는 시리얼 포트와 상관없어 release 가 필요 없다.

**펌웨어 업데이트 도구(mcumgr, smpclient 등)를 쓸 때는 거의 항상 release 가 필요하다.** 요즘 펌웨어는
업데이트 프로토콜(SMP)을 CLI 와 **같은 포트** 에 얹는 경우가 많고, BLE 도 한 번에 한 중앙만 붙는다.
release 하지 않으면 baram-term 이 응답 일부를 가져가 업로드가 알 수 없는 이유로 실패한다.
BLE 는 `resume` 이 연결을 기다리지 않고 바로 답하므로, 이어서 명령을 보내기 전에
`status` 의 `connected` 를 보거나 `wait --until '<프롬프트>'` 로 링크가 살아나기를 기다린다.

## 종료 코드와 대처

| 코드 | 뜻 | 할 일 |
|---|---|---|
| 0 | 성공 | |
| 1 | 오류. `not_connected`: 창은 있는데 포트가 닫혀 있음 / `released`: release 상태 / `open_failed` / `bad_regex` | `status` 로 확인. 닫혀 있으면 사용자에게 연결을 부탁하거나, 직접 놓았던 것이면 `resume` |
| 2 | 인자 오류 | `baram-ctl --help`, `baram-ctl send --help` |
| 3 | 시간 초과. 그때까지 받은 출력은 그대로 나온다 | 정규식·시간 확인, `read --last 20` 으로 화면 보기 |
| 4 | baram-term 이 떠 있지 않거나 외부 제어가 꺼져 있음 | 사용자에게 baram-term 을 실행하고 **포트 메뉴 > 외부 제어 허용** 을 켜 달라고 한다. 외부 제어가 없는 옛 버전이면 업데이트가 필요하다. 포트를 직접 열지 않는다 |
| 5 | 창이 여럿인데 대상을 안 줬거나, 맞는 창이 없거나 여럿 | 후보 목록을 사용자에게 보여 주고 어느 보드인지 묻는다 |

`list` 에 원하는 보드가 없으면 그 보드의 포트를 baram-term 이 열고 있지 않은 것이다. 사용자에게 알린다.
