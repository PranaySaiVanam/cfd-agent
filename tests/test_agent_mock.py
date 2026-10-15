import pytest

from cfd_agent.agent import MAX_ATTEMPTS, refine, resolve_spec, run_request
from cfd_agent.audit import Audit
from cfd_agent.llm_client import MockLLM
from cfd_agent.rules import parse_request
from cfd_agent.runners import MockRunner
from cfd_agent.schemas import CavitySpec


def go(tmp_path, req, runner=None, llm=None, **kw):
    return run_request(req, runner or MockRunner(), llm, tmp_path, **kw)


# ---------------------------------------------------------------- rule parser
@pytest.mark.parametrize("text,re_,n", [
    ("cavity flow at Re=400 with grid 48", 400, 48),
    ("lid driven cavity Reynolds number of 250, 32x32", 250, 32),
    ("Lid-driven cavity Re 75 with 30 cells per side", 75, 30),
    ("cavity Re 20 on a 24 by 24 mesh", 20, 24),
])
def test_rule_parser(text, re_, n):
    e = parse_request(text)
    assert e.supported and e.reynolds == re_ and e.grid_n == n


def test_rule_parser_rejects_unsupported():
    assert not parse_request("airfoil at Mach 0.8").supported
    assert not parse_request("lid-driven cavity 40x20").supported


# ---------------------------------------------------------------- happy path + safe rejection
def test_success_runs_fixed_tool_order(tmp_path):
    r = MockRunner()
    res = go(tmp_path, "lid-driven cavity at Re 100 with a 32x32 grid", r)
    assert res.status == "success" and res.is_mock
    assert r.calls == ["blockMesh", "checkMesh", "icoFoam"]
    assert "MOCK RUN" in open(res.report_path).read()
    assert res.final_attempt.validation is None            # never benchmark-validate synthetic data


@pytest.mark.parametrize("req", [
    "airfoil at Mach 0.8", "lid-driven cavity at Re 1000000",
    "lid-driven cavity Re 100 5x5 grid", "lid-driven cavity 40x20",
])
def test_invalid_requests_rejected_without_running_solver(tmp_path, req):
    r = MockRunner()
    res = go(tmp_path, req, r)
    assert res.status == "rejected" and res.message and r.calls == [] and res.attempts == []


def test_missing_values_use_flagged_defaults(tmp_path):
    res = go(tmp_path, "simulate cavity flow")
    assert res.status == "success" and res.spec["reynolds"] == 100
    assert any("Reynolds" in w for w in res.warnings) and any("grid" in w for w in res.warnings)


# ---------------------------------------------------------------- bounded retry ladder
def test_refine_ladder():
    s = CavitySpec(grid_n=40, courant=0.2)
    a2 = refine(s, 2); a3 = refine(a2, 3)
    assert a2.grid_n == 60 and a2.courant == 0.2 and a3.grid_n == 90 and a3.courant == 0.1
    assert refine(CavitySpec(grid_n=128), 2).grid_n == 128   # capped


def test_bad_mesh_recovers_on_refinement(tmp_path):
    res = go(tmp_path, "cavity Re 100 grid 40", MockRunner(bad_mesh_below_grid=50))
    assert res.status == "success" and len(res.attempts) == 2
    assert res.attempts[0].failure.startswith("mesh quality gate failed")
    assert any("refinement" in w for w in res.warnings)


def test_divergence_and_unconverged_recover(tmp_path):
    assert go(tmp_path, "cavity Re 100 grid 40", MockRunner(diverge_below_grid=50)).status == "success"
    assert go(tmp_path, "cavity Re 100 grid 40", MockRunner(unconverged_below_grid=80)).status == "success"


def test_always_failing_stops_after_max_attempts(tmp_path):
    r = MockRunner(bad_mesh_below_grid=10_000)
    res = go(tmp_path, "cavity Re 100 grid 40", r)
    assert res.status == "failed" and len(res.attempts) == MAX_ATTEMPTS
    assert r.calls.count("blockMesh") == MAX_ATTEMPTS and "icoFoam" not in r.calls
    assert "Failed after 3 attempt" in res.message


def test_blockmesh_failure_is_a_clean_failure(tmp_path):
    res = go(tmp_path, "cavity Re 100 grid 40", MockRunner(fail_blockmesh=True))
    assert res.status == "failed" and len(res.attempts) == MAX_ATTEMPTS


def test_audit_log_written(tmp_path):
    res = go(tmp_path, "cavity Re 100 grid 32")
    lines = (tmp_path / res.run_dir.split("/")[-1] / "audit.jsonl").read_text().splitlines()
    tools = [__import__("json").loads(x)["tool"] for x in lines]
    assert tools == ["rule_parse", "build_case", "blockMesh", "checkMesh", "icoFoam", "postprocess"]


# ---------------------------------------------------------------- LLM paths (scripted, no network)
def test_llm_valid_extraction(tmp_path):
    llm = MockLLM([{"supported": True, "reynolds": 250, "grid_n": 32}])
    res = go(tmp_path, "whatever", llm=llm)
    assert res.status == "success" and res.spec_source == "llm" and res.spec["reynolds"] == 250


def test_llm_malformed_then_reprompt_succeeds(tmp_path):
    llm = MockLLM([{"supported": True, "reynolds": 1e6}, {"supported": True, "reynolds": 300}])
    res = go(tmp_path, "cavity Re 300", llm=llm)
    assert res.status == "success" and res.spec["reynolds"] == 300
    assert llm.calls[1][1] is not None                       # validation error was fed back once


def test_llm_keeps_failing_falls_back_to_rules(tmp_path):
    llm = MockLLM([{"supported": True, "reynolds": 1e6}, {"nonsense": 1}])
    res = go(tmp_path, "lid-driven cavity at Re 120 grid 30", llm=llm)
    assert res.status == "success" and res.spec_source.startswith("rules") and res.spec["reynolds"] == 120
    assert any("rule-based parser" in w for w in res.warnings)


def test_llm_outage_falls_back_to_rules(tmp_path):
    res = go(tmp_path, "lid-driven cavity at Re 120 grid 30", llm=MockLLM([ConnectionError("down")]))
    assert res.status == "success" and res.spec_source.startswith("rules")


def test_llm_says_unsupported_is_rejected(tmp_path):
    llm = MockLLM([{"supported": False, "reason": "airfoil"}])
    res = go(tmp_path, "airfoil", llm=llm)
    assert res.status == "rejected" and "airfoil" in res.message and res.attempts == []


def test_user_out_of_range_not_silently_clamped(tmp_path):
    llm = MockLLM([{"supported": True, "reynolds": 1e6}] * 2)
    res = go(tmp_path, "lid-driven cavity at Re 1000000", llm=llm)
    assert res.status == "rejected" and "reynolds" in res.message.lower()
