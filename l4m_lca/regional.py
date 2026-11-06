"""Impacts and costs with the electricity market of each country.

Only the electricity changes. All other inputs keep their ecoinvent datasets and prices.
"""

import pandas as pd

from .constants import SCENARIOS
from .impacts import consumable_cost, foreground_flows
from .lcia import COST_COLUMN
from .project import category, find_activity

ELECTRICITY_MARKET_NAME = "market for electricity, medium voltage"


def electricity_markets(database, countries):
    """{country code: medium-voltage electricity market of that country} in `database`."""
    return {c: find_activity(database.name, ELECTRICITY_MARKET_NAME, c) for c in countries}


def regional_table(databases, impacts, markets, electricity_prices, prices, baseline, scenarios=SCENARIOS, foreground=None):
    """Impacts and consumable cost of each process, with each country's electricity market.

    Args:
        databases: Brightway databases whose processes are calculated.
        impacts: a BackgroundImpacts object.
        markets: {country code: electricity market}.
        electricity_prices: {country code: EUR/kWh}; it must also have `baseline`.
        prices: {activity key: EUR per unit} for the other inputs.
        baseline: label of the rows with the electricity as modelled (for example "RER").

    Returns a long table: database, process, key, scenario, country, indicator, impact.
    """
    foreground = set(foreground or [db.name for db in databases])
    categories = [category(m) for m in impacts.methods]
    rows = []
    for db in databases:
        for process in sorted(db, key=lambda a: a.key):
            for scenario in scenarios:
                flows = foreground_flows(process, foreground, scenario)
                for country, market in [(baseline, None), *markets.items()]:
                    base = dict(database=db.name, process=process["name"], key=process.key[1],
                                scenario=scenario, country=country)
                    for name, value in zip(categories, impacts.of_flows(flows, electricity=market)):
                        rows.append({**base, "indicator": name, "impact": value})
                    cost = consumable_cost(flows, prices, electricity_price=electricity_prices[country])
                    rows.append({**base, "indicator": COST_COLUMN, "impact": cost})
    return pd.DataFrame(rows)


def system_regional(systems, flows, impacts, markets, baseline):
    """{(system, country): impact array} for walked product systems.

    `flows` maps each system to its foreground flows. The `baseline` rows use the
    electricity as modelled.
    """
    out = {}
    for system in systems:
        out[system, baseline] = impacts.of_flows(flows[system])
        for country, market in markets.items():
            out[system, country] = impacts.of_flows(flows[system], electricity=market)
    return out
