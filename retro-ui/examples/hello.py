"""P1 demo: basic widgets, focus, mouse, timer and a worker-thread signal.

usage: python examples/hello.py [theme] [font]
  theme: dos_blue | amber | green_phosphor | mono_dark | mono (검정 배경 흑백 + 박스 버튼)
  font : d2coding | dunggeunmo | /path/to/font.ttf

글자 크기: [ - ] / [ + ] 버튼, 또는 Cmd/Ctrl + = / Cmd/Ctrl + -
"""

import sys
import threading
import time

import retroui as rui

theme = sys.argv[1] if len(sys.argv) > 1 else "mono"
font = sys.argv[2] if len(sys.argv) > 2 else "d2coding"

# 너무 작으면 읽을 수 없고, 너무 크면 창이 화면을 넘어 보이는 칸 수가 줄어든다
FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 40

app = rui.App(title="retroui hello", size=(64, 20), theme=theme, font=font, font_size=16)

status = rui.Label("ready", fg="accent")
worker_label = rui.Label("worker: -")
# 도움말이 길어도 시계는 잘리지 않게 HH:MM:SS 8칸을 보장한다
clock = rui.Label("", align="right", min_size=(8, 1))
font_size_label = rui.Label(f"{app.fonts.size:2d}", bold=True)
count = {"n": 0}


def on_start():
    count["n"] += 1
    status.set_text(f"Start 클릭 {count['n']}회")


def change_font_size(delta):
    size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, app.fonts.size + delta))
    app.set_font_size(size)
    font_size_label.set_text(f"{app.fonts.size:2d}")
    status.set_text(f"글자 크기 {app.fonts.size}")


hex_cb = rui.CheckBox("Hex 표시", on_toggle=lambda on: status.set_text(f"hex={on}"))
servo_cb = rui.CheckBox("Servo ON", checked=True, on_toggle=lambda on: status.set_text(f"servo={on}"))

app.set_root(
    rui.VBox(
        rui.GroupBox(
            "모터 제어",
            rui.VBox(
                rui.HBox(
                    rui.Button("&Start", on_click=on_start),
                    rui.Button("S&top", on_click=lambda: status.set_text("정지")),
                    rui.Button("&Reset", on_click=lambda: status.set_text("리셋")),
                    rui.Spacer(),
                    spacing=1,
                ),
                rui.HBox(hex_cb, servo_cb, rui.Spacer(), spacing=2),
                rui.HBox(rui.Label("상태:"), status, spacing=1),
                worker_label,
                spacing=1,
                margin=1,
            ),
            stretch=1,
        ),
        rui.HBox(
            rui.Label("글자 크기", align="center"),
            rui.Button("-", on_click=lambda: change_font_size(-1)),
            font_size_label,
            rui.Button("+", on_click=lambda: change_font_size(+1)),
            rui.Spacer(),
            spacing=1,
            align="center",
        ),
        rui.HBox(
            rui.Label("Tab 이동 · Space 누르기 · Cmd/Ctrl +/- 크기 · Q 종료", fg="dim"),
            rui.Spacer(),
            clock,
        ),
    )
)

tick = rui.Signal()
tick.connect(lambda n: worker_label.set_text(f"worker: tick {n} (스레드에서 emit)"))


def worker():
    n = 0
    while app.running:
        n += 1
        tick.emit(n)
        time.sleep(1.0)


threading.Thread(target=worker, daemon=True).start()
app.set_interval(500, lambda: clock.set_text(time.strftime("%H:%M:%S")))
app.add_shortcut("Primary+=", lambda: change_font_size(+1))
app.add_shortcut("Primary+-", lambda: change_font_size(-1))
app.add_shortcut("Primary+Q", app.quit)
app.run()
