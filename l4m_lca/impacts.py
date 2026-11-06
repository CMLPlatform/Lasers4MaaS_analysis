"""Linear LCIA engine.

The foreground (the processes that the notebooks write or import) is small. The
background (ecoinvent) is large and does not change. So the engine:

1. Walks each foreground process down to its background inputs and biosphere flows
   (`foreground_flows`), with the amounts of one scenario.
2. Calculates the impact of 1 unit of each background input one time (`BackgroundImpacts`).
3. Multiplies and adds.

The result is the same as a regular bw2calc LCA, because an LCA is linear in the
foreground amounts. `bw2calc_scores` gives the regular result, for checks.
The engine never changes the stored exchanges.
"""

import re
from dataclasses import dataclass

import bw2data as bd
import numpy as np
from bw2calc import LCA

SCENARIO_FIELDS = {"minimum": ("minimum", "min"), "amount": ("amount",), "maximum": ("maximum", "max")}

ELECTRICITY_MARKET = re.compile(r"market (group )?for electricity, medium voltage")


def scenario_amount(exchange, scenario):
    """Amount of an exchange in a scenario ("minimum", "amount" or "maximum").

    An exchange without a minimum or maximum uses its amount in all scenarios.
    """
    return next((exchange[f] for f in SCENARIO_FIELDS[scenario] if f in exchange), exchange["amount"])


def is_electricity(node):
    """True for a medium-voltage electricity market (or market group)."""
    return bool(ELECTRICITY_MARKET.match(node["name"]))


@dataclass(frozen=True)
class Flow:
    """One background input or biosphere flow, per 1 unit of the demanded process."""

    path: tuple   # keys of the foreground processes, from the demanded process to the direct user
    node: object  # background activity or biosphere flow
    kind: str     # "technosphere" or "biosphere"
    amount: float


def production_amount(activity):
    return next(e["amount"] for e in activity.exchanges() if e["type"] == "production")


def foreground_flows(activity, foreground, scenario="amount", amount=1.0, path=()):
    """Walk the foreground below `activity` and return its background flows.

    `foreground` is a set of database names. An input from one of these databases
    is walked further; any other input is a background flow.
    Amounts are scaled to `amount` units of the reference product of `activity`.
    """
    path = path + (activity.key,)
    scale = amount / production_amount(activity)
    flows = []
    for exc in activity.exchanges():
        kind = exc["type"]
        if kind == "production":
            continue
        if kind not in ("technosphere", "biosphere"):
            raise ValueError(f"{activity['name']}: exchange type {kind!r} is not supported")
        value = scale * scenario_amount(exc, scenario)
        node = exc.input
        if kind == "technosphere" and node["database"] in foreground:
            flows.extend(foreground_flows(node, foreground, scenario, value, path))
        else:
            flows.append(Flow(path, node, kind, value))
    return flows


def lca_for(demand, method):
    """bw2calc LCA object for a {node: amount} demand, with the data that bw2data supplies."""
    fu, data_objs, remapping = bd.prepare_lca_inputs(demand, method=method)
    return LCA(fu, data_objs=data_objs, remapping_dicts=remapping)


def _factors(method):
    """Characterisation factors of a method: {biosphere flow id: factor}."""
    out = {}
    for row in bd.Method(method).load():
        flow, cf = row[0], row[1]
        if isinstance(flow, (tuple, list)):  # (database, code) key
            flow = bd.get_node(database=flow[0], code=flow[1]).id
        out[flow] = out.get(flow, 0.0) + (cf["amount"] if isinstance(cf, dict) else cf)
    return out


def bw2calc_scores(activity, methods, amount=1.0):
    """Regular bw2calc scores of `amount` units of `activity`, one per method."""
    lca = lca_for({activity: amount}, methods[0])
    lca.lci()
    scores = []
    for method in methods:
        lca.switch_method(method)
        lca.lcia()
        scores.append(lca.score)
    return np.array(scores)


class BackgroundImpacts:
    """Impact of 1 unit of each background activity or biosphere flow, one value per method.

    Builds one LCA of the background database, factorises the technosphere matrix one
    time and keeps one characterisation matrix per method. Each new activity then
    needs one back-substitution only. Results are kept in memory.
    """

    def __init__(self, methods, background):
        """`background` is any activity of the background database (for example ecoinvent)."""
        self.methods = list(methods)
        self._lca = lca_for({background: 1}, self.methods[0])
        self._lca.lci(factorize=True)
        # Characterisation matrices are diagonal: keep the factors as one row per method
        rows = []
        for method in self.methods:
            self._lca.switch_method(method)
            rows.append(self._lca.characterization_matrix.diagonal())
        self._cfs = np.vstack(rows)
        self._bio_factors = None
        self._memo = {}

    def unit(self, node, kind="technosphere"):
        """Impacts of 1 unit of `node` (an array with one value per method)."""
        if (node.id, kind) not in self._memo:
            self._memo[node.id, kind] = self._technosphere(node) if kind == "technosphere" else self._biosphere(node)
        return self._memo[node.id, kind]

    def _technosphere(self, node):
        if node.id not in self._lca.dicts.activity:
            raise KeyError(f"{node['name']!r} ({node['database']}) is not in the background database. "
                           "Add its database to the foreground set.")
        self._lca.redo_lci({node.id: 1})
        emissions = np.asarray(self._lca.inventory.sum(axis=1)).ravel()  # total of each biosphere flow
        return self._cfs @ emissions

    def _biosphere(self, node):
        if self._bio_factors is None:
            self._bio_factors = [_factors(m) for m in self.methods]
        return np.array([factors.get(node.id, 0.0) for factors in self._bio_factors])

    def of_flows(self, flows, electricity=None):
        """Total impacts of `flows`. With `electricity`, every electricity input uses that market."""
        total = np.zeros(len(self.methods))
        for flow in flows:
            node = electricity if electricity is not None and flow.kind == "technosphere" and is_electricity(flow.node) else flow.node
            total += flow.amount * self.unit(node, flow.kind)
        return total

    def by_flow(self, flows, electricity=None):
        """Impacts of each flow: a list of (flow, array with one value per method)."""
        out = []
        for flow in flows:
            node = electricity if electricity is not None and flow.kind == "technosphere" and is_electricity(flow.node) else flow.node
            out.append((flow, flow.amount * self.unit(node, flow.kind)))
        return out


def direct_inputs(flows):
    """Flows that the demanded process uses directly (not through another foreground process)."""
    return [f for f in flows if len(f.path) == 1 and f.kind == "technosphere"]


def electricity_kwh(flows):
    """Electricity that the demanded process uses directly (kWh)."""
    return sum(f.amount for f in direct_inputs(flows) if is_electricity(f.node))


def consumable_cost(flows, prices, electricity_price=None, warn=None):
    """Cost (EUR) of the direct technosphere inputs.

    `prices` maps an activity key to its price per unit of that activity.
    With `electricity_price`, every electricity input uses that price.
    An input without a price costs 0. Its name goes into the `warn` set, if one is given.
    """
    total = 0.0
    for f in direct_inputs(flows):
        if electricity_price is not None and is_electricity(f.node):
            total += f.amount * electricity_price
        elif f.node.key in prices:
            total += f.amount * prices[f.node.key]
        elif warn is not None:
            warn.add(f.node["name"])
    return total
