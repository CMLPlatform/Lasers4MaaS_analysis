"""Product systems of the L4M R&D study (reference flow: 1 set of optimised welding parameters).

Each use case has 2 scenarios. A scenario is a sequence of rounds. Each round has
coupon welds, prototype welds, digital lab runs, optimization runs, CT-scan verifications
and sets of validation tests (the D13.1 tests of the prototype).
"""

import math
import re

import bw2data as bd

DBS = "Dynamic Beam Shaping"


def validation_test_sets(prototypes, prototypes_per_set=10):
    """Number of sets of validation tests for a number of prototype welds.

    One set of tests covers `prototypes_per_set` prototypes. The result is rounded up:
    a lab cannot do part of a set.
    """
    if prototypes_per_set <= 0:
        raise ValueError("prototypes_per_set must be positive")
    return math.ceil(prototypes / prototypes_per_set)


def make_round(coupon=0, prototype=0, digital=0, optimization=0, verification=1, tests=0):
    """Contents of one R&D round (counts per set of parameters).

    `verification` is the number of CT scans. `tests` is the number of sets of validation tests.
    """
    return dict(coupon=coupon, prototype=prototype, digital=digital,
                optimization=optimization, verification=verification, tests=tests)


class RDBuilder:
    """Collects the Brightway data of the R&D database, then writes it."""

    def __init__(self, name, background_name, include_material=True):
        self.name = name
        self.background_name = background_name
        self.include_material = include_material
        self.data = {}

    def sourcing(self, market):
        """Raw material sourcing: supplies 1 unit of a background material.

        The process that uses the material then is a pure service.
        """
        key = (self.name, "sourcing_" + market["code"])
        if key not in self.data:
            self.data[key] = {
                "name": "Raw material sourcing",
                "reference product": market.get("reference product") or market["name"],
                "unit": market["unit"], "location": market.get("location", "GLO"),
                "technology": "Raw material sourcing",
                "exchanges": [{"input": key, "amount": 1, "type": "production"},
                              {"input": market.key, "amount": 1, "type": "technosphere"}],
            }
        return key

    def copy(self, proc, suffix, technology, electricity=1.0, replace=None, drop=(), extra=(), sourcing=False):
        """Copy a process into the R&D database (same name, code + `suffix`).

        Args:
            electricity: factor on the electricity inputs.
            replace: {input key: other key}.
            drop: input keys to remove.
            extra: (key, amount) inputs to add.
            sourcing: move each aluminium input of the background database to a Raw material sourcing process.
                If `include_material` is False, remove these inputs instead.
        """
        key = (self.name, proc["code"] + suffix)
        prod = next(e["amount"] for e in proc.exchanges() if e["type"] == "production")
        exchanges = [{"input": key, "amount": prod, "type": "production"}]
        for e in proc.exchanges():
            if e["type"] == "production" or e["input"] in drop:
                continue
            # Lower case: BAFU names start with a capital ("Electricity, ...", "Aluminium ...")
            amount = e["amount"] * (electricity if "electricity" in e.input["name"].lower() else 1)
            target = (replace or {}).get(e["input"], e["input"])
            if (sourcing and e["type"] == "technosphere" and e.input["database"] == self.background_name
                    and "aluminium" in e.input["name"].lower()):
                if not self.include_material:
                    continue
                target = self.sourcing(e.input)
            exchanges.append({"input": target, "amount": amount, "type": e["type"]})
        exchanges += [{"input": k, "amount": a, "type": "technosphere"} for k, a in extra]
        self.data[key] = {"name": proc["name"], "reference product": proc.get("reference product"),
                          "unit": proc["unit"], "location": proc["location"], "technology": technology,
                          "exchanges": exchanges}
        return key

    def electricity_only(self, code, name, product, electricity, kwh, location="GLO"):
        """Process with one electricity input (for example an optimization run)."""
        key = (self.name, code)
        self.data[key] = {"name": name, "reference product": product, "unit": "unit", "location": location,
                          "exchanges": [{"input": key, "amount": 1, "type": "production"},
                                        {"input": electricity.key, "amount": kwh, "type": "technosphere"}]}
        return key

    def test_set(self, use_case, tests):
        """Set of validation tests of a use case: {test process key: number of tests}."""
        key = (self.name, f"{use_case} | validation tests")
        self.data[key] = {"name": "Validation tests", "reference product": "set of validation tests",
                          "unit": "unit", "location": "GLO",
                          "exchanges": [{"input": key, "amount": 1, "type": "production"}]
                          + [{"input": k, "amount": n, "type": "technosphere"} for k, n in tests.items() if n]}
        return key

    def system(self, use_case, scenario, rounds, inputs):
        """Product system of one use case and scenario, made of its rounds.

        `inputs` maps a round field (coupon, prototype, digital, optimization,
        verification, tests) to the key of the process that one count of it uses.
        """
        round_keys = []
        for round_name, counts in rounds.items():
            rkey = (self.name, f"{use_case} | {scenario} | {round_name}")
            exchanges = [{"input": rkey, "amount": 1, "type": "production"}]
            exchanges += [{"input": inputs[field], "amount": n, "type": "technosphere"}
                          for field, n in counts.items() if n]
            self.data[rkey] = {"name": round_name, "reference product": "round", "unit": "unit",
                               "location": "GLO", "exchanges": exchanges}
            round_keys.append(rkey)
        key = (self.name, f"{use_case} | {scenario}")
        self.data[key] = {"name": f"{use_case} | {scenario}", "reference product": "1 set of optimised parameters",
                          "unit": "set of parameters", "location": "GLO",
                          "exchanges": [{"input": key, "amount": 1, "type": "production"}]
                          + [{"input": k, "amount": 1, "type": "technosphere"} for k in round_keys]}
        return key

    def write(self):
        db = bd.Database(self.name)
        db.write(self.data)
        return db


