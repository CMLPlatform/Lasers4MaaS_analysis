"""Exchanges of the chemical and mechanical pre- and post-joining processes.

The functional unit of each process is 1 minute of the process.
"""
import pickle
import bw2data as bd
from bw2data.errors import UnknownObject

PROJECT = "L4M-DPP"
ECOINVENT = "ecoinvent-3.12-cutoff"
BONSAI_DB = "BONSAI v2.4.0"
BAFU_DB = "bafu-2026"
BACKGROUND = ECOINVENT  # or BAFU_DB

LABOUR_FIELD = "labour_h"

def labour_range(low, high):
    """Labour hours of the minimum, amount (midpoint) and maximum scenarios."""
    if low > high:
        raise ValueError(f"Labour hours: minimum {low} is above maximum {high}")
    return {"minimum": low, "amount": (low + high) / 2, "maximum": high}


def bounds(value):
    """Return (low, high) of a {"min", "max"} range, or (value, value) for a number."""
    if isinstance(value, dict):
        return float(value["min"]), float(value["max"])
    value = float(value)
    return value, value


def as_key(node_or_key):
    """Return the key of a Brightway node, or the value itself if it is a key already."""
    return getattr(node_or_key, "key", node_or_key)


def production(database_name, code, amount=1):
    """Production exchange of a new process."""
    return {"input": (database_name, code), "amount": amount, "type": "production"}


def ranged_exchange(input_, low, high, always_ranged=True):
    """Technosphere exchange with amount = midpoint, and minimum/maximum for the scenarios.

    With `always_ranged=False`, a range with low == high gives a plain exchange
    (no minimum, maximum or uncertainty type).
    """
    if low > high:
        raise ValueError(f"Range of {input_!r} has minimum {low} above maximum {high}")
    exchange = {"input": as_key(input_), "amount": (low + high) / 2, "type": "technosphere"}
    if always_ranged or low != high:
        exchange.update({"minimum": low, "maximum": high, "uncertainty_type": 1})
    return exchange

def find_activity(database, name, location, reference_product=None):
    """Return the one activity with this exact name and location (and reference product).

    Raises UnknownObject if no activity matches, MultipleResults if more than one matches.
    """
    filters = {"database": database, "name": name, "location": location}
    if reference_product is not None:
        filters["product"] = reference_product
    try:
        return bd.get_node(**filters)
    except UnknownObject:
        raise UnknownObject(f"No match for {filters}")


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

    def heat(temp, volume, time_min):
        return tank_heat_loss(volume / 1000, temp, room_temp_c, u_value,
                              time_hours=time_min / 60, heater_efficiency=heater_efficiency)[3]

    return [
        production(database_name, code),
        ranged_exchange(active_chemical, acid(conc_low, volume_low, time_low),
                        acid(conc_high, volume_high, time_high)),
        ranged_exchange(electricity, heat(temp_low, volume_low, time_low), heat(temp_high, volume_high, time_high)),
        ranged_exchange(water, water_low, water_high),
    ]


def mechanical_exchanges(database_name, code, params, parameter_flows):
    """Exchanges of one execution of a mechanical process.

    `params` is the material-specific dict of MECH_PREPOST_PARAMS. Each value is the total
    consumed over one execution, as a {"min", "max"} range.
    `parameter_flows` maps a parameter name to (flow, factor to the ecoinvent unit).
    Parameters without a flow (time, area, roughness), or with flow None (no dataset in
    the background database), are not modelled.

    Returns (exchanges, names of the parameters without a flow).
    """
    exchanges = [production(database_name, code)]
    ignored = []
    for parameter, value in params.items():
        if parameter not in parameter_flows or parameter_flows[parameter][0] is None:
            ignored.append(parameter)
            continue
        flow, factor = parameter_flows[parameter]
        low, high = bounds(value)
        exchanges.append(ranged_exchange(flow, low * factor, high * factor))
    return exchanges, ignored


