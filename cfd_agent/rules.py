"""Rule-based request parser: the deterministic fallback when no LLM is available or its output is invalid."""
from __future__ import annotations

import re

from .schemas import LLMExtraction

_NUM = r"([0-9]*\.?[0-9]+(?:[eE][+-]?\d+)?)"


def parse_request(text: str) -> LLMExtraction:
    t = text.strip()
    low = t.lower()
    if not re.search(r"cavity|lid[\s-]?driven", low):
        return LLMExtraction(supported=False,
                             reason="only lid-driven cavity flow is supported by this agent")
    out: dict = {"supported": True}

    m = re.search(r"\bre(?:ynolds)?(?:\s+number)?\s*(?:=|:|of|is)?\s*" + _NUM, low)
    if m:
        out["reynolds"] = float(m.group(1))

    mx = re.search(r"(\d+)\s*(?:x|×|by)\s*(\d+)", low)
    if mx:
        a, b = int(mx.group(1)), int(mx.group(2))
        if a != b:
            return LLMExtraction(supported=False, reason=f"only square grids are supported (got {a}x{b})")
        out["grid_n"] = a
    else:
        mg = (re.search(r"(?:grid|mesh|resolution)(?:\s*size)?\s*(?:of|=|:)?\s*(\d+)\b", low)
              or re.search(r"(\d+)\s*cells(?:\s*per\s*side)?", low))
        if mg:
            out["grid_n"] = int(mg.group(1))

    mv = re.search(_NUM + r"\s*m/s", low)
    if mv:
        out["lid_velocity"] = float(mv.group(1))
    return LLMExtraction(**out)
