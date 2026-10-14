from texclaims import tex as X

TABLE = r"""
\begin{table}[t]
\caption{Results}\label{tab:res}
\begin{tabular}{@{}lp{2cm}c@{}}
\toprule
Model & F1 & $q$ \\
\midrule
% Old & 0.1 & 0.9 \\
RF & \textbf{0.938} & 0.01 \\
LogReg & 0.901 & 0.20 \\[2pt]
\bottomrule
\end{tabular}
\end{table}
"""


def test_table_rows_reads_cells_and_skips_comments():
    assert X.table(TABLE, "tab:res") == [["Model", "F1", "$q$"],
                                          ["RF", "\\textbf{0.938}", "0.01"],
                                          ["LogReg", "0.901", "0.20"]]


def test_table_rows_skips_multicolumn_only_rows(tmp_path):
    p = tmp_path / "t.tex"
    p.write_text("\\multicolumn{2}{c}{Group} \\\\\nRF & 0.938 \\\\\n  CatBoost & 0.941 \\\\\n\\hline\n")
    assert X.table_rows(str(p)) == [["RF", "0.938"], ["CatBoost", "0.941"]]


def test_bold_and_cell_text():
    assert X.is_bold("\\textbf{0.9}") and X.is_bold("{\\bfseries 0.9}") and not X.is_bold("0.9")
    assert X.cell_text("\\textbf{$0.938$}") == "0.938"


def test_missing_label_raises():
    import pytest
    with pytest.raises(KeyError):
        X.table(TABLE, "tab:nope")


def test_flatten_keeps_tex_line_ends(tmp_path):
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "num.tex").write_text("0.853%\n")
    (tmp_path / "sec" / "par.tex").write_text("Para one.\n")
    (tmp_path / "main.tex").write_text(
        "F1 was \\input{sec/num} overall.\n\\input{sec/par}\nNext.\n% \\input{sec/par}\n")
    flat = X.flatten(str(tmp_path / "main.tex"))
    # mid-line input keeps the file's own newline; end-of-line input does not add a blank line
    assert flat == "F1 was 0.853%\n overall.\nPara one.\nNext.\n% \\input{sec/par}\n"


def test_flatten_rejects_a_cycle(tmp_path):
    import pytest
    (tmp_path / "a.tex").write_text("\\input{b}\n")
    (tmp_path / "b.tex").write_text("\\input{a}\n")
    with pytest.raises(ValueError, match="cycle"):
        X.flatten(str(tmp_path / "a.tex"))


def test_floats_and_references(tmp_path):
    (tmp_path / "main.tex").write_text(
        "\\input{s}\n\\begin{figure}\\label{fig:a}\\end{figure}\n"
        "\\begin{table}\\label{tab:b}\\end{table}\nSee \\cref{fig:a, tab:c}.\n")
    (tmp_path / "s.tex").write_text("\\begin{figure*}\\label{fig:z}\\end{figure*} \\ref{fig:z}\n")
    files = X.included_files(str(tmp_path / "main.tex"))
    src = "\n".join(open(f).read() for f in files)
    assert X.float_labels(src) == ["fig:a", "tab:b", "fig:z"]
    assert X.references(src) == {"fig:a", "tab:c", "fig:z"}


def test_flatten_resolves_relative_to_cwd_and_detects_cycle_through_dot(tmp_path, monkeypatch):
    import pytest
    (tmp_path / "p").mkdir()
    (tmp_path / "p" / "main.tex").write_text("A \\input{s}\n")
    (tmp_path / "p" / "s.tex").write_text("B\n")
    monkeypatch.chdir(tmp_path)
    assert X.flatten("p/main.tex") == "A B\n"
    (tmp_path / "p" / "s.tex").write_text("\\input{./main}\n")
    with pytest.raises(ValueError):
        X.flatten("./p/main.tex")
