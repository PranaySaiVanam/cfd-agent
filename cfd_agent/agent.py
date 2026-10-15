"""CFD-Agent pipeline.

Design: the LLM (optional) only turns the request into a validated CavitySpec. Everything after that is a
fixed, code-enforced sequence: build_case -> blockMesh -> checkMesh gate -> icoFoam -> convergence gate ->
benchmark validation. Failures walk a bounded retry ladder (max 3 attempts). No step can be skipped."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from . import postprocess as pp
from .audit import Audit
from .case_builder import build_case
from .checks import Convergence, MeshQuality, parse_checkmesh, parse_solver_log
from .llm_client import LLMClient
from .rules import parse_request
from .runners.base import Runner
from .schemas import CavitySpec, LLMExtraction

MAX_ATTEMPTS = 3


@dataclass
class Attempt:
    index: int
    spec: dict
    ok: bool = False
    failure: str | None = None
    mesh: MeshQuality | None = None
    convergence: Convergence | None = None
    steady_change: float | None = None
    validation: pp.Validation | None = None
    solver_seconds: float = 0.0


@dataclass
class AgentResult:
    status: str                      # success | failed | rejected
    message: str
    request: str
    spec_source: str = "none"        # llm | rules | rules (llm unavailable/invalid)
    spec: dict | None = None
    attempts: list[Attempt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation_message: str = ""
    run_dir: str | None = None
    report_path: str | None = None
    plot_path: str | None = None
    is_mock: bool = False
    runner: str = ""
    openfoam_build: str | None = None

    @property
    def final_attempt(self) -> Attempt | None:
        return self.attempts[-1] if self.attempts else None

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- request -> spec
def _short_validation_error(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())


def resolve_spec(request: str, llm: LLMClient | None, audit: Audit) -> tuple[CavitySpec | None, str, str, list[str]]:
    """Returns (spec, source, rejection_reason, warnings). spec is None => reject with reason."""
    warnings: list[str] = []
    extraction: LLMExtraction | None = None
    source = "rules"

    if llm is not None:
        feedback = None
        for attempt in (1, 2):                       # one re-prompt on validation failure, then fall back
            t0 = time.time()
            try:
                raw = llm.extract(request, feedback)
                ext = LLMExtraction(**raw)
                if not ext.supported:
                    audit.log("llm_extract", {"request": request}, {"supported": False, "reason": ext.reason}, time.time() - t0)
                    return None, "llm", ext.reason or "request is not a lid-driven cavity flow", warnings
                spec = ext.to_spec()
                audit.log("llm_extract", {"request": request, "attempt": attempt}, {"ok": True, "spec": spec.input_dict()}, time.time() - t0)
                return spec, "llm", "", _default_warnings(ext, warnings)
            except ValidationError as e:
                feedback = _short_validation_error(e)
                audit.log("llm_extract", {"request": request, "attempt": attempt}, {"ok": False, "validation_error": feedback}, time.time() - t0)
            except Exception as e:                    # network/API/schema problems -> deterministic fallback
                audit.log("llm_extract", {"request": request, "attempt": attempt}, {"ok": False, "error": repr(e)}, time.time() - t0)
                feedback = None
                break
        warnings.append("LLM extraction unavailable or invalid; used the rule-based parser instead")
        source = "rules (llm unavailable/invalid)"

    ext = parse_request(request)
    if not ext.supported:
        audit.log("rule_parse", {"request": request}, {"supported": False, "reason": ext.reason})
        return None, source, ext.reason or "unsupported request", warnings
    try:
        spec = ext.to_spec()
    except ValidationError as e:
        reason = "invalid parameter(s): " + _short_validation_error(e)
        audit.log("rule_parse", {"request": request}, {"ok": False, "validation_error": reason})
        return None, source, reason, warnings
    audit.log("rule_parse", {"request": request}, {"ok": True, "spec": spec.input_dict()})
    return spec, source, "", _default_warnings(ext, warnings)


def _default_warnings(ext: LLMExtraction, warnings: list[str]) -> list[str]:
    w = list(warnings)
    d = CavitySpec()
    if ext.reynolds is None:
        w.append(f"Reynolds number not specified; using default Re={d.reynolds:g}")
    if ext.grid_n is None:
        w.append(f"grid size not specified; using default {d.grid_n}x{d.grid_n}")
    return w


# ---------------------------------------------------------------- retry ladder
def refine(spec: CavitySpec, step: int) -> CavitySpec:
    """Attempt 2: refine mesh x1.5. Attempt 3: refine mesh again and halve the Courant target."""
    d = spec.input_dict()
    n = min(128, int(round(spec.grid_n * 1.5 / 2.0)) * 2)
    d["grid_n"] = n
    if step >= 3:
        d["courant"] = max(0.02, spec.courant / 2)
    return CavitySpec(**d)


def run_request(request: str, runner: Runner, llm: LLMClient | None = None, out_dir: Path = Path("runs"),
                max_attempts: int = MAX_ATTEMPTS, validate: bool = True) -> AgentResult:
    from .report import write_report  # local import avoids a cycle

    max_attempts = max(1, min(max_attempts, MAX_ATTEMPTS))
    run_dir = Path(out_dir) / datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")
    run_dir.mkdir(parents=True, exist_ok=True)
    audit = Audit(run_dir / "audit.jsonl")
    res = AgentResult(status="rejected", message="", request=request, run_dir=str(run_dir),
                      is_mock=runner.is_mock, runner=runner.name)

    spec, source, reason, warns = resolve_spec(request, llm, audit)
    res.spec_source, res.warnings = source, warns
    if spec is None:
        res.message = f"Request rejected: {reason}. No simulation was run."
        return _finish(res, run_dir, write_report)

    current = spec
    for i in range(1, max_attempts + 1):
        if i > 1:
            current = refine(spec if i == 2 else current, i)
        res.spec = current.model_dump()
        att = Attempt(index=i, spec=current.model_dump())
        res.attempts.append(att)
        case = run_dir / f"attempt_{i}"
        t0 = time.time()
        build_case(current, case)
        audit.log("build_case", current.input_dict(), {"dir": str(case)}, time.time() - t0)

        bm = runner.run("blockMesh", case)
        audit.log("blockMesh", {"attempt": i}, {"ok": bm.ok, "rc": bm.returncode}, bm.duration_s)
        if not bm.ok:
            att.failure = f"blockMesh failed (rc={bm.returncode})"
            if bm.returncode == 127:                  # tool missing: refinement cannot help
                res.warnings.append("OpenFOAM executable not found - stopping (environment problem, not a mesh problem)")
                break
            continue

        cm = runner.run("checkMesh", case)
        att.mesh = parse_checkmesh(cm.log)
        audit.log("checkMesh", {"attempt": i}, asdict(att.mesh), cm.duration_s)
        if not att.mesh.passed:
            att.failure = "mesh quality gate failed: " + "; ".join(att.mesh.failures)
            continue

        sv = runner.run("icoFoam", case)
        att.solver_seconds = sv.duration_s
        att.convergence = parse_solver_log(sv.log)
        res.openfoam_build = res.openfoam_build or att.convergence.openfoam_build
        audit.log("icoFoam", {"attempt": i}, asdict(att.convergence), sv.duration_s)
        if not sv.ok or not att.convergence.converged:
            att.failure = "solver gate failed: " + "; ".join(att.convergence.failures or [f"rc={sv.returncode}"])
            if sv.returncode == 124:                  # timeout: a finer mesh would be even slower
                res.warnings.append("solver timed out - stopping (refinement would only be slower)")
                break
            continue

        try:
            att.steady_change = pp.steady_change(case, current.grid_n ** 2, current.lid_velocity)
            if runner.is_mock:
                res.validation_message = "benchmark validation skipped: mock runner produces synthetic data"
            elif validate:
                att.validation, res.validation_message = pp.validate_against_ghia(
                    case, current.grid_n, current.reynolds, current.lid_velocity)
            audit.log("postprocess", {"attempt": i}, {"validation": asdict(att.validation) if att.validation else None,
                                                      "message": res.validation_message, "steady_change": att.steady_change})
        except Exception as e:                        # unreadable/malformed fields are a hard failure
            att.failure = f"postprocess failed: {e}"
            audit.log("postprocess", {"attempt": i}, {"error": repr(e)})
            continue

        if att.validation is not None and not att.validation.passed:
            att.failure = (f"benchmark validation failed: RMS error {att.validation.rms_error:.4f} "
                           f"> {att.validation.threshold}")
            continue
        att.ok = True
        break

    last = res.attempts[-1] if res.attempts else None
    if last and last.ok:
        res.status = "success"
        res.message = f"Completed after {len(res.attempts)} attempt(s)."
        if len(res.attempts) > 1:
            res.warnings.append("Required mesh refinement; final grid differs from the requested grid")
        if last.validation is not None:
            from .postprocess import plot_validation
            res.plot_path = str(plot_validation(last.validation, current.grid_n, current.reynolds,
                                                run_dir / "validation.png"))
    else:
        res.status = "failed"
        res.message = (f"Failed after {len(res.attempts)} attempt(s): "
                       f"{last.failure if last else 'no attempts ran'}")
    return _finish(res, run_dir, write_report)


def _finish(res: AgentResult, run_dir: Path, write_report) -> AgentResult:
    res.report_path = str(write_report(res, run_dir))
    (run_dir / "result.json").write_text(json.dumps(res.to_dict(), indent=2, default=str))
    return res
