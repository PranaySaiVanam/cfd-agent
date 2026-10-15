"""Markdown report. Mock runs are loudly labelled; failures and warnings are never hidden."""
from __future__ import annotations

from pathlib import Path


def _fmt(x, spec=".3g"):
    return "n/a" if x is None else format(x, spec)


def write_report(res, run_dir: Path) -> Path:
    L: list[str] = ["# CFD-Agent report", ""]
    if res.is_mock:
        L += ["> **MOCK RUN - synthetic output. No physics was solved; these numbers are NOT valid results.**", ""]
    L += [f"**Request:** {res.request}", "",
          f"**Status:** `{res.status.upper()}` - {res.message}", "",
          f"**Parameter source:** {res.spec_source}  |  **Runner:** {res.runner}"
          + (f"  |  **OpenFOAM:** {res.openfoam_build}" if res.openfoam_build else ""), ""]
    if res.warnings:
        L += ["## Warnings"] + [f"- {w}" for w in res.warnings] + [""]
    if res.spec:
        s = res.spec
        L += ["## Final case parameters", "",
              "| Parameter | Value |", "|---|---|",
              f"| Reynolds number | {s['reynolds']:g} |",
              f"| Grid | {s['grid_n']} x {s['grid_n']} (1 cell deep, 2D) |",
              f"| Lid velocity | {s['lid_velocity']:g} m/s |",
              f"| Cavity size | {s['cavity_size']:g} m |",
              f"| Kinematic viscosity nu | {s['nu']:.6g} m^2/s |",
              f"| Time step | {s['delta_t']:g} s (target Courant {s['courant']:g}) |",
              f"| End time | {s['end_time']:g} s ({s['n_steps']} steps) |", ""]
    if res.attempts:
        L += ["## Attempts", "", "| # | Grid | Mesh gate | Solver gate | Max Co | Final Ux res | Benchmark RMS | Result |",
              "|---|---|---|---|---|---|---|---|"]
        for a in res.attempts:
            m, c, v = a.mesh, a.convergence, a.validation
            L.append(f"| {a.index} | {a.spec['grid_n']}x{a.spec['grid_n']} | "
                     f"{'pass' if m and m.passed else ('FAIL' if m else '-')} | "
                     f"{'pass' if c and c.converged else ('FAIL' if c else '-')} | "
                     f"{_fmt(c.max_courant if c else None, '.2f')} | {_fmt(c.final_ux_residual if c else None, '.1e')} | "
                     f"{_fmt(v.rms_error if v else None, '.4f')} | "
                     f"{'OK' if a.ok else 'FAILED: ' + (a.failure or '')} |")
        L.append("")
        last = res.attempts[-1]
        if last.mesh:
            m = last.mesh
            L += ["## Mesh quality (final attempt)", "", "| Metric | Value | Limit |", "|---|---|---|",
                  f"| Cells | {m.cells} | |", f"| Max non-orthogonality | {_fmt(m.max_non_orthogonality)} deg | 65 |",
                  f"| Max skewness | {_fmt(m.max_skewness)} | 4 |", f"| Max aspect ratio | {_fmt(m.max_aspect_ratio)} | 50 |", ""]
        if last.convergence:
            L += ["## Convergence (final attempt)", "",
                  f"- Final initial residuals: Ux {_fmt(last.convergence.final_ux_residual, '.2e')}, "
                  f"Uy {_fmt(last.convergence.final_uy_residual, '.2e')}, p {_fmt(last.convergence.final_p_residual, '.2e')} "
                  f"(gate: Ux,Uy <= 1e-6)",
                  f"- Relative change in U between last two write times: {_fmt(last.steady_change, '.2e')}", ""]
        if last.validation:
            v = last.validation
            L += ["## Benchmark validation", "",
                  f"- Reference: {v.reference}", f"- u-centerline RMS error: **{v.rms_error:.4f}** "
                  f"(max {v.max_error:.4f}) over {v.n_points} points; gate <= {v.threshold}",
                  "- Result: " + ("PASS" if v.passed else "FAIL"), ""]
            if res.plot_path:
                L += [f"![validation]({Path(res.plot_path).name})", ""]
    if res.validation_message and res.validation_message != "ok":
        L += [f"_Validation note: {res.validation_message}_", ""]
    L += ["---", "Parameters were validated by code; case files come from templates; every tool call is in `audit.jsonl`."]
    out = Path(run_dir) / "report.md"
    out.write_text("\n".join(L) + "\n")
    return out
