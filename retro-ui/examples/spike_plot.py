"""P0 spike: 실시간 플롯 렌더링 비용 측정.

3 plot x 3 series, 워커 스레드가 1kHz 로 링버퍼에 기록.
각 phase 의 평균 draw/present 시간, fps, 프로세스 CPU 사용률을 출력한다.

phase:
  idle        : 그리지 않음 (워커 스레드 + 루프 자체 비용 baseline)
  raw-aa      : 모든 점을 aalines 로 그림
  dec-aa      : 픽셀 열마다 min/max 로 줄여서 aalines
  dec-lines   : min/max + 안티앨리어싱 없는 lines
  dec-lines30 : dec-lines 를 30Hz 로 갱신 (pglive update_rate 와 같은 throttle 효과)

usage: python examples/spike_plot.py [seconds_per_phase] [capacity]
"""

import math
import os
import random
import sys
import threading
import time

import numpy as np
import pygame

OUT_DIR = os.environ.get("SPIKE_OUT", "_spike_out")
COLORS = [(85, 255, 85), (85, 255, 255), (255, 255, 85)]
PHASES = [
  ("idle", None, 60),
  ("raw-aa", "raw-aa", 60),
  ("dec-aa", "dec-aa", 60),
  ("dec-lines", "dec-lines", 60),
  ("dec-lines30", "dec-lines", 30),
]


class Ring:
  def __init__(self, capacity):
    self.buf = np.zeros(capacity, dtype=np.float64)
    self.head = 0
    self.count = 0
    self.lock = threading.Lock()

  def append(self, v):
    with self.lock:
      self.buf[self.head] = v
      self.head = (self.head + 1) % len(self.buf)
      self.count = min(self.count + 1, len(self.buf))

  def snapshot(self):
    with self.lock:
      if self.count < len(self.buf):
        return self.buf[: self.count].copy()
      return np.concatenate((self.buf[self.head :], self.buf[: self.head]))


def decimate(ys, width):
  n = len(ys)
  if n <= width * 2:
    return np.arange(n) * (width - 1) / max(1, n - 1), ys
  cols = (np.arange(n) * width // n).astype(np.intp)
  starts = np.flatnonzero(np.diff(cols)) + 1
  starts = np.concatenate(([0], starts))
  mins = np.minimum.reduceat(ys, starts)
  maxs = np.maximum.reduceat(ys, starts)
  xs = cols[starts].astype(np.float64)
  out_x = np.repeat(xs, 2)
  out_y = np.empty(len(starts) * 2)
  out_y[0::2] = mins
  out_y[1::2] = maxs
  return out_x, out_y


def main():
  seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
  capacity = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
  os.makedirs(OUT_DIR, exist_ok=True)

  pygame.init()
  win = pygame.Window("spike_plot", (1200, 780), allow_high_dpi=True)
  surf = win.get_surface()
  scale = surf.get_width() / win.size[0]
  w, h = surf.get_size()
  print(f"[info] surface={w}x{h} scale={scale:.1f} capacity={capacity}")

  rings = [[Ring(capacity) for _ in range(3)] for _ in range(3)]
  stop = threading.Event()

  def producer():
    t = 0.0
    next_t = time.perf_counter()
    while not stop.is_set():
      for p, series in enumerate(rings):
        for s, r in enumerate(series):
          v = math.sin(t * (1 + p) * 2 + s) + random.gauss(0.0, 0.1)
          if random.random() < 0.0005:
            v += 3.0  # 스파이크: decimation 이 보존하는지 눈으로 확인
          r.append(v)
      t += 0.001
      next_t += 0.001
      delay = next_t - time.perf_counter()
      if delay > 0:
        time.sleep(delay)

  th = threading.Thread(target=producer, daemon=True)
  th.start()
  time.sleep(capacity / 1000 * 0.2)

  margin = int(8 * scale)
  plot_h = (h - margin * 4) // 3
  plot_rects = [pygame.Rect(margin, margin + i * (plot_h + margin), w - margin * 2, plot_h) for i in range(3)]
  line_w = max(1, int(scale))

  quit_req = False
  for name, mode, fps in PHASES:
    frames = 0
    draw_s = 0.0
    present_s = 0.0
    points_drawn = 0
    cpu0 = time.process_time()
    t0 = time.monotonic()
    next_frame = t0
    while time.monotonic() - t0 < seconds and not quit_req:
      for ev in pygame.event.get():
        if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
          quit_req = True

      if mode is not None:
        ta = time.perf_counter()
        surf.fill((0, 0, 100))
        for rect, series in zip(plot_rects, rings):
          pygame.draw.rect(surf, (0, 0, 60), rect)
          for gy in range(1, 4):
            y = rect.top + rect.height * gy // 4
            pygame.draw.line(surf, (40, 40, 140), (rect.left, y), (rect.right - 1, y))
          for color, r in zip(COLORS, series):
            ys = r.snapshot()
            if len(ys) < 2:
              continue
            if mode == "raw-aa":
              xs = np.arange(len(ys)) * (rect.width - 1) / (len(ys) - 1)
            else:
              xs, ys = decimate(ys, rect.width)
            px = rect.left + xs
            py = rect.top + rect.height * 0.5 - ys * (rect.height * 0.2)
            np.clip(py, rect.top, rect.bottom - 1, out=py)
            pts = np.column_stack((px, py)).tolist()
            if mode == "dec-lines":
              pygame.draw.lines(surf, color, False, pts, line_w)
            else:
              pygame.draw.aalines(surf, color, False, pts)
            points_drawn += len(pts)
        tb = time.perf_counter()
        win.flip()
        tc = time.perf_counter()
        frames += 1
        draw_s += tb - ta
        present_s += tc - tb

      next_frame += 1 / fps
      delay = next_frame - time.monotonic()
      if delay > 0:
        time.sleep(delay)
      else:
        next_frame = time.monotonic()

    wall = time.monotonic() - t0
    cpu = time.process_time() - cpu0
    if frames:
      print(
        f"[{name:11}] fps={frames / wall:5.1f} draw={draw_s / frames * 1000:6.2f}ms "
        f"present={present_s / frames * 1000:5.2f}ms pts/frame={points_drawn // frames:6d} "
        f"cpu={cpu / wall * 100:5.1f}%"
      )
      pygame.image.save(surf, os.path.join(OUT_DIR, f"plot_{name}.png"))
    else:
      print(f"[{name:11}] cpu={cpu / wall * 100:5.1f}% (producer thread + idle loop only)")

  stop.set()
  th.join()
  win.destroy()
  pygame.quit()


if __name__ == "__main__":
  main()
