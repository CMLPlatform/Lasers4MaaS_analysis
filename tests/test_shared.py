"""Shared settings and table helpers: background selection, result stems, cost and contribution tables."""

import pandas as pd
import pytest

from l4m_lca.constants import BACKGROUNDS, L4M_SOLUTION_DATABASE, JOINING_STEM, SOA_DATABASE
from l4m_lca.project import BACKGROUND_VARIABLE, select_background


def test_select_background_default_and_override(monkeypatch):
    monkeypatch.delenv(BACKGROUND_VARIABLE, raising=False)
    bg = select_background("ecoinvent")
    assert (bg.name, bg.project, bg.database, bg.results) == (
        "ecoinvent", *(BACKGROUNDS["ecoinvent"][k] for k in ("project", "database", "results")))
    monkeypatch.setenv(BACKGROUND_VARIABLE, "bafu")
    assert select_background("ecoinvent").database == BACKGROUNDS["bafu"]["database"]
    monkeypatch.setenv(BACKGROUND_VARIABLE, "other")
    with pytest.raises(ValueError):
        select_background()


def test_joining_stem_names_both_databases():
    assert JOINING_STEM == f"{SOA_DATABASE}_{L4M_SOLUTION_DATABASE}"


def test_cost_table_adds_totals():
    from l4m_lca.workflow import cost_table
    rows = [{"product": "P", "technology": "T", "indicator": ind, "stage": stage, "value": v}
            for ind, values in {"a": {"pre": 1.0, "join": 2.0}, "b": {"pre": 3.0, "join": 4.0}}.items()
            for stage, v in values.items()]
    rows.append({"product": "P", "technology": "T", "indicator": "impact", "stage": "pre", "value": 99.0})
    table = cost_table(pd.DataFrame(rows), ("a", "b"))
    assert list(table.columns) == [("a", "pre"), ("a", "join"), ("a", "total"),
                                   ("b", "pre"), ("b", "join"), ("b", "total")]
    assert table.loc[("P", "T"), ("a", "total")] == 3.0
    assert table.loc[("P", "T"), ("b", "total")] == 7.0


def test_contribution_rows_and_stack_table(monkeypatch):
    import numpy as np

    from l4m_lca import rd
    from l4m_lca.impacts import Flow
    from fakes import Node

    names = {("fg", "weld"): "Weld A", ("fg", "cut"): "04_Cutting of coupons"}
    monkeypatch.setattr(rd.bd, "get_activity", lambda key: {"name": names[key]})
    elec = Node("bg", "e", "market group for electricity, medium voltage", location="RER", unit="kilowatt hour")
    argon = Node("bg", "ar", "market for argon, liquid", location="RER", unit="kilogram")
    contribs = {("UC", "SoA"): [(Flow((("fg", "weld"),), elec, "technosphere", 2.0), np.array([1.0, 10.0])),
                                (Flow((("fg", "cut"),), argon, "technosphere", 0.5), np.array([0.5, 5.0])),
                                (Flow((("fg", "weld"),), argon, "technosphere", 0.1), np.array([0.25, 2.5]))]}
    rows = rd.contribution_rows(contribs, {"Weld A"}, ["ghg", "acid"])
    assert [r["process"] for r in rows] == ["Prototype joining", "Cutting (weld cross-sections)", "Prototype joining"]
    assert [r["electricity_kwh"] for r in rows] == [2.0, 0.0, 0.0]
    assert rows[1]["background_input"] == "market for argon, liquid [RER]"
    table = rd.stack_table(rows, "ghg")
    assert list(table.columns) == ["Prototype joining", "Cutting (weld cross-sections)"]
    assert table.loc[("UC", "SoA"), "Prototype joining"] == 1.25