def prepost_labour(params, operator_share=1.0):
    """Labour hours (minimum, amount, maximum) of one execution: process time x `operator_share`.

    The process time is the first of `TIME_PARAMETERS` in `params` (minutes).
    `operator_share` is the share of the process time that 1 operator works on the part:
    1 = full attention (mechanical work), below 1 = the operator also does other work
    (for example, a chemical bath only needs loading and unloading).
    Returns None if `params` has no process time.
    """
    if not 0 <= operator_share <= 1:
        raise ValueError(f"operator_share must be in [0, 1], not {operator_share!r}")
    low, high = bounds(params["time_min"])
    return labour_range(low / 60 * operator_share, high / 60 * operator_share)


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


# Background activities of ecoinvent 3.12: (name, location, reference product or None)
ECOINVENT_FLOWS = {
    "electricity":        ("market group for electricity, medium voltage", "RER", None),          # kWh
    "water":              ("market group for tap water", "RER", None),                            # kg
    "sodium_hydroxide":   ("market for sodium hydroxide, without water, in 50% solution state", "RER", None),
    "hydrochloric_acid":  ("market for hydrochloric acid, without water, in 30% solution state", "RER", None),
    "nitric_acid":        ("market for nitric acid, without water, in 50% solution state", "RER w/o RU", None),
    # Mechanical flows are PROXIES, all in kg. ecoinvent 3.12 has no "grinding wheel" or
    # "metal working fluid" dataset, and "abrasive blasting, alumina" is a service in m2.
    "abrasive":           ("aluminium oxide production", "RoW", "aluminium oxide, non-metallurgical"),  # alumina grit (corundum)
    "grinding_wheel":     ("market for silicon carbide", "GLO", None),        # abrasive grain of wheels
    "polishing_compound": ("aluminium oxide production", "RoW", "aluminium oxide, non-metallurgical"),  # alumina powder
    "coolant":            ("market for lubricating oil", "RER", None),        # no emulsion dataset in ecoinvent
    "tool_material":      ("market for tungsten carbide powder", "GLO", None),  # cutting tool material
}

# Background activities of BAFU-2026 (ecoinvent v2 names). None = no dataset: the parameter is not modelled.
BAFU_FLOWS = {
    "electricity":        ("Electricity, medium voltage, at grid", "RER", None),       # consumption mix 2023
    "water":              ("Tap water, at user", "RER", None),
    "sodium_hydroxide":   ("Sodium hydroxide, 50% in H2O, production mix, at plant", "RER", None),  # per kg NaOH
    "hydrochloric_acid":  ("Hydrochloric acid, 30% in H2O, at plant", "RER", None),    # per kg HCl
    "nitric_acid":        ("Nitric acid, 50% in H2O, at plant", "RER", None),          # per kg HNO3
    "abrasive":           ("Aluminium oxide, at plant", "RER", None),                  # alumina proxy
    "grinding_wheel":     ("Silicon carbide, at plant", "RER", None),
    "polishing_compound": ("Aluminium oxide, at plant", "RER", None),
    "coolant":            ("Lubricating oil, at plant", "RER", None),
    "tool_material":      None,   # BAFU has no tungsten carbide: tool wear is not modelled
}
FLOWS = BAFU_FLOWS if BACKGROUND == BAFU_DB else ECOINVENT_FLOWS

# Prices per ecoinvent unit of each flow. INDICATIVE PLACEHOLDER PRICES except electricity:
# replace with supplier quotes. Chemicals are per kg of ACTIVE substance, as modelled
# (ecoinvent "without water" datasets), so they are higher than the diluted commercial price.
COST_FACTORS = {
    # "electricity": EUROSTAT_ELEC_PRICE_2025S1["RER"],   # EUR/kWh, Eurostat 2025-S1, band ID, EU27 average (0.164)
    "water":              0.004,  # EUR/kg, tap water with discharge (about 4 EUR/m3)
    "sodium_hydroxide":   0.50,   # EUR/kg
    "hydrochloric_acid":  0.25,   # EUR/kg
    "nitric_acid":        0.45,   # EUR/kg
    "abrasive":           1.50,   # EUR/kg, alumina grit
    "polishing_compound": 1.50,   # EUR/kg, alumina proxy
    "grinding_wheel":     2.50,   # EUR/kg, silicon carbide proxy
    "coolant":            2.00,   # EUR/kg, lubricating oil proxy
    "tool_material":      60.0,   # EUR/kg, tungsten carbide
}

