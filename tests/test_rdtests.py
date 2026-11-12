"""Helpers and exchange builders of the R&D test processes (l4m_lca.rdtests)."""

import pytest

from l4m_lca.rdtests import (add, background_inputs_per_unit, burst_test_time_h, cooling_kwh, cycle_time_h, div,
                             free_air_nm3, heating_kwh, mul, power_time_kwh, rd_test_exchanges, rd_test_processes, rng)
from fakes import Node, process

ELEC, WATER = ("ei", "elec"), ("ei", "water")


def test_rng_accepts_number_dict_and_tuple():
    assert rng(2) == (2.0, 2.0)
    assert rng({"min": 1, "max": 3}) == (1.0, 3.0)
    assert rng((1, 3)) == (1.0, 3.0)
    with pytest.raises(ValueError):
        rng((3, 1))


def test_range_arithmetic():
    assert mul((1, 2), (3, 4)) == (3.0, 8.0)
    assert add((1, 2), 3) == (4.0, 5.0)
    assert div((6, 8), (2, 4)) == (1.5, 4.0)


def test_energy_helpers():
    assert power_time_kwh(2, (0.5, 1)) == (1.0, 2.0)
    # 10 kg water heated by 70 K with a perfect heater: 10 * 4.186 * 70 / 3600 kWh
    low, high = heating_kwh(10, 4.186, 70, 1.0)
    assert low == pytest.approx(10 * 4.186 * 70 / 3600) and high == pytest.approx(low)
    assert cooling_kwh(10, 4.186, 70, (2, 4)) == pytest.approx((low / 4, low / 2))


def test_test_durations():
    assert cycle_time_h(120_000, 1) == pytest.approx((120_000 / 3600,) * 2)
    # burst at 10 bar: 100 s of ramps + 2 x 300 s holds
    assert burst_test_time_h(10) == pytest.approx((700 / 3600,) * 2)


def test_free_air():
    low, high = free_air_nm3(1.0, 2.5)
    assert low == pytest.approx(1.0 / 1000 * 3.513 / 1.013)


def test_background_inputs_per_unit_skips_foreground():
    resin = Node("ei", "resin", "phenolic resin")
    coupon = process("lab", "coupon", "welded coupon")
    step = process("lab", "mount", "hot mounting", production=6.0)
    step.add(resin, 0.6).add(coupon, 6.0)
    inputs = background_inputs_per_unit(step, {"lab"})
    assert [(n.key, k, a) for n, k, a in inputs] == [(("ei", "resin"), "technosphere", pytest.approx(0.1))]


def test_test_exchanges_and_missing_flow():
    flows = {"electricity": ELEC, "water": WATER, "glycol": None}
    spec = {"electricity_kwh": (1, 3), "inputs": {"water": (2, 4), "glycol": (1, 1)},
            "links": [(("db", "leak"), 1)]}
    exchanges, ignored = rd_test_exchanges("db", "burst", spec, flows)
    assert exchanges[0] == {"input": ("db", "burst"), "amount": 1, "type": "production"}
    assert exchanges[1]["input"] == ELEC and exchanges[1]["amount"] == pytest.approx(2)
    assert exchanges[2]["input"] == WATER and exchanges[2]["minimum"] == 2
    assert exchanges[3]["input"] == ("db", "leak")
    assert ignored == ["glycol"]


def test_copied_inputs_scale_with_factor():
    resin = Node("ei", "resin", "phenolic resin")
    spec = {"copied": [(resin, "technosphere", 0.1, (2, 6))]}
    exchanges, _ = rd_test_exchanges("db", "macro", spec, {})
    assert exchanges[1]["minimum"] == pytest.approx(0.2) and exchanges[1]["maximum"] == pytest.approx(0.6)


def test_test_processes():
    specs = {"leak": {"name": "Leak tightness test", "unit": "test", "electricity_kwh": 0.01}}
    data, ignored = rd_test_processes("db", specs, {"electricity": ELEC})
    assert data[("db", "leak")]["name"] == "Leak tightness test" and ignored == {}
