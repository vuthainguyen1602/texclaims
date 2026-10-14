# texclaims

Check that a LaTeX manuscript still says what its data says.

Numbers typed into a paper drift away from the files that produced them, and nothing about a
stale number is syntactically wrong. `texclaims` runs checks you write against your own CSV/JSON
results and your `.tex` sources, prints one line per check, and exits non-zero on any mismatch,
so it can sit in a Makefile, a pre-commit hook or CI.

It is for papers whose prose is written by hand. If every number is generated into the text
(knitr, Quarto, showyourwork!), drift in those numbers cannot happen; the sentences around them,
the bolding of a table, a cover letter or a submission archive can still disagree with the data.

## Install

```
pip install texclaims          # Python >= 3.10, no dependencies
```

`pdftotext` (poppler) is needed only if your checks read the rendered PDF.

## Use

Write a `claims.py` next to your manuscript:

```python
import csv, re
from texclaims import claim, guards, text

RES = {r["model"]: r for r in csv.DictReader(open("data/results.csv"))}
PROSE = text.prose("sections/*.tex")      # hand-written sections, normalised toward the PDF

@claim("results")
def headline():
    f1 = float(RES["RandomForest"]["f1"])
    guards.consistent("random-forest F1", PROSE,
                      r"random forest reaches an F1 of (\d\.\d+)", f"{f1:.3f}")
```

Then:

```
texclaims run                    # all families
texclaims run -f results         # one family
texclaims run --update-floors    # record how many checks each family runs
texclaims run --json report.json
```

`examples/toy_paper` is a complete example with one planted stale number:

```
cd examples/toy_paper && texclaims run
...
  [FAIL] random-forest F1 is stated consistently - 2 mention(s); expected 0.938, also found 0.931
...
13/14 checks passed
```

## What it gives you

**A registry with coverage floors.** Checks are grouped in families. A check whose input file
disappeared usually just stops running, and a suite that checks less still passes; `texclaims`
records how many checks each family ran (`claims_floors.json`) and fails a run that executes
fewer. A family that raises is reported as a failure and the other families still run.
`with pinned("data as of ..."):` reports failures as `pin` for a paper frozen at a data snapshot.

**Comparison at printed precision** (`texclaims.numbers`). `matches("0.853", 0.85349)` compares at
three decimals, accepts either rounding of an exact half, understands `64\%`, `51{,}362`,
`\textbf{...}` and Unicode minus. For proportions, `numerators("90%", 1000)` returns every count
that prints as 90%, and `interval_consistent` accepts a printed interval if any such count
produces it, because an interval cannot be recomputed from a rounded rate.

**Text you can search** (`texclaims.text`, `texclaims.tex`). Hand-written prose with generated
files excluded (a value taken from a generated table and searched for in the PDF finds the table
and cannot fail); LaTeX normalised toward the rendered text; PDF text with ligatures and Unicode
math letters folded back; table cells read from `.tex` (pdftotext emits tables column-wise);
`\input` trees flattened with TeX's end-of-line rules.

**Guards** (`texclaims.guards`), each written after a real miss:

| guard | catches |
|---|---|
| `consistent` | one quantity restated with different values, including a stale copy next to correct ones |
| `value_at_precision` | a printed number that no longer matches the computed value |
| `bold_matches` | bold cells that disagree with the table's own rule (e.g. q < 0.05) |
| `cells_match` | a generated table that was not regenerated |
| `forbidden` | phrases that must not appear, in sections, letters or highlights (`REVIEW_TALK` included) |
| `floats_referenced` | a figure or table no sentence refers to |
| `word_limit`, `highlights` | venue limits, counted from source |
| `letter_current` | a cover letter older in git than its manuscript |
| `pack_matches` | a submission archive whose prose no longer matches the sources |

## Tests

```
pip install -e '.[test]' && pytest
```

## Licence

MIT.
