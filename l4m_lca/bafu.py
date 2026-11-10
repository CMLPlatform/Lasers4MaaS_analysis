"""Import of the BAFU LCI database (EcoSpold v1) as an alternative background.

Source: "Life Cycle Inventory database of the Swiss Federal Administration, BAFU:2026".
The data sets use the ecoinvent v2 names. The import maps the elementary flows to
the biosphere database of the project (ecoinvent-3.12-biosphere), so that the
ecoinvent EF 3.1 methods can characterise them. A flow without a match gets no
characterisation factor: check `unlinked_report` before you use the results.

Import the database one time, from the project folder:

    python -m l4m_lca.bafu [ECOSPOLD_DIR]
"""

import collections
import functools
import re
import sys
import time
from pathlib import Path

import bw2data as bd
import numpy as np
import pandas as pd
from bw2io.extractors.ecospold1 import Ecospold1DataExtractor
from bw2io.importers import SingleOutputEcospold1Importer
from bw2io.strategies import (link_iterable_by_fields, migrate_exchanges, normalize_biosphere_categories,
                              normalize_biosphere_names)
from lxml import objectify
from pyecospold.core import EcospoldLookupV1

from l4m_lca.constants import BACKGROUNDS

ECOSPOLD1_NAMESPACE = b'<ecoSpold xmlns="http://www.EcoInvent.org/EcoSpold01"'
TIMESTAMP = re.compile(rb'timestamp="(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)[^"]*"')
DATE_WITH_ZONE = re.compile(rb"(>\d{4}-\d\d-\d\d)[+-]\d\d:\d\d<")
EMPTY_ATTRIBUTE = re.compile(rb'\s[A-Za-z]+="(nan)?"')
EMPTY_TIME_PERIOD = re.compile(rb"<timePeriod([^>]*)/>")


class OpenLCAEcospold1Extractor(Ecospold1DataExtractor):
    """EcoSpold v1 extractor for the openLCA export of BAFU.

    The openLCA files are not valid against the EcoSpold01 schema: the root element has
    no namespace, dates are "YYYY-MM" and some elements are in another order. So this
    extractor adds the namespace and parses without schema validation.
    """

    @classmethod
    def process_file(cls, filepath, db_name):
        text = Path(filepath).read_bytes()
        if b"<ecoSpold>" in text:
            text = text.replace(b"<ecoSpold>", ECOSPOLD1_NAMESPACE + b">", 1)
        # Metadata timestamps: "2023-08-28T15:03:42.257+02:00" or "2025-09-04 18:38:45.97" -> "2023-08-28T15:03:42"
        text = TIMESTAMP.sub(rb'timestamp="\1T\2"', text)
        # Dates with a time zone: "2023-12-31+01:00" -> "2023-12-31"
        text = DATE_WITH_ZONE.sub(rb"\1<", text)
        # Empty or "nan" attributes (for example year="" of a literature source): leave them out
        text = EMPTY_ATTRIBUTE.sub(b"", text)
        # Empty time period: use 9999, the value that BAFU uses for "unknown" (metadata only)
        text = EMPTY_TIME_PERIOD.sub(rb"<timePeriod\1><startYear>9999</startYear><endYear>9999</endYear></timePeriod>", text)
        parser = objectify.makeparser(remove_blank_text=True)
        parser.set_element_class_lookup(EcospoldLookupV1())
        root = objectify.fromstring(text, parser)
        return [cls.process_dataset(ds, str(filepath), db_name) for ds in root.datasets if ds.tag != "comment"]


# openLCA compartment names (category, subcategory) -> ecoinvent 3 biosphere categories
OPENLCA_COMPARTMENTS = {
    "emissions to air": "air",
    "emissions to water": "water",
    "emissions to soil": "soil",
    "resources": "natural resource",
}
OPENLCA_SUBCOMPARTMENTS = {
    ("air", "low. pop."): "non-urban air or from high stacks",
    ("air", "high. pop."): "urban air close to ground",
    ("air", "indoor"): "urban air close to ground",
    ("air", "low. pop., long-term"): "low population density, long-term",
    ("air", "stratosphere + troposphere"): "lower stratosphere + upper troposphere",
    ("water", "river"): "surface water",
    ("water", "lake"): "surface water",
    ("water", "river, long-term"): "surface water",
    ("water", "groundwater"): "ground-",
    ("water", "groundwater, long-term"): "ground-, long-term",
    ("water", "fossilwater"): "fossil well",
}


