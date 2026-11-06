"""Comparison of the results of two background databases (for example ecoinvent and BAFU)."""

from pathlib import Path

import pandas as pd

from .lcia import INDEX
from .workflow import base_name, read_results


def long_results(path, label):
    """Exported LCIA results as a long table: Process, Key, Scenario, indicator, value, background."""
    table = read_results(path)
    value_cols = [c for c in table.columns if c not in INDEX and c != "Functional unit"]
    out = table.melt(id_vars=[c for c in INDEX if c in table.columns], value_vars=value_cols,
                     var_name="indicator", value_name="value")
    out["indicator"] = out["indicator"].map(base_name)
    out["background"] = label
    return out.drop(columns=["Database"], errors="ignore")


def compare(dir_a, dir_b, stem, label_a="ecoinvent", label_b="bafu", scenario="amount"):
    """Results of `stem` in both result folders, side by side, with the ratio b / a.

    Returns: Process, Key, indicator, <label_a>, <label_b>, ratio.
    """
    file = f"{stem}_LCIA_results.json" if not stem.endswith(".json") else stem
    a = long_results(Path(dir_a) / file, label_a)
    b = long_results(Path(dir_b) / file, label_b)
    # Joining results share a Key (use case) between technologies, so the process name is part of the match.
    # Material results name the background market in Process, so they match on Key only.
    same_process = set(a["Process"]) == set(b["Process"])
    keys = (["Process"] if same_process else []) + ["Key", "indicator"] + (["Scenario"] if "Scenario" in a.columns else [])
    merged = a.merge(b, on=keys, suffixes=("_a", "_b"))
    if len(merged) != len(a) or len(merged) != len(b):
        raise ValueError(f"{stem}: rows do not match one to one ({len(a)} vs {len(b)} -> {len(merged)})")
    if "Scenario" in merged.columns:
        merged = merged[merged["Scenario"] == scenario]
    process = merged["Process"] if same_process else merged["Key"]
    out = pd.DataFrame({
        "Process": process, "Key": merged["Key"], "indicator": merged["indicator"],
        label_a: merged["value_a"], label_b: merged["value_b"],
    })
    out["ratio"] = out[label_b] / out[label_a]
    return out.reset_index(drop=True)


def unit_comparison(pairs, impacts_a, impacts_b, categories):
    """Impacts of 1 unit of matching background activities in both databases.

    `pairs` maps a label to (activity in a, activity in b). The two BackgroundImpacts
    objects must use the same methods. Returns: input, indicator, a, b, ratio.
    """
    rows = []
    for label, (node_a, node_b) in pairs.items():
        for cat, va, vb in zip(categories, impacts_a.unit(node_a), impacts_b.unit(node_b)):
            rows.append({"input": label, "indicator": cat, "a": va, "b": vb, "ratio": vb / va if va else float("nan")})
    return pd.DataFrame(rows)
