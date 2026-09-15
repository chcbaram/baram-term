# 실제 장치로 터미널 확인하기

터미널 위젯이 실제 펌웨어 CLI 의 출력(줄 편집, 커서 이동, 삽입/삭제 코드)을 제대로 그리는지,
장치에서 기록한 바이트를 재생해서 확인한다.

> ⚠ **기록 파일은 저장소에 올리지 않는다.** 회사 보드에서 기록하면 보드 이름, 프롬프트, 명령 목록이 들어갈 수 있다.
> 기록은 git 이 무시하는 `retro-ui/tests/fixtures/local/` 에만 둔다. 이 저장소는 Public 이다.
> 이슈, PR, 문서에도 기록 내용이나 장치 이름을 붙여 넣지 않는다.

## 1. 기록

장치를 연결하고, 같은 포트를 쓰는 다른 프로그램(minicom 등)을 닫은 뒤:

```bash
cd retro-ui
../.venv/bin/python tools/record_cli_session.py /dev/cu.usbmodemXXXX            # macOS
../.venv/bin/python tools/record_cli_session.py /dev/ttyACM0                    # Linux
..\.venv\Scripts\python.exe tools\record_cli_session.py COM3                    # Windows
```

- 기본 저장 위치: `tests/fixtures/local/cli_session.json` (여러 장치면 `-o tests/fixtures/local/<이름>.json`)
- 포트 사용 여부 확인 (macOS/Linux): `lsof /dev/cu.usbmodem*`
- pyserial 이 필요하다 (baram-term 설치 시 함께 설치됨, 없으면 `uv pip install pyserial`)

### 장치에 보내는 것

**명령은 실행하지 않는다.** 빈 Enter 와 줄 편집 키만 보내고, 편집한 줄은 모두 지운 뒤 빈 Enter 로 끝낸다.

| 단계 | 바이트 | 목적 |
|---|---|---|
| enter_prompt | `\r` | 프롬프트 받기 |
| type_h/e/l | `h` `e` `l` | 입력 에코 |
| left | `ESC [ D` | 커서 왼쪽 |
| insert_x | `X` | 가운데 삽입 (`ESC[4h`) |
| backspace_x | `0x08` | 삭제 (`\b \b ESC[1P`) |
| home / end | `ESC [ 1 ~` / `ESC [ 4 ~` | 줄 처음/끝 |
| clear_line | `0x08` x3 | 줄 비우기 |
| history_up | `ESC [ A` | 이력 불러오기 (이력이 비어 있으면 아무 일 없음) |
| clear_history | `0x08` x16 | 불러온 줄 비우기 |
| enter_empty | `\r` | 빈 줄 Enter |

`--with-help` 를 주면 이력 확인용으로 `help` 를 먼저 실행한다 (명령 목록이 기록에 들어가므로 필요할 때만).

## 2. 재생 테스트

```bash
cd retro-ui
../.venv/bin/python -m pytest -q tests/test_terminal_recorded_sessions.py
```

- `tests/fixtures/local/*.json` 을 모두 재생한다. 없으면 skip.
- 프롬프트 문자열은 코드에 적지 않고 기록에서 뽑아, 각 단계 뒤 커서 줄 글자와 커서 열만 비교한다.
- 실패하면 `TerminalScreen` 이 장치가 보낸 제어 코드를 다르게 해석한 것이다.
  기록 도구 출력의 "replayed last lines" 와 원본 바이트(JSON 의 `hex`)를 비교해 원인을 찾는다.

## 3. 커밋 전 확인

```bash
git status --short --ignored retro-ui/tests/fixtures    # local/ 은 !! (ignored) 로 보여야 한다
```

## 공개해도 되는 테스트 데이터

저장소에 올리는 CLI 관련 테스트는 공개 펌웨어([weact-h750-mini](https://github.com/chcbaram/weact-h750-mini) 의 `cli# `)
형식이나 baram-term 의 가짜 장치(`demo://`)만 사용한다.
