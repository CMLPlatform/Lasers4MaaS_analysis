
CHEM_PREPOST_PARAMS = {
"alkaline_degreasing": {
            "standard": {
                "steel": "ASTM B183",
                "aluminium": "ASTM B254",
            },
            "parameters": {
                "steel": {
                    "acid_concentration_%": {"min": 0.05, "max": 0.1},
                    "water_consumption_l": {"min": 5.0, "max": 15.0},
                    "temperature_C": {"min": 60, "max": 80},
                    "time_min": {"min": 5, "max": 15},
                },
                "aluminium": {
                    "acid_concentration_%": {"min": 0.03, "max": 0.1},
                    "water_consumption_l": {"min": 3.0, "max": 10.0},
                    "temperature_C": {"min": 50, "max": 70},
                    "time_min": {"min": 8, "max": 20},
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
                    "time_min": {"min": 2, "max": 10},
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
                    "hydrofloric_acid_consumption_%": {"min": 0.01, "max": 0.02},
                    "water_consumption_l": {"min": 10.0, "max": 25.0},
                    "time_min": {"min": 10, "max": 30},
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
                    "time_min": {"min": 20, "max": 30},
                    "temperature_C": {"min": 20, "max": 50},
                },
            },
            "description": "Form protective oxide layer on stainless steel surface",
        },
}

MECH_PREPOST_PARAMS = {
"mechanical_treatment": {
            "standard": {
                "steel": "ISO 8501-1 (surface preparation)",
                "aluminium": "ISO 8501-1",
            },
            "parameters": {
                "steel": {
                    "abrasive_consumption_kg": {"min": 0.01, "max": 0.05},
                    "electricity_kwh": {"min": 0.1, "max": 0.4},
                    "time_min": {"min": 5, "max": 20},
                    "surface_area_m2": {"min": 0.5, "max": 2.0},
                },
                "aluminium": {
                    "abrasive_consumption_kg": {"min": 0.005, "max": 0.02},
                    "coolant_consumption_l": {"min": 0.5, "max": 2.0},
                    "electricity_kwh": {"min": 0.05, "max": 0.2},
                    "time_min": {"min": 3, "max": 15},
                    "surface_area_m2": {"min": 0.3, "max": 1.5},
                },
            },
            "condition": {
                "steel": "if oxides/scale are present",
            },
            "note": {
                "aluminium": "Use non-ferrous tools with coolant",
            },
            "description": {
                "steel": "Remove oxides and scale using abrasive methods",
                "aluminium": "Surface preparation using non-ferrous tools with mandatory coolant",
            },
        },
"machining": {
            "standard": "ISO 3685 (tool life)",
            "parameters": {
                "steel": {
                    "machining_time_min": {"min": 1, "max": 5},
                    "tool_wear_pct": {"min": 5, "max": 15},
                    "electricity_kwh": {"min": 0.05, "max": 0.2},
                },
            },
            "condition": "if tight tolerances are required",
            "description": "Precision machining for tight tolerance requirements",
        },
"grinding_polishing":{
            "standard": {
                "steel": "ISO 16048, ASTM B912 (electropolishing)",
                "aluminium": "ISO 16048, ASTM B209",
            },
            "parameters": {
                "steel": {
                    "grinding_wheel_consumption_kg": {"min": 0.005, "max": 0.02},
                    "polishing_compound_kg": {"min": 0.01, "max": 0.05},
                    "electricity_kwh": {"min": 0.1, "max": 0.5},
                    "time_min": {"min": 5, "max": 25},
                    "surface_roughness_um": {"min": 0.1, "max": 1.6},
                },
                "aluminium": {
                    "grinding_wheel_consumption_kg": {"min": 0.002, "max": 0.01},
                    "polishing_compound_kg": {"min": 0.005, "max": 0.02},
                    "coolant_consumption_l": {"min": 0.1, "max": 0.5},
                    "electricity_kwh": {"min": 0.05, "max": 0.2},
                    "time_min": {"min": 3, "max": 15},
                    "surface_roughness_um": {"min": 0.05, "max": 1.0},
                },
            },
            "condition": {
                "steel": "as needed for surface finish",
            },
            "note": {
                "aluminium": "Use non-ferrous tools with mandatory coolant",
            },
            "description": {
                "steel": "Achieve required surface finish and dimensional accuracy",
                "aluminium": "Final surface finishing using non-ferrous tools with coolant",
            },
        }
}

# convert pre/post parameter dictionary  (run once)
import json

def pick(value, material):
    """Fields may be a per-material dict or a single value shared by all materials."""
    return value.get(material) if isinstance(value, dict) else value

out = {}
for source in (CHEM_PREPOST_PARAMS, MECH_PREPOST_PARAMS):
    for process, spec in source.items():
        for material, params in spec["parameters"].items():
            entry = {
                "parameters": {
                    name: [rng["min"], rng["max"]] for name, rng in params.items()
                }
            }
            for key in ("standard", "description", "condition", "note"):
                if key in spec:
                    val = pick(spec[key], material)
                    if val is not None:
                        entry[key] = val
            out.setdefault(material, {})[process] = entry

with open("process_defaults.json", "w") as f:
    json.dump(out, f, indent=2)
