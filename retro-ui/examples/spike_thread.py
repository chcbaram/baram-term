"""P0 spike: 워커 스레드에서 이벤트 루프 깨우기.

1) raw      : 1kHz 로 매 샘플마다 pygame.event.post
2) coalesced: 큐에 넣고, 대기 중인 WAKE 가 없을 때만 post (계획의 call_soon 방식)
두 방식의 수신 개수, 최대 지연, CPU 사용률을 비교한다.

usage: python examples/spike_thread.py [seconds_per_phase]
"""

import os
import queue
import sys
import threading
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame  # noqa: E402


def run_phase(name, seconds, coalesce):
  wake = pygame.event.custom_type()
  q = queue.SimpleQueue()
  wake_pending = threading.Event()
  stop = threading.Event()
  stats = {"produced": 0, "posted": 0}

  def producer():
    period = 0.001
    next_t = time.perf_counter()
    while not stop.is_set():
      q.put(time.perf_counter())
      stats["produced"] += 1
      if not coalesce:
        pygame.event.post(pygame.event.Event(wake))
        stats["posted"] += 1
      elif not wake_pending.is_set():
        wake_pending.set()
        pygame.event.post(pygame.event.Event(wake))
        stats["posted"] += 1
      next_t += period
      delay = next_t - time.perf_counter()
      if delay > 0:
        time.sleep(delay)

  th = threading.Thread(target=producer, daemon=True)
  received = 0
  wakeups = 0
  max_lag = 0.0

  cpu0 = time.process_time()
  t0 = time.monotonic()
  th.start()
  while time.monotonic() - t0 < seconds:
    ev = pygame.event.wait(100)
    events = [ev, *pygame.event.get()]
    for e in events:
      if e.type == wake:
        wakeups += 1
    # WAKE 를 처리하기 직전에 플래그를 내려야 그 사이 들어온 항목도 다음 WAKE 로 깨운다
    wake_pending.clear()
    now = time.perf_counter()
    while True:
      try:
        ts = q.get_nowait()
      except queue.Empty:
        break
      received += 1
      max_lag = max(max_lag, now - ts)
  stop.set()
  th.join()
  wall = time.monotonic() - t0
  cpu = time.process_time() - cpu0

  print(
    f"[{name:9}] produced={stats['produced']} posted={stats['posted']} "
    f"wakeups={wakeups} received={received} "
    f"max_lag={max_lag * 1000:.2f}ms cpu={cpu / wall * 100:.1f}%"
  )


def main():
  seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
  pygame.init()
  pygame.display.set_mode((1, 1))
  run_phase("raw", seconds, coalesce=False)
  run_phase("coalesced", seconds, coalesce=True)
  pygame.quit()


if __name__ == "__main__":
  main()
