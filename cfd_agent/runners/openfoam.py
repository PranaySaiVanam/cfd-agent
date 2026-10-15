"""Real OpenFOAM runner: native install (source its bashrc) or Docker."""
from __future__ import annotations

import os
import shlex
import subprocess
import time
from pathlib import Path

from .base import RunResult

ALLOWED = {"blockMesh", "checkMesh", "icoFoam"}
BASHRC_CANDIDATES = [
    "/usr/share/openfoam/etc/bashrc",                 # Debian/Ubuntu apt package
    "/usr/lib/openfoam/openfoam2406/etc/bashrc",      # ESI packages / opencfd images
    "/usr/lib/openfoam/openfoam2312/etc/bashrc",
    "/opt/openfoam2406/etc/bashrc",
]


def find_bashrc() -> str | None:
    env = os.environ.get("CFD_AGENT_FOAM_BASHRC")
    if env and Path(env).exists():
        return env
    return next((p for p in BASHRC_CANDIDATES if Path(p).exists()), None)


class OpenFOAMRunner:
    """mode='native' uses a local OpenFOAM (WSL/Linux). mode='docker' runs inside an OpenFOAM image
    (UNTESTED in the original build environment - see README)."""

    is_mock = False

    def __init__(self, mode: str = "native", timeout_s: int = 900, bashrc: str | None = None,
                 docker_image: str = "opencfd/openfoam-run:2406",
                 docker_bashrc: str = "/usr/lib/openfoam/openfoam2406/etc/bashrc"):
        if mode not in {"native", "docker"}:
            raise ValueError("mode must be 'native' or 'docker'")
        self.mode, self.timeout_s = mode, timeout_s
        self.bashrc = bashrc or find_bashrc()
        self.docker_image, self.docker_bashrc = docker_image, docker_bashrc
        self.name = f"openfoam-{mode}"

    def available(self) -> bool:
        if self.mode == "native":
            return self.bashrc is not None
        try:
            return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def run(self, command: str, case_dir: Path) -> RunResult:
        if command not in ALLOWED:
            return RunResult(False, 2, f"command '{command}' not allowed", 0.0, command)
        case_dir = Path(case_dir).resolve()
        if self.mode == "native":
            if not self.bashrc:
                return RunResult(False, 127, "OpenFOAM bashrc not found; set CFD_AGENT_FOAM_BASHRC", 0.0, command)
            argv = ["bash", "-c", f"source {shlex.quote(self.bashrc)} >/dev/null 2>&1; {command}"]
            cwd = str(case_dir)
        else:
            inner = f"source {shlex.quote(self.docker_bashrc)} >/dev/null 2>&1; {command}"
            argv = ["docker", "run", "--rm", "-v", f"{case_dir}:/case", "-w", "/case",
                    "--entrypoint", "bash", self.docker_image, "-c", inner]
            cwd = None
        t0 = time.time()
        try:
            p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=self.timeout_s)
            log, rc = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else ""), p.returncode
        except subprocess.TimeoutExpired as e:
            log, rc = f"TIMEOUT after {self.timeout_s}s\n{(e.stdout or b'')[-2000:]!r}", 124
        except OSError as e:
            log, rc = f"failed to launch: {e}", 127
        dur = time.time() - t0
        (case_dir / f"log.{command}").write_text(log)
        return RunResult(rc == 0, rc, log, dur, command)
