"""End-to-end tests against a REAL OpenFOAM install (skipped automatically if none is found)."""
import pytest

from cfd_agent.agent import run_request
from cfd_agent.runners import OpenFOAMRunner

runner = OpenFOAMRunner()
pytestmark = [pytest.mark.openfoam, pytest.mark.skipif(not runner.available(), reason="OpenFOAM not installed")]


def test_real_cavity_re100_matches_ghia(tmp_path):
    res = run_request("lid-driven cavity at Re 100 with a 32x32 grid", runner, None, tmp_path)
    assert res.status == "success", res.message
    v = res.final_attempt.validation
    assert v is not None and v.rms_error < 0.02
    assert res.final_attempt.convergence.converged and res.final_attempt.mesh.passed
    assert not res.is_mock and res.plot_path


def test_real_invalid_request_runs_nothing(tmp_path):
    res = run_request("lid-driven cavity at Re 100 with a 5x5 grid", runner, None, tmp_path)
    assert res.status == "rejected" and not res.attempts
