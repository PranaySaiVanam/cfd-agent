"""Runner interface. Agent code only ever talks to this - real and mock runners are swappable."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RunResult:
    ok: bool
    returncode: int
    log: str
    duration_s: float
    command: str


class Runner(Protocol):
    name: str
    is_mock: bool

    def run(self, command: str, case_dir: Path) -> RunResult:
        """Run one OpenFOAM utility/solver (blockMesh | checkMesh | icoFoam) inside case_dir."""
        ...
