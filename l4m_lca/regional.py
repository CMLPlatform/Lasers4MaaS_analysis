"""Impacts and costs with the electricity market of each country.

Only the electricity changes. All other inputs keep their ecoinvent datasets and prices.
"""

import pandas as pd

from .constants import SCENARIOS
from .costs import cost_values, labour_hours, personnel_cost
from .impacts import consumable_cost, foreground_flows
from .project import category, find_activity

from bw2data.errors import UnknownObject

ELECTRICITY_MARKET_NAME = "market for electricity, medium voltage"


def electricity_markets(database, countries, name=ELECTRICITY_MARKET_NAME):
    """{country code: medium-voltage electricity market of that country} in `database`.

    `name` is the name of the country datasets (ecoinvent 3: the default; BAFU:
    "Electricity, medium voltage, at grid"). A country without a dataset is left out, with a warning.
    """
    markets = {}
    for country in countries:
        try:
            markets[country] = find_activity(database.name, name, country)
        except UnknownObject:
            print(f"WARNING: no {name!r} for {country} in {database.name}. The country is left out.")
    return markets


def regional_table(databases, impacts, markets, electricity_prices, prices, baseline, scenarios=SCENARIOS,
                   foreground=None, wages=None):
    """Impacts and costs of each process, with each country's electricity market and labour cost.

    Args:
        databases: Brightway databases whose processes are calculated.
        impacts: a BackgroundImpacts object.
        markets: {country code: electricity market}.
        electricity_prices: {country code: EUR/kWh}; it must also have `baseline`.
        prices: {activity key: EUR per unit} for the other inputs.
        baseline: label of the rows with the electricity as modelled (for example "RER").
        wages: {country code: labour cost in EUR/h}, with `baseline`. A process with labour hours
            in a country without a labour cost gets NaN personnel costs and nominal OPEX.

    Returns a long table: database, process, key, scenario, country, indicator, impact.
    The cost indicators are the consumable costs, the personnel costs and the nominal OPEX.
    """
    wages = wages or {}
    foreground = set(foreground or [db.name for db in databases])
    no_wage = set()
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
                    consumable = consumable_cost(flows, prices, electricity_price=electricity_prices[country])
                    if country not in wages and labour_hours(process, scenario):
                        no_wage.add(country)
                    personnel = personnel_cost(process, scenario, wages.get(country))
                    for name, value in cost_values(consumable, personnel).items():
                        rows.append({**base, "indicator": name, "impact": value})
    if no_wage:
        print(f"WARNING: no labour cost for {', '.join(sorted(no_wage))}. "
              "Their personnel costs and nominal OPEX are NaN (no data).")
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
