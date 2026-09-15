# retro-ui 구조

## 모듈 지도 (`retro-ui/src/retroui/`)

| 모듈 | 역할 |
|---|---|
| `app.py` | App: 창, HiDPI 배율 (Windows 는 DPI 힌트), 이벤트 루프, 포커스, 팝업 스택, damage 기반 페인트, 픽셀 위젯 합성, IME 켜고 끄기(`refresh_text_input`), 툴팁 띄우기 |
| `theme.py` | Palette(역할별 색), BoxStyle, 테마 프리셋, `resolve_color`, `lighten` |
| `core/geometry.py` | Rect (셀/픽셀 공용), `subtract` (팝업 가림 계산) |
| `core/wcwidth.py` | 글자 폭 (한글 2칸, 모호폭 1칸), NFC 정규화, `slice_cols`, `truncate` |
| `core/layout.py` | `distribute()` — min/pref/stretch 로 길이 나누기 (순수 함수) |
| `core/signal.py` | Signal — 워커 스레드에서 emit 하면 메인 스레드로 넘어간다 |
| `core/timers.py` | TimerQueue — 누적 지연 없는 반복 타이머 |
| `render/cellbuffer.py` | 셀 `(ch, fg, bg, attr)` 버퍼, 와이드 문자, 변경 구간 추적, `fill_attr` |
| `render/fonts.py` | FontSet — 폰트 찾기(저장소 폰트 우선), 셀 크기, 글리프 캐시, fallback |
| `render/boxdraw.py` | 박스/블록/사분면/버튼 테두리 문자를 도형으로 그림 |
| `render/painter.py` | 위젯 로컬 좌표 + 클립으로 셀 버퍼에 쓰기 |
| `render/renderer.py` | 변경된 셀만 서피스에 그림 |
| `input/events.py` | pygame 이벤트 → Key/Text/Composition/Mouse/Wheel 이벤트, scancode 로 키 이름 복원, `KeyEvent.scancode`/`caps`, 미국 배열 글자 `us_ascii` |
| `input/ime.py` | ImeFilter (macOS 한글 조합 보정, 입력 전환 단축키가 만든 스페이스 버리기), `hangul_backspace` |
| `input/mac_hotkeys.py` | macOS 입력 소스 전환 단축키(`com.apple.symbolichotkeys` 60·61) 중 스페이스 조합 읽기 |
| `widgets/*` | base, containers, label, button, checkbox, frame, pixel, plot, popup, tooltip, menu, lineedit, combobox, dialog, terminal |

툴팁은 위젯마다 만들지 않는다. 위젯에 `tooltip = "설명"` 만 넣으면 App 이 hover 를 재서
`App.tooltip_delay` 초 뒤에 위젯 **위**로 띄우고, hover 가 바뀌거나 키/클릭이 오면 지운다
(커서와 겹치면 hover 가 툴팁으로 넘어가 깜빡인다).

터미널 입력 모드: `Terminal.ascii_input` 이 켜지면 `wants_text_input` 이 False 가 되어 App 이 IME 를 끄고,
글자는 KEYDOWN 의 물리 키 위치(`us_ascii`, 미국 배열 + Shift + Caps Lock)로 만든다. 포커스는 그대로인데
이 값을 바꿨다면 `App.refresh_text_input()` 을 불러야 IME 상태가 따라온다 (IME 는 포커스가 바뀔 때만 다시 본다).

휠: SDL 값에는 OS 설정(macOS 자연스러운 스크롤, 속도·가속)이 이미 들어 있어 그대로 쓴다. `flipped` 를 보고
다시 뒤집지 않는다. `Terminal.wheel_lines` 는 값 1 에 움직일 줄 수로 macOS 1, 그 외(휠 한 칸 = 1) 3.
소수 값은 모아서 줄 단위로 움직인다.

## 그리기 흐름

```
위젯.invalidate() ─▶ App.damage(합쳐진 사각형)
                        │ (fps 상한 안에서)
                        ▼
  damage 영역 배경 채우기 → root 위젯 paint → 팝업(그림자 → 팝업) paint     ← 셀 버퍼에 쓰기
                        ▼
  Renderer: 이전 프레임과 다른 셀만 서피스에 그림 (박스 문자는 도형, 글자는 캐시 글리프)
                        ▼
  픽셀 위젯 합성: 오프스크린 서피스를 팝업 영역을 뺀 부분만 blit
                        ▼
  window.flip()
```

