"""P2 demo: 3 live plots x 3 series fed at 1kHz from a worker thread.

워커 스레드는 EtherCAT 주기 처리처럼 10ms 마다 10 샘플 묶음을 링버퍼에 넣는다.
상단 stats 는 초당 화면 갱신 수와 프로세스 CPU 사용률 (워커 스레드 포함).

usage: python examples/live_plot.py [theme] [font]
"""

import math
import random
import sys
import threading
import time

import numpy as np

import retroui as rui

theme = sys.argv[1] if len(sys.argv) > 1 else "mono"
font = sys.argv[2] if len(sys.argv) > 2 else "d2coding"

app = rui.App(title="retroui live plot", size=(120, 44), theme=theme, font=font, font_size=13)

NAMES = ("POSITION", "VELOCITY", "CURRENT")
plots = []
series = []
for name in NAMES:
    plot = rui.LivePlot(name, window=4000, update_hz=30)
    plots.append(plot)
    series.append([plot.add_series(f"axis{k}", capacity=8192) for k in range(3)])
plots[2].set_y_range((-2.0, 6.0))

stats = rui.Label("", fg="dim", align="right")


def toggle_pause():
    paused = not plots[0].paused
    for p in plots:
        p.set_paused(paused)


def clear_all():
    for p in plots:
        p.clear()


app.set_root(
    rui.VBox(
        rui.HBox(
            rui.Button("&Pause", on_click=toggle_pause),
            rui.Button("&Clear", on_click=clear_all),
            rui.Label("Tab 이동  Space/더블클릭: 포커스 플롯 일시정지", fg="dim"),
            rui.Spacer(),
            stats,
            spacing=1,
        ),
        *plots,
        spacing=1,
    )
)


def worker():
    t = 0.0
    block = 10
    period = block / 1000.0
    next_t = time.perf_counter()
    while app.running:
        ts = t + np.arange(block) / 1000.0
        for p, ss in enumerate(series):
            for k, s in enumerate(ss):
                ys = np.sin(ts * (1 + p) * 2 + k) * (1 + p) + np.random.normal(0, 0.05, block)
                if p == 2 and random.random() < 0.02:
                    ys[random.randrange(block)] += 4.0  # 전류 스파이크
                s.extend(ys)
        t += period
        next_t += period
        delay = next_t - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            next_t = time.perf_counter()


threading.Thread(target=worker, daemon=True).start()

_last = {"wall": time.monotonic(), "cpu": time.process_time(), "frames": 0}


def update_stats():
    wall = time.monotonic()
    cpu = time.process_time()
    dt = wall - _last["wall"]
    fps = (app.frame_count - _last["frames"]) / dt
    stats.set_text(f"{fps:4.1f} fps  cpu {(cpu - _last['cpu']) / dt * 100:4.1f}%")
    _last.update(wall=wall, cpu=cpu, frames=app.frame_count)


app.set_interval(1000, update_stats)
app.add_shortcut("Primary+Q", app.quit)
app.run()