# Regional analysis: EU27 member states and the United Kingdom (GB).
# Industrial electricity price of each country (EUR/kWh). GB: DESNZ (see l4m_lca/constants.py for the sources).
# REGIONAL_COUNTRIES = EU27_GB
# ELEC_PRICE = {**EUROSTAT_ELEC_PRICE_2025S1, **GB_ELEC_PRICE_2025S1}
REGIONAL_BASELINE = "RER"

# Labour cost per hour of each country (EUR/h), as in joining_task.ipynb: Eurostat lc_lci_lev 2025, NACE C,
# sheet "labour_cost" of country_data.xlsx; GB from l4m_lca/constants.py. The EU27 average is the baseline.
LABOUR_COST_FILE = "Input_data/country_data.xlsx"
# LABOUR_COSTS = {**read_labour_costs(LABOUR_COST_FILE, baseline=REGIONAL_BASELINE), **GB_LABOUR_COST_2025}
# LABOUR_COST = LABOUR_COSTS[REGIONAL_BASELINE]   # 35.0 EUR/h, EU27 average

# Labour hours per execution = process time (time_min or machining_time_min) x operator share.
# The operator share is the part of the process time that 1 operator works on the part.
CHEM_OPERATOR_SHARE = 0.25   # chemical baths: the operator loads and unloads, and does other work during immersion
MECH_OPERATOR_SHARE = 1.0    # mechanical treatments: the operator works on the part for the full time
OPERATOR_SHARE = {}          # override per process, for example {"pickling": 0.5}

# Chemical bath processes
INDUSTRIAL_TANK_SIZES_L = {
    "pickling": 10000,             # 10 m3, standard for joining preparation (ASTM A380)
    "alkaline_degreasing": 7500,   # 7.5 m3, common for degreasing
    "passivation": 7500,           # 7.5 m3, as degreasing
    "chemical_etching": 7500,      # 7.5 m3, as pickling
    "conversion_coating": 3000,    # 3 m3, smaller for dip coating
}
DEFAULT_TANK_SIZE_L = 7500

# Active chemical of each bath
ACTIVE_CHEMICAL = {
    "pickling": "hydrochloric_acid",
    "alkaline_degreasing": "sodium_hydroxide",
    "passivation": "nitric_acid",
    "chemical_etching": "sodium_hydroxide",
}

BATH_DENSITY_KG_PER_L = 1.0      # dilute process baths (water-like)
REPLENISHMENT_PER_H = 0.001      # fraction of the active chemical replenished per hour (losses, degradation)
ROOM_TEMP_C = 20
HEATER_EFFICIENCY = 0.95

# U-values (W/m2.K) of tank walls
U_VALUES = {
    "bare_steel": 9.8,          # uninsulated steel tank
    "stainless_steel": 8.5,
    "fiberglass_5cm": 0.57,     # 5 cm fiberglass insulation
    "polyurethane_5cm": 0.45,
    "typical_insulated": 0.6,
}
TANK_U_VALUE = U_VALUES["typical_insulated"]

