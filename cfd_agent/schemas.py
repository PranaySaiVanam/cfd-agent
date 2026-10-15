"""Validated parameter schemas. The LLM may only ever produce these - never solver files."""
from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class CavitySpec(BaseModel):
    """Fully specified, validated lid-driven cavity case (2D, laminar, incompressible, icoFoam)."""

    model_config = ConfigDict(extra="forbid")

    reynolds: float = Field(100.0, ge=10, le=1000, description="Re = U*L/nu (laminar range)")
    grid_n: int = Field(40, ge=10, le=128, description="cells per side (uniform N x N grid)")
    lid_velocity: float = Field(1.0, ge=0.1, le=10.0, description="lid speed U [m/s]")
    cavity_size: float = Field(0.1, gt=0, le=10, description="cavity side length L [m]")
    courant: float = Field(0.2, ge=0.02, le=0.5, description="target Courant number")
    flow_throughs: Optional[float] = Field(
        None, ge=1, le=500, description="simulated time in units of L/U; auto if omitted"
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def nu(self) -> float:
        return self.lid_velocity * self.cavity_size / self.reynolds

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dx(self) -> float:
        return self.cavity_size / self.grid_n

    @computed_field  # type: ignore[prop-decorator]
    @property
    def delta_t(self) -> float:
        return float(f"{self.courant * self.dx / self.lid_velocity:.4g}")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def n_steps(self) -> int:
        ft = self.flow_throughs if self.flow_throughs is not None else max(30.0, self.reynolds / 5.0)
        return int(math.ceil(ft * self.cavity_size / self.lid_velocity / self.delta_t))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def end_time(self) -> float:
        return float(f"{self.n_steps * self.delta_t:.8g}")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def write_interval(self) -> int:
        return max(1, self.n_steps // 10)

    def input_dict(self) -> dict:
        """Only the user-settable fields (what gets re-validated / refined)."""
        return self.model_dump(include={"reynolds", "grid_n", "lid_velocity", "cavity_size", "courant", "flow_throughs"})


class LLMExtraction(BaseModel):
    """What the LLM is allowed to return from a natural-language request."""

    model_config = ConfigDict(extra="ignore")

    supported: bool = Field(..., description="true only for a lid-driven cavity flow request")
    reason: Optional[str] = Field(None, description="why unsupported, if supported is false")
    reynolds: Optional[float] = None
    grid_n: Optional[int] = None
    lid_velocity: Optional[float] = None
    flow_throughs: Optional[float] = None

    def to_spec(self) -> CavitySpec:
        """Fill only what the user stated; everything else uses schema defaults. Out-of-range -> ValidationError."""
        data = {k: v for k, v in self.model_dump(exclude={"supported", "reason"}).items() if v is not None}
        return CavitySpec(**data)
