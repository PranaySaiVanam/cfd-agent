from pathlib import Path

import numpy as np
import pytest

from cfd_agent import checks, postprocess as pp
from cfd_agent.benchmarks import reference_for

DATA = Path(__file__).parent / "data"


def test_checkmesh_real_log_passes():
    q = checks.parse_checkmesh((DATA / "checkMesh_ok.log").read_text())
    assert q.passed and q.cells == 1600 and q.max_aspect_ratio == 1.0


def test_checkmesh_failures_detected():
    log = "cells: 10\nMax aspect ratio = 100 OK.\nMesh non-orthogonality Max: 80 average: 5\nMax skewness = 1 OK.\nFailed 1 mesh checks.\n"
    q = checks.parse_checkmesh(log)
    assert not q.passed and len(q.failures) >= 3
    assert not checks.parse_checkmesh("garbage").passed


def test_solver_real_log_converged_and_no_false_crash():
    c = checks.parse_solver_log((DATA / "icoFoam_converged.log").read_text())
    # the header line "Floating point exception trapping enabled" must NOT count as a crash
    assert c.converged, c.failures
    assert c.openfoam_build and c.openfoam_build.startswith("1912")


def test_solver_failures_detected():
    base = (DATA / "icoFoam_converged.log").read_text()
    assert not checks.parse_solver_log(base + "\n--> FOAM FATAL ERROR: boom\n").converged
    head, _, _ = base.rpartition("\nEnd")
    unconverged = head + ("\nsmoothSolver:  Solving for Ux, Initial residual = 0.01, Final residual = 1e-3, No Iterations 3"
                          "\nsmoothSolver:  Solving for Uy, Initial residual = 0.02, Final residual = 1e-3, No Iterations 3\n\nEnd\n")
    c = checks.parse_solver_log(unconverged)
    assert not c.converged and any("not converged" in f for f in c.failures)
    assert not checks.parse_solver_log("nothing useful").converged


def _write_field(path: Path, vel: np.ndarray):
    n = len(vel)
    body = "\n".join(f"({a} {b} {c})" for a, b, c in vel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"FoamFile\n{{\n}}\ninternalField nonuniform List<vector>\n{n}\n(\n{body}\n)\n;\n")


def test_read_vector_field_and_errors(tmp_path):
    vel = np.random.default_rng(0).random((16, 3))
    _write_field(tmp_path / "1" / "U", vel)
    assert np.allclose(pp.read_vector_field(tmp_path / "1" / "U", 16), vel)
    with pytest.raises(ValueError):
        pp.read_vector_field(tmp_path / "1" / "U", 15)              # wrong cell count
    (tmp_path / "bad").write_text("internalField nonuniform List<vector> 1 ( (nan 0 0) ) ;")
    with pytest.raises(ValueError):
        pp.read_vector_field(tmp_path / "bad", 1)


def test_centerline_and_validation_logic(tmp_path):
    n = 20
    ref = reference_for(100)
    ry = np.array([p[0] for p in ref]); ru = np.array([p[1] for p in ref])
    # build a field that exactly reproduces the reference profile in y (function of y only)
    yc = (np.arange(n) + 0.5) / n
    prof = np.interp(yc, ry[::-1], ru[::-1])
    vel = np.zeros((n * n, 3))
    for j in range(n):
        vel[j * n:(j + 1) * n, 0] = prof[j]
    _write_field(tmp_path / "2" / "U", vel)
    v, msg = pp.validate_against_ghia(tmp_path, n, 100, 1.0)
    assert v is not None and v.rms_error < 0.03 and v.passed
    # same field claimed to be Re=100 but scaled wrongly -> must fail the gate
    _write_field(tmp_path / "3" / "U", vel * 3)
    v2, _ = pp.validate_against_ghia(tmp_path, n, 100, 1.0)
    assert v2 is not None and not v2.passed


def test_no_reference_means_skip_not_fake_pass(tmp_path):
    _write_field(tmp_path / "2" / "U", np.zeros((400, 3)))
    v, msg = pp.validate_against_ghia(tmp_path, 20, 150, 1.0)
    assert v is None and "no Ghia reference" in msg
