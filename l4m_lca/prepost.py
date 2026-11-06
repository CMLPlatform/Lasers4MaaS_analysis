"""Exchanges of the chemical and mechanical pre- and post-joining processes.

The functional unit of each process is 1 execution of the process.
"""

from .ranges import bounds, production, ranged_exchange

WATER_HEAT_CAPACITY_J_PER_KG_K = 4186


def tank_heat_loss(volume_m3, fluid_temp_c, room_temp_c, u_value, time_hours=1.0, heater_efficiency=0.95):
    """Heat loss of a cubic, water-filled tank.

    Args:
        volume_m3: tank volume (m3).
        fluid_temp_c: bath temperature (degC).
        room_temp_c: room temperature (degC).
        u_value: heat transfer coefficient (W/m2.K).
        time_hours: duration (h).
        heater_efficiency: fraction of the electricity that becomes heat in the bath.

    Returns:
        (heat_loss_kwh, temp_drop_c, final_temp_c, heat_maintenance_kwh).
        heat_maintenance_kwh is the electricity that replaces the heat loss.
    """
    side = volume_m3 ** (1 / 3)
    area = 6 * side ** 2
    mass_kg = volume_m3 * 1000
    heat_loss_kwh = u_value * area * (fluid_temp_c - room_temp_c) * time_hours / 1000
    temp_drop = heat_loss_kwh * 3.6e6 / (mass_kg * WATER_HEAT_CAPACITY_J_PER_KG_K)
    return heat_loss_kwh, temp_drop, fluid_temp_c - temp_drop, heat_loss_kwh / heater_efficiency


def chemical_exchanges(database_name, code, params, active_chemical, electricity, water, *,
                       tank_volume_l, replenishment_per_h, bath_density_kg_per_l,
                       room_temp_c, u_value, heater_efficiency):
    """Exchanges of one execution of a chemical bath process.

    `params` is the material-specific dict of CHEM_PREPOST_PARAMS. It has
    `acid_concentration_%` (mass fraction of active chemical: 0.05 = 5 wt%),
    `time_min`, `temperature_C` and `water_consumption_l`, each a {"min", "max"} range.

    - Active chemical (kg of active substance, as the ecoinvent "without water" datasets):
      concentration * bath mass * replenished fraction per hour * hours.
    - Electricity (kWh): heat that replaces the tank heat loss during the process time.
    - Water (kg = l): rinsing water.
    """
    time_low, time_high = bounds(params["time_min"])
    volume_low, volume_high = bounds(tank_volume_l)
    conc_low, conc_high = bounds(params["acid_concentration_%"])
    temp_low, temp_high = bounds(params["temperature_C"])
    water_low, water_high = bounds(params["water_consumption_l"])

    def acid(conc, volume, time_min):
        return conc * volume * bath_density_kg_per_l * replenishment_per_h * time_min / 60

    def heat(temp, time_min):
        return tank_heat_loss(volume_low / 1000, temp, room_temp_c, u_value,
                              time_hours=time_min / 60, heater_efficiency=heater_efficiency)[3]

    return [
        production(database_name, code),
        ranged_exchange(active_chemical, acid(conc_low, volume_low, time_low),
                        acid(conc_high, volume_high, time_high)),
        ranged_exchange(electricity, heat(temp_low, time_low), heat(temp_high, time_high)),
        ranged_exchange(water, water_low, water_high),
    ]


def mechanical_exchanges(database_name, code, params, parameter_flows):
    """Exchanges of one execution of a mechanical process.

    `params` is the material-specific dict of MECH_PREPOST_PARAMS. Each value is the total
    consumed over one execution, as a {"min", "max"} range.
    `parameter_flows` maps a parameter name to (flow, factor to the ecoinvent unit).
    Parameters without a flow (time, area, roughness) are not modelled.

    Returns (exchanges, names of the parameters without a flow).
    """
    exchanges = [production(database_name, code)]
    ignored = []
    for parameter, value in params.items():
        if parameter not in parameter_flows:
            ignored.append(parameter)
            continue
        flow, factor = parameter_flows[parameter]
        low, high = bounds(value)
        exchanges.append(ranged_exchange(flow, low * factor, high * factor))
    return exchanges, ignored


def per_material(process_params):
    """Yield (service, material, material parameters, record) for each process and material."""
    for service, record in process_params.items():
        for material, params in record["parameters"].items():
            yield service, material, params, record


def process_code(service, material):
    """Process code: one process per service and material, e.g. "pickling_steel"."""
    return f"{service}_{material}"


def process_name(service, material):
    return f"{service} for {material}"
