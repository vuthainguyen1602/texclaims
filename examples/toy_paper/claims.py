"""Claims for the toy paper. Run from this directory:  texclaims run

The results section carries one deliberately stale number (0.931, from an earlier run); the
abstract and the generated table are current. `texclaims run` reports it and exits 1.
"""
import csv
import json
import re

from texclaims import check, claim, guards, numbers, tex, text

RESULTS = {r["model"]: r for r in csv.DictReader(open("data/results.csv", encoding="utf-8"))}
ANN = json.load(open("data/annotation.json", encoding="utf-8"))
PROSE = text.prose("sections/*.tex")          # hand-written sections only, normalised


@claim("results")
def headline_f1():
    rf = float(RESULTS["RandomForest"]["f1"])
    # Every sentence that states the random forest's F1 must print the same, current value.
    pattern = r"random forest reaches an F1 of (\d\.\d+)"
    guards.consistent("random-forest F1", PROSE, pattern, f"{rf:.3f}")
    m = re.search(pattern, PROSE)
    guards.value_at_precision("random-forest F1 matches results.csv", m and m.group(1), rf)


@claim("results")
def table_bolding():
    rows = tex.table_rows("sections/tab_results.tex")[1:]          # skip the header row
    guards.bold_matches("bold marks exactly the q < 0.05 rows", rows, 1,
                        lambda r: float(r[2]) < 0.05)
    expected = [[m, float(r["f1"]), float(r["q_value"])] for m, r in RESULTS.items()]
    guards.cells_match("table equals results.csv", rows, expected)


@claim("results")
def only_one_survives():
    survivors = [m for m, r in RESULTS.items() if float(r["q_value"]) < 0.05]
    says_only = "is the only model whose advantage" in PROSE
    check("'the only model' sentence agrees with the q-values", not says_only or survivors == ["RandomForest"],
          f"survivors: {survivors}")


@claim("results")
def agreement_interval():
    m = re.search(r"agreed on ([\d.]+%) of the (\d+) labels \(95% CI ([\d.]+)–([\d.]+)%\)", PROSE)
    if not check("agreement sentence found", m is not None):
        return
    rate, n, lo, hi = m.group(1), int(m.group(2)), m.group(3) + "%", m.group(4) + "%"
    check("n matches annotation.json", n == ANN["n"], f"printed {n}, data {ANN['n']}")
    check("printed rate is consistent with the data", ANN["agree"] in numbers.numerators(rate, n),
          f"{rate} of {n}; data {ANN['agree']}/{ANN['n']}")
    check("printed interval is a Wilson interval for a consistent count",
          numbers.interval_consistent(rate, lo, hi, n))


@claim("conventions")
def manuscript_hygiene():
    guards.floats_referenced("main.tex")
    guards.word_limit("abstract within 250 words", "sections/00_abstract.tex", 250)
    guards.forbidden("no talk of the review process", "sections/*.tex", guards.REVIEW_TALK)