def openlca_compartments_to_ecoinvent3(db):
    """Rename the openLCA biosphere compartments of BAFU to the ecoinvent 3 categories."""
    for ds in db:
        for exc in ds.get("exchanges", []):
            if exc.get("type") != "biosphere" or not exc.get("categories"):
                continue
            cats = list(exc["categories"])
            top = OPENLCA_COMPARTMENTS.get(cats[0], cats[0])
            sub = [OPENLCA_SUBCOMPARTMENTS.get((top, c), c) for c in cats[1:]]
            if top == "natural resource" and exc.get("name") == "Carbon dioxide, in air":
                sub = ["in air"]   # CO2 uptake is a resource "in air" in ecoinvent 3
            exc["categories"] = tuple([top] + sub)
    return db


# Names that ecoinvent changed after 3.3 (bw2io's biosphere-2-3 migration ends at 3.0-3.3 names)
RENAMES_AFTER_3_3 = {
    "Particulates, < 2.5 um": "Particulate Matter, < 2.5 um",
    "Particulates, > 10 um": "Particulate Matter, > 10 um",
    "Particulates, > 2.5 um, and < 10um": "Particulate Matter, > 2.5 um and < 10um",
    "NMVOC, non-methane volatile organic compounds, unspecified origin": "NMVOC, non-methane volatile organic compounds",
    "Ethene": "Ethylene",
    "Propene": "Propylene",
    "Ethyne": "Acetylene",
    "Xylene": "Xylenes, unspecified",
    "Chromium": "Chromium III",   # ASSUMPTION: unspecified chromium is trivalent (Chromium VI stays separate)
    "Carbon dioxide": "Carbon dioxide, fossil",     # ASSUMPTION: unspecified origin counted as fossil
    "Carbon monoxide": "Carbon monoxide, fossil",   # ASSUMPTION: unspecified origin counted as fossil
}
IONIC_FORM = r"^{name} (I|II|III|IV|V|VI|ion)$"


def _normal(label):
    """Lower case, letters and digits only: "Dioxin, 2,3,7,8 Tetrachlorodibenzo-p-" -> "dioxin2378tetrachlorodibenzop"."""
    return re.sub(r"[^a-z0-9]", "", label.lower())


