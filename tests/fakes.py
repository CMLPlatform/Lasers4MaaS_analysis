"""Small stand-ins for Brightway nodes and exchanges, so that unit tests need no project."""

import itertools

_ids = itertools.count(1)


class Node(dict):
    """Activity or biosphere flow: dict access for fields, plus key, id and exchanges()."""

    def __init__(self, database, code, name, **fields):
        super().__init__(database=database, code=code, name=name, **fields)
        self.key = (database, code)
        self.id = next(_ids)
        self._exchanges = []

    def add(self, node, amount, kind="technosphere", **fields):
        self._exchanges.append(Exchange(node, amount, kind, **fields))
        return self

    def exchanges(self):
        return list(self._exchanges)


class Exchange(dict):
    def __init__(self, node, amount, kind, **fields):
        super().__init__(input=node.key, amount=amount, type=kind, **fields)
        self.input = node


def process(database, code, name, production=1.0):
    node = Node(database, code, name)
    node.add(node, production, "production")
    return node


class FakeImpacts:
    """BackgroundImpacts stand-in with fixed unit impacts: {node id: [values]}."""

    def __init__(self, unit_values, methods=None):
        from l4m_lca.impacts import BackgroundImpacts
        n = len(next(iter(unit_values.values())))
        self.methods = methods or [("m", "EF v3.1", f"category {i}", "u") for i in range(n)]
        self._unit = {k: list(v) for k, v in unit_values.items()}
        self.of_flows = BackgroundImpacts.of_flows.__get__(self)
        self.by_flow = BackgroundImpacts.by_flow.__get__(self)

    def unit(self, node, kind="technosphere"):
        import numpy as np
        return np.array(self._unit[node.id], dtype=float)
