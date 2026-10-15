# Evaluation results

| Metric | Value |
|---|---|
| Valid requests completed correctly | 16 / 16 |
| Invalid requests safely rejected (no simulation run) | 4 / 4 |
| Retries used (valid requests) | 0 |
| Mean runtime per valid request | 12.5 s |
| Cases with Ghia benchmark | 9 |
| Mean / max u-centerline RMS error | 0.0043 / 0.0118 |

| id | request | status | attempts | grid | Re | RMS | time (s) | pass |
|---|---|---|---|---|---|---|---|---|
| v01 | Simulate lid-driven cavity flow at Reynolds number 100 with a 40x40 grid | success | 1 | 40 | 100.0 | 0.0011 | 9.6 | yes |
| v02 | cavity flow Re=100, grid 32 | success | 1 | 32 | 100.0 | 0.0017 | 5.1 | yes |
| v03 | Run a lid driven cavity at Re 50 with 32 cells per side | success | 1 | 32 | 50.0 |  | 4.3 | yes |
| v04 | lid-driven cavity, Reynolds number 10, 24x24 mesh | success | 1 | 24 | 10.0 |  | 2.2 | yes |
| v05 | Please simulate the classic lid driven cavity problem at Re = 200 on a 40 by 40 grid | success | 1 | 40 | 200.0 |  | 13.2 | yes |
| v06 | cavity flow Re 100 | success | 1 | 40 | 100.0 | 0.0011 | 8.6 | yes |
| v07 | simulate cavity flow | success | 1 | 40 | 100.0 | 0.0011 | 9.0 | yes |
| v08 | lid-driven cavity at Reynolds number 400 using a 48x48 grid | success | 1 | 48 | 400.0 | 0.0077 | 40.8 | yes |
| v09 | Lid-driven cavity, Re=100, lid speed 2 m/s, grid 40 | success | 1 | 40 | 100.0 | 0.0011 | 9.5 | yes |
| v10 | Simulate a lid driven cavity at Re 20 with grid size 20 | success | 1 | 20 | 20.0 |  | 1.6 | yes |
| v11 | cavity Re 150, 36x36 | success | 1 | 36 | 150.0 |  | 7.6 | yes |
| v12 | Reynolds number 75 lid-driven cavity flow, 30 cells per side | success | 1 | 30 | 75.0 |  | 4.0 | yes |
| v13 | I need a lid-driven cavity simulation at a Reynolds number of 300 on a 40x40 mesh | success | 1 | 40 | 300.0 |  | 18.1 | yes |
| v14 | Cavity flow, Re 100, 64x64 grid | success | 1 | 64 | 100.0 | 0.0017 | 41.7 | yes |
| v15 | lid driven cavity flow with Reynolds number 400, grid 40 | success | 1 | 40 | 400.0 | 0.0113 | 22.8 | yes |
| v16 | Please run a quick lid-driven cavity at Re 100 with a coarse 16x16 grid | success | 1 | 16 | 100.0 | 0.0118 | 1.3 | yes |
| x01 | Simulate turbulent flow over an airfoil at Mach 0.8 | rejected | 0 | None | None |  | 0.0 | yes |
| x02 | lid-driven cavity at Reynolds number 1000000 | rejected | 0 | None | None |  | 0.0 | yes |
| x03 | lid-driven cavity at Re 100 with a 5x5 grid | rejected | 0 | None | None |  | 0.0 | yes |
| x04 | lid-driven cavity at Re 100 on a 40x20 grid | rejected | 0 | None | None |  | 0.0 | yes |
