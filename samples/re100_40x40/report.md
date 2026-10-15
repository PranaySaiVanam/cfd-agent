# CFD-Agent report

**Request:** Simulate lid-driven cavity flow at Reynolds number 100 with a 40x40 grid

**Status:** `SUCCESS` - Completed after 1 attempt(s).

**Parameter source:** rules  |  **Runner:** openfoam-native  |  **OpenFOAM:** 1912 patch 200626

## Final case parameters

| Parameter | Value |
|---|---|
| Reynolds number | 100 |
| Grid | 40 x 40 (1 cell deep, 2D) |
| Lid velocity | 1 m/s |
| Cavity size | 0.1 m |
| Kinematic viscosity nu | 0.001 m^2/s |
| Time step | 0.0005 s (target Courant 0.2) |
| End time | 3 s (6000 steps) |

## Attempts

| # | Grid | Mesh gate | Solver gate | Max Co | Final Ux res | Benchmark RMS | Result |
|---|---|---|---|---|---|---|---|
| 1 | 40x40 | pass | pass | 0.18 | 1.8e-10 | 0.0011 | OK |

## Mesh quality (final attempt)

| Metric | Value | Limit |
|---|---|---|
| Cells | 1600 | |
| Max non-orthogonality | 0 deg | 65 |
| Max skewness | 3.2e-14 | 4 |
| Max aspect ratio | 1 | 50 |

## Convergence (final attempt)

- Final initial residuals: Ux 1.76e-10, Uy 2.18e-10, p 2.72e-08 (gate: Ux,Uy <= 1e-6)
- Relative change in U between last two write times: 2.82e-07

## Benchmark validation

- Reference: Ghia et al. (1982) u-centerline
- u-centerline RMS error: **0.0011** (max 0.0026) over 15 points; gate <= 0.05
- Result: PASS

![validation](validation.png)

---
Parameters were validated by code; case files come from templates; every tool call is in `audit.jsonl`.
