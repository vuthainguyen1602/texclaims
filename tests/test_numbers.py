import math

import pytest

from texclaims import numbers as N


@pytest.mark.parametrize("printed, value, scale, ok", [
    ("0.853", 0.85349, 1, True),
    ("0.853", 0.8536, 1, False),
    ("0.85", 0.845, 1, True),           # exact half: either rounding accepted
    ("64\\%", 0.6412, 100, True),
    ("$64\\%$", 0.6450, 100, True),
    ("65%", 0.6412, 100, False),
    ("51{,}362", 51362, 1, True),
    ("51,362", 51361, 1, False),
    ("\\textbf{0.941}", 0.9409, 1, True),
    ("$-0.009$", -0.0091, 1, True),
    ("\u22120.009", -0.0091, 1, True),
    ("n/a", 0.5, 1, False),
])
def test_matches_at_printed_precision(printed, value, scale, ok):
    assert N.matches(printed, value, scale=scale) is ok


def test_nan_never_matches():
    assert not N.matches("0.5", float("nan"))


def test_decimals_and_parse():
    assert N.decimals("0.8530") == 4 and N.decimals("51{,}362") == 0
    assert N.parse("$0.968 $") == 0.968 and N.parse("abc") is None


def test_renderings_cover_tex_and_pdf_forms():
    assert N.renderings(51362) == ("51,362", "51362", "51{,}362", "51\\,362")


def test_wilson_known_interval():
    lo, hi = N.wilson(50, 100)
    assert (round(lo, 4), round(hi, 4)) == (0.4038, 0.5962)


def test_wilson_is_clamped_and_safe_at_zero():
    assert N.wilson(10, 10)[1] == 1.0 and N.wilson(0, 10)[0] == 0.0
    assert all(math.isnan(x) for x in N.wilson(0, 0))


def test_several_numerators_print_the_same_rate():
    # 89.7% of 1000 is 897; at one decimal 89.65%..89.75% admits 897 only, at zero decimals
    # 89.5%..90.5% admits 895..905: the interval cannot be recomputed from the printed rate.
    assert N.numerators("89.7%", 1000) == [897]
    assert N.numerators("90%", 1000) == list(range(895, 906))


def test_interval_consistent_accepts_any_consistent_numerator():
    k = 902
    lo, hi = N.wilson(k, 1000)
    plo, phi = f"{lo * 100:.1f}%", f"{hi * 100:.1f}%"
    assert N.interval_consistent("90%", plo, phi, 1000)
    # recomputing from the printed 90% (k=900) would give a different interval
    assert (f"{N.wilson(900, 1000)[0] * 100:.1f}%", f"{N.wilson(900, 1000)[1] * 100:.1f}%") != (plo, phi)
    assert not N.interval_consistent("90%", "80.0%", phi, 1000)