- **셀 모델**: 화면은 글자 셀 격자다. 와이드 문자는 `x` 에 글자, `x+1` 에 `WIDE_CONT`. 한쪽 절반이 덮이면 나머지는 공백이 된다.
- **PIXEL 셀**: 픽셀 위젯 영역 셀은 `Attr.PIXEL` 로 표시해 셀 렌더러가 건너뛴다.
- **FILL 속성**: 셀에 세 번째 색(안쪽 채움)이 필요할 때 attr 상위 비트에 RGB 를 싣는다 (박스 버튼 테두리).
- **팝업 가림**: 픽셀 위젯은 `Rect.subtract` 로 팝업(+그림자) 영역을 빼고 합성한다.

## 이벤트 루프

- 그릴 게 없으면 `pygame.event.wait(timeout)` 으로 **다음 타이머/플롯 폴링 시각까지 잠든다** (idle CPU ≈ 0).
- 픽셀 위젯은 `frame_deadline()` 으로 다음 확인 시각을 알려주고, 반 프레임 안에 몰린 폴링은 한 프레임에 묶는다.
- 워커 스레드 → UI: `app.call_soon(fn, *args)` 또는 `Signal.emit()`. WAKE 이벤트는 한 번만 보내고 합친다.
- 플롯 데이터는 스레드가 `RingBuffer` 에 직접 쓰고, UI 는 버전 번호로 바뀐 것만 다시 그린다.

## 입력

- **포커스/키**: 키 필터(`add_key_filter`) → 포커스 위젯에서 부모로 bubble → 전역 키 훅(`global_key`, 예: MenuBar F10)
  → 단축키(`add_shortcut`) → Alt+니모닉 → Tab 포커스 이동.
- **마우스**: 위 레이어부터 hit 판정. 비모달 팝업은 바깥 클릭 시 닫히고 클릭은 아래로 전달, 모달은 막는다.
  누른 위젯이 캡처해서 드래그/놓기를 받는다.
- **IME**: `wants_text_input` 위젯이 포커스를 가질 때만 켠다. 모든 입력 이벤트는 `ImeFilter` 를 거친다
  (보정 내용은 [decisions.md](decisions.md#한글-ime-보정)). 후보창 위치는 위젯의 `caret_cell()` 로 맞춘다.

## 레이아웃

- 모든 크기는 **셀 단위**. 위젯은 `size_hint()` 로 min/pref/max 를 알려준다.
- HBox/VBox 는 `distribute()` 로 주 축을 나누고(pref 먼저, 남으면 stretch 비율), 교차 축은 fill/start/center/end.
- 레이아웃은 필요할 때만(`relayout()`) 다시 계산하고 전체를 다시 칠한다. 셀 diff 덕분에 실제로 그리는 양은 작다.

## 위젯 작성 규칙

- `paint(p)` 는 로컬 좌표, `rect` 는 절대 셀 좌표. 이벤트의 `cx/cy` 는 절대 좌표.
- 상태가 바뀌면 `invalidate()`, 크기가 바뀌면 `relayout()`.
- `on_event` 가 True 를 돌려주면 소비, False 면 부모로.
- 크기 계산에 테마가 필요하면 앱에 붙은 뒤 계산해야 한다 (`Dialog.open` 버그 참고).
- 위젯은 pygame 을 직접 쓰지 않는다 (예외: PixelWidget 계열의 픽셀 그리기).

## 테스트 방식

- 순수 로직: layout, wcwidth, cellbuffer, timers, signal, ringbuffer/decimate, ime, TerminalScreen.
- 헤드리스 앱: `App(headless=True)` + `app.dispatch(이벤트)` + `app.screen_text()` / `app.buf.get()` / 서피스 픽셀 검사.
- 실제 창 확인은 `examples/*.py` 를 타이머로 자동 종료시키며 스크린샷을 찍는 방식으로 했다.
