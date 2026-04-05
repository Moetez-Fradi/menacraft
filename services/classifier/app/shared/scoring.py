from __future__ import annotations


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def weighted_avg(values: list[tuple[float, float]]) -> float:
    total_weight = sum(w for _, w in values)
    if total_weight <= 0:
        return 0.0
    return sum(v * w for v, w in values) / total_weight
