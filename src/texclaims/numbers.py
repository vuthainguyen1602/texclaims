"""Comparing printed numbers with computed ones, at the precision they were printed.

A manuscript prints 0.853 for 0.85349 and 64% for 0.6412. Equality with a tolerance picked by
hand either lets a stale value through or fails on rounding; comparing at the printed precision
does neither. The proportion helpers exist because an interval cannot be recomputed from a
rounded rate: for a large n several numerators round to the same printed rate and give different
intervals, so the check accepts any numerator consistent with what is printed.
"""
from __future__ import annotations

import math
import re
from typing import Callable

_STRIP = re.compile(r"[\s$~]|\\,|\\!|\{,\}|\\%|%|\\textbf\{|\\mathbf\{|\\emph\{|[{}]")


def clean(s: str) -> str:
    """The digits of a printed number: LaTeX spacing, math, percent and grouping removed."""
    s = s.replace("−", "-").replace("\\textminus", "-").replace("--", "-")
    s = _STRIP.sub("", s)
    return s.replace(",", "")


def parse(s: str) -> float | None:
    """Value of a printed number, or None if the string is not one."""
    c = clean(s)
    try:
        return float(c)
    except ValueError:
        return None


def decimals(s: str) -> int:
    """Number of digits printed after the decimal point."""
    c = clean(s)
    return len(c.split(".", 1)[1]) if "." in c else 0


def matches(printed: str, value: float, *, scale: float = 1.0) -> bool:
    """Whether `printed` is `value * scale` rounded to the precision it shows.

    Accepts either rounding of an exact half, so it does not care whether the generator used
    round-half-even or round-half-up. `scale=100` compares a printed percentage with a fraction.
    """
    p = parse(printed)
    if p is None or value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    half = 0.5 * 10 ** -decimals(printed)
    return abs(p - value * scale) <= half + 1e-9 * max(1.0, abs(p))


def renderings(n: int) -> tuple[str, ...]:
    """Ways a paper may print an integer: 51,362, 51362, 51{,}362, 51\\,362."""
    g = f"{n:,}"
    return (g, str(n), g.replace(",", "{,}"), g.replace(",", "\\,"))


def numerators(printed_rate: str, n: int, *, percent: bool | None = None) -> list[int]:
    """Every k in 0..n for which k/n rounds to `printed_rate`.

    `percent` defaults to whether the string carries a % sign."""
    if percent is None:
        percent = "%" in printed_rate
    scale = 100.0 if percent else 1.0
    return [k for k in range(n + 1) if matches(printed_rate, k / n, scale=scale)]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials."""
    if not n:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def interval_consistent(printed_rate: str, printed_lo: str, printed_hi: str, n: int, *,
                        method: Callable[[int, int], tuple[float, float]] = wilson,
                        percent: bool | None = None) -> bool:
    """Whether some numerator consistent with the printed rate gives the printed interval."""
    if percent is None:
        percent = "%" in printed_rate
    scale = 100.0 if percent else 1.0
    for k in numerators(printed_rate, n, percent=percent):
        lo, hi = method(k, n)
        if matches(printed_lo, lo, scale=scale) and matches(printed_hi, hi, scale=scale):
            return True
    return False
