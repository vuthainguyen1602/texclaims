import subprocess
import zipfile

from texclaims import guards as G, tex
from conftest import outcomes

PAT = r"([\d.]+)% (?:of indicators|coverage)"


def test_consistent_passes_when_every_restatement_agrees(suite):
    G.consistent("coverage", "41% of indicators; 41% coverage", PAT, "41", suite=suite)
    assert outcomes(suite) == ["ok"]


def test_consistent_catches_the_stale_copy(suite):
    """Four correct restatements and one stale one fail, although a presence test passes."""
    t = "41% of indicators; 41% coverage; 41% coverage; 41% coverage; 38% of indicators"
    G.present("coverage present", t, "41%", suite=suite)
    G.consistent("coverage", t, PAT, "41", suite=suite)
    assert outcomes(suite) == ["ok", "fail"]
    assert "38" in suite.results[1].detail


def test_consistent_accepts_only_declared_roundings(suite):
    t = "40.8% of indicators; 41% coverage"
    G.consistent("c", t, PAT, "40.8", "41", suite=suite)
    G.consistent("c", t, PAT, "40.8", suite=suite)
    assert outcomes(suite) == ["ok", "fail"]


def test_consistent_fails_when_the_claim_vanishes(suite):
    G.consistent("c", "no such sentence", PAT, "41", suite=suite)
    assert outcomes(suite) == ["fail"]


def test_value_at_precision(suite):
    G.value_at_precision("f1", "0.853", 0.85349, suite=suite)
    G.value_at_precision("f1", "0.853", 0.8549, suite=suite)
    G.value_at_precision("rate", "64\\%", 0.6412, scale=100, suite=suite)
    G.value_at_precision("missing", None, 0.5, suite=suite)
    assert outcomes(suite) == ["ok", "fail", "ok", "fail"]


ROWS = [["RF", "\\textbf{0.938}", "0.01"], ["LogReg", "0.901", "0.20"], ["SVM", "\\textbf{0.930}", "0.09"]]


def test_bold_matches_the_tables_own_rule(suite):
    rule = lambda r: float(r[2]) < 0.05
    G.bold_matches("bold = q<0.05", ROWS[:2], 1, rule, suite=suite)
    G.bold_matches("bold = q<0.05", ROWS, 1, rule, suite=suite)
    assert outcomes(suite) == ["ok", "fail"]
    assert "SVM: bold" in suite.results[1].detail


def test_cells_match(suite):
    G.cells_match("t", [["RF", "\\textbf{0.938}"]], [["RF", 0.9381]], suite=suite)
    G.cells_match("t", [["RF", "0.938"]], [["RF", 0.9391]], suite=suite)
    G.cells_match("t", [["RF", "0.938"]], [["RF", 0.938], ["X", 1]], suite=suite)
    assert outcomes(suite) == ["ok", "fail", "fail"]


def test_forbidden_ignores_comments_and_reports_location(tmp_path, suite):
    (tmp_path / "a.tex").write_text("Fine.\n% the reviewers asked for this\n")
    (tmp_path / "letter.tex").write_text("As the reviewer suggested, we added X.\n")
    G.forbidden("no review talk", str(tmp_path / "a.tex"), G.REVIEW_TALK, suite=suite)
    G.forbidden("no review talk", str(tmp_path / "*.tex"), G.REVIEW_TALK, suite=suite)
    G.forbidden("no review talk", str(tmp_path / "*.tex"), G.REVIEW_TALK,
                exempt=lambda p: p.endswith("letter.tex"), suite=suite)
    assert outcomes(suite) == ["ok", "fail", "ok"]
    assert "letter.tex:1" in suite.results[1].detail


def test_review_talk_spares_ordinary_uses_of_review():
    for ok in ("A review of phishing detection", "two annotators reviewed each label",
               "Writing - review & editing"):
        assert not G.REVIEW_TALK.search(ok)
    for bad in ("the reviewer comments", "changed in this revision", "an earlier draft of"):
        assert G.REVIEW_TALK.search(bad)


