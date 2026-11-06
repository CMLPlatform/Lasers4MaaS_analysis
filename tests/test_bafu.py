"""BAFU import repairs (no Brightway project needed)."""

import pytest

from l4m_lca.bafu import (DATE_WITH_ZONE, EMPTY_ATTRIBUTE, EMPTY_TIME_PERIOD, TIMESTAMP,
                          openlca_compartments_to_ecoinvent3, repair_technosphere_links)


def test_text_repairs():
    assert TIMESTAMP.sub(rb'timestamp="\1T\2"', b'timestamp="2023-08-28T15:03:42.257+02:00"') == \
        b'timestamp="2023-08-28T15:03:42"'
    assert TIMESTAMP.sub(rb'timestamp="\1T\2"', b'timestamp="2025-09-04 18:38:45.979289"') == \
        b'timestamp="2025-09-04T18:38:45"'
    assert DATE_WITH_ZONE.sub(rb"\1<", b"<endDate>2023-12-31+01:00</endDate>") == b"<endDate>2023-12-31</endDate>"
    assert EMPTY_ATTRIBUTE.sub(b"", b'<source year="" title="x" volumeNo="nan"/>') == b'<source title="x"/>'
    assert EMPTY_TIME_PERIOD.sub(rb"<timePeriod\1><startYear>9999</startYear><endYear>9999</endYear></timePeriod>",
                                 b'<timePeriod a="1"/>') == \
        b'<timePeriod a="1"><startYear>9999</startYear><endYear>9999</endYear></timePeriod>'


@pytest.mark.parametrize("name, cats, expected", [
    ("Methane, fossil", ("emissions to air", "low. pop."), ("air", "non-urban air or from high stacks")),
    ("Methane, fossil", ("emissions to air", "high. pop."), ("air", "urban air close to ground")),
    ("Zinc", ("emissions to water", "river"), ("water", "surface water")),
    ("Zinc", ("emissions to water", "groundwater, long-term"), ("water", "ground-, long-term")),
    ("Copper", ("emissions to soil", "agricultural"), ("soil", "agricultural")),
    ("Carbon dioxide, in air", ("resources", "biotic"), ("natural resource", "in air")),
])
def test_openlca_compartments(name, cats, expected):
    db = [{"exchanges": [{"type": "biosphere", "name": name, "categories": cats}]}]
    assert openlca_compartments_to_ecoinvent3(db)[0]["exchanges"][0]["categories"] == expected


def test_repair_technosphere_links():
    grid = {"name": "Electricity, medium voltage, production ENTSO-E, at grid", "categories": ["electricity", "production mix"],
            "unit": "kilowatt hour", "location": "ENTSO-E", "exchanges": []}
    gas = {"name": "Natural gas, at production", "categories": ["natural gas", "production"],
           "unit": "normal cubic meter", "location": "NL", "exchanges": []}
    user = {"name": "user", "categories": [], "unit": "kg", "location": "CH", "exchanges": [
        {"type": "technosphere", "name": grid["name"], "categories": ("electricity", "production mix"),
         "unit": "kilowatt hour", "location": ""},
        {"type": "technosphere", "name": grid["name"], "categories": ("electricity", "production mix"),
         "unit": "kilowatt hour", "location": "ENTSO"},
        {"type": "technosphere", "name": gas["name"], "categories": ("natural gas", "production"),
         "unit": "cubic meter", "location": "NL"},
    ]}
    repaired = repair_technosphere_links([grid, gas, user])[2]["exchanges"]
    assert [e["location"] for e in repaired] == ["ENTSO-E", "ENTSO-E", "NL"]
    assert repaired[2]["unit"] == "normal cubic meter"