def map_to_biosphere_names(db, biosphere):
    """Map the unlinked biosphere exchanges to the names and units of `biosphere`.

    1. Explicit renames after ecoinvent 3.3 (RENAMES_AFTER_3_3).
    2. Water flows in kg -> m3 (amount / 1000), and the openLCA suffix "/m3" is removed.
    3. Synonyms: the name, or one of its comma-separated parts ("HFC-134a"), equals a name or
       synonym of exactly one flow with the same compartment and unit (case and punctuation ignored).
    4. Ionic form: "Mercury" -> "Mercury II", if exactly one such flow has the same compartment and unit.
    Each exchange that changes gets "bafu_mapping" with the original name and unit.
    """
    index = collections.defaultdict(list)
    synonyms = collections.defaultdict(set)
    for flow in bd.Database(biosphere):
        cats, unit = tuple(flow["categories"]), flow["unit"]
        index[cats, unit].append(flow["name"])
        for label in [flow["name"], *(flow.get("synonyms") or [])]:
            synonyms[_normal(label), cats, unit].add(flow["name"])
    known = {(name, cats, unit) for (cats, unit), names in index.items() for name in names}

    def by_synonym(name, cats, unit):
        parts = [p.strip() for p in name.split(",")]
        labels = [name, *parts, ", ".join(parts[:-1])] if len(parts) > 1 else [name]
        for label in labels:
            hits = synonyms.get((_normal(label), cats, unit), set())
            if len(hits) == 1:
                return next(iter(hits))
        return None

    for ds in db:
        for exc in ds.get("exchanges", []):
            if exc.get("type") != "biosphere" or exc.get("input"):
                continue
            name, cats, unit = exc["name"], tuple(exc.get("categories") or ()), exc.get("unit")
            new_name, new_unit, factor = name.removesuffix("/m3"), unit, 1.0
            if name.endswith("/m3"):
                new_unit = "cubic meter"
            if new_name in RENAMES_AFTER_3_3:
                new_name = RENAMES_AFTER_3_3[new_name]
            if (new_name, cats, new_unit) not in known and new_name.startswith("Water") and new_unit == "kilogram":
                new_unit, factor = "cubic meter", 0.001
            if (new_name, cats, new_unit) not in known:
                new_name = by_synonym(new_name, cats, new_unit) or new_name
            if (new_name, cats, new_unit) not in known:
                pattern = re.compile(IONIC_FORM.format(name=re.escape(new_name)))
                ionic = [n for n in index.get((cats, new_unit), []) if pattern.match(n)]
                if len(ionic) == 1:
                    new_name = ionic[0]
            new_cats = cats
            if (new_name, cats, new_unit) not in known and len(cats) > 1:
                # 5. Fallback: the parent compartment ("air", unspecified), with the same rules
                parent = cats[:1]
                if (new_name, parent, new_unit) in known:
                    new_cats = parent
                elif by_synonym(new_name, parent, new_unit):
                    new_name, new_cats = by_synonym(new_name, parent, new_unit), parent
            if (new_name, new_cats, new_unit) != (name, cats, unit) and (new_name, new_cats, new_unit) in known:
                exc["bafu_mapping"] = {"name": name, "categories": cats, "unit": unit}
                exc["name"], exc["unit"], exc["categories"] = new_name, new_unit, new_cats
                if factor != 1.0:
                    exc["amount"] *= factor
                    for field in ("loc", "minimum", "maximum"):   # keep the uncertainty in the new unit
                        if field in exc and exc.get("uncertainty type") != 2:
                            exc[field] *= factor
                    if exc.get("uncertainty type") == 2 and "loc" in exc:
                        exc["loc"] += float(np.log(factor))
    return db


LOCATION_ALIASES = {"ENTSO": "ENTSO-E"}
# Units that openLCA wrote differently on the exchange and on the dataset (same quantity)
UNIT_ALIASES = {"cubic meter": "normal cubic meter"}   # ASSUMPTION: ecoinvent v2 gas volumes are standard m3


def repair_technosphere_links(db):
    """Repair technosphere exchanges that the openLCA export wrote inconsistently.

    - Location alias ("ENTSO" -> "ENTSO-E").
    - Unit alias ("cubic meter" -> "normal cubic meter"), when only the alias gives a dataset.
    - Empty location: the location of the only dataset with the same name, categories and unit.
      If more than one dataset matches, the exchange stays unlinked.
    """
    locations = collections.defaultdict(set)
    for ds in db:
        locations[ds["name"], tuple(ds.get("categories") or ()), ds["unit"]].add(ds["location"])
    for ds in db:
        for exc in ds.get("exchanges", []):
            if exc.get("type") != "technosphere":
                continue
            exc["location"] = LOCATION_ALIASES.get(exc.get("location"), exc.get("location"))
            key = (exc["name"], tuple(exc.get("categories") or ()))
            unit = exc.get("unit")
            if key + (unit,) not in locations and key + (UNIT_ALIASES.get(unit),) in locations:
                exc["unit"] = UNIT_ALIASES[unit]
            if not exc.get("location"):
                found = locations.get(key + (exc.get("unit"),), set())
                if len(found) == 1:
                    exc["location"] = next(iter(found))
    return db


