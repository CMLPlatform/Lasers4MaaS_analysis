"""Scenario result tables of the foreground processes, and their export."""

import json
from pathlib import Path

import pandas as pd

from .constants import SCENARIOS
from .costs import CONSUMABLE_COLUMN, cost_values, personnel_cost
from .impacts import consumable_cost, electricity_kwh, foreground_flows
from .project import category

INDEX = ["Database", "Process", "Key", "Scenario"]
ELECTRICITY_COLUMN = "Electricity Consumption (kWh)"
COST_COLUMN = CONSUMABLE_COLUMN   # old name, kept for the notebooks that import it


def scenario_table(databases, impacts, prices, scenarios=SCENARIOS, foreground=None, wage=None):
    """Impacts, electricity and costs of each process in each scenario.

    Args:
        databases: Brightway databases whose processes are calculated.
        impacts: a BackgroundImpacts object.
        prices: {activity key: EUR per unit} for the consumable cost.
        foreground: database names to walk through (default: the names of `databases`).
        wage: labour cost (EUR/h) for the personnel cost. A process without labour hours costs 0.

    Returns one row per process and scenario. The impact columns have the category names.
    The cost columns are the consumable costs, the personnel costs and the nominal OPEX (their sum).
    """
    foreground = set(foreground or [db.name for db in databases])
    unpriced = set()
    rows = []
    for db in databases:
        for process in sorted(db, key=lambda a: a.key):
            for scenario in scenarios:
                flows = foreground_flows(process, foreground, scenario)
                row = {"Database": db.filename, "Process": process["name"], "Key": process.key[1], "Scenario": scenario}
                row.update(zip((category(m) for m in impacts.methods), impacts.of_flows(flows)))
                row[ELECTRICITY_COLUMN] = electricity_kwh(flows)
                row.update(cost_values(consumable_cost(flows, prices, warn=unpriced),
                                       personnel_cost(process, scenario, wage)))
                rows.append(row)
    for name in sorted(unpriced):
        print(f"WARNING: no price for {name!r}. Its cost is 0.")
    return pd.DataFrame(rows)


def with_units(table, units):
    """Copy of `table` with the unit in each impact column name, e.g. "acidification [mol H+-Eq]"."""
    return table.rename(columns={c: f"{c} [{u}]" for c, u in units.items() if u})


def export(table, units, results_dir, stem):
    """Write `table` (with units in the column names) as <stem>_LCIA_results.csv and .json."""
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    out = with_units(table, units)
    csv_file = results_dir / f"{stem}_LCIA_results.csv"
    json_file = results_dir / f"{stem}_LCIA_results.json"
    out.to_csv(csv_file, index=False)
    # json.dump keeps full precision (DataFrame.to_json rounds to 10 decimal places, so 6.5e-09 loses digits)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(out.to_dict(orient="records"), f, indent=2)
    print(f"Results saved to {csv_file} and {json_file}")
    return csv_file, json_file
