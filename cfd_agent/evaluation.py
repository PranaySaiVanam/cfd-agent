"""Evaluation harness: runs benchmarks/requests.json and reports success / safe-failure rates."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .agent import run_request

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "benchmarks" / "requests.json"


def run_eval(runner, llm, out_dir: Path, requests_file: Path = DEFAULT_FILE, echo=print) -> dict:
    cases = json.loads(Path(requests_file).read_text())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, t_start = [], time.time()
    for c in cases:
        t0 = time.time()
        r = run_request(c["request"], runner, llm, out_dir / c["id"])
        dur = time.time() - t0
        problems: list[str] = []
        if c["expect"] == "rejected":
            if r.status != "rejected":
                problems.append(f"expected rejection, got {r.status}")
            if r.attempts:
                problems.append("a simulation was run for a request that should be rejected")
            if not r.message:
                problems.append("no message")
        else:
            if r.status != "success":
                problems.append(f"expected success, got {r.status}: {r.message}")
            else:
                a = r.final_attempt
                req = r.attempts[0].spec
                for k, v in c.get("expect_params", {}).items():
                    if abs(req[k] - v) > 1e-9:
                        problems.append(f"parsed {k}={req[k]}, expected {v}")
                if not runner.is_mock and a.validation is not None and not a.validation.passed:
                    problems.append("benchmark validation failed")
        rows.append({
            "id": c["id"], "request": c["request"], "expect": c["expect"], "status": r.status,
            "attempts": len(r.attempts), "grid": (r.spec or {}).get("grid_n"),
            "reynolds": (r.spec or {}).get("reynolds"),
            "rms": (r.final_attempt.validation.rms_error if r.final_attempt and r.final_attempt.validation else None),
            "runtime_s": round(dur, 1), "passed": not problems, "problems": problems,
        })
        echo(f"{'PASS' if not problems else 'FAIL'}  {c['id']:<22} {r.status:<9} attempts={len(r.attempts)} {dur:5.1f}s  {'; '.join(problems)}")

    valid = [x for x in rows if x["expect"] == "success"]
    invalid = [x for x in rows if x["expect"] == "rejected"]
    refs = [x["rms"] for x in valid if x["rms"] is not None]
    summary = {
        "runner": runner.name, "is_mock": runner.is_mock, "total": len(rows),
        "valid_requests": len(valid), "valid_passed": sum(x["passed"] for x in valid),
        "invalid_requests": len(invalid), "invalid_safely_rejected": sum(x["passed"] for x in invalid),
        "retries_used": sum(max(0, x["attempts"] - 1) for x in valid),
        "mean_runtime_s": round(sum(x["runtime_s"] for x in valid) / max(1, len(valid)), 1),
        "benchmark_cases": len(refs), "mean_benchmark_rms": round(sum(refs) / len(refs), 4) if refs else None,
        "max_benchmark_rms": round(max(refs), 4) if refs else None,
        "wall_time_s": round(time.time() - t_start, 1),
    }
    summary["all_passed"] = all(x["passed"] for x in rows)
    (out_dir / "eval_results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    md = ["# Evaluation results", ""]
    if runner.is_mock:
        md += ["> **MOCK RUNNER - synthetic output; this only exercises the code paths, not the physics.**", ""]
    md += ["| Metric | Value |", "|---|---|",
           f"| Valid requests completed correctly | {summary['valid_passed']} / {summary['valid_requests']} |",
           f"| Invalid requests safely rejected (no simulation run) | {summary['invalid_safely_rejected']} / {summary['invalid_requests']} |",
           f"| Retries used (valid requests) | {summary['retries_used']} |",
           f"| Mean runtime per valid request | {summary['mean_runtime_s']} s |",
           f"| Cases with Ghia benchmark | {summary['benchmark_cases']} |",
           f"| Mean / max u-centerline RMS error | {summary['mean_benchmark_rms']} / {summary['max_benchmark_rms']} |", "",
           "| id | request | status | attempts | grid | Re | RMS | time (s) | pass |", "|---|---|---|---|---|---|---|---|---|"]
    for x in rows:
        md.append(f"| {x['id']} | {x['request']} | {x['status']} | {x['attempts']} | {x['grid']} | {x['reynolds']} | "
                  f"{'' if x['rms'] is None else format(x['rms'], '.4f')} | {x['runtime_s']} | {'yes' if x['passed'] else 'NO'} |")
    (out_dir / "eval_results.md").write_text("\n".join(md) + "\n")
    echo(json.dumps(summary, indent=2))
    return summary
