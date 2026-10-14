"""Ready-made checks. Each records its result(s) through a Suite and returns whether it passed.

Every guard here was written after a real miss in a multi-paper LaTeX project:

consistent          one quantity restated in several places: a figure caption kept 38% while four
                    sections said 41%, and a presence test passed on all five.
value_at_precision  a printed number against the value computed from the data.
bold_matches        a table bolded a model as best when the paired test put the difference
                    across zero.
forbidden           phrases that must not appear (a manuscript talking about its own review; a
                    sentence withdrawn after the data reversed it), letters and highlights in scope.
floats_referenced   LaTeX warns about a \\ref without a \\label, never about a float nobody cites.
word_limit          an abstract over the venue's limit, counted from source, not from pdftotext.
highlights          Elsevier-style highlights, whose submission form truncates without warning.
letter_current      a cover letter older (in git) than the manuscript it introduces.
pack_matches        a submission archive whose prose no longer matches the sources on disk.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import zipfile
from typing import Callable, Iterable, Sequence

from . import core, numbers, tex, text


def _s(suite: core.Suite | None) -> core.Suite:
    return suite or core.current()


def _short(items: Sequence[str], k: int = 4) -> str:
    return "; ".join(items[:k]) + (f" (+{len(items) - k} more)" if len(items) > k else "")


# ---------------------------------------------------------------------------- numbers in text
def consistent(name: str, haystack: str, pattern: str, *expected: str,
               suite: core.Suite | None = None) -> bool:
    """Every restatement of one quantity carries an accepted rendering.

    `pattern` has exactly one capture group and must pin ONE quantity (anchor it on the words
    around the number). `expected` lists the legitimate renderings ('40.8%', '41%'); anything
    else found is drift. Zero matches fail too: a pattern that stopped matching checks nothing."""
    found = [m.group(1) for m in re.finditer(pattern, haystack)]
    bad = sorted({f for f in found if f not in set(expected)})
    return _s(suite).check(
        f"{name} is stated consistently", bool(found) and not bad,
        f"{len(found)} mention(s)" + (f"; expected {' or '.join(expected)}, also found {', '.join(bad)}"
                                     if bad else "" if found else "; pattern matched nothing"))


def value_at_precision(name: str, printed: str | None, value: float, *, scale: float = 1.0,
                       suite: core.Suite | None = None) -> bool:
    """A printed number equals the computed value at the precision it is printed with."""
    ok = printed is not None and numbers.matches(printed, value, scale=scale)
    return _s(suite).check(name, ok, f"printed {printed!r}, data gives {value * scale!r}")


def present(name: str, haystack: str, *variants: str, suite: core.Suite | None = None) -> bool:
    """At least one rendering of a value occurs. Prefer `consistent`, which also catches a
    stale copy sitting beside a correct one."""
    return _s(suite).check(name, text.has(haystack, *variants),
                           f"looked for {' / '.join(variants[:3])}")


# ---------------------------------------------------------------------------- tables
def bold_matches(name: str, rows: Sequence[Sequence[str]], column: int,
                 should_bold: Callable[[Sequence[str]], bool], *,
                 suite: core.Suite | None = None) -> bool:
    """The cells bolded in `column` are exactly those in rows where `should_bold(row)` holds.

    `should_bold` encodes the table's own rule, e.g. "q < 0.05 in the next column" or "the best
    value whose interval excludes the runner-up", so the bolding cannot drift from the numbers."""
    wrong = []
    for row in rows:
        if column >= len(row):
            continue
        b, want = tex.is_bold(row[column]), bool(should_bold(row))
        if b != want:
            wrong.append(f"{tex.cell_text(row[0])}: {'bold' if b else 'plain'}, rule says "
                         f"{'bold' if want else 'plain'}")
    return _s(suite).check(name, not wrong, _short(wrong))


def cells_match(name: str, printed: Sequence[Sequence[str]], expected: Sequence[Sequence[float | str]],
                *, scale: float = 1.0, suite: core.Suite | None = None) -> bool:
    """A printed table equals an expected one cell by cell (numbers at printed precision,
    strings after markup is removed). Shape differences fail."""
    bad = []
    if len(printed) != len(expected):
        bad.append(f"{len(printed)} rows printed, {len(expected)} expected")
    for i, (pr, ex) in enumerate(zip(printed, expected)):
        if len(pr) != len(ex):
            bad.append(f"row {i}: {len(pr)} cells printed, {len(ex)} expected")
            continue
        for j, (p, e) in enumerate(zip(pr, ex)):
            c = tex.cell_text(p)
            ok = numbers.matches(c, e, scale=scale) if isinstance(e, (int, float)) else c == str(e)
            if not ok:
                bad.append(f"row {i} col {j}: printed {c!r}, expected {e!r}")
    return _s(suite).check(name, not bad, _short(bad))


