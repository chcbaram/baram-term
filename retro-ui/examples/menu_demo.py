"""Pull-down menu demo in the style of DOS-era word processors.

F10 또는 마우스로 메뉴를 연다. Alt+F/E/C/V 로 해당 메뉴를 바로 연다.
아래 실시간 플롯 위로 메뉴를 열어도 플롯이 메뉴를 덮지 않는지 확인할 수 있다.

usage: python examples/menu_demo.py [theme] [font]
"""

import math
import sys
import threading
import time

import numpy as np

import retroui as rui
from retroui import Menu, MenuBar, MenuItem

theme = sys.argv[1] if len(sys.argv) > 1 else "mono"
font = sys.argv[2] if len(sys.argv) > 2 else "d2coding"

app = rui.App(title="retroui menu", size=(84, 32), theme=theme, font=font, font_size=15)

status = rui.Label("F10 또는 마우스로 메뉴를 여세요", fg="accent")
plot = rui.LivePlot("SIGNAL", window=3000, update_hz=30)
signal = plot.add_series("sin")


def set_status(text):
    status.set_text(text)


def toggle_pause():
    plot.set_paused(view_items["pause"].checked)


style_items = [
    MenuItem("외곽선", key="O", checked=False),
    MenuItem("그림자", key="S", checked=False),
    MenuItem("음영", key="A", checked=False),
    MenuItem("역상", key="R", checked=False),
    MenuItem("밑줄", key="U", checked=False),
    MenuItem("진하게", key="B", checked=True),
    MenuItem.sep(),
    MenuItem("보통모양", key="N"),
]

view_items = {
    "pause": MenuItem("플롯 일시정지", toggle_pause, key="P", checked=False),
    "status": MenuItem("상태줄 표시", lambda: setattr(status, "visible", view_items["status"].checked), key="T", checked=True),
}

bar = MenuBar(
    [
        Menu(
            "한",
            [
                MenuItem("한글 이란", lambda: set_status("retroui 풀다운 메뉴 데모")),
                MenuItem("도움말", shortcut="F1"),
                MenuItem("자판배열", shortcut="Alt+F1"),
                MenuItem("달력"),
                MenuItem("계산기", enabled=False),
                MenuItem("전화번호부"),
            ],
        ),
        Menu(
            "서류철(&F)",
            [
                MenuItem("새 서류", shortcut="Alt+N", key="N"),
                MenuItem("불러오기", shortcut="Alt+O", key="O"),
                MenuItem("저장하기", shortcut="Alt+S", key="S"),
                MenuItem.sep(),
                MenuItem("끝", app.quit, shortcut="Primary+Q", key="X"),
            ],
        ),
        Menu(
            "편집(&E)",
            [
                MenuItem("오려두기", shortcut="Primary+X"),
                MenuItem("복사하기", shortcut="Primary+C"),
                MenuItem("붙이기", shortcut="Primary+V"),
                MenuItem.sep(),
                MenuItem("모두 선택", shortcut="Primary+A"),
            ],
        ),
        Menu("글자(&C)", style_items),
        Menu("화면(&V)", list(view_items.values())),
    ]
)


def on_triggered(item):
    if item.checked is None:
        set_status(f"선택: {item.text}")
    else:
        set_status(f"선택: {item.text} = {'켜짐' if item.checked else '꺼짐'}")


bar.triggered.connect(on_triggered)

document = rui.VBox(
    rui.Label("밤새 내린 눈이 공장 지붕을 하얗게 덮었다. 제어반의 초록 불빛만이 깜박이며"),
    rui.Label("모터가 여전히 돌고 있다는 것을 알려 주었다. 나는 식은 커피를 한 모금 마시고"),
    rui.Label("다시 화면을 들여다보았다. 위치 오차는 어제보다 조금 줄어 있었다."),
    rui.Label(""),
    rui.Label("메뉴는 F10, Alt+F/E/C/V, 방향키, Enter, Esc 로도 조작할 수 있다.", fg="dim"),
    margin=1,
)

app.set_root(
    rui.VBox(
        bar,
        rui.GroupBox("문서", document, stretch=1),
        plot,
        rui.HBox(status, rui.Spacer(), rui.Label("[한글]  1 장  1 열  삽입", fg="dim")),
    )
)


def worker():
    t = 0.0
    while app.running:
        ts = t + np.arange(10) / 1000.0
        signal.extend(np.sin(ts * 2 * math.pi * 0.7) + np.random.normal(0, 0.03, 10))
        t += 0.01
        time.sleep(0.01)


threading.Thread(target=worker, daemon=True).start()
app.add_shortcut("Primary+Q", app.quit)
app.run()
