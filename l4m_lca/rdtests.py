"""Unit processes of the R&D validation tests described in D13.1.

Functional unit of each process: one test of one component (or one prepared specimen).

D13.1 describes the test procedures (durations, pressures, temperatures, flows) but gives no
power ratings or consumable amounts. The amounts are therefore engineering estimates: the
energy follows from the D13.1 durations and typical equipment power, heating and cooling
from mass x heat capacity x temperature difference, and consumables are (min, max) ranges.
Every estimate is a parameter in `rd_tests.ipynb`, to be replaced by partner data.

All helpers work on ranges: a number, a {"min", "max"} dict or a (low, high) tuple.
They return a (low, high) tuple, where low combines the low ends of the inputs that
lower the result, and high the high ends.
"""

from .ranges import bounds, production, ranged_exchange

WATER_CP_KJ_PER_KG_K = 4.186
ALUMINIUM_CP_KJ_PER_KG_K = 0.90
STEEL_CP_KJ_PER_KG_K = 0.50
ATMOSPHERIC_PRESSURE_BAR = 1.013


def rng(value):
    """(low, high) of a number, a {"min", "max"} dict or a (low, high) tuple."""
    if isinstance(value, (tuple, list)):
        low, high = float(value[0]), float(value[1])
    else:
        low, high = bounds(value)
    if low > high:
        raise ValueError(f"Range {value!r} has minimum above maximum")
    return low, high


def mul(*values):
    """Product of non-negative ranges."""
    low, high = 1.0, 1.0
    for v in values:
        a, b = rng(v)
        if a < 0:
            raise ValueError("mul() expects non-negative ranges")
        low, high = low * a, high * b
    return low, high


def add(*values):
    """Sum of ranges."""
    pairs = [rng(v) for v in values]
    return sum(a for a, _ in pairs), sum(b for _, b in pairs)


def div(value, divisor):
    """Range divided by a positive range: low = low / high divisor."""
    a, b = rng(value)
    c, d = rng(divisor)
    if c <= 0:
        raise ValueError("div() expects a positive divisor")
    return a / d, b / c


def power_time_kwh(power_kw, time_h):
    """Electricity (kWh) of equipment with a power (kW) running for a time (h)."""
    return mul(power_kw, time_h)


def heating_kwh(mass_kg, cp_kj_per_kg_k, delta_t_k, efficiency):
    """Electricity (kWh) to heat a mass by delta_t with an electric heater of the given efficiency."""
    return div(mul(mass_kg, cp_kj_per_kg_k, delta_t_k, 1 / 3600), efficiency)


def cooling_kwh(mass_kg, cp_kj_per_kg_k, delta_t_k, cop):
    """Electricity (kWh) of a chiller with the given COP that removes mass x cp x delta_t."""
    return div(mul(mass_kg, cp_kj_per_kg_k, delta_t_k, 1 / 3600), cop)


def free_air_nm3(volume_l, gauge_bar):
    """Free air (Nm3) needed to fill a volume (l) to a gauge pressure (bar)."""
    return mul(volume_l, 1 / 1000, add(gauge_bar, ATMOSPHERIC_PRESSURE_BAR), 1 / ATMOSPHERIC_PRESSURE_BAR)


def burst_test_time_h(burst_pressure_bar, ramp_bar_per_s=0.1, hold_s=300.0, holds=2):
    """Duration (h) of the D13.1 burst test.

    Ramps at `ramp_bar_per_s` from ambient pressure up to the burst pressure, with `holds`
    holds of `hold_s` (at P_max and 2 x P_max). The ramps add up to burst pressure / ramp rate.
    """
    return div(add(div(burst_pressure_bar, ramp_bar_per_s), mul(hold_s, holds)), 3600)


def cycle_time_h(cycles, frequency_hz):
    """Duration (h) of a cyclic test."""
    return div(cycles, mul(frequency_hz, 3600))


def background_inputs_per_unit(activity, exclude_databases):
    """Technosphere and biosphere inputs of `activity` from databases not in `exclude_databases`,
    per unit of its reference product: [(node, kind, amount)].

    Used to copy the direct inputs of a lab step (for example a metallographic preparation step)
    without its upstream foreground chain (the welded coupon).
    """
    prod = next(e["amount"] for e in activity.exchanges() if e["type"] == "production")
    out = []
    for e in activity.exchanges():
        if e["type"] in ("technosphere", "biosphere") and e.input["database"] not in exclude_databases:
            out.append((e.input, e["type"], e["amount"] / prod))
    return out


def rd_test_exchanges(database_name, code, spec, flows):
    """Exchanges of one test process and the names of the inputs without a background flow.

    `spec` keys:
        "electricity_kwh": range of the electricity per test.
        "inputs": {flow name: range} of background inputs per test (units of the flow).
        "links": [(node, range)] inputs from other processes (foreground or background nodes).
        "copied": [(node, kind, amount, factor range)] copied inputs; the amount is multiplied
            by the factor range (for example the number of specimens).
    `flows` maps a flow name to a Brightway node, or to None when the background has no dataset.
    """
    exchanges = [production(database_name, code)]
    ignored = []
    if "electricity_kwh" in spec:
        exchanges.append(ranged_exchange(flows["electricity"], *rng(spec["electricity_kwh"])))
    for name, value in spec.get("inputs", {}).items():
        if flows.get(name) is None:
            ignored.append(name)
            continue
        exchanges.append(ranged_exchange(flows[name], *rng(value)))
    for node, value in spec.get("links", []):
        exchanges.append(ranged_exchange(node, *rng(value)))
    for node, kind, amount, factor in spec.get("copied", []):
        low, high = mul(abs(amount), factor)
        sign = -1 if amount < 0 else 1
        exc = ranged_exchange(node, low, high)
        if sign < 0:
            exc.update(amount=-exc["amount"], minimum=-high, maximum=-low)
        exc["type"] = kind
        exchanges.append(exc)
    return exchanges, ignored


def rd_test_processes(database_name, specs, flows, location="RER"):
    """Brightway data of the test processes: {key: data}, and {code: ignored input names}.

    `specs` maps a process code to a spec with "name" and "unit", plus the keys of `rd_test_exchanges`.
    Specs may refer to other processes of the same database in "links" with the key
    (database_name, code).
    """
    data, ignored = {}, {}
    for code, spec in specs.items():
        exchanges, missing = rd_test_exchanges(database_name, code, spec, flows)
        data[(database_name, code)] = {
            "name": spec["name"],
            "unit": spec.get("unit", "unit"),
            "location": spec.get("location", location),
            "reference product": spec.get("reference product", spec["name"]),
            "comment": spec.get("comment", ""),
            "exchanges": exchanges,
        }
        if missing:
            ignored[code] = missing
    return data, ignored
