# BLE 장치 (`ble://`)

BLE 보드를 시리얼 포트처럼 쓴다. [Nordic UART Service(NUS)](https://docs.nordicsemi.com/bundle/ncs-latest/page/nrf/libraries/bluetooth/services/nus.html)
로 주고받으므로, 펌웨어가 UART CLI 를 NUS 위에 올려 두었으면 baram-term 은 시리얼과 똑같이 쓴다
(터미널·그래프·HEX·로그·찾기·자동완성·매크로·메모·외부 제어 모두 그대로).

## 쓰는 법

1. **포트 메뉴 > BLE 장치 사용** 을 켠다 (기본 꺼짐, 설정 `"ble": true`). 꺼져 있으면 스캔도 하지 않는다 —
   시리얼만 쓰는 사람에게 macOS 블루투스 권한을 묻지 않으려는 것이다.
2. **포트 설정**(`Ctrl-A O`) 에서 종류를 `BLE` 로 바꾸고 **검색** 을 누른다. 몇 초 뒤 가까운 장치가 가까운 순으로 나온다.
3. 장치를 고르고 확인하면 주소 칸이 `ble://이름` 이 된다. 다음부터는 상태줄 포트 메뉴의 최근 목록에 남는다.

`baram-term "ble://CLI-BOARD"` 처럼 실행 인자로 바로 열 수도 있다.

설치는 선택이다: `pip install "baram-term[ble]"` (또는 `uv pip install -e "baram-term[dev,ble]"`).
**이미 만들어 둔 개발 환경에는 bleak 이 없다.** `git pull` 만으로는 들어오지 않으니 설치 명령을 한 번 더 돌린다.
릴리스 빌드(.dmg/zip/tar.gz)에는 포함돼 있어 설정에서 켜기만 하면 된다. bleak 이 없으면 메뉴를 켤 때 안내가 뜬다.

## 주소 형태

| 주소 | 무엇을 찾나 |
|---|---|
| `ble://CLI-BOARD` | 그 이름을 광고하는 장치 |
| `ble://CLI-BOARD#1a2b3c4d` | 같은 이름이 여럿일 때: 광고 제조사 데이터의 끝 4바이트가 꼬리표 |
| `ble://6C1F0A72-3B54-...` | 장치 주소로 바로 (macOS 는 CoreBluetooth UUID, 그 외는 MAC) |

**기본은 이름이다.** macOS 는 장치의 MAC 대신 PC 마다 다른 UUID 를 주기 때문에, 주소로 저장하면 같은 보드라도
다른 PC 에서 찾지 못한다. 이름은 어느 PC 에서나 같다.

## 목록에 나오는 것

검색은 **NUS 를 광고하는 장치만** 보여준다. 둘레에 흔한 이어폰·시계·TV 까지 나오면 고르기 어렵고,
그것들은 어차피 열어도 쓸 수 없다. 광고에 서비스 UUID 를 싣지 않는 보드는 목록에 나오지 않는다
(그럴 일이 생기면 "전부 보기" 를 더한다).

펌웨어 쪽 권장 사항:

- 광고 패킷에 NUS 128비트 UUID, 스캔 응답에 완전한 로컬 이름. 31바이트에 둘 다 넣기는 빠듯하다.
- 제조사 데이터 끝에 보드 고유 ID 4바이트 — 같은 이름 보드를 구별하는 꼬리표로 쓴다.
- 줄끝 CR, 프롬프트 `cli# ` 처럼 시리얼과 같게. 프롬프트가 `^\S*# ` 에 맞아야 Tab 자동완성과
  메모 여러 줄 보내기(프롬프트 대기)가 동작한다.
- 구독(notify)이 꺼져 있으면 출력은 버리고, 구독이 켜지면 프롬프트를 한 번 다시 찍는다.
- 연결이 끊기면 **광고를 다시 시작한다.** Zephyr 는 연결 해제 콜백 안에서 `bt_le_adv_start()` 가
  `-ENOMEM` 을 내므로 워크큐로 미뤄야 한다 (실제로 여기서 막힌 적이 있다).

## 알아 둘 것

- **한 번에 한 창만** 붙는다. 중앙(PC) 하나가 이미 연결 중이면 보드는 광고하지 않으므로 다른 창에서는 보이지 않는다.
- 속도·패리티·흐름 제어는 BLE 에 없다. 그 줄들은 포트 설정 창에서 숨고, 상태줄에는 `BLE MTU 247` 처럼 나온다.
- MTU 는 연결할 때 정해진다. 23(협상 실패)이면 한 번에 20바이트씩만 나가므로 긴 출력이 느리다.
- 연결 간격이 길면 타이핑 에코가 느리게 느껴진다. 15~30ms 를 권한다.
- 자동 재연결은 시리얼과 같게 동작한다. 다만 BLE 는 매번 스캔부터 하므로 몇 초 걸린다.
- 시리얼(VCOM)과 BLE 를 동시에 열어 두었고 펌웨어가 CLI 채널을 하나만 쓰면, 한쪽에 입력하는 순간
  다른 쪽 출력이 멈출 수 있다. 펌웨어의 채널 전환 규칙을 따른다.

## 외부 제어

`baram-term ctl` 은 포트 종류를 가리지 않는다. BLE 창도 똑같이 다룬다 ([external-control.md](external-control.md)).

```bash
baram-term ctl list
# pid 71892  ble://CLI-BOARD  BLE MTU 247  connected
baram-term ctl --match CLI-BOARD send "adc info" --until 'cli# $'
```

`status` 는 BLE 창에 `kind: ble`, `mtu: 247` 을 주고 `baud`/`framing` 은 주지 않는다.
`--match` 는 포트 문자열과 창 제목에서 찾으므로 장치 이름으로 고르면 된다.

## 구현

- `baram_term/ble.py` — 스캔(`scan`)과 장치(`BleDevice`). `open_device()` 가 `ble://` 를 여기로 보낸다.
- 장치 객체는 pyserial 처럼 `read`/`write`/`in_waiting`/`close`/`is_open` 만 제공한다. 그래서 앱은 BLE 인지
  모르고 쓴다 (`fake_device.py` 와 같은 방식).
- bleak 은 asyncio 전용이라 장치마다 이벤트 루프를 백그라운드 스레드에서 돌리고, 앱의 수신/송신 스레드는
  `run_coroutine_threadsafe` 로 건너간다. 알림은 콜백에서 버퍼에 쌓고 `read` 가 조건 변수로 기다린다.
- 쓰기는 MTU-3 바이트씩 잘라 **응답 없는 쓰기**로 보낸다 (장치가 에코를 보내므로 응답을 기다릴 필요가 없다).
- 끊기면 `read`/`write` 가 `OSError` 를 낸다. 그 뒤는 시리얼이 뽑혔을 때와 같은 길(자동 재연결)로 간다.
- bleak 은 `ble.py` 안에서, 그것도 함수 안에서 늦게 불러온다. 설치돼 있지 않아도 baram-term 은 그대로 뜬다.
- 테스트는 가짜 bleak 으로 돈다 (`tests/test_ble.py`): 실제 블루투스 없이 스캔·연결·쓰기·끊김·MTU 분할을 확인한다.
