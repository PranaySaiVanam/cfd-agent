"""Deterministic case generation from a validated spec (Jinja2 templates, strict undefined)."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .schemas import CavitySpec

_ENV = Environment(
    loader=FileSystemLoader(str(Path(__file__).parent / "templates")),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

# template -> destination inside the case directory
FILES = {
    "blockMeshDict.j2": "system/blockMeshDict",
    "controlDict.j2": "system/controlDict",
    "fvSchemes.j2": "system/fvSchemes",
    "fvSolution.j2": "system/fvSolution",
    "transportProperties.j2": "constant/transportProperties",
    "U.j2": "0/U",
    "p.j2": "0/p",
}


def build_case(spec: CavitySpec, case_dir: Path) -> list[Path]:
    """Write a complete icoFoam cavity case. Returns the files written."""
    case_dir = Path(case_dir)
    written: list[Path] = []
    for tmpl, dest in FILES.items():
        out = case_dir / dest
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_ENV.get_template(tmpl).render(s=spec))
        written.append(out)
    sp = case_dir / "spec.json"  # reproducibility: the exact validated spec used
    sp.write_text(json.dumps(spec.model_dump(), indent=2))
    written.append(sp)
    return written
