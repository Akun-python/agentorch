from __future__ import annotations

import math
from statistics import mean, stdev
from typing import Iterable


def safe_mean(values: Iterable[float]) -> float:
    values = list(values)
    return float(mean(values)) if values else 0.0


def safe_std(values: Iterable[float]) -> float:
    values = list(values)
    return float(stdev(values)) if len(values) > 1 else 0.0


def ci95(values: Iterable[float]) -> tuple[float, float]:
    values = list(values)
    if not values:
        return (0.0, 0.0)
    m = safe_mean(values)
    if len(values) == 1:
        return (m, m)
    margin = 1.96 * safe_std(values) / math.sqrt(len(values))
    return (m - margin, m + margin)


def cohen_d(lhs: Iterable[float], rhs: Iterable[float]) -> float:
    lhs = list(lhs)
    rhs = list(rhs)
    if not lhs or not rhs:
        return 0.0
    lhs_mean = safe_mean(lhs)
    rhs_mean = safe_mean(rhs)
    lhs_var = safe_std(lhs) ** 2
    rhs_var = safe_std(rhs) ** 2
    pooled_den = max(1e-8, (((len(lhs) - 1) * lhs_var) + ((len(rhs) - 1) * rhs_var)) / max(1, len(lhs) + len(rhs) - 2))
    return (lhs_mean - rhs_mean) / math.sqrt(pooled_den)


def approximate_p_value(lhs: Iterable[float], rhs: Iterable[float]) -> float:
    lhs = list(lhs)
    rhs = list(rhs)
    if len(lhs) < 2 or len(rhs) < 2:
        return 1.0
    lhs_mean = safe_mean(lhs)
    rhs_mean = safe_mean(rhs)
    lhs_std = safe_std(lhs)
    rhs_std = safe_std(rhs)
    se = math.sqrt((lhs_std**2 / len(lhs)) + (rhs_std**2 / len(rhs)))
    if se <= 1e-8:
        return 1.0 if abs(lhs_mean - rhs_mean) <= 1e-8 else 0.0
    z_score = abs(lhs_mean - rhs_mean) / se
    return max(0.0, min(1.0, math.erfc(z_score / math.sqrt(2.0))))
