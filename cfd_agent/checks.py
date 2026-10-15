"""Parse OpenFOAM logs into pass/fail quality gates. No LLM involved."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# thresholds (documented in README)
MAX_NON_ORTHO = 65.0
MAX_SKEWNESS = 4.0
MAX_ASPECT = 50.0
RESIDUAL_TOL = 1e-6          # final-step initial residual of Ux/Uy to call steady state
MAX_COURANT = 1.0


@dataclass
class MeshQuality:
    passed: bool
    cells: int | None = None
    max_non_orthogonality: float | None = None
    max_skewness: float | None = None
    max_aspect_ratio: float | None = None
    failures: list[str] = field(default_factory=list)


def _f(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def parse_checkmesh(log: str) -> MeshQuality:
    q = MeshQuality(passed=False)
    cells = _f(r"cells:\s+(\d+)", log)
    q.cells = int(cells) if cells is not None else None
    q.max_aspect_ratio = _f(r"Max aspect ratio\s*=\s*([0-9.eE+-]+)", log)
    q.max_non_orthogonality = _f(r"non-orthogonality Max:\s*([0-9.eE+-]+)", log)
    q.max_skewness = _f(r"Max skewness\s*=\s*([0-9.eE+-]+)", log)
    if q.cells is None or q.max_non_orthogonality is None or q.max_skewness is None or q.max_aspect_ratio is None:
        q.failures.append("checkMesh output incomplete or unparsable")
    if re.search(r"Failed\s+\d+\s+mesh checks", log):
        q.failures.append("checkMesh reported failed checks")
    if "Mesh OK" not in log:
        q.failures.append("checkMesh did not report 'Mesh OK'")
    if q.max_non_orthogonality is not None and q.max_non_orthogonality > MAX_NON_ORTHO:
        q.failures.append(f"non-orthogonality {q.max_non_orthogonality} > {MAX_NON_ORTHO}")
    if q.max_skewness is not None and q.max_skewness > MAX_SKEWNESS:
        q.failures.append(f"skewness {q.max_skewness} > {MAX_SKEWNESS}")
    if q.max_aspect_ratio is not None and q.max_aspect_ratio > MAX_ASPECT:
        q.failures.append(f"aspect ratio {q.max_aspect_ratio} > {MAX_ASPECT}")
    q.passed = not q.failures
    return q


@dataclass
class Convergence:
    converged: bool
    final_ux_residual: float | None = None
    final_uy_residual: float | None = None
    final_p_residual: float | None = None
    max_courant: float | None = None
    openfoam_build: str | None = None
    failures: list[str] = field(default_factory=list)


def parse_solver_log(log: str, tol: float = RESIDUAL_TOL) -> Convergence:
    c = Convergence(converged=False)
    m = re.search(r"OPENFOAM=(\S+)(?:\s+patch=(\S+))?", log)
    if m:
        c.openfoam_build = m.group(1) + (f" patch {m.group(2)}" if m.group(2) else "")
    if re.search(r"FOAM FATAL|sigFpe::sigHandler|Floating point exception \(core dumped\)|\bnan\b", log, re.I):
        c.failures.append("solver crashed or diverged (fatal error / FPE / NaN in log)")
    if "TIMEOUT" in log:
        c.failures.append("solver timed out")
    ux = re.findall(r"Solving for Ux, Initial residual = ([0-9.eE+-]+)", log)
    uy = re.findall(r"Solving for Uy, Initial residual = ([0-9.eE+-]+)", log)
    pp = re.findall(r"Solving for p, Initial residual = ([0-9.eE+-]+)", log)
    cour = re.findall(r"Courant Number mean: [0-9.eE+-]+ max: ([0-9.eE+-]+)", log)
    if not ux or not uy:
        c.failures.append("no velocity residuals found in solver log")
    else:
        c.final_ux_residual, c.final_uy_residual = float(ux[-1]), float(uy[-1])
        if max(c.final_ux_residual, c.final_uy_residual) > tol:
            c.failures.append(
                f"not converged: final Ux/Uy initial residual {max(c.final_ux_residual, c.final_uy_residual):.2e} > {tol:.0e}")
    if pp:
        c.final_p_residual = float(pp[-1])
    if cour:
        c.max_courant = max(float(x) for x in cour)
        if c.max_courant > MAX_COURANT:
            c.failures.append(f"max Courant number {c.max_courant:.2f} > {MAX_COURANT}")
    if not re.search(r"^End\s*$", log, re.M):
        c.failures.append("solver log has no clean 'End'")
    c.converged = not c.failures
    return c
