"""Workflow assembly with small synthetic result tables."""

import pandas as pd
import pytest

from l4m_lca.rd import process_label
from l4m_lca.workflow import cumulative_regional, mean_part_weight, workflow_table

GWP = "climate change [kg CO2-Eq]"

WORKFLOWS = {
    "Tank": {
        "material": "steel",
        "pre_joining": {"degreasing": True, "machining": False},
        "post_joining": {"pickling": True, "coating": True},   # no data for coating
        "process_parameters": {"prototype": {"part_weight_kg": {"min": 1.0, "max": 3.0}}},
    },
}


def rows(process, key, values):
    return [{"Database": "db", "Process": process, "Key": key, "Scenario": s, GWP: v} for s, v in values.items()]


@pytest.fixture
def tables():
    joining = pd.DataFrame(rows("Tank joined with TIG", "Tank", {"minimum": 1, "amount": 2, "maximum": 3})
                           + rows("Tank joined with DBS", "Tank", {"minimum": 0.5, "amount": 1, "maximum": 1.5}))
    prepost = pd.DataFrame(rows("degreasing for steel", "degreasing_steel", {"amount": 0.1, "maximum": 0.2})
                           + rows("degreasing for aluminium", "degreasing_aluminium", {"amount": 9.0})
                           + rows("machining for steel", "machining_steel", {"amount": 5.0})
                           + rows("pickling for steel", "pickling_steel", {"amount": 0.3}))
    material = pd.DataFrame([{"Key": "steel", "Scenario": "amount", "climate change [kg CO2-Eq]": 4.0}])
    return joining, prepost, material


def test_mean_part_weight():
    assert mean_part_weight(WORKFLOWS["Tank"], "prototype") == 2.0
    assert mean_part_weight(WORKFLOWS["Tank"], "production") is None


def test_workflow_table(tables, capsys):
    t = workflow_table(WORKFLOWS, *tables, case="prototype", scenario="amount")
    tig = t[(t.technology == "TIG") & (t.indicator == GWP)].set_index("step")["value"]
    assert tig.to_dict() == {"material production": 8.0, "degreasing": 0.1, "pickling": 0.3,
                             "coating": 0.0, "joining": 2.0}
    assert "machining" not in tig      # disabled step
    assert "no LCIA data for 'coating'" in capsys.readouterr().out


def test_workflow_table_scenario(tables):
    t = workflow_table(WORKFLOWS, *tables, case="prototype", scenario="maximum")
    dbs = t[(t.technology == "DBS") & (t.indicator == GWP)].set_index("step")["value"]
    assert dbs["joining"] == 1.5 and dbs["degreasing"] == 0.2 and dbs["material production"] == 8.0


def test_cumulative_regional():
    def reg(process, key, values):
        return [{"process": process, "key": key, "scenario": "amount", "country": c, "indicator": GWP, "impact": v}
                for c, v in values.items()]
    joining = pd.DataFrame(reg("Tank joined with TIG", "Tank", {"RER": 1.0, "FR": 0.5}))
    prepost = pd.DataFrame(reg("degreasing for steel", "degreasing_steel", {"RER": 0.1, "FR": 0.05})
                           + reg("pickling for steel", "pickling_steel", {"RER": 0.2, "FR": 0.1}))
    out = cumulative_regional(WORKFLOWS, joining, prepost).set_index("country")["impact"]
    assert out["RER"] == pytest.approx(1.3)
    assert out["FR"] == pytest.approx(0.65)


def test_process_label():
    welds = {"Pharma welding"}
    assert process_label("Pharma welding", welds) == "Prototype joining"
    assert process_label("03_Laser welding", welds) == "Coupon joining"
    assert process_label("001_Pyshical_Cleaning", welds) == "Cleaning"
    assert process_label("04_Cutting", welds) == "Cutting (weld cross-sections)"
