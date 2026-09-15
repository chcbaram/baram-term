"""Layout math in cell units (backend-independent)."""

from __future__ import annotations

from typing import Sequence


def _largest_remainder(amount: int, weights: Sequence[int]) -> list[int]:
    total = sum(weights)
    if amount <= 0 or total <= 0:
        return [0] * len(weights)
    shares = [amount * w // total for w in weights]
    left = amount - sum(shares)
    # 나머지가 큰 순서, 같으면 앞쪽 항목부터 1씩 더 준다 (정수 연산으로 합이 정확히 amount)
    order = sorted(range(len(weights)), key=lambda i: (-(amount * weights[i] % total), i))
    for i in order[:left]:
        shares[i] += 1
    return shares


def distribute(total: int, items: Sequence[tuple[int, int, int]], spacing: int = 0) -> list[int]:
    """주 축 길이 total 을 (min, pref, stretch) 항목들에 나눠 준다.

    1. 모든 항목에 min 을 준다.
    2. 남는 공간으로 pref 까지 (pref - min) 비율로 키운다.
    3. 그래도 남으면 stretch 비율로 나눈다. stretch 가 하나라도 있으면 합은 정확히
       total - spacing*(n-1) 이다. 없으면 남는 공간은 호출자가 정렬로 처리한다.
    total 이 min 합보다 작으면 뒤쪽 항목부터 줄인다 (음수 크기는 없다).
    """
    n = len(items)
    if n == 0:
        return []
    avail = max(0, total - spacing * (n - 1))
    mins = [max(0, it[0]) for it in items]
    prefs = [max(m, it[1]) for m, it in zip(mins, items)]
    stretches = [max(0, it[2]) for it in items]

    sum_min = sum(mins)
    if avail <= sum_min:
        sizes = list(mins)
        excess = sum_min - avail
        for i in reversed(range(n)):
            if excess <= 0:
                break
            cut = min(sizes[i], excess)
            sizes[i] -= cut
            excess -= cut
        return sizes

    sizes = list(mins)
    extra = avail - sum_min
    wants = [p - m for p, m in zip(prefs, mins)]
    want = sum(wants)
    if want > 0:
        grow = min(extra, want)
        for i, s in enumerate(_largest_remainder(grow, wants)):
            sizes[i] += s
        extra -= grow

    if extra > 0 and sum(stretches) > 0:
        for i, s in enumerate(_largest_remainder(extra, stretches)):
            sizes[i] += s
    return sizes