# ---------------------------------------------------------------------------- phrases
def forbidden(name: str, files: Iterable[str] | str, pattern: str | re.Pattern, *,
              exempt: Callable[[str], bool] = lambda p: False,
              suite: core.Suite | None = None) -> bool:
    """No line of `files` (a glob or list) matches `pattern`, comments excluded.

    Point it at letters, highlights and abstracts as well as sections: a withdrawn sentence once
    survived in the cover letter, the one document the editor reads first."""
    if isinstance(files, str):
        files = sorted(glob.glob(files, recursive=True))
    rx = re.compile(pattern, re.I) if isinstance(pattern, str) else pattern
    hits = []
    for p in files:
        if exempt(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            for i, ln in enumerate(fh, 1):
                m = rx.search(re.split(r"(?<!\\)%", ln, 1)[0] if p.endswith(".tex") else ln)
                if m:
                    hits.append(f"{p}:{i} {m.group(0)!r}")
    return _s(suite).check(name, not hits, _short(hits))


# The phrases a published paper should not contain about its own review history.
REVIEW_TALK = re.compile(
    r"\b(?:the|a|one|each|both|all|two|three)\s+(?:anonymous\s+)?(?:reviewers?|referees?)\s+"
    r"(?:asked|requested|suggested|noted|pointed|raised|recommended|questioned|argued)"
    r"|\b(?:at|following|per)\s+(?:the\s+)?(?:reviewers?'?s?|referees?'?s?)\s+"
    r"(?:request|suggestion|recommendation|comment)"
    r"|\b(?:reviewer|referee)\s+(?:comment|point|concern|question)s?\b"
    r"|\b(?:added|introduced|changed|corrected|removed)\s+(?:at|in|during|for)\s+(?:this\s+|the\s+)?revision\b"
    r"|\bin\s+(?:this|the)\s+revision\b|\bat\s+revision\b"
    r"|\b(?:earlier|previous|first)\s+(?:draft|version of (?:this|the) (?:paper|manuscript))\b"
    r"|\boriginal(?:ly)?\s+(?:submission|submitted\s+(?:version|manuscript))\b"
    r"|\bresponse\s+(?:letter|to\s+(?:the\s+)?reviewers)\b", re.I)


# ---------------------------------------------------------------------------- structure
def floats_referenced(main: str, *, suite: core.Suite | None = None) -> bool:
    """Every figure/table float in the document reached from `main` is \\ref'd somewhere."""
    src = "\n".join(open(p, encoding="utf-8").read() for p in tex.included_files(main))
    refs = tex.references(src)
    orphans = [lab for lab in tex.float_labels(src) if lab not in refs]
    return _s(suite).check(f"{os.path.basename(main)}: every float is referenced", not orphans,
                           f"{len(orphans)} orphan(s): {', '.join(orphans[:5])}" if orphans else "")


def word_count(tex_src: str) -> int:
    """Words in a TeX fragment as a reader counts them: an inline formula is one word."""
    t = text.strip_comments(tex_src)
    t = re.sub(r"\$[^$]*\$", " X ", t)
    t = re.sub(r"\\(?:cite[pt]?|ref|label)\*?\{[^}]*\}", " ", t)
    t = re.sub(r"\\[A-Za-z]+\*?", " ", t)
    return sum(1 for w in re.sub(r"[{}~\\]", " ", t).split() if re.search(r"\w", w))


def word_limit(name: str, path: str, limit: int, *, env: str | None = "abstract",
               suite: core.Suite | None = None) -> bool:
    """The text of `env` in `path` (or the whole file if env is None) is within `limit` words."""
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if env:
        m = re.search(rf"\\begin\{{{env}\}}(.*?)\\end\{{{env}\}}", src, re.S)
        if not m:
            return _s(suite).check(name, False, f"no {env} environment in {path}")
        src = m.group(1)
    n = word_count(src)
    return _s(suite).check(name, n <= limit, f"{n} words, limit {limit}")


def highlights(name: str, items: Sequence[str], *, count: tuple[int, int] = (3, 5),
               max_chars: int = 85, suite: core.Suite | None = None) -> bool:
    """Highlight bullets: how many, and each within the character limit (spaces included)."""
    s = _s(suite)
    ok1 = s.check(f"{name}: {count[0]}-{count[1]} highlights", count[0] <= len(items) <= count[1],
                  f"{len(items)} bullets")
    over = [f"{len(b)} chars: {b[:40]!r}" for b in items if len(b) > max_chars]
    ok2 = s.check(f"{name}: every highlight within {max_chars} characters", not over, _short(over))
    return ok1 and ok2


# ---------------------------------------------------------------------------- submission
def _git_time(paths: Sequence[str], cwd: str | None = None) -> int:
    best = 0
    for p in paths:
        try:
            out = subprocess.run(["git", "log", "-1", "--format=%ct", "--", p], cwd=cwd,
                                 capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return 0
        if out.isdigit():
            best = max(best, int(out))
    return best


def _git_dirty(path: str) -> bool:
    try:
        return bool(subprocess.run(["git", "status", "--porcelain", "--", path],
                                   capture_output=True, text=True, timeout=20).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def letter_current(name: str, letter: str, manuscript: Sequence[str], *,
                   suite: core.Suite | None = None) -> bool:
    """The letter's last commit is no older than the manuscript's.

    A letter with uncommitted edits counts as being fixed. Working-tree mtimes are not used:
    a fresh clone would make every file look new."""
    s = _s(suite)
    if _git_dirty(letter):
        return s.check(name, True, "letter has uncommitted edits: taken as work in progress")
    t_letter, t_ms = _git_time([letter]), _git_time(list(manuscript))
    if not (t_letter and t_ms):
        return s.check(name, False, "git has no commit time for the letter or the manuscript")
    gap = (t_ms - t_letter) / 86400
    return s.check(name, t_ms <= t_letter,
                   f"the manuscript moved {gap:.1f} day(s) after the letter" if t_ms > t_letter else "")


def _body_text(t: str) -> str:
    """Body of a flattened document with TeX's comment and end-of-line rules applied."""
    t = t.split("\\begin{document}", 1)[-1]
    out = []
    for ln in t.split("\n"):
        m = re.search(r"(?<!\\)%", ln)
        out.append(ln[:m.start()] if m else ln + " ")
    return " ".join("".join(out).split())


def _prose_chunks(t: str, min_chars: int = 120, min_words: int = 18) -> list[str]:
    out = []
    for c in re.split(r"(?<=\.)\s", t):
        c = c.strip()
        if not c[:1].isalpha() or any(k in c for k in ("\\begin{", "\\end{", "\\input{",
                                                        "\\includegraphics", "\\maketitle")):
            continue
        if len(c) >= min_chars and len(c.split()) >= min_words and c.count("\\") <= len(c.split()) // 4:
            out.append(c)
    return out


def pack_matches(name: str, pack: str, main: str, *, member: str = "main.tex",
                 declared: Iterable[str] = (), suite: core.Suite | None = None) -> bool:
    """The prose in a submission archive is still in the sources on disk, and vice versa.

    Both sides are flattened and normalised the same way first; comparing raw text reports every
    sentence that spans an \\input as changed. `declared` lists fragments (40+ characters) of
    divergences that are known and intended, e.g. edits made after a pack was sent."""
    with zipfile.ZipFile(pack) as z:
        arc = next((n for n in z.namelist() if n.endswith(member)), None)
        if arc is None:
            return _s(suite).check(name, False, f"{member} not found in {pack}")
        sent = _body_text(z.read(arc).decode("utf-8", "replace"))
    cur = _body_text(tex.flatten(main))
    frags = [" ".join(f.split()) for f in declared if len(f) >= 40]
    known = lambda c: any(f in c for f in frags)
    lost = [c for c in _prose_chunks(sent) if c not in cur and not known(c)]
    gained = [c for c in _prose_chunks(cur) if c not in sent and not known(c)]
    detail = []
    if lost:
        detail.append(f"{len(lost)} passage(s) only in the pack, e.g. {lost[0][:70]!r}")
    if gained:
        detail.append(f"{len(gained)} passage(s) only on disk, e.g. {gained[0][:70]!r}")
    return _s(suite).check(name, not (lost or gained), "; ".join(detail))
