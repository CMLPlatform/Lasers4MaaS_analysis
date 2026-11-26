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


KPI_FILE = Path(__file__).parents[1] / "Input_data" / "KPI_calculations.xlsx"


def test_production_costs_of_kpi_file():
    from l4m_lca.costs import PRODUCTION_COSTS, read_production_costs
    costs = read_production_costs(KPI_FILE)
    assert set(costs["cost"]) == set(PRODUCTION_COSTS)
    totals = costs.groupby(["use_case", "technology"])["value"].sum()
    assert totals[("Battery cooling plate", "SoA")] == pytest.approx(75.75, abs=0.05)
    assert totals[("Heat exchanger", "L4M")] == pytest.approx(241.6, abs=0.5)
    assert ("Fusion plant pipe", "SoA") not in totals.index   # no SoA for this use case
    assert len(totals) == 11
    assert list(dict.fromkeys(costs["use_case"])) == ["Heat exchanger", "Fuel tank", "Heterogeneous pipe",
                                                     "Freeze Dryers Shelf", "Battery cooling plate",
                                                     "Fusion plant pipe"]


def test_ghg_cost_bars_joining_stage_of_use_cases_with_both_results():
    from l4m_lca import plots
    from l4m_lca.costs import read_production_costs
    workflow = pd.DataFrame([
        dict(product="Heat exchanger", technology=t, stage=st, step=sp, indicator="climate change: total [kg CO2-Eq]",
             value=v)
        for t, st, sp, v in [("standard laser", "pre", "alkaline_degreasing", 1.0), ("standard laser", "join", "joining", 5.0),
                             ("L4M-solution", "pre", "alkaline_degreasing", 1.0), ("L4M-solution", "join", "joining", 2.0)]])
    fig = plots.ghg_cost_bars(workflow, read_production_costs(KPI_FILE), "climate change", {"pre": "Pre", "join": "Join"},
                              ["Heat exchanger", "Fusion plant pipe"])
    totals = [t for t in fig.data if t.type == "scatter" and t.mode == "text"]
    assert len(totals) == 2                                    # Fusion plant pipe has no LCA results: left out
    assert list(totals[0].y) == pytest.approx([5.0, 2.0])      # joining stage only: SoA, L4M-solution
    assert list(totals[1].text) == ["343", "242"]               # costs of the Heat exchanger


# --- Costs of a product system (L4M_R&D.ipynb)

def _rd_system():
    from fakes import Node, process
    elec_gb = Node("ei", "e", "market for electricity, medium voltage", location="GB")
    argon = Node("ei", "ar", "Argon, liquid, at plant", location="RER")
    resin = Node("ei", "r", "market for phenolic resin", location="RER")
    co2 = Node("bio", "co2", "Carbon dioxide")
    weld = process("fg", "weld", "Laser welding", production=2.0).add(elec_gb, 4.0).add(argon, 1.0).add(co2, 5.0, "biosphere")
    mount = process("fg", "mount", "Hot-mounting").add(resin, 0.5)
    top = process("fg", "top", "System").add(weld, 3.0).add(mount, 2.0)
    return top


def test_price_of():
    from fakes import Node
    from l4m_lca.costs import price_of
    prices = {"argon": 5.0, "tap water": 0.004}
    assert price_of(Node("ei", "a", "market for argon, liquid"), prices, {}) == 5.0
    assert price_of(Node("ei", "b", "Argon, liquid, at plant"), prices, {}) == 5.0
    assert price_of(Node("ei", "c", "market for electricity, medium voltage", location="GB"), prices, {"GB": 0.3}) == 0.3
    assert price_of(Node("ei", "d", "market for acetone, liquid"), prices, {}) is None


def test_system_costs():
    from l4m_lca.costs import LABOUR_HOURS_COLUMN, system_costs
    from l4m_lca.impacts import foreground_executions, foreground_flows
    top = _rd_system()
    flows = foreground_flows(top, {"fg"})
    executions = foreground_executions(top, {"fg"})
    assert executions == {("fg", "top"): 1.0, ("fg", "weld"): 3.0, ("fg", "mount"): 2.0}
    names = {("fg", "top"): "System", ("fg", "weld"): "Laser welding", ("fg", "mount"): "Hot-mounting"}
    costs, unpriced, untimed = system_costs(flows, executions, {"argon": 5.0}, {"GB": 0.5},
                                            {"Laser welding": 0.25}, wage=40.0, name_of=names.get)
    # 3 weld units = 1.5 executions: 6 kWh x 0.5 + 1.5 kg argon x 5; resin has no price
    assert costs[CONSUMABLE_COLUMN] == pytest.approx(3.0 + 7.5)
    assert costs[LABOUR_HOURS_COLUMN] == pytest.approx(0.75)
    assert costs[PERSONNEL_COLUMN] == pytest.approx(30.0)
    assert costs[OPEX_COLUMN] == pytest.approx(40.5)
    assert unpriced == {"market for phenolic resin [RER]"}
    assert untimed == {"Hot-mounting"}   # "System" uses no background input directly
