import json

from conftest import outcomes


def test_check_records_and_returns(suite):
    assert suite.check("a", True) is True
    assert suite.check("b", 0) is False
    assert outcomes(suite) == ["ok", "fail"]


def test_pinned_failures_are_shown_not_failed(suite):
    with suite.pinned("data as of 2026-09-01"):
        assert suite.check("live count", False) is True
    suite.check("after pin", False)
    assert outcomes(suite) == ["pin", "fail"]
    assert "2026-09-01" in suite.results[0].detail


def test_family_that_raises_is_a_failure_and_others_still_run(suite):
    @suite.claim("broken")
    def boom():
        raise FileNotFoundError("results.csv")

    @suite.claim("fine")
    def fine():
        suite.check("x", True)

    rep = suite.run(echo=None)
    assert [r.status for r in rep.results] == ["fail", "ok"]
    assert "FileNotFoundError" in rep.results[0].detail and not rep.ok


def test_floor_catches_a_check_that_stopped_running(suite, tmp_path):
    """The failure mode the floor exists for: an input disappears, its checks silently stop
    running, and every check that still runs passes."""
    floors = tmp_path / "floors.json"
    present = {"on": True}

    @suite.claim("paper")
    def paper():
        suite.check("always", True)
        if present["on"]:
            suite.check("needs input", True)

    assert suite.run(floors_path=str(floors), update_floors=True, echo=None).ok
    assert json.loads(floors.read_text()) == {"paper": 2}
    assert suite.run(floors_path=str(floors), echo=None).ok
    present["on"] = False
    rep = suite.run(floors_path=str(floors), echo=None)
    assert not rep.ok and "floor is 2" in rep.failed[0].detail


def test_family_without_a_floor_fails_until_recorded(suite, tmp_path):
    @suite.claim("new")
    def new():
        suite.check("x", True)

    rep = suite.run(floors_path=str(tmp_path / "f.json"), echo=None)
    assert not rep.ok and "record it" in rep.failed[0].detail


def test_unknown_family_fails(suite):
    rep = suite.run(["nope"], echo=None)
    assert not rep.ok


def test_several_functions_per_family_accumulate(suite):
    for i in range(2):
        suite.claim("p")(lambda: suite.check("x", True))
    rep = suite.run(echo=None)
    assert rep.counts == {"p": 2}


def test_report_json_shape(suite):
    suite.claim("p")(lambda: suite.check("x", False, "why"))
    d = suite.run(echo=None).to_dict()
    assert d["passed"] == 0 and d["total"] == 1 and d["results"][0]["detail"] == "why"