def make_importer(ecospold_dir, db_name="BAFU-2026", biosphere=None):
    """Extract the EcoSpold v1 files and apply the linking strategies. Nothing is written yet."""
    biosphere = biosphere or bd.config.biosphere
    # one process: the base extractor sends work to its own class, not to this subclass
    importer = SingleOutputEcospold1Importer(str(ecospold_dir), db_name, use_mp=False,
                                             extractor=OpenLCAEcospold1Extractor)
    defaults = [s for s in importer.strategies
                if getattr(s, "func", s) not in (link_iterable_by_fields,)]
    # v2 -> v3 biosphere names and categories, then link to the project biosphere
    importer.strategies = defaults[:4] + [
        openlca_compartments_to_ecoinvent3,
        normalize_biosphere_categories,
        normalize_biosphere_names,
        functools.partial(migrate_exchanges, migration="fix-ecoinvent-flows-pre-35"),
        functools.partial(link_iterable_by_fields, other=bd.Database(biosphere), edge_kinds=["biosphere"]),
        functools.partial(map_to_biosphere_names, biosphere=biosphere),
        functools.partial(link_iterable_by_fields, other=bd.Database(biosphere), edge_kinds=["biosphere"]),
    ] + defaults[4:-1] + [repair_technosphere_links, defaults[-1]]   # the last default links the technosphere
    importer.apply_strategies()
    return importer


def unlinked_report(importer):
    """Unlinked exchanges as {(type, name, categories, unit): number of occurrences}."""
    out = collections.Counter()
    for ds in importer.data:
        for exc in ds.get("exchanges", []):
            if not exc.get("input"):
                out[(exc.get("type"), exc.get("name"), tuple(exc.get("categories") or ()), exc.get("unit"))] += 1
    return out


def drop_unlinked_and_write(importer):
    """Remove unlinked exchanges (they cannot be calculated) and write the database."""
    importer.drop_unlinked(i_am_reckless=True)
    importer.write_database()
    return bd.Database(importer.db_name)


DEFAULT_ECOSPOLD_DIR = ("/Users/francodonati/Library/CloudStorage/OneDrive-UniversiteitLeiden/1_CML/1_projects/"
                        "bafu_database/ecoSpold files")


def import_bafu(ecospold_dir=DEFAULT_ECOSPOLD_DIR):
    """Import BAFU-2026 into the Brightway project of the BAFU background.

    The project is a copy of the ecoinvent project (Lasers4MaaS), so that it has the
    EF 3.1 methods and ecoinvent-3.12-biosphere. The function writes a report of the
    exchanges that do not link (results/bafu/unlinked_exchanges.csv). These exchanges
    are removed: their impacts are missing from the BAFU results.
    """
    start = time.time()
    profile = BACKGROUNDS["bafu"]
    source_project = BACKGROUNDS["ecoinvent"]["project"]
    if profile["project"] not in bd.projects:
        bd.projects.set_current(source_project)
        bd.projects.copy_project(profile["project"], switch=False)
        print(f"Copied {source_project} to {profile['project']}")
    bd.projects.set_current(profile["project"])
    if profile["database"] in bd.databases:
        print(f"{profile['database']} is already in {profile['project']}. Delete it first to import it again.")
        return None

    importer = make_importer(ecospold_dir, profile["database"])
    importer.statistics()

    report = pd.DataFrame(
        [{"type": k[0], "name": k[1], "categories": "::".join(k[2]), "unit": k[3], "occurrences": n}
         for k, n in unlinked_report(importer).items()]
    ).sort_values(["type", "occurrences"], ascending=[True, False])
    out = Path(profile["results"])
    out.mkdir(parents=True, exist_ok=True)
    report.to_csv(out / "unlinked_exchanges.csv", index=False)
    print(report.groupby("type")[["occurrences"]].agg(["count", "sum"]))
    print(f"Report: {out / 'unlinked_exchanges.csv'}")

    db = drop_unlinked_and_write(importer)
    print(f"Wrote {len(db)} datasets to {db.name} in {time.time() - start:.0f} s")
    return db


if __name__ == "__main__":   # required: the extractor starts worker processes
    import_bafu(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ECOSPOLD_DIR)
