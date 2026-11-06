"""Linear LCIA engine: foreground walk, scenario amounts, costs. Uses fake nodes, no project."""

import numpy as np
import pytest

from fakes import FakeImpacts, Node, process
from l4m_lca.impacts import consumable_cost, electricity_kwh, foreground_flows, scenario_amount

FG = {"fg"}


@pytest.fixture
def system():
    elec = Node("ei", "e", "market group for electricity, medium voltage")
    elec_de = Node("ei", "de", "market for electricity, medium voltage")
    gas = Node("ei", "g", "market for argon, liquid")
    co2 = Node("bio", "co2", "Carbon dioxide")
    # sub-process produces 4 units; the top process uses 2 of them
    sub = process("fg", "sub", "sub", production=4.0).add(elec, 8.0).add(co2, 1.0, "biosphere")
    top = process("fg", "top", "top").add(sub, 2.0).add(gas, 3.0, minimum=1.0, maximum=5.0).add(elec, 1.0)
    return dict(elec=elec, elec_de=elec_de, gas=gas, co2=co2, sub=sub, top=top)


def test_scenario_amount():
    exc = {"amount": 2.0, "minimum": 1.0, "maximum": 3.0}
    assert [scenario_amount(exc, s) for s in ("minimum", "amount", "maximum")] == [1.0, 2.0, 3.0]
    assert scenario_amount({"amount": 2.0}, "maximum") == 2.0
    assert scenario_amount({"amount": 2.0, "min": 0.5}, "minimum") == 0.5


def test_walk_scales_by_production_amount(system):
    flows = foreground_flows(system["top"], FG)
    amounts = {(f.node["code"], f.path): f.amount for f in flows}
    top, sub = system["top"].key, system["sub"].key
    assert amounts[("e", (top, sub))] == pytest.approx(8.0 * 2 / 4)
    assert amounts[("co2", (top, sub))] == pytest.approx(1.0 * 2 / 4)
    assert amounts[("g", (top,))] == 3.0
    assert amounts[("e", (top,))] == 1.0


def test_walk_uses_scenario_amounts(system):
    gas = [f for f in foreground_flows(system["top"], FG, "maximum") if f.node["code"] == "g"]
    assert gas[0].amount == 5.0


def test_impacts_are_linear_and_swap_electricity(system):
    impacts = FakeImpacts({system["elec"].id: [1.0, 0.0], system["elec_de"].id: [10.0, 0.0],
                           system["gas"].id: [0.0, 2.0], system["co2"].id: [1.0, 0.0]})
    flows = foreground_flows(system["top"], FG)
    # elec 4 + 1 kWh, gas 3 kg, co2 0.5 kg
    assert np.allclose(impacts.of_flows(flows), [4 + 1 + 0.5, 6.0])
    assert np.allclose(impacts.of_flows(flows, electricity=system["elec_de"]), [40 + 10 + 0.5, 6.0])


def test_direct_electricity_and_cost(system):
    flows = foreground_flows(system["top"], FG)
    assert electricity_kwh(flows) == 1.0   # the sub-process electricity is not direct
    unpriced = set()
    cost = consumable_cost(flows, {system["gas"].key: 2.0}, electricity_price=0.5, warn=unpriced)
    assert cost == pytest.approx(3 * 2.0 + 1 * 0.5)
    assert unpriced == set()
    consumable_cost(flows, {}, warn=unpriced)
    assert unpriced == {"market for argon, liquid", "market group for electricity, medium voltage"}


def test_unsupported_exchange_type():
    p = process("fg", "p", "p").add(Node("ei", "x", "x"), 1.0, "substitution")
    with pytest.raises(ValueError):
        foreground_flows(p, FG)


@pytest.mark.parametrize("name, expected", [
    ("market group for electricity, medium voltage", True),
    ("market for electricity, medium voltage", True),
    ("Electricity, medium voltage, at grid", True),                     # BAFU country mix
    ("Electricity, medium voltage, production RER, at grid", True),     # BAFU production mix
    ("Electricity, medium voltage, SBB, at grid", False),               # railway grid
    ("Electricity, medium voltage, PV, open ground, single-Si", False),
    ("market for electricity, low voltage", False),
])
def test_is_electricity_both_backgrounds(name, expected):
    from l4m_lca.impacts import is_electricity
    assert is_electricity({"name": name}) is expected
