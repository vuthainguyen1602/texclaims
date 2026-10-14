import pytest

from texclaims import core


@pytest.fixture
def suite():
    """A fresh suite whose output is not printed."""
    s = core.Suite()
    s._echo = None
    return s


def outcomes(suite):
    return [r.status for r in suite.results]
