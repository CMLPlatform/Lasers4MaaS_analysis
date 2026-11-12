"""Exchange builders: ranges, joining, pre- and post-joining processes."""

import pytest

from l4m_lca.joining import joining_amounts, joining_exchanges, joining_processes, technology_of
from l4m_lca.prepost import chemical_exchanges, mechanical_exchanges, tank_heat_loss
from l4m_lca.ranges import bounds, ranged_exchange

ELEC, GAS = ("ei", "elec"), ("ei", "gas")

HEAT_EXCHANGER_SOA = {
    "power_kW_joining": {"min": 1.4, "max": 1.5},
    "power_kW_station": {"min": 21.7, "max": 21.7},
    "joining_speed_m_per_s": {"min": 0.012, "max": 0.014},
    "joint_length_m": 42.9,
    "gas_flow_kg_per_s": {"min": 0.002676, "max": 0.002676},
}


def test_bounds():
    assert bounds({"min": 1, "max": 3}) == (1.0, 3.0)
    assert bounds(2) == (2.0, 2.0)


def test_ranged_exchange_midpoint_and_range():
    exc = ranged_exchange(ELEC, 1.0, 3.0)
    assert exc == {"input": ELEC, "amount": 2.0, "type": "technosphere",
                   "minimum": 1.0, "maximum": 3.0, "uncertainty_type": 1}


def test_ranged_exchange_plain_when_fixed():
    assert "minimum" not in ranged_exchange(ELEC, 2.0, 2.0, always_ranged=False)


def test_ranged_exchange_rejects_reversed_range():
    with pytest.raises(ValueError):
        ranged_exchange(ELEC, 3.0, 1.0)


def test_joining_minimum_is_shortest_time_at_lowest_power():
    amounts = joining_amounts(HEAT_EXCHANGER_SOA)
    t_min, t_max = 42.9 / 0.014, 42.9 / 0.012
    assert amounts["electricity"] == pytest.approx((23.1 * t_min / 3600, 23.2 * t_max / 3600))
    assert amounts["gas"] == pytest.approx((0.002676 * t_min, 0.002676 * t_max))
    for low, high in amounts.values():
        assert low <= high


def test_joining_laser_efficiency_divides_joining_power_only():
    params = {**HEAT_EXCHANGER_SOA, "laser_efficiency": 0.34}
    amounts = joining_amounts(params)
    t_min, t_max = 42.9 / 0.014, 42.9 / 0.012
    assert amounts["electricity"] == pytest.approx(((1.4 / 0.34 + 21.7) * t_min / 3600,
                                                    (1.5 / 0.34 + 21.7) * t_max / 3600))
    assert amounts["gas"] == joining_amounts(HEAT_EXCHANGER_SOA)["gas"]


def test_joining_laser_efficiency_range():
    # minimum electricity uses the highest efficiency, maximum the lowest
    params = {**HEAT_EXCHANGER_SOA, "laser_efficiency": {"min": 0.3, "max": 0.4}}
    low, high = joining_amounts(params)["electricity"]
    t_min, t_max = 42.9 / 0.014, 42.9 / 0.012
    assert (low, high) == pytest.approx(((1.4 / 0.4 + 21.7) * t_min / 3600,
                                         (1.5 / 0.3 + 21.7) * t_max / 3600))


@pytest.mark.parametrize("efficiency", [0, -0.1, 1.2])
def test_joining_laser_efficiency_rejects_invalid(efficiency):
    with pytest.raises(ValueError):
        joining_amounts({**HEAT_EXCHANGER_SOA, "laser_efficiency": efficiency})


def test_joining_exchanges():
    exchanges = joining_exchanges("db", "Heat exchanger", HEAT_EXCHANGER_SOA, ELEC, GAS)
    assert exchanges[0] == {"input": ("db", "Heat exchanger"), "amount": 1, "type": "production"}
    elec = exchanges[1]
    assert elec["amount"] == pytest.approx((elec["minimum"] + elec["maximum"]) / 2)


