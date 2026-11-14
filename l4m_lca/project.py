"""Brightway project setup, impact method selection and activity lookup."""

import os
from dataclasses import dataclass

import bw2data as bd
import bw2io as bi
from bw2data.errors import UnknownObject
from bw2io import BW2Package

from .constants import BACKGROUNDS

BACKGROUND_VARIABLE = "L4M_BACKGROUND"   # environment variable that selects the background

# EF 3.1 indicators that the notebooks report (matched as substrings of the method name)
DEFAULT_INDICATORS = [
    "climate change: total",
    "particulate matter formation",
    "acidification",
    "eutrophication: terrestrial",
    "photochemical oxidant formation: human health",
    "human toxicity: carcinogenic",
]


@dataclass(frozen=True)
class Background:
    """Settings of one background database (see constants.BACKGROUNDS)."""

    name: str                  # "ecoinvent" or "bafu"
    project: str               # Brightway project
    database: str              # background database in that project
    results: str               # results folder
    country_electricity: str   # name of the electricity market of each country


def select_background(default="ecoinvent"):
    """Background settings. The environment variable L4M_BACKGROUND overrides `default`."""
    name = os.environ.get(BACKGROUND_VARIABLE) or default
    if name not in BACKGROUNDS:
        raise ValueError(f"Unknown background {name!r}: use one of {sorted(BACKGROUNDS)}")
    return Background(name=name, **BACKGROUNDS[name])


def open_project(project, background="ecoinvent-3.12-cutoff", version="3.12", system_model="cutoff"):
    """Set the current project and return the background database.

    If the project does not have an ecoinvent background, import that ecoinvent release.
    Any other background (for example BAFU) must be imported first (see l4m_lca.bafu).
    """
    bd.projects.set_current(project)
    if background not in bd.databases:
        if not background.startswith("ecoinvent-"):
            raise RuntimeError(f"Project {project!r} has no database {background!r}. "
                               "Import it first, for example with l4m_lca.bafu.import_bafu.")
        bi.import_ecoinvent_release(version=version, system_model=system_model)
    return bd.Database(background)


def ensure_package(db_name, package_file, force=False):
    """Import a .bw2package file, unless the database already holds activities.

    With `force`, delete the database and import it again.
    """
    if db_name in bd.databases and len(bd.Database(db_name)) > 0 and not force:
        print(f"{db_name}: {len(bd.Database(db_name))} activities already in the project, import skipped.")
        return
    if db_name in bd.databases:
        del bd.databases[db_name]
    BW2Package.import_file(str(package_file))
    print(f"{db_name}: imported {len(bd.Database(db_name))} activities from {package_file}")


def drop_inputs_from(db_name, source):
    """Delete the exchanges of database `db_name` whose input is in database `source`.

    Returns the number of deleted exchanges. A second call deletes nothing.
    """
    doomed = [e for act in bd.Database(db_name) for e in act.exchanges()
              if e["type"] != "production" and e["input"][0] == source]
    for e in doomed:
        e.delete()
    return len(doomed)


def check_links(db_names):
    """Raise UnknownObject if an exchange links to a missing activity. Then process the databases."""
    for name in db_names:
        for act in bd.Database(name):
            for exc in act.exchanges():
                exc.input
        bd.Database(name).process()


def relink_background(db_names, source, target, links):
    """Point each input from database `source` to its counterpart in database `target`.

    Use it for imported packages that link to ecoinvent, in a project with another background.
    `links` maps (source name, location) -> (target name, location).
    It makes no change if one input has no link or a different unit: it raises KeyError or ValueError.
    Inputs that are already relinked stay as they are, so a second call does nothing.

    Returns {(source name, location): number of relinked exchanges}.
    """
    exchanges = [e for name in db_names for act in bd.Database(name) for e in act.exchanges()
                 if e["type"] != "production" and e.input["database"] == source]
    missing = sorted({(e.input["name"], e.input["location"]) for e in exchanges} - set(links))
    if missing:
        raise KeyError(f"No {target} link for these {source} inputs: {missing}")
    counterparts = {k: find_activity(target, *v) for k, v in links.items()}
    for e in exchanges:
        new = counterparts[e.input["name"], e.input["location"]]
        if new["unit"] != e.input["unit"]:
            raise ValueError(f"Unit of {e.input['name']!r} ({e.input['unit']}) differs from "
                             f"{new['name']!r} ({new['unit']})")
    counts = {}
    for e in exchanges:
        old = (e.input["name"], e.input["location"])
        e["input"] = counterparts[old].key
        e.save()
        counts[old] = counts.get(old, 0) + 1
    return counts


def background_inputs(db_names, foreground):
    """Names of the databases (other than `foreground` and biosphere) that `db_names` take inputs from."""
    return {e.input["database"] for name in db_names for act in bd.Database(name)
            for e in act.technosphere() if e.input["database"] not in foreground}


def ef31_methods(indicators=DEFAULT_INDICATORS):
    """EF 3.1 methods whose name contains one of `indicators` (long-term variants excluded)."""
    return [
        m for m in bd.methods
        if ("EF v3.1" in str(m) or "EF 3.1" in str(m))
        and "no LT" not in str(m)
        and any(indicator in str(m) for indicator in indicators)
    ]


def category(method):
    """Impact category name of a method: the third element of the method tuple."""
    return method[2]


def method_units(methods):
    """Map impact category -> unit, from the method metadata."""
    return {category(m): bd.Method(m).metadata.get("unit", "") for m in methods}


def short(name):
    """Category name without the "(EF v3.1 - IPCC 2021)" suffix, for plot titles."""
    return name.split(" (EF")[0]


def find_activity(database, name, location, reference_product=None, suggest=False):
    """Return the one activity with this exact name and location (and reference product).

    Raises UnknownObject if no activity matches, MultipleResults if more than one matches.
    With `suggest`, a missing activity gives None and a printed list of candidates instead.
    """
    filters = {"database": database, "name": name, "location": location}
    if reference_product is not None:
        filters["product"] = reference_product
    try:
        return bd.get_node(**filters)
    except UnknownObject:
        if not suggest:
            raise
    words = name.replace("market group for ", "").replace("market for ", "").split(",")[0]
    hits = bd.Database(database).search(words, limit=8)
    print(f"NOT FOUND: {(name, location)}. Candidates: {[(a['name'], a['location']) for a in hits]}")
    return None
