"""Product systems of the L4M R&D study (reference flow: 1 set of optimised welding parameters).

Each use case has 2 scenarios. A scenario is a sequence of rounds. Each round has
coupon welds, prototype welds, digital lab runs, optimization runs and verifications.
"""

import re

import bw2data as bd

DBS = "Dynamic Beam Shaping"


def make_round(coupon=0, prototype=0, digital=0, optimization=0, verification=1):
    """Contents of one R&D round (counts per set of parameters)."""
    return dict(coupon=coupon, prototype=prototype, digital=digital,
                optimization=optimization, verification=verification)


class RDBuilder:
    """Collects the Brightway data of the R&D database, then writes it."""

    def __init__(self, name, background_name):
        self.name = name
        self.background_name = background_name
        self.data = {}

    def sourcing(self, market):
        """Raw material sourcing: supplies 1 unit of an ecoinvent material.

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
            sourcing: move each ecoinvent aluminium input to a Raw material sourcing process.
        """
        key = (self.name, proc["code"] + suffix)
        prod = next(e["amount"] for e in proc.exchanges() if e["type"] == "production")
        exchanges = [{"input": key, "amount": prod, "type": "production"}]
        for e in proc.exchanges():
            if e["type"] == "production" or e["input"] in drop:
                continue
            amount = e["amount"] * (electricity if "electricity" in e.input["name"] else 1)
            target = (replace or {}).get(e["input"], e["input"])
            if (sourcing and e["type"] == "technosphere" and e.input["database"] == self.background_name
                    and "aluminium" in e.input["name"]):
                target = self.sourcing(e.input)
            exchanges.append({"input": target, "amount": amount, "type": e["type"]})
        exchanges += [{"input": k, "amount": a, "type": "technosphere"} for k, a in extra]
        self.data[key] = {"name": proc["name"], "reference product": proc.get("reference product"),
                          "unit": proc["unit"], "location": proc["location"], "technology": technology,
                          "exchanges": exchanges}
        return key

    def electricity_only(self, code, name, product, electricity, kwh):
        """Process with one electricity input (for example an optimization run)."""
        key = (self.name, code)
        self.data[key] = {"name": name, "reference product": product, "unit": "unit", "location": "GLO",
                          "exchanges": [{"input": key, "amount": 1, "type": "production"},
                                        {"input": electricity.key, "amount": kwh, "type": "technosphere"}]}
        return key

    def system(self, use_case, scenario, rounds, inputs):
        """Product system of one use case and scenario, made of its rounds.

        `inputs` maps a round field (coupon, prototype, digital, optimization,
        verification) to the key of the process that one count of it uses.
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


def build_rd_database(name, background_name, l4m, metallurgic, ct_scan, use_cases, scenarios,
                      dbs_energy_factor, optimization_kwh):
    """Write the R&D database and return {(use case, scenario): product system}.

    Args:
        l4m, metallurgic, ct_scan: {label: activity} of the imported packages.
        use_cases: {use case: its welding process}.
        scenarios: {use case: {scenario: {"joining": technology, "rounds": {round: make_round(...)}}}}.
        dbs_energy_factor: factor on the electricity of the DBS joining steps.
        optimization_kwh: electricity of one optimization run.
    """
    b = RDBuilder(name, background_name)

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

    # Verification of the joined welds (no extra weld or cleaning): cutting -> polishing -> etching -> CT-scan
    ct_cut = ct_scan["04_Cutting"]
    ct_weld = next(e.input for e in ct_cut.exchanges()
                   if e["type"] == "technosphere" and e.input["database"] == ct_cut["database"])
    polishing, etching = metallurgic["07_Polishing"], metallurgic["08_Etching"]
    ver_cut = b.copy(ct_cut, "_ver", "Verification", drop={ct_weld.key}, sourcing=True)
    ver_polish = b.copy(polishing, "_ver", "Verification", extra=[(ver_cut, 6)])
    ver_etch = b.copy(etching, "_ver", "Verification", replace={polishing.key: ver_polish})
    ver_ct = b.copy(l4m["CT-scan X-ray"], "_ver", "Verification", replace={ct_cut.key: ver_etch})

    # Optimization of the welding parameters: electricity only
    electricity = next(e.input for e in l4m["Platform"].exchanges() if e["type"] == "technosphere")
    optimization = b.electricity_only("optimization", "Optimization", "optimization of the welding parameters",
                                      electricity, optimization_kwh)

    keys = {}
    for uc, scs in scenarios.items():
        for sc, spec in scs.items():
            dbs = spec["joining"] == DBS
            inputs = {"coupon": coupon[DBS if dbs else "Standard laser"],
                      "prototype": dbs_welding[uc] if dbs else use_cases[uc].key,
                      "digital": l4m["Digital lab processes"].key,
                      "optimization": optimization, "verification": ver_ct}
            keys[uc, sc] = b.system(uc, sc, spec["rounds"], inputs)
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
