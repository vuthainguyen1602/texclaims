"""texclaims: check that a LaTeX manuscript still says what its data says.

A claims file registers check functions under families; `texclaims run` executes them, fails on
any mismatch, and fails when a family runs fewer checks than its recorded floor.
"""
from . import guards, numbers, tex, text
from .core import Report, Result, Suite, check, claim, current, pinned

__version__ = "0.1.0"
__all__ = ["Report", "Result", "Suite", "check", "claim", "current", "pinned",
           "guards", "numbers", "tex", "text", "__version__"]
