"""Check registry, results and coverage floors.

A claims file registers check functions under named families. Running a family calls its
functions; every `check()` they make is recorded. Two rules come from experience with a
manuscript suite that grew to over a thousand checks:

* A check that cannot find its input usually just does not run, so the suite stays green while
  checking less. Each family therefore has a recorded floor, the number of checks it ran last
  time it was deliberately updated, and a run that executes fewer checks than the floor fails.
* A family function that raises is a failure, not a crash: the remaining families still run and
  the report says which family broke and why.
"""
from __future__ import annotations

import contextlib
import json
import os
import traceback
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

OK, FAIL, PIN = "ok", "fail", "pin"


@dataclass
class Result:
    family: str
    name: str
    status: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status != FAIL


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    floors: dict[str, int] = field(default_factory=dict)

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if not r.passed]

    @property
    def ok(self) -> bool:
        return not self.failed

    def to_dict(self) -> dict:
        return {
            "passed": len(self.results) - len(self.failed),
            "total": len(self.results),
            "counts": self.counts,
            "floors": self.floors,
            "results": [r.__dict__ for r in self.results],
        }


class Suite:
    """A set of check families and the results of running them."""

    def __init__(self) -> None:
        self.families: dict[str, list[Callable[[], None]]] = {}
        self.results: list[Result] = []
        self._family = ""
        self._pin: str | None = None
        self._echo: Callable[[str], None] | None = print

    # -- registration -------------------------------------------------------------------------
    def claim(self, family: str) -> Callable[[Callable[[], None]], Callable[[], None]]:
        """Decorator: register a function as part of `family`. A family may have several."""
        def deco(fn: Callable[[], None]) -> Callable[[], None]:
            self.families.setdefault(family, []).append(fn)
            return fn
        return deco

    # -- recording ----------------------------------------------------------------------------
    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        """Record one assertion. Returns `ok` so callers can branch on it."""
        ok = bool(ok)
        status = OK if ok else (PIN if self._pin else FAIL)
        if status == PIN:
            detail = (detail + " " if detail else "") + f"(pinned: {self._pin})"
        self.results.append(Result(self._family, name, status, detail))
        if self._echo:
            tag = {OK: "ok  ", FAIL: "FAIL", PIN: "pin "}[status]
            self._echo(f"  [{tag}] {name}{(' - ' + detail) if detail else ''}")
        return ok if status != PIN else True

    @contextlib.contextmanager
    def pinned(self, reason: str) -> Iterator[None]:
        """Report failures inside the block as `pin`, not `fail`.

        For a manuscript whose numbers are frozen at a data snapshot while collection goes on:
        disagreement with live data is expected drift past the pin, shown but not failed. Pair
        it with an unpinned check that the snapshot itself is unchanged, or the pin hides
        everything."""
        prev, self._pin = self._pin, reason
        try:
            yield
        finally:
            self._pin = prev

    # -- running ------------------------------------------------------------------------------
    def run(self, families: Iterable[str] | None = None, *, floors_path: str | None = None,
            update_floors: bool = False, echo: Callable[[str], None] | None = print) -> Report:
        self._echo = echo
        self.results = []
        wanted = list(families) if families else list(self.families)
        unknown = [f for f in wanted if f not in self.families]
        counts: dict[str, int] = {}
        for fam in wanted:
            if fam in unknown:
                continue
            if echo:
                echo(f"\n{fam}")
            self._family = fam
            before = len(self.results)
            for fn in self.families[fam]:
                try:
                    fn()
                except Exception as exc:  # a broken family must not hide the others
                    tb = traceback.extract_tb(exc.__traceback__)[-1]
                    self.check(f"{fn.__name__} ran to completion", False,
                               f"{type(exc).__name__}: {exc} ({os.path.basename(tb.filename)}:{tb.lineno})")
            counts[fam] = len(self.results) - before
        self._family = "coverage"
        for fam in unknown:
            self.check(f"family {fam!r} exists", False, "no function registered under that name")

        floors = load_floors(floors_path) if floors_path else {}
        if floors_path and update_floors:
            floors.update(counts)
            save_floors(floors_path, floors)
            if echo:
                echo(f"\nfloors updated: {floors_path}")
        elif floors_path:
            if echo:
                echo("\ncoverage (checks that ran vs the recorded floor)")
            for fam in sorted(counts):
                want = floors.get(fam)
                if want is None:
                    self.check(f"{fam}: has a recorded floor", False,
                               f"{counts[fam]} ran; record it with --update-floors")
                elif counts[fam] < want:
                    self.check(f"{fam}: no checks went missing", False,
                               f"{counts[fam]} ran, floor is {want}: a check stopped firing "
                               "(missing input, or text that no longer parses)")
                else:
                    self.check(f"{fam}: {counts[fam]} ran (floor {want})", True)
        self._echo = print
        return Report(list(self.results), counts, floors)


def load_floors(path: str) -> dict[str, int]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {k: int(v) for k, v in json.load(fh).items()}


def save_floors(path: str, floors: dict[str, int]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(floors, fh, indent=2, sort_keys=True)
        fh.write("\n")


# A default suite, so a claims file can use the module-level `claim` and `check`.
default = Suite()
claim = default.claim
check = default.check
pinned = default.pinned


def current() -> Suite:
    return default