# Pre-/post-joining process parameters with min/max ranges.
# Material-specific fields are keyed by "steel" / "aluminium".
# acid_concentration_% is the mass fraction of active chemical: 0.05 = 5 wt%.
CHEM_PREPOST_PARAMS = {
    "alkaline_degreasing": {
        "standard": {"steel": "ASTM B183", "aluminium": "ASTM B254"},
        "parameters": {
            "steel": {
                "acid_concentration_%": {"min": 0.05, "max": 0.1},
                "water_consumption_l": {"min": 5.0, "max": 15.0},
                "temperature_C": {"min": 60, "max": 80},
                "time_min": {"min": 1, "max": 1},
            },
            "aluminium": {
                "acid_concentration_%": {"min": 0.03, "max": 0.1},
                "water_consumption_l": {"min": 3.0, "max": 10.0},
                "temperature_C": {"min": 50, "max": 70},
                "time_min": {"min": 1, "max": 1},
            },
        },
        "description": {
            "steel": "Remove oils, grease, and contaminants from steel surface",
            "aluminium": "Remove oxides and contaminants using alkaline solutions with inhibitors",
        },
    },
    "chemical_etching": {
        "standard": "ASTM B253",
        "parameters": {
            "aluminium": {
                "acid_concentration_%": {"min": 0.05, "max": 0.10},
                "water_consumption_l": {"min": 5.0, "max": 15.0},
                "time_min": {"min": 1, "max": 1},
                "temperature_C": {"min": 50, "max": 65},
            },
        },
        "description": "Alkaline (NaOH) etch of aluminium to remove the natural oxide layer and a thin surface layer",
    },
    "pickling": {
        "standard": "ASTM A380, ISO 16048",
        "parameters": {
            "steel": {
                "acid_concentration_%": {"min": .1, "max": 0.2},
                "hydrofluoric_acid_consumption_%": {"min": 0.01, "max": 0.02},  # not modelled yet
                "water_consumption_l": {"min": 10.0, "max": 25.0},
                "time_min": {"min": 1, "max": 1},
                "temperature_C": {"min": 20, "max": 50},
            },
        },
        "description": "Remove weld scale and oxides using acid solutions",
    },
    "passivation": {
        "standard": "ASTM A380, ASTM A967",
        "parameters": {
            "steel": {
                "acid_concentration_%": {"min": 0.2, "max": 0.4},
                "water_consumption_l": {"min": 5.0, "max": 10.0},
                "time_min": {"min": 1, "max": 1},
                "temperature_C": {"min": 20, "max": 50},
            },
        },
        "description": "Form protective oxide layer on stainless steel surface",
    },
}

# Mechanical treatments. Each value is the total consumed over one execution.
MECH_PREPOST_PARAMS = {
    "mechanical_treatment": {
        "standard": {"steel": "ISO 8501-1 (surface preparation)", "aluminium": "ISO 8501-1"},
        "parameters": {
            "steel": {
                "abrasive_consumption_kg": {"min": 0.01, "max": 0.05},
                "electricity_kwh": {"min": 0.1, "max": 0.4},
                "time_min": {"min": 1, "max": 1},
                "surface_area_m2": {"min": 0.5, "max": 2.0},
            },
            "aluminium": {
                "abrasive_consumption_kg": {"min": 0.005, "max": 0.02},
                "coolant_consumption_l": {"min": 0.5, "max": 2.0},
                "electricity_kwh": {"min": 0.05, "max": 0.2},
                "time_min": {"min": 1, "max": 1},
                "surface_area_m2": {"min": 0.3, "max": 1.5},
            },
        },
        "condition": {"steel": "if oxides/scale are present"},
        "note": {"aluminium": "Use non-ferrous tools with coolant"},
        "description": {
            "steel": "Remove oxides and scale using abrasive methods",
            "aluminium": "Surface preparation using non-ferrous tools with mandatory coolant",
        },
    },
    "machining": {
        "standard": "ISO 3685 (tool life)",
        "parameters": {
            "steel": {
                "time_min": {"min": 1, "max": 1},
                "tool_wear_pct": {"min": 5, "max": 15},
                "electricity_kwh": {"min": 0.05, "max": 0.2},
            },
        },
        "condition": "if tight tolerances are required",
        "description": "Precision machining for tight tolerance requirements",
    },
    "grinding_polishing": {
        "standard": {"steel": "ISO 16048, ASTM B912 (electropolishing)", "aluminium": "ISO 16048, ASTM B209"},
        "parameters": {
            "steel": {
                "grinding_wheel_consumption_kg": {"min": 0.005, "max": 0.02},
                "polishing_compound_kg": {"min": 0.01, "max": 0.05},
                "electricity_kwh": {"min": 0.1, "max": 0.5},
                "time_min": {"min": 1, "max": 1},
                "surface_roughness_um": {"min": 0.1, "max": 1.6},
            },
            "aluminium": {
                "grinding_wheel_consumption_kg": {"min": 0.002, "max": 0.01},
                "polishing_compound_kg": {"min": 0.005, "max": 0.02},
                "coolant_consumption_l": {"min": 0.1, "max": 0.5},
                "electricity_kwh": {"min": 0.05, "max": 0.2},
                "time_min": {"min": 1, "max": 1},
                "surface_roughness_um": {"min": 0.05, "max": 1.0},
            },
        },
        "condition": {"steel": "as needed for surface finish"},
        "note": {"aluminium": "Use non-ferrous tools with mandatory coolant"},
        "description": {
            "steel": "Achieve required surface finish and dimensional accuracy",
            "aluminium": "Final surface finishing using non-ferrous tools with coolant",
        },
    },
}

