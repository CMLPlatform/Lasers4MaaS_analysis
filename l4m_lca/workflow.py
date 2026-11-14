"""Assembly of the full workflow of each product: material, pre-joining, joining, post-joining.

The inputs are the result tables that joining_task.ipynb and pre_post.ipynb export.
"""

import json
from pathlib import Path

import pandas as pd

from .joining import technology_of
from .lcia import INDEX
from .project import category

STAGES = ("mat", "pre", "join", "post")
STAGE_TITLES = {"mat": "Material", "pre": "Pre-joining", "join": "Joining", "post": "Post-joining"}
CONFIG_STAGE = {"pre_joining": "pre", "post_joining": "post"}


def read_results(path):
    """Read an exported LCIA result file (.json) as a DataFrame."""
    with open(path, encoding="utf-8") as f:
        return pd.DataFrame(json.load(f))


def base_name(column):
    """Column name without the unit suffix: "acidification [mol H+-Eq]" -> "acidification"."""
    return column.split(" [")[0]


def unit_of(column):
    return column.split("[")[-1].rstrip("]") if "[" in column else ""


def indicator_columns(table):
    return [c for c in table.columns if c not in INDEX]


def material_table(markets, impacts, units, database_name):
    """Impacts of 1 unit (kg) of each material market, in the format of the exported results."""
    rows = []
    for material, node in markets.items():
        row = {"Database": database_name, "Process": f"{node['name']} [{node['location']}]",
               "Key": material, "Scenario": "amount", "Functional unit": f"1 {node['unit']}"}
        for method, value in zip(impacts.methods, impacts.unit(node)):
            row[f"{category(method)} [{units[category(method)]}]"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def mean_part_weight(config, case):
    """Mean of the min and max part weight (kg) of a case, or None if the product has none."""
    weight = config["process_parameters"].get(case, {}).get("part_weight_kg")
    return None if weight is None else (weight["min"] + weight["max"]) / 2


def step_rows(prepost, step, material):
    """Rows of a pre/post step for a material. The key is "<step>_<material>" (or "<step>")."""
    keys = {step, f"{step}_{material}"}
    return prepost[prepost["Key"].isin(keys) & prepost["Process"].str.lower().str.contains(material.lower())]


def _value(rows, column, scenario):
    """Value of `column` (matched without its unit) in the row of `scenario`, or 0."""
    rows = rows[rows["Scenario"] == scenario]
    match = [c for c in rows.columns if base_name(c) == base_name(column)]
    if rows.empty or not match:
        return 0.0
    return float(rows[match[0]].iloc[0])


def enabled_steps(config):
    """(stage, step) of each enabled pre- and post-joining step, in configuration order."""
    return [(CONFIG_STAGE[stage], step) for stage in CONFIG_STAGE for step, on in config[stage].items() if on]


def workflow_table(workflows, joining, prepost, material, case, scenario="amount", include_material=True):
    """Contribution of each step to each product and joining technology.

    Args:
        workflows: PRODUCT_WORKFLOWS (material, enabled steps and part weight of each product).
        joining, prepost, material: exported result tables (DataFrames).
        case: "prototype" or "production"; it selects the part weight of the material stage.
        scenario: "minimum", "amount" or "maximum".
        include_material: False removes the material stage ("mat") from the table.

    Returns a long table: product, technology, stage, step, indicator, value.
    A step without data counts as 0, with a warning.
    """
    indicators = indicator_columns(joining)
    rows = []
    for product, config in workflows.items():
        mat = config["material"]
        steps = []
        if include_material:
            weight = mean_part_weight(config, case)
            mat_rows = material[material["Key"] == mat]
            if weight is None or mat_rows.empty:
                print(f"WARNING: no part weight or material LCIA for {product}. Material stage = 0.")
            steps.append(("mat", "material production", mat_rows, weight or 0.0))
        for stage, step in enabled_steps(config):
            found = step_rows(prepost, step, mat)
            if found.empty:
                print(f"WARNING: no LCIA data for '{step}' ({mat}) in {product}. Plotted as 0.")
            steps.append((stage, step, found, 1.0))

        for process, join_rows in joining[joining["Key"] == product].groupby("Process", sort=False):
            tech = technology_of(process)
            for indicator in indicators:
                for stage, step, found, factor in steps:
                    # the material table has one "amount" row per kg
                    sc = "amount" if stage == "mat" else scenario
                    rows.append(dict(product=product, technology=tech, stage=stage, step=step,
                                     indicator=indicator, value=factor * _value(found, indicator, sc)))
                rows.append(dict(product=product, technology=tech, stage="join", step="joining",
                                 indicator=indicator, value=_value(join_rows, indicator, scenario)))
    return pd.DataFrame(rows)


def cumulative_regional(workflows, reg_joining, reg_prepost, scenario="amount"):
    """Regional impact of pre-joining + joining + post-joining of each product and technology.

    The material stage is not included. Returns: product, technology, country, indicator, impact.
    """
    reg_prepost = reg_prepost[reg_prepost["scenario"] == scenario]
    reg_joining = reg_joining[reg_joining["scenario"] == scenario]
    parts = []
    for product, config in workflows.items():
        mat = config["material"]
        prepost = []
        for _, step in enabled_steps(config):
            sel = reg_prepost[reg_prepost["key"].isin({step, f"{step}_{mat}"})
                              & reg_prepost["process"].str.lower().str.contains(mat.lower())]
            if sel.empty:
                print(f"WARNING: no regional data for '{step}' ({mat}) in {product}. Counted as 0.")
            prepost.append(sel.groupby(["country", "indicator"])["impact"].sum())
        prepost = pd.concat(prepost).groupby(level=[0, 1]).sum() if prepost else pd.Series(dtype=float)

        for process, grp in reg_joining[reg_joining["key"] == product].groupby("process", sort=False):
            # NaN (no data, e.g. no labour cost for a country) stays NaN; a missing pre/post row counts as 0
            joined = grp.groupby(["country", "indicator"])["impact"].sum(min_count=1)
            total = joined + prepost.reindex(joined.index, fill_value=0.0)
            parts.append(total.rename("impact").reset_index().assign(product=product, technology=technology_of(process)))
    return pd.concat(parts, ignore_index=True)


def write_json(table, path):
    """Write `table` as a JSON list of records, with full float precision."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(table.to_dict(orient="records"), f, indent=2)


def cost_table(workflow, cost_columns):
    """Costs per product and technology: one column per (cost indicator, stage), plus the total of each indicator."""
    costs = workflow[workflow["indicator"].isin(cost_columns)]
    table = costs.pivot_table(index=["product", "technology"], columns=["indicator", "stage"], values="value",
                              aggfunc="sum", sort=False)
    for col in cost_columns:
        table[(col, "total")] = table[col].sum(axis=1)
    return table[[k for col in cost_columns for k in table.columns if k[0] == col]]
