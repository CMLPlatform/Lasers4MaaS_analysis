"""Checks against the real Brightway project. Skipped when the project or its databases are missing.

Run only these with: pytest -m brightway
"""

import numpy as np
import pytest

bd = pytest.importorskip("bw2data")

from l4m_lca.constants import (BACKGROUNDS, CHEM_PREPOST_DATABASE, L4M_SOLUTION_DATABASE, EU27_GB, L4M_DATABASE,
                               MECH_PREPOST_DATABASE, METALLURGIC_DATABASE, RD_DATABASE, RD_TESTS_DATABASE,
                               SOA_DATABASE)

PROJECT = BACKGROUNDS["ecoinvent"]["project"]
ECOINVENT = BACKGROUNDS["ecoinvent"]["database"]
UNIT_PROCESS_DATABASES = [SOA_DATABASE, L4M_SOLUTION_DATABASE, CHEM_PREPOST_DATABASE, MECH_PREPOST_DATABASE]
FOREGROUND = UNIT_PROCESS_DATABASES + [L4M_DATABASE, METALLURGIC_DATABASE, RD_TESTS_DATABASE, RD_DATABASE]

pytestmark = pytest.mark.brightway


@pytest.fixture(scope="module")
def setup():
    if PROJECT not in bd.projects:
        pytest.skip(f"Brightway project {PROJECT!r} not found")
    bd.projects.set_current(PROJECT)
    if ECOINVENT not in bd.databases:
        pytest.skip(f"{ECOINVENT} not in the project")
    from l4m_lca.impacts import BackgroundImpacts
    from l4m_lca.project import ef31_methods
    methods = ef31_methods()
    impacts = BackgroundImpacts(methods, next(iter(bd.Database(ECOINVENT))))
    return methods, impacts, {db for db in FOREGROUND if db in bd.databases}


def products(foreground):
    for name in sorted(foreground):
        if name == RD_DATABASE:
            yield from (a for a in bd.Database(name) if a.get("reference product") == "1 set of optimised parameters")
        elif name in UNIT_PROCESS_DATABASES:
            yield from bd.Database(name)


def test_engine_reproduces_bw2calc(setup):
    from l4m_lca.impacts import bw2calc_scores, foreground_flows
    methods, impacts, foreground = setup
    checked = 0
    for act in products(foreground):
        engine = impacts.of_flows(foreground_flows(act, foreground))
        assert np.allclose(engine, bw2calc_scores(act, methods), rtol=1e-6), act["name"]
        checked += 1
    if not checked:
        pytest.skip("No foreground databases in the project. Run the notebooks first.")


def test_joining_ranges_are_ordered(setup):
    from l4m_lca.impacts import scenario_amount
    for name in (SOA_DATABASE, L4M_SOLUTION_DATABASE):
        if name not in bd.databases:
            continue
        for act in bd.Database(name):
            for exc in act.technosphere():
                assert scenario_amount(exc, "minimum") <= scenario_amount(exc, "maximum"), act["name"]


def test_electricity_markets_exist(setup):
    from l4m_lca.regional import electricity_markets
    markets = electricity_markets(bd.Database(ECOINVENT), EU27_GB)
    assert len(markets) == 28
