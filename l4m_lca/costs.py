"""Operating costs per functional unit: consumables, personnel, and nominal OPEX.

- Consumable costs: price x amount of each direct input (electricity, gases, filler, chemicals).
- Personnel costs: labour hours of the process x labour cost per hour.
- Nominal OPEX: consumable costs + personnel costs.

A process stores its labour hours in the field `LABOUR_FIELD`, with one value per scenario.
A process without that field has 0 labour hours.
"""

import math

import bw2data as bd
import pandas as pd

from .constants import (GB_LABOUR_COST_2025, KPI_COST_SHEETS, KPI_FILE, KPI_USE_CASE_NAMES, LABOUR_COST_FILE,
                        REGIONAL_BASELINE, USE_CASE_ORDER)
from .impacts import is_electricity

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


LABOUR_HOURS_COLUMN = "Labour (h)"


def price_of(node, prices, electricity_prices):
    """Price (EUR per unit) of a background input, or None if it has no price.

    Electricity uses the price of its location in `electricity_prices`. Any other input uses the
    first key of `prices` that is part of its lower-case name, so one table serves the ecoinvent
    and the BAFU names ("market for argon, liquid" and "Argon, liquid, at plant" both match "argon").
    """
    if is_electricity(node):
        return electricity_prices.get(node.get("location"))
    name = node["name"].lower()
    return next((price for key, price in prices.items() if key.lower() in name), None)


def system_costs(flows, executions, prices, electricity_prices, hours_per_unit, wage, name_of=None):
    """Operating costs of a product system: all its background inputs and 1 operator per process.

    Args:
        flows: background flows of the system (impacts.foreground_flows).
        executions: {foreground key: units supplied} (impacts.foreground_executions).
        prices, electricity_prices: see `price_of`.
        hours_per_unit: {process name: operator hours per unit of its reference product}.
        wage: labour cost (EUR/h).
        name_of: function(key) -> process name (default: the name of the Brightway activity).

    Returns (costs, unpriced, untimed). `costs` has the labour hours and the cost columns.
    `unpriced` names the background inputs without a price (they cost 0). `untimed` names the
    foreground processes that use background inputs directly but have no hours (they count 0 h).
    """
    consumable, unpriced, users = 0.0, set(), set()
    for f in flows:
        if f.kind != "technosphere":
            continue
        users.add(f.path[-1])
        price = price_of(f.node, prices, electricity_prices)
        if price is None:
            unpriced.add(f"{f.node['name']} [{f.node.get('location', '')}]")
        else:
            consumable += f.amount * price
    name_of = name_of or (lambda key: bd.get_activity(key)["name"])
    hours, untimed = 0.0, set()
    for key, units in executions.items():
        name = name_of(key)
        if name in hours_per_unit:
            hours += units * hours_per_unit[name]
        elif key in users:
            untimed.add(name)
    return {LABOUR_HOURS_COLUMN: hours, **cost_values(consumable, hours * wage)}, unpriced, untimed


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


def regional_labour_costs(path=LABOUR_COST_FILE, baseline=REGIONAL_BASELINE):
    """Labour cost per hour of the EU27 countries, the EU27 average (`baseline`) and GB (EUR/h).

    Eurostat values from `path`. GB is not in Eurostat after 2016: its value is in constants.py.
    """
    return {**read_labour_costs(path, baseline=baseline), **GB_LABOUR_COST_2025}


# Production costs of the KPI calculations (EUR per item), in stack order (bottom to top)
PRODUCTION_COSTS = ("Labour costs", "Consumables + energy costs", "Material costs", "Maintenance costs",
                    "Depreciation costs")
KPI_TECHNOLOGIES = ("SoA", "L4M")


def read_production_costs(path=KPI_FILE, sheets=KPI_COST_SHEETS, names=KPI_USE_CASE_NAMES, order=USE_CASE_ORDER):
    """Total production costs per item of each use case and technology, by cost type (EUR/item).

    Each sheet has a header row with "Name" in column B and one column per case, with the label
    "<technology> <use case>" (technology "SoA" or "L4M"). The cost breakdown is the block of rows
    that starts with "Labour costs" directly above "Consumables + energy costs".

    `names` renames the use cases to the names of the LCA notebooks. The rows follow `order`;
    use cases that are not in `order` come last, in sheet order.

    Returns a long table with the columns use_case, technology, cost and value.
    A use case without a SoA column (for example "Fusion plant pipe") has L4M rows only.
    """
    rows = []
    for sheet in sheets:
        raw = pd.read_excel(path, sheet_name=sheet, header=None)
        labels = raw.iloc[:, 1].astype(str).str.strip()
        header = raw.iloc[labels[labels == "Name"].index[0]]
        top = next((i for i in range(len(labels) - 1)
                    if labels.iloc[i] == PRODUCTION_COSTS[0] and labels.iloc[i + 1] == PRODUCTION_COSTS[1]), None)
        if top is None:
            raise ValueError(f"No production cost breakdown in sheet {sheet!r} of {path}")
        block = raw.iloc[top:top + len(PRODUCTION_COSTS)]
        if list(block.iloc[:, 1].str.strip()) != list(PRODUCTION_COSTS):
            raise ValueError(f"Sheet {sheet!r}: the cost rows are not {PRODUCTION_COSTS}")
        for col, label in header.items():
            technology, _, use_case = str(label).partition(" ")
            if technology not in KPI_TECHNOLOGIES:
                continue
            for cost, value in zip(PRODUCTION_COSTS, pd.to_numeric(block[col], errors="coerce")):
                use_case = use_case.strip()
                rows.append({"use_case": names.get(use_case, use_case), "technology": technology, "cost": cost,
                             "value": float(value)})
    out = pd.DataFrame(rows)
    rank = {u: i for i, u in enumerate(order)}
    key = out["use_case"].map(lambda u: rank.get(u, len(rank)))
    return out.iloc[key.argsort(kind="stable")].reset_index(drop=True)
