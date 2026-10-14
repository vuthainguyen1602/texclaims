"""Command line: `texclaims run`, `texclaims list`."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

from . import __version__, core


def load_claims(path: str) -> core.Suite:
    """Import the user's claims file; its @claim decorators register on the default suite."""
    if not os.path.exists(path):
        raise SystemExit(f"texclaims: claims file not found: {path}")
    path = os.path.abspath(path)
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location("_texclaims_user", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return core.current()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="texclaims",
                                 description="Check a LaTeX manuscript against the data behind it.")
    ap.add_argument("--version", action="version", version=f"texclaims {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("run", "list"):
        p = sub.add_parser(name)
        p.add_argument("-c", "--claims", default="claims.py", help="claims file (default claims.py)")
        p.add_argument("-C", "--directory", default=None,
                       help="change to this directory first; paths in the claims file are relative to it")
    run = sub.choices["run"]
    run.add_argument("-f", "--family", action="append", help="run only this family (repeatable)")
    run.add_argument("--floors", default="claims_floors.json",
                     help="per-family check-count floors (default claims_floors.json); '' disables")
    run.add_argument("--update-floors", action="store_true",
                     help="record the current counts as floors; do this when checks are added, "
                          "never to silence a shortfall")
    run.add_argument("--json", metavar="PATH", help="also write the report as JSON")
    run.add_argument("-q", "--quiet", action="store_true", help="print failures and the total only")
    args = ap.parse_args(argv)

    if args.directory:
        os.chdir(args.directory)
    suite = load_claims(args.claims)

    if args.cmd == "list":
        for fam, fns in suite.families.items():
            print(f"{fam}: {', '.join(f.__name__ for f in fns)}")
        return 0

    echo = None if args.quiet else print
    report = suite.run(args.family, floors_path=args.floors or None,
                       update_floors=args.update_floors, echo=echo)
    if args.quiet:
        for r in report.failed:
            print(f"  [FAIL] {r.family}: {r.name}{(' - ' + r.detail) if r.detail else ''}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report.to_dict(), fh, indent=2)
    n, bad = len(report.results), len(report.failed)
    print(f"\n{n - bad}/{n} checks passed")
    return 0 if report.ok else 1
