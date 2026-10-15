"""Deterministic MockRunner for tests/CI. Produces OpenFOAM-shaped logs and a SYNTHETIC field.
Its output is NEVER physically meaningful and is flagged as mock everywhere it is reported."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .base import RunResult


class MockRunner:
    is_mock = True
    name = "mock"

    def __init__(self, fail_blockmesh: bool = False, bad_mesh_below_grid: int = 0,
                 diverge_below_grid: int = 0, unconverged_below_grid: int = 0):
        # failure injection: behaviours depend on grid size so the retry ladder (refine mesh) can recover
        self.fail_blockmesh = fail_blockmesh
        self.bad_mesh_below_grid = bad_mesh_below_grid
        self.diverge_below_grid = diverge_below_grid
        self.unconverged_below_grid = unconverged_below_grid
        self.calls: list[str] = []

    def _spec(self, case_dir: Path) -> dict:
        return json.loads((Path(case_dir) / "spec.json").read_text())

    def run(self, command: str, case_dir: Path) -> RunResult:
        case_dir = Path(case_dir)
        self.calls.append(command)
        spec = self._spec(case_dir)
        n = spec["grid_n"]
        if command == "blockMesh":
            ok = not self.fail_blockmesh
            log = "Build  : OPENFOAM=MOCK\nEnd\n" if ok else "--> FOAM FATAL ERROR : mock blockMesh failure\n"
            res = RunResult(ok, 0 if ok else 1, log, 0.01, command)
        elif command == "checkMesh":
            bad = n < self.bad_mesh_below_grid
            nonorth = 85.0 if bad else 0.0
            log = (f"    cells:            {n * n}\n    Max aspect ratio = {1 + (0.1 / n) * 100:.4g} OK.\n"
                   f"    Mesh non-orthogonality Max: {nonorth} average: 0\n    Max skewness = 1e-14 OK.\n"
                   + ("\nFailed 1 mesh checks.\n" if bad else "\nMesh OK.\n") + "\nEnd\n")
            res = RunResult(not bad, 0 if not bad else 1, log, 0.01, command)
        elif command == "icoFoam":
            res = self._solve(case_dir, spec)
        else:
            res = RunResult(False, 2, "unknown command", 0.0, command)
        (case_dir / f"log.{command}").write_text(res.log)
        return res

    def _solve(self, case_dir: Path, spec: dict) -> RunResult:
        n, U = spec["grid_n"], spec["lid_velocity"]
        diverge = n < self.diverge_below_grid
        unconv = n < self.unconverged_below_grid
        res_u = 1e-3 if unconv else 1e-9
        lines = ["Build  : OPENFOAM=MOCK", "Time = 0.1", "",
                 "Courant Number mean: 0.05 max: 0.2",
                 f"smoothSolver:  Solving for Ux, Initial residual = {res_u:.3e}, Final residual = 1e-10, No Iterations 1",
                 f"smoothSolver:  Solving for Uy, Initial residual = {res_u:.3e}, Final residual = 1e-10, No Iterations 1",
                 "DICPCG:  Solving for p, Initial residual = 1e-9, Final residual = 1e-10, No Iterations 1"]
        if diverge:
            lines.append("--> FOAM FATAL ERROR: Floating point exception (sigFpe)")
        lines.append("End")
        log = "\n".join(lines) + "\n"
        if diverge:
            return RunResult(False, 1, log, 0.01, "icoFoam")
        # synthetic, clearly non-physical field: u = U*y^4, v = 0
        y = (np.arange(n) + 0.5) / n
        vel = np.zeros((n * n, 3))
        for j in range(n):
            vel[j * n:(j + 1) * n, 0] = U * y[j] ** 4
        for t in ("0.1", "0.2"):
            d = case_dir / t
            d.mkdir(exist_ok=True)
            body = "\n".join(f"({a:.8g} {b:.8g} {c:.8g})" for a, b, c in vel)
            (d / "U").write_text(
                f"FoamFile\n{{\n    version 2.0;\n    format ascii;\n    class volVectorField;\n    object U;\n}}\n\n"
                f"dimensions [0 1 -1 0 0 0 0];\ninternalField nonuniform List<vector>\n{n * n}\n(\n{body}\n)\n;\n")
        return RunResult(True, 0, log, 0.01, "icoFoam")
