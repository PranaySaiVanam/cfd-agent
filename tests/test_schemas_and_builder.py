import json
import pytest
from pydantic import ValidationError

from cfd_agent.case_builder import FILES, build_case
from cfd_agent.schemas import CavitySpec, LLMExtraction


def test_defaults_and_derived_values():
    s = CavitySpec()
    assert s.reynolds == 100 and s.grid_n == 40
    assert s.nu == pytest.approx(0.001)           # nu = U*L/Re = 1*0.1/100
    assert s.delta_t == pytest.approx(0.0005)     # 0.2 * dx / U, dx = 0.0025
    assert s.end_time == pytest.approx(s.n_steps * s.delta_t)
    assert s.write_interval >= 1


@pytest.mark.parametrize("bad", [
    {"reynolds": 5}, {"reynolds": 1e6}, {"grid_n": 5}, {"grid_n": 500},
    {"lid_velocity": 0}, {"courant": 0.9}, {"unknown_field": 1},
])
def test_out_of_range_or_unknown_rejected(bad):
    with pytest.raises(ValidationError):
        CavitySpec(**bad)


def test_llm_extraction_fills_only_stated_values():
    s = LLMExtraction(supported=True, reynolds=400).to_spec()
    assert s.reynolds == 400 and s.grid_n == 40   # default grid, not invented by the LLM


def test_case_files_complete_and_rendered(tmp_path):
    spec = CavitySpec(reynolds=200, grid_n=32, lid_velocity=2)
    written = build_case(spec, tmp_path)
    for dest in FILES.values():
        f = tmp_path / dest
        assert f.exists() and f.stat().st_size > 50, dest
        assert "{{" not in f.read_text() and "{%" not in f.read_text(), dest
    assert "(32 32 1)" in (tmp_path / "system/blockMeshDict").read_text()
    assert "0.001" in (tmp_path / "constant/transportProperties").read_text()   # nu = 2*0.1/200
    assert "uniform (2.0 0 0)" in (tmp_path / "0/U").read_text()
    assert json.loads((tmp_path / "spec.json").read_text())["reynolds"] == 200
    assert len(written) == len(FILES) + 1
