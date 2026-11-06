"""Exchanges of the joining processes (functional unit: 1 joined unit)."""

from .ranges import production, ranged_exchange


def joining_amounts(params):
    """Electricity (kWh) and gas (kg) ranges of one joined unit.

    minimum = lowest power (or gas flow) during the shortest joining time (fastest speed).
    maximum = highest power (or gas flow) during the longest joining time (slowest speed).
    Returns {"electricity": (low, high), "gas": (low, high)}.
    """
    time_min_s = params["joint_length_m"] / params["joining_speed_m_per_s"]["max"]
    time_max_s = params["joint_length_m"] / params["joining_speed_m_per_s"]["min"]

    # (joining power + welding station power) in kW * hours
    power_min = params["power_kW_joining"]["min"] + params["power_kW_station"]["min"]
    power_max = params["power_kW_joining"]["max"] + params["power_kW_station"]["max"]

    return {
        "electricity": (power_min * time_min_s / 3600, power_max * time_max_s / 3600),
        "gas": (params["gas_flow_kg_per_s"]["min"] * time_min_s,
                params["gas_flow_kg_per_s"]["max"] * time_max_s),
    }


def joining_exchanges(database_name, code, params, electricity, gas):
    """Production, electricity and gas exchanges of one joining process."""
    amounts = joining_amounts(params)
    return [
        production(database_name, code),
        ranged_exchange(electricity, *amounts["electricity"], always_ranged=False),
        ranged_exchange(gas, *amounts["gas"], always_ranged=False),
    ]


def joining_processes(database_name, joining_params, technology, electricity, gas, location="NL"):
    """Brightway data of the joining processes, one per use case.

    `technology` maps a use case to its technology name, or is one name for all use cases.
    The process name is "<use case> joined with <technology>".
    """
    data = {}
    for use_case, params in joining_params.items():
        tech = technology if isinstance(technology, str) else technology[use_case]
        data[(database_name, use_case)] = {
            "name": f"{use_case} joined with {tech}",
            "unit": "unit",
            "location": location,
            "exchanges": joining_exchanges(database_name, use_case, params, electricity, gas),
        }
    return data


def technology_of(process_name):
    """Technology part of a joining process name ("<use case> joined with <technology>")."""
    return process_name.split(" joined with ", 1)[-1]