def test_floats_referenced(tmp_path, suite):
    (tmp_path / "main.tex").write_text(
        "\\input{s}\n\\begin{figure}\\label{fig:a}\\end{figure}\nSee Fig.~\\ref{fig:a}.\n")
    (tmp_path / "s.tex").write_text("\\begin{table}\\label{tab:orphan}\\end{table}\n")
    G.floats_referenced(str(tmp_path / "main.tex"), suite=suite)
    assert outcomes(suite) == ["fail"] and "tab:orphan" in suite.results[0].detail


def test_word_limit_counts_source_not_pdf(tmp_path, suite):
    (tmp_path / "abs.tex").write_text(
        "\\begin{abstract}\nWe find $p<0.05$ in \\textbf{three} cases~\\cite{a}. % 99 words of comment\n"
        "\\end{abstract}\n")
    G.word_limit("abstract", str(tmp_path / "abs.tex"), 6, suite=suite)
    G.word_limit("abstract", str(tmp_path / "abs.tex"), 5, suite=suite)
    assert outcomes(suite) == ["ok", "fail"]


def test_highlights(suite):
    G.highlights("hl", ["a" * 85, "b", "c"], suite=suite)
    G.highlights("hl", ["a" * 86, "b"], suite=suite)
    assert outcomes(suite) == ["ok", "ok", "fail", "fail"]


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
                        "GIT_AUTHOR_DATE": args[-1] if args[0] == "commit" else "",
                        "GIT_COMMITTER_DATE": args[-1] if args[0] == "commit" else ""})


def test_letter_current(tmp_path, suite, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _git(tmp_path, "init", "-q")
    (tmp_path / "letter.tex").write_text("Dear editor\n")
    (tmp_path / "main.tex").write_text("v1\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "both", "--date", "2026-01-01T00:00:00")
    G.letter_current("letter", "letter.tex", ["main.tex"], suite=suite)
    (tmp_path / "main.tex").write_text("v2\n")
    _git(tmp_path, "commit", "-qam", "ms", "--date", "2026-01-03T00:00:00")
    G.letter_current("letter", "letter.tex", ["main.tex"], suite=suite)
    (tmp_path / "letter.tex").write_text("Dear editor, updated\n")
    G.letter_current("letter", "letter.tex", ["main.tex"], suite=suite)
    assert outcomes(suite) == ["ok", "fail", "ok"]
    assert "2.0 day" in suite.results[1].detail


SENT = ("\\documentclass{article}\\begin{document}\n"
        "The classifier reaches an F1 of 0.853 on the temporal split, which is lower than the random "
        "split by a margin that the composition of the test set explains almost entirely.\n"
        "\\end{document}\n")


def test_pack_matches_flattened_sources_and_honours_declared_drift(tmp_path, suite):
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "num.tex").write_text("0.853%\n")
    (tmp_path / "main.tex").write_text(SENT.replace("0.853", "\\input{sec/num}"))
    with zipfile.ZipFile(tmp_path / "pack.zip", "w") as z:
        z.writestr("main.tex", SENT)
    G.pack_matches("pack", str(tmp_path / "pack.zip"), str(tmp_path / "main.tex"), suite=suite)
    (tmp_path / "sec" / "num.tex").write_text("0.861%\n")
    G.pack_matches("pack", str(tmp_path / "pack.zip"), str(tmp_path / "main.tex"), suite=suite)
    G.pack_matches("pack", str(tmp_path / "pack.zip"), str(tmp_path / "main.tex"),
                   declared=["The classifier reaches an F1 of 0.853 on the temporal split",
                             "The classifier reaches an F1 of 0.861 on the temporal split"], suite=suite)
    assert outcomes(suite) == ["ok", "fail", "ok"]
