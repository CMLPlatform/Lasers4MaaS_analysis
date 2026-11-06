"""Import BAFU-2026 into the Brightway project of the BAFU background.

Usage:
    python import_bafu.py [ECOSPOLD_DIR]

The project is a copy of the ecoinvent project (Lasers4MaaS), so that it has the
EF 3.1 methods and ecoinvent-3.12-biosphere. The script writes a report of the
exchanges that do not link (results/bafu/unlinked_exchanges.csv). These exchanges
are removed: their impacts are missing from the BAFU results.
"""

import sys
import time
from pathlib import Path

import bw2data as bd
import pandas as pd

from l4m_lca.bafu import drop_unlinked_and_write, make_importer, unlinked_report
from l4m_lca.constants import BACKGROUNDS

DEFAULT_DIR = ("/Users/francodonati/Library/CloudStorage/OneDrive-UniversiteitLeiden/1_CML/1_projects/"
               "bafu_database/ecoSpold files")


def main(ecospold_dir):
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
        return

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


if __name__ == "__main__":   # required: the extractor starts worker processes
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DIR)