# Conversion of the mechanical parameters to ecoinvent units
COOLANT_DENSITY_KG_PER_L = 0.9     # density of the oil (lubricating oil proxy)
COOLANT_OIL_FRACTION = 0.05        # water-miscible coolant: emulsion with 5 % oil (5-9 % in practice)
COOLANT_LOSS_FRACTION = 0.10       # share of the coolant per execution that is lost (drag-out, mist) and topped up
TOOL_MASS_KG = 0.01   # about 10 g carbide indexable insert (typical 5-15 g), consumed at 100 % wear

# Parameter -> (flow, factor to the ecoinvent unit). Parameters without a flow are not modelled.
MECH_PARAMETER_FLOWS = {
    "electricity_kwh": ("electricity", 1.0),
    "abrasive_consumption_kg": ("abrasive", 1.0),
    "grinding_wheel_consumption_kg": ("grinding_wheel", 1.0),
    "polishing_compound_kg": ("polishing_compound", 1.0),
    "coolant_consumption_l": ("coolant", COOLANT_LOSS_FRACTION * COOLANT_OIL_FRACTION * COOLANT_DENSITY_KG_PER_L),  # kg oil per l
    "tool_wear_pct": ("tool_material", TOOL_MASS_KG / 100),   # % -> kg
}

bd.projects.set_current(PROJECT)
flows = {name: find_activity(BACKGROUND, *spec) if spec else None for name, spec in FLOWS.items()}

PREPOST_NAME = "Pre_and_Post_processes"

act_data = {}
for service, material, params, _ in per_material(CHEM_PREPOST_PARAMS):
    code = process_code(service, material)
    act_data[str((PREPOST_NAME, code))] = {
        "name": process_name(service, material), "unit": "min", "location": "NL",
        "exchanges": chemical_exchanges(
            PREPOST_NAME, code, params, flows[ACTIVE_CHEMICAL[service]], flows["electricity"], flows["water"],
            tank_volume_l=INDUSTRIAL_TANK_SIZES_L.get(service, DEFAULT_TANK_SIZE_L),
            replenishment_per_h=REPLENISHMENT_PER_H, bath_density_kg_per_l=BATH_DENSITY_KG_PER_L,
            room_temp_c=ROOM_TEMP_C, u_value=TANK_U_VALUE, heater_efficiency=HEATER_EFFICIENCY),
        LABOUR_FIELD: prepost_labour(params, OPERATOR_SHARE.get(service, CHEM_OPERATOR_SHARE)),
    }

parameter_flows = {p: (flows[f], factor) for p, (f, factor) in MECH_PARAMETER_FLOWS.items()}
for service, material, params, _ in per_material(MECH_PREPOST_PARAMS):
    code = process_code(service, material)
    exchanges, ignored = mechanical_exchanges(PREPOST_NAME, code, params, parameter_flows)
    ignored = [p for p in ignored if p != "time_min"]   # the process time gives the labour hours
    print(f"{code}: not modelled (no ecoinvent flow): {ignored}")
    act_data[str((PREPOST_NAME, code))] = {
        "name": process_name(service, material), "unit": "min", "location": "NL", "exchanges": exchanges,
        LABOUR_FIELD: prepost_labour(params, OPERATOR_SHARE.get(service, MECH_OPERATOR_SHARE))}

# prepost_db = bd.Database(PREPOST_NAME)
# prepost_db.write(act_data)
with open("prepostprocess_data.pkl", "wb") as f:
    pickle.dump(act_data, f, protocol=5)
