"""Exchanges of the joining processes (functional unit: 1 joined unit)."""

from .costs import LABOUR_FIELD, labour_range
from .ranges import bounds, production, ranged_exchange


def joining_amounts(params):
    """Electricity (kWh) and gas (kg) ranges of one joined unit.

    minimum = lowest power (or gas flow) during the shortest joining time (fastest speed).
    maximum = highest power (or gas flow) during the longest joining time (slowest speed).
    `params["laser_efficiency"]` (optional, default 1) is the power return rate of a laser:
    laser output power / electrical power. The joining power is divided by it.
    The minimum uses the highest efficiency, the maximum the lowest.
    Labour (h) = joining time x `params["operators"]` (optional, default 1 operator per station).
    Returns {"electricity": (low, high), "gas": (low, high), "filler": (low, high), "labour_h": (low, high)}.
    """
    time_min_s = params["joint_length_m"] / params["joining_speed_m_per_s"]["max"]
    time_max_s = params["joint_length_m"] / params["joining_speed_m_per_s"]["min"]

    eff_low, eff_high = bounds(params.get("laser_efficiency", 1.0))
    if not 0 < eff_low <= eff_high <= 1:
        raise ValueError(f"laser_efficiency must be in (0, 1], not {params['laser_efficiency']!r}")

    # (electrical joining power + welding station power) in kW * hours
    power_min = params["power_kW_joining"]["min"] / eff_high + params["power_kW_station"]["min"]
    power_max = params["power_kW_joining"]["max"] / eff_low + params["power_kW_station"]["max"]

    filler = params.get("filler_kg", {"min": 0.0, "max": 0.0})
    operators = params.get("operators", 1)
    return {
        "electricity": (power_min * time_min_s / 3600, power_max * time_max_s / 3600),
        "gas": (params["gas_flow_kg_per_s"]["min"] * time_min_s,
                params["gas_flow_kg_per_s"]["max"] * time_max_s),
        "filler": (filler["min"], filler["max"]),
        "labour_h": (operators * time_min_s / 3600, operators * time_max_s / 3600),
    }


def joining_exchanges(database_name, code, params, electricity, gas, filler=None):
    """Production, electricity, gas and filler wire exchanges of one joining process.

    `gas` is one activity, or {gas name: activity}; then `params["gas"]` selects the gas
    (default "argon"). The filler wire exchange is added when `params["filler_kg"]` is not 0.
    """
    amounts = joining_amounts(params)
    if isinstance(gas, dict):
        gas = gas[params.get("gas", "argon")]
    exchanges = [
        production(database_name, code),
        ranged_exchange(electricity, *amounts["electricity"], always_ranged=False),
        ranged_exchange(gas, *amounts["gas"], always_ranged=False),
    ]
    if any(amounts["filler"]):
        if filler is None:
            raise ValueError(f"{code}: filler_kg is set, but no filler activity was given")
        exchanges.append(ranged_exchange(filler, *amounts["filler"], always_ranged=False))
    return exchanges


def joining_processes(database_name, joining_params, technology, electricity, gas, location="NL", filler=None):
    """Brightway data of the joining processes, one per use case.

    `technology` maps a use case to its technology name, or is one name for all use cases.
    `gas` is one activity or {gas name: activity}; `filler` is the filler wire activity (optional).
    The process name is "<use case> joined with <technology>".
    Each process stores its labour hours (minimum, amount, maximum) in the field `LABOUR_FIELD`.
    """
    data = {}
    for use_case, params in joining_params.items():
        tech = technology if isinstance(technology, str) else technology[use_case]
        data[(database_name, use_case)] = {
            "name": f"{use_case} joined with {tech}",
            "unit": "unit",
            "location": location,
            "exchanges": joining_exchanges(database_name, use_case, params, electricity, gas, filler),
            LABOUR_FIELD: labour_range(*joining_amounts(params)["labour_h"]),
        }
    return data


def technology_of(process_name):
    """Technology part of a joining process name ("<use case> joined with <technology>")."""
    return process_name.split(" joined with ", 1)[-1]
