"""Reference data shared by the notebooks."""

SCENARIOS = ("minimum", "amount", "maximum")

# Background databases. Each has its own Brightway project and results folder,
# so that the results of the two backgrounds do not overwrite each other.
BACKGROUNDS = {
    "ecoinvent": {
        "project": "Lasers4MaaS",
        "database": "ecoinvent-3.12-cutoff",
        "results": "results",
        "country_electricity": "market for electricity, medium voltage",
    },
    "bafu": {
        "project": "Lasers4MaaS_BAFU",
        "database": "BAFU-2026",
        "results": "results/bafu",
        "country_electricity": "Electricity, medium voltage, at grid",
    },
}

# EU member states: ISO 3166 alpha-2 code (ecoinvent location) -> alpha-3 code (Plotly maps)
EU27 = {
    "AT": "AUT", "BE": "BEL", "BG": "BGR", "HR": "HRV", "CY": "CYP", "CZ": "CZE", "DK": "DNK",
    "EE": "EST", "FI": "FIN", "FR": "FRA", "DE": "DEU", "GR": "GRC", "HU": "HUN", "IE": "IRL",
    "IT": "ITA", "LV": "LVA", "LT": "LTU", "LU": "LUX", "MT": "MLT", "NL": "NLD", "PL": "POL",
    "PT": "PRT", "RO": "ROU", "SK": "SVK", "SI": "SVN", "ES": "ESP", "SE": "SWE",
}

# Industrial electricity prices, EUR/kWh. Source: Eurostat nrg_pc_205, 2025-S1,
# consumption band ID (2-20 GWh/yr), excluding VAT and recoverable taxes.
# "RER" is the EU27 average.
EUROSTAT_ELEC_PRICE_2025S1 = {
    "BE": 0.1659, "BG": 0.1206, "CZ": 0.1655, "DK": 0.126, "DE": 0.1932, "EE": 0.1302,
    "IE": 0.2357, "GR": 0.1811, "ES": 0.125, "FR": 0.1296, "HR": 0.1534, "IT": 0.203,
    "CY": 0.2267, "LV": 0.113, "LT": 0.1347, "LU": 0.1476, "HU": 0.1871, "MT": 0.1177,
    "NL": 0.1889, "AT": 0.1803, "PL": 0.1726, "PT": 0.123, "RO": 0.1633, "SI": 0.1456,
    "SK": 0.1782, "FI": 0.0697, "SE": 0.0838,
    "RER": 0.164,
}
