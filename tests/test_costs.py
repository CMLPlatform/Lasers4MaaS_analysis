"""Operating costs: labour hours, personnel costs and nominal OPEX."""

import math
from pathlib import Path

import pandas as pd
import pytest

from l4m_lca.costs import (CONSUMABLE_COLUMN, LABOUR_FIELD, OPEX_COLUMN, PERSONNEL_COLUMN, cost_values,
                           labour_hours, labour_range, personnel_cost, read_labour_costs)
from l4m_lca.joining import joining_amounts, joining_processes
from l4m_lca.workflow import cumulative_regional

COUNTRY_DATA = Path(__file__).parents[1] / "Input_data" / "country_data.xlsx"

PARAMS = {
    "power_kW_joining": {"min": 1.0, "max": 1.0},
    "power_kW_station": {"min": 0.0, "max": 0.0},
    "joining_speed_m_per_s": {"min": 0.01, "max": 0.02},
    "joint_length_m": 36.0,                       # 1800 s to 3600 s
    "gas_flow_kg_per_s": {"min": 0.0, "max": 0.0},
}


def test_labour_hours_are_joining_time():
    assert joining_amounts(PARAMS)["labour_h"] == pytest.approx((0.5, 1.0))
    assert joining_amounts({**PARAMS, "operators": 2})["labour_h"] == pytest.approx((1.0, 2.0))


def test_joining_process_stores_labour_range():
    data = joining_processes("db", {"Tank": PARAMS}, "TIG", ("ei", "elec"), ("ei", "gas"))
    assert data[("db", "Tank")][LABOUR_FIELD] == pytest.approx({"minimum": 0.5, "amount": 0.75, "maximum": 1.0})


def test_labour_range_rejects_reversed_range():
    with pytest.raises(ValueError):
        labour_range(2.0, 1.0)


def test_personnel_cost():
    process = {LABOUR_FIELD: labour_range(0.5, 1.0)}
    assert personnel_cost(process, "amount", 40.0) == pytest.approx(30.0)
    assert personnel_cost(process, "maximum", 40.0) == pytest.approx(40.0)
    assert math.isnan(personnel_cost(process, "amount", None))   # labour hours, no wage: no data


def test_no_labour_hours_costs_zero():
    assert labour_hours({}, "amount") == 0.0
    assert personnel_cost({}, "amount", None) == 0.0
    assert personnel_cost({}, "amount", math.nan) == 0.0


def test_opex_is_consumable_plus_personnel():
    values = cost_values(2.0, 3.0)
    assert values == {CONSUMABLE_COLUMN: 2.0, PERSONNEL_COLUMN: 3.0, OPEX_COLUMN: 5.0}


@pytest.mark.skipif(not COUNTRY_DATA.exists(), reason="country_data.xlsx not available")
def test_read_labour_costs():
    wages = read_labour_costs(COUNTRY_DATA)
    assert wages["RER"] == 35.0      # EU27 average
    assert wages["GR"] == 18.2       # Eurostat code EL
    assert "NL" not in wages         # confidential value
    assert "BE" not in wages         # no value


def test_cumulative_regional_keeps_missing_labour_cost():
    workflows = {"Tank": {"material": "steel", "pre_joining": {"degreasing": True}, "post_joining": {}}}

    def reg(process, key, values):
        return [{"process": process, "key": key, "scenario": "amount", "country": c,
                 "indicator": PERSONNEL_COLUMN, "impact": v} for c, v in values.items()]

    joining = pd.DataFrame(reg("Tank joined with TIG", "Tank", {"RER": 10.0, "NL": math.nan}))
    prepost = pd.DataFrame(reg("degreasing for steel", "degreasing_steel", {"RER": 0.0, "NL": 0.0}))
    out = cumulative_regional(workflows, joining, prepost).set_index("country")["impact"]
    assert out["RER"] == 10.0
    assert math.isnan(out["NL"])


def test_gb_values():
    from l4m_lca.constants import EU27, EU27_GB, GB_ELEC_PRICE_2025S1, GB_LABOUR_COST_2025
    assert EU27_GB == {**EU27, "GB": "GBR"}
    assert GB_ELEC_PRICE_2025S1["GB"] == pytest.approx(0.26542 / 0.84232, abs=1e-4)   # DESNZ, ECB H1 2025
    assert GB_LABOUR_COST_2025["GB"] == pytest.approx(21.8 * 116.1182 / 79.4559 / 0.85661, abs=0.05)


def test_prepost_labour():
    from l4m_lca.prepost import prepost_labour
    assert prepost_labour({"time_min": {"min": 6, "max": 30}}) == pytest.approx(
        {"minimum": 0.1, "amount": 0.3, "maximum": 0.5})
    assert prepost_labour({"time_min": {"min": 6, "max": 30}}, operator_share=0.25)["maximum"] == pytest.approx(0.125)
    assert prepost_labour({"machining_time_min": {"min": 1, "max": 5}})["maximum"] == pytest.approx(5 / 60)
    assert prepost_labour({"electricity_kwh": 1.0}) is None
    with pytest.raises(ValueError):
        prepost_labour({"time_min": 5}, operator_share=1.5)
