"""Reference data: u-velocity along the vertical centerline (x = 0.5) of the lid-driven cavity.
Source: Ghia, Ghia & Shin (1982), J. Comput. Phys. 48, 387-411, Table I.
Values were transcribed by hand - verify them against the paper before quoting results publicly.
Columns: y/L, u/U_lid.  (y=0 -> 0, y=1 -> 1 are the wall boundary conditions.)"""

GHIA_U_CENTERLINE = {
    100: [
        (1.0000, 1.00000), (0.9766, 0.84123), (0.9688, 0.78871), (0.9609, 0.73722),
        (0.9531, 0.68717), (0.8516, 0.23151), (0.7344, 0.00332), (0.6172, -0.13641),
        (0.5000, -0.20581), (0.4531, -0.21090), (0.2813, -0.15662), (0.1719, -0.10150),
        (0.1016, -0.06434), (0.0703, -0.04775), (0.0625, -0.04192), (0.0547, -0.03717),
        (0.0000, 0.00000),
    ],
    400: [
        (1.0000, 1.00000), (0.9766, 0.75837), (0.9688, 0.68439), (0.9609, 0.61756),
        (0.9531, 0.55892), (0.8516, 0.29093), (0.7344, 0.16256), (0.6172, 0.02135),
        (0.5000, -0.11477), (0.4531, -0.17119), (0.2813, -0.32726), (0.1719, -0.24299),
        (0.1016, -0.14612), (0.0703, -0.10338), (0.0625, -0.09266), (0.0547, -0.08186),
        (0.0000, 0.00000),
    ],
}


def reference_for(reynolds: float) -> list[tuple[float, float]] | None:
    """Return Ghia data only if Re matches a tabulated value exactly (no interpolation across Re)."""
    r = round(reynolds)
    return GHIA_U_CENTERLINE.get(r) if abs(reynolds - r) < 1e-9 else None
