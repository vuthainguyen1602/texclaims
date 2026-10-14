"""Reading LaTeX structure: \\input trees, tables, bold cells, floats and their references."""
from __future__ import annotations

import os
import re

INPUT_RE = re.compile(r"\\(?:input|include)\{([^}]*)\}")
_COMMENT_START = re.compile(r"(?<!\\)%")


def _resolve(name: str, base: str) -> str | None:
    for cand in (name, name + ".tex"):
        p = os.path.normpath(os.path.join(base, cand))
        if os.path.exists(p):
            return p
    return None


def flatten(path: str, base: str | None = None, *, strip_comments: bool = False,
            _stack: tuple[str, ...] = ()) -> str:
    """Inline every \\input/\\include recursively, preserving TeX's end-of-line behaviour.

    `base` is the directory names are resolved against (TeX resolves them against the main
    file's directory, not the including file's). An \\input at the end of a line contributes
    its file without the file's final newline, so the flat source does not gain a paragraph
    break the original build never had; a trailing comment on the file's last line is dropped
    for the same reason. An \\input cycle raises ValueError."""
    path = os.path.abspath(path)
    base = os.path.abspath(base) if base is not None else os.path.dirname(path)
    if path in _stack:
        # TeX itself would recurse until it ran out of input stack, so this is an error.
        raise ValueError("\\input cycle: " + " -> ".join(os.path.basename(p) for p in _stack + (path,)))
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    stack = _stack + (path,)

    def body(p: str, at_eol: bool) -> str:
        t = flatten(p, base, strip_comments=strip_comments, _stack=stack)
        if not at_eol:
            return t
        t = t[:-1] if t.endswith("\n") else t
        head, _, last = t.rpartition("\n")
        cm = _COMMENT_START.search(last)
        if cm:
            t = (head + "\n" if head else "") + last[:cm.start()]
        return t

    out = []
    for line in txt.splitlines(keepends=True):
        cm = _COMMENT_START.search(line)
        code, comment = (line[:cm.start()], line[cm.start():]) if cm else (line, "")
        if strip_comments and comment:
            if code.strip():
                comment = "%" + ("\n" if comment.endswith("\n") else "")
            else:
                continue

        def sub(m: re.Match, _code: str = code, _comment: str = comment) -> str:
            p = _resolve(m.group(1), base)
            if p is None:
                return m.group(0)
            trailing = not _code[m.end():].strip() and not _comment.strip("%\n")
            return body(p, trailing)

        out.append(INPUT_RE.sub(sub, code) + comment)
    return "".join(out)


def included_files(main: str, base: str | None = None) -> list[str]:
    """Every file reached from `main` through \\input/\\include, in reading order."""
    main = os.path.abspath(main)
    base = os.path.abspath(base) if base is not None else os.path.dirname(main)
    seen: list[str] = []

    def walk(p: str) -> None:
        if p in seen:
            return
        seen.append(p)
        with open(p, encoding="utf-8") as fh:
            src = "\n".join(_COMMENT_START.split(ln, 1)[0] for ln in fh.read().split("\n"))
        for name in INPUT_RE.findall(src):
            q = _resolve(name, base)
            if q:
                walk(q)

    walk(main)
    return seen


# ---------------------------------------------------------------------------------- tables
def _body(src: str) -> str:
    return "\n".join(_COMMENT_START.split(ln, 1)[0] for ln in src.split("\n"))


def table_rows(src: str) -> list[list[str]]:
    """Cells of every tabular row in `src` (a path or TeX text), rules and comments dropped.

    A row is a line segment ending in \\\\ that contains &. \\multicolumn rows are kept with
    their raw cell text, since header rows often use them."""
    if "\n" not in src and os.path.exists(src):
        with open(src, encoding="utf-8") as fh:
            src = fh.read()
    t = _body(src)
    t = re.sub(r"\\(?:toprule|midrule|bottomrule|hline|cmidrule(?:\([^)]*\))?\{[^}]*\})", "", t)
    rows = []
    for chunk in re.split(r"\\\\(?:\[[^\]]*\])?", t):
        chunk = chunk.strip()
        if "&" not in chunk:
            continue
        m = re.search(r"\\begin\{(?:tabular\*?|tabularx|longtable)\}", chunk)
        if m:
            chunk = _skip_groups(chunk[m.end():]).strip()
        rows.append([c.strip() for c in re.split(r"(?<!\\)&", chunk)])
    return rows


def _skip_groups(t: str) -> str:
    """Drop leading balanced {...} / [...] groups (a tabular's width and column spec)."""
    t = t.lstrip()
    while t[:1] in ("{", "["):
        close = "}" if t[0] == "{" else "]"
        depth, i = 0, 0
        for i, ch in enumerate(t):
            if ch == t[0]:
                depth += 1
            elif ch == close:
                depth -= 1
                if depth == 0:
                    break
        t = t[i + 1:].lstrip()
    return t


def table(src: str, label: str) -> list[list[str]]:
    """Rows of the table environment carrying \\label{label}."""
    if "\n" not in src and os.path.exists(src):
        with open(src, encoding="utf-8") as fh:
            src = fh.read()
    for m in re.finditer(r"\\begin\{(table\*?|longtable)\}(.*?)\\end\{\1\}", src, re.S):
        if f"\\label{{{label}}}" in m.group(2):
            return table_rows(m.group(2))
    raise KeyError(f"no table labelled {label!r}")


def is_bold(cell: str) -> bool:
    """Whether a cell is set in bold (\\textbf, \\mathbf, \\bfseries, \\bm)."""
    return bool(re.search(r"\\(?:textbf|mathbf|bm|boldsymbol)\{|\\bfseries", cell))


def cell_text(cell: str) -> str:
    """A cell without its markup: '\\textbf{0.853}' -> '0.853'."""
    t = re.sub(r"\\(?:textbf|mathbf|bm|boldsymbol|textit|emph|underline|text)\{([^{}]*)\}", r"\1", cell)
    t = re.sub(r"\\bfseries|\\itshape|\\(?:multicolumn|multirow)\{[^}]*\}\{[^}]*\}", "", t)
    return " ".join(t.replace("$", "").replace("{", "").replace("}", "").split())


# ---------------------------------------------------------------------------------- floats
_FLOAT = re.compile(r"\\begin\{(figure\*?|table\*?)\}(.*?)\\end\{\1\}", re.S)
_LABEL = re.compile(r"\\label\{([^}]*)\}")
_REF = re.compile(r"\\(?:ref|autoref|cref|Cref|eqref|pageref)\*?\{([^}]*)\}")


def float_labels(src: str) -> list[str]:
    """Labels set inside figure/table floats (longtable is not a float and is ignored)."""
    return [lab for m in _FLOAT.finditer(_body(src)) for lab in _LABEL.findall(m.group(2))]


def references(src: str) -> set[str]:
    """Every label referenced with \\ref and friends (comma lists of \\cref split)."""
    return {k.strip() for m in _REF.finditer(_body(src)) for k in m.group(1).split(",")}
