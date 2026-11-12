"""Operating costs per functional unit: consumables, personnel, and nominal OPEX.

- Consumable costs: price x amount of each direct input (electricity, gases, filler, chemicals).
- Personnel costs: labour hours of the process x labour cost per hour.
- Nominal OPEX: consumable costs + personnel costs.

A process stores its labour hours in the field `LABOUR_FIELD`, with one value per scenario.
A process without that field has 0 labour hours.
"""

import math

import pandas as pd

CONSUMABLE_COLUMN = "Consumable costs (EUR)"
PERSONNEL_COLUMN = "Personnel costs (EUR)"
OPEX_COLUMN = "Nominal OPEX (EUR)"
COST_COLUMNS = (CONSUMABLE_COLUMN, PERSONNEL_COLUMN, OPEX_COLUMN)
COST_UNITS = {column: "EUR" for column in COST_COLUMNS}

LABOUR_FIELD = "labour_h"

# Country codes of the Eurostat file that differ from the codes of the model (ISO 3166 / ecoinvent)
EUROSTAT_CODES = {"EL": "GR", "UK": "GB"}


def labour_range(low, high):
    """Labour hours of the minimum, amount (midpoint) and maximum scenarios."""
    if low > high:
        raise ValueError(f"Labour hours: minimum {low} is above maximum {high}")
    return {"minimum": low, "amount": (low + high) / 2, "maximum": high}


def labour_hours(process, scenario):
    """Labour hours of `process` in `scenario` (0 if the process has no labour hours)."""
    hours = process.get(LABOUR_FIELD) or {}
    return float(hours.get(scenario, 0.0))


def personnel_cost(process, scenario, wage):
    """Personnel cost (EUR) = labour hours x `wage` (EUR/h).

    A process without labour hours costs 0, also when `wage` is None or NaN.
    With labour hours and no wage, the cost is NaN (no data).
    """
    hours = labour_hours(process, scenario)
    if hours == 0:
        return 0.0
    if wage is None or (isinstance(wage, float) and math.isnan(wage)):
        return math.nan
    return hours * wage


def cost_values(consumable, personnel):
    """{cost column: value} with nominal OPEX = consumable + personnel."""
    return {CONSUMABLE_COLUMN: consumable, PERSONNEL_COLUMN: personnel, OPEX_COLUMN: consumable + personnel}


def read_labour_costs(path, sheet="labour_cost", baseline="RER", average="EU27_2020"):
    """Labour cost per hour of each country (EUR/h), from the Eurostat sheet of country_data.xlsx.

    The sheet has the country code in column A and the cost in column C.
    The `average` row (EU27 average) gets the label `baseline`.
    Countries without a value (confidential "C", or not available) are left out.
    """
    raw = pd.read_excel(path, sheet_name=sheet, header=None)
    codes = raw.iloc[:, 0].astype(str).str.strip()
    values = pd.to_numeric(raw.iloc[:, 2], errors="coerce")
    out = {}
    for code, value in zip(codes, values):
        if pd.isna(value):
            continue
        code = baseline if code == average else EUROSTAT_CODES.get(code, code)
        out[code] = float(value)
    if baseline not in out:
        raise ValueError(f"No {average!r} row in sheet {sheet!r} of {path}")
    return out