def test_joining_processes_names():
    data = joining_processes("db", {"Fuel tank": HEAT_EXCHANGER_SOA}, {"Fuel tank": "TIG"}, ELEC, GAS)
    assert data[("db", "Fuel tank")]["name"] == "Fuel tank joined with TIG"
    assert technology_of("Fuel tank joined with TIG") == "TIG"


def test_joining_gas_selected_per_use_case():
    gases = {"argon": GAS, "nitrogen": ("ei", "n2")}
    brazing = {**HEAT_EXCHANGER_SOA, "gas": "nitrogen"}
    assert joining_exchanges("db", "a", brazing, ELEC, gases)[2]["input"] == ("ei", "n2")
    assert joining_exchanges("db", "b", HEAT_EXCHANGER_SOA, ELEC, gases)[2]["input"] == GAS


def test_joining_filler_wire():
    filler = ("ei", "wire")
    with_filler = {**HEAT_EXCHANGER_SOA, "filler_kg": {"min": 0.0765, "max": 0.0765}}
    exchanges = joining_exchanges("db", "a", with_filler, ELEC, GAS, filler)
    assert exchanges[3]["input"] == filler and exchanges[3]["amount"] == pytest.approx(0.0765)
    assert len(joining_exchanges("db", "b", HEAT_EXCHANGER_SOA, ELEC, GAS, filler)) == 3
    with pytest.raises(ValueError):
        joining_exchanges("db", "c", with_filler, ELEC, GAS)


def test_tank_heat_loss():
    loss, drop, final, electricity = tank_heat_loss(1.0, 60, 20, 0.6, time_hours=2, heater_efficiency=0.95)
    assert loss == pytest.approx(0.6 * 6 * 40 * 2 / 1000)
    assert drop == pytest.approx(loss * 3.6e6 / (1000 * 4186))
    assert final == pytest.approx(60 - drop)
    assert electricity == pytest.approx(loss / 0.95)


DEGREASING_STEEL = {
    "acid_concentration_%": {"min": 0.05, "max": 0.1},
    "water_consumption_l": {"min": 5.0, "max": 15.0},
    "temperature_C": {"min": 60, "max": 80},
    "time_min": {"min": 5, "max": 15},
}


def test_chemical_exchanges_match_stored_model():
    # amounts of "alkaline_degreasing for steel" in the database written by the original notebook
    exchanges = chemical_exchanges("db", "alkaline_degreasing_steel", DEGREASING_STEEL, ("ei", "naoh"), ELEC,
                                   ("ei", "water"), tank_volume_l=7500, replenishment_per_h=0.001,
                                   bath_density_kg_per_l=1.0, room_temp_c=20, u_value=0.6, heater_efficiency=0.95)
    naoh, elec, water = exchanges[1:]
    assert naoh["amount"] == pytest.approx(0.109375)
    assert elec["amount"] == pytest.approx(0.13310, rel=1e-4)
    assert water["amount"] == 10.0


def test_mechanical_exchanges():
    params = {"electricity_kwh": {"min": 0.1, "max": 0.4}, "coolant_consumption_l": {"min": 1, "max": 2},
              "time_min": {"min": 5, "max": 20}}
    flows = {"electricity_kwh": (ELEC, 1.0), "coolant_consumption_l": (("ei", "oil"), 0.9)}
    exchanges, ignored = mechanical_exchanges("db", "x", params, flows)
    assert ignored == ["time_min"]
    assert exchanges[2]["minimum"] == pytest.approx(0.9)
    assert exchanges[2]["maximum"] == pytest.approx(1.8)


def test_mechanical_flow_without_dataset_is_not_modelled():
    params = {"electricity_kwh": {"min": 0.1, "max": 0.2}, "tool_wear_pct": {"min": 5, "max": 15}}
    flows = {"electricity_kwh": (ELEC, 1.0), "tool_wear_pct": (None, 0.0001)}
    exchanges, ignored = mechanical_exchanges("db", "x", params, flows)
    assert ignored == ["tool_wear_pct"]
    assert len(exchanges) == 2
