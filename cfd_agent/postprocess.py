"""Read OpenFOAM ASCII fields with numpy only (no ParaView needed) and validate against Ghia."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .benchmarks import reference_for


@dataclass
class Validation:
    reference: str
    rms_error: float
    max_error: float
    n_points: int
    passed: bool
    threshold: float
    y: list[float]
    u_sim: list[float]
    u_ref: list[float]


def time_dirs(case_dir: Path) -> list[Path]:
    out = []
    for d in Path(case_dir).iterdir():
        if d.is_dir():
            try:
                out.append((float(d.name), d))
            except ValueError:
                pass
    return [d for _, d in sorted(out)]


def read_vector_field(path: Path, n_cells: int) -> np.ndarray:
    """Parse `internalField nonuniform List<vector> N ( (x y z) ... )` or `uniform (x y z)`."""
    text = Path(path).read_text()
    m = re.search(r"internalField\s+uniform\s+\(([^)]*)\)", text)
    if m:
        return np.tile(np.array(m.group(1).split(), float), (n_cells, 1))
    m = re.search(r"internalField\s+nonuniform\s+List<vector>\s*(\d+)\s*\(", text)
    if not m:
        raise ValueError(f"cannot parse internalField in {path}")
    n = int(m.group(1))
    if n != n_cells:
        raise ValueError(f"{path}: expected {n_cells} cells, file has {n}")
    body = text[m.end():]
    vals = re.findall(r"\(\s*([^()\s]+)\s+([^()\s]+)\s+([^()\s]+)\s*\)", body)[:n]
    arr = np.array(vals, float)
    if arr.shape != (n, 3) or not np.isfinite(arr).all():
        raise ValueError(f"{path}: malformed or non-finite vector data")
    return arr


def centerline_u(U: np.ndarray, n: int, lid_velocity: float) -> tuple[np.ndarray, np.ndarray]:
    """u/U_lid at x = L/2 for a uniform n x n grid (cells ordered x-fastest). Includes wall values."""
    ux = U[:, 0].reshape(n, n)  # [j (y), i (x)]
    col = 0.5 * (ux[:, n // 2 - 1] + ux[:, n // 2]) if n % 2 == 0 else ux[:, n // 2]
    y = (np.arange(n) + 0.5) / n
    y = np.concatenate([[0.0], y, [1.0]])
    u = np.concatenate([[0.0], col / lid_velocity, [1.0]])
    return y, u


def steady_change(case_dir: Path, n_cells: int, lid_velocity: float) -> float | None:
    """Relative change of U between the last two written times (steady-state evidence)."""
    ts = time_dirs(case_dir)
    ts = [t for t in ts if (t / "U").exists() and t.name != "0"]
    if len(ts) < 2:
        return None
    a, b = read_vector_field(ts[-2] / "U", n_cells), read_vector_field(ts[-1] / "U", n_cells)
    return float(np.linalg.norm(b - a) / (np.linalg.norm(b) + 1e-30))


def validate_against_ghia(case_dir: Path, n: int, reynolds: float, lid_velocity: float,
                          threshold: float = 0.05) -> tuple[Validation | None, str]:
    """Returns (validation, message). validation is None when no reference exists for this Re."""
    ref = reference_for(reynolds)
    if ref is None:
        return None, f"no Ghia reference data for Re={reynolds:g}; benchmark comparison skipped"
    ts = [t for t in time_dirs(case_dir) if (t / "U").exists() and t.name != "0"]
    if not ts:
        return None, "no solution time directories found"
    U = read_vector_field(ts[-1] / "U", n * n)
    y, u = centerline_u(U, n, lid_velocity)
    ry = np.array([p[0] for p in ref])
    ru = np.array([p[1] for p in ref])
    us = np.interp(ry, y, u)
    interior = (ry > 0) & (ry < 1)  # wall points match by construction; exclude from the error
    err = us[interior] - ru[interior]
    rms, mx = float(np.sqrt(np.mean(err ** 2))), float(np.max(np.abs(err)))
    v = Validation("Ghia et al. (1982) u-centerline", rms, mx, int(interior.sum()), rms <= threshold,
                   threshold, ry.tolist(), us.tolist(), ru.tolist())
    return v, "ok"


def plot_validation(v: Validation, n: int, reynolds: float, out_png: Path) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(4.6, 5.2), dpi=130)
    ax.plot(v.u_ref, v.y, "ko", label="Ghia et al. (1982)")
    ys = np.linspace(0, 1, 200)
    ax.plot(v.u_sim, v.y, "r-", lw=1.4, label=f"OpenFOAM icoFoam ({n}x{n})")
    ax.set_xlabel("u / U_lid"); ax.set_ylabel("y / L")
    ax.set_title(f"Lid-driven cavity, Re={reynolds:g}\nRMS error = {v.rms_error:.4f}")
    ax.grid(alpha=.3); ax.legend(loc="lower right")
    fig.tight_layout(); fig.savefig(out_png); plt.close(fig)
    return out_png