def build_rd_database(name, background_name, l4m, metallurgic, use_cases, scenarios,
                      dbs_energy_factor, optimization_kwh, ct_scan_kwh, validation_tests=None,
                      include_material=True):
    """Write the R&D database and return {(use case, scenario): product system}.

    Args:
        l4m, metallurgic: {label: activity} of the imported packages.
        use_cases: {use case: its welding process}.
        scenarios: {use case: {scenario: {"joining": technology, "rounds": {round: make_round(...)}}}}.
        dbs_energy_factor: factor on the electricity of the DBS joining steps.
        optimization_kwh: electricity of one optimization run.
        ct_scan_kwh: electricity of one CT scan (scanner power x scan time).
        validation_tests: {use case: {test process key: tests per set}}. A use case without tests
            gets no "tests" input, whatever its rounds say.
        include_material: False removes the material inputs (aluminium of the coupons).
    """
    b = RDBuilder(name, background_name, include_material)

    # Coupon preparation: cutting and cleaning are services; the aluminium comes from Raw material sourcing
    met_cut, met_clean = metallurgic["01_Cutting"], metallurgic["02_Cleaning"]
    coupon_joining = l4m["001_Physical_Laser welding"]  # pulls in the cleaned and cut coupons
    cut = b.copy(met_cut, "_svc", "Cutting service", sourcing=True)
    clean = b.copy(met_clean, "_svc", "Cleaning service", replace={met_cut.key: cut})
    coupon = {
        "Standard laser": b.copy(coupon_joining, "_std", "Standard laser", replace={met_clean.key: clean}),
        DBS: b.copy(coupon_joining, "_DBS", DBS, dbs_energy_factor, replace={met_clean.key: clean}),
    }
    dbs_welding = {uc: b.copy(p, "_DBS", DBS, dbs_energy_factor) for uc, p in use_cases.items()}

    # Verification of the joined welds: CT scan only (non-destructive), with the electricity of the
    # L4M "CT-scan X-ray" process (GB grid) and the amount ct_scan_kwh
    ct = l4m["CT-scan X-ray"]
    ct_electricity = next(e.input for e in ct.exchanges()
                          if e["type"] == "technosphere" and "electricity" in e.input["name"].lower())
    ver_ct = b.electricity_only("ct_scan", "CT-scan X-ray", ct.get("reference product") or "Tested coupon",
                                ct_electricity, ct_scan_kwh, location=ct["location"])

    # Optimization of the welding parameters: electricity only
    electricity = next(e.input for e in l4m["Platform"].exchanges() if e["type"] == "technosphere")
    optimization = b.electricity_only("optimization", "Optimization", "optimization of the welding parameters",
                                      electricity, optimization_kwh)

    # One set of validation tests per use case (processes of the RD_validation_tests database)
    test_sets = {uc: b.test_set(uc, tests) for uc, tests in (validation_tests or {}).items() if tests}

    keys = {}
    for uc, scs in scenarios.items():
        for sc, spec in scs.items():
            dbs = spec["joining"] == DBS
            inputs = {"coupon": coupon[DBS if dbs else "Standard laser"],
                      "prototype": dbs_welding[uc] if dbs else use_cases[uc].key,
                      "digital": l4m["Digital lab processes"].key,
                      "optimization": optimization, "verification": ver_ct}
            rounds = spec["rounds"]
            if uc in test_sets:
                inputs["tests"] = test_sets[uc]
            else:
                rounds = {r: {**counts, "tests": 0} for r, counts in rounds.items()}
            keys[uc, sc] = b.system(uc, sc, rounds, inputs)
    db = b.write()
    return {k: db.get(key[1]) for k, key in keys.items()}


def standard_welds_left(flows, use_cases):
    """Names of standard-laser weld processes in the walked flows (none may remain in a DBS scenario)."""
    welds = {p["name"] for p in use_cases.values()}
    names = set()
    for f in flows:
        for key in f.path:
            act = bd.get_activity(key)
            if ("Laser welding" in act["name"] or act["name"] in welds) and act.get("technology") != DBS:
                names.add(act["name"])
    return names


def sankey_links(contributions, index, node_label):
    """Links of a Sankey from background inputs (left) through the foreground to the system (right).

    Args:
        contributions: list of (flow, impact array), from BackgroundImpacts.by_flow.
        index: position of the indicator in the impact arrays.
        node_label: function(key) -> label of a foreground process.

    Returns (labels, sources, targets, values). Negative links are left out: a Sankey cannot show them.
    """
    links = {}
    for flow, impact in contributions:
        name = flow.node["name"]
        leaf = f"{name[:40]} [input]" if flow.kind == "technosphere" else f"{name} [flow]"
        nodes = [leaf] + [node_label(k) for k in reversed(flow.path)]
        for a, b in zip(nodes[:-1], nodes[1:]):
            links[a, b] = links.get((a, b), 0.0) + impact[index]
    labels = list(dict.fromkeys(n for pair in links for n in pair))
    pos = [(labels.index(a), labels.index(b), v) for (a, b), v in links.items() if v > 0]
    return labels, [p[0] for p in pos], [p[1] for p in pos], [p[2] for p in pos]


def process_label(name, use_case_weld_names):
    """Plot label of a foreground process name."""
    if name in use_case_weld_names:
        return "Prototype joining"
    if name.startswith("04_Cutting"):
        return "Cutting (weld cross-sections)"
    label = re.sub(r"^\d+_(Physical_|Pyshical_)?", "", name)
    return "Coupon joining" if label == "Laser welding" else label
