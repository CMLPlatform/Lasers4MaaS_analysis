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

# United Kingdom (ISO code GB). Eurostat has no recent UK prices or labour costs (none after Brexit),
# so the UK values come from UK sources, converted to EUR with ECB reference rates.
# They are close to the Eurostat definitions, but not the same statistics.
EU27_GB = {**EU27, "GB": "GBR"}

# ECB reference rates GBP per EUR (series EXR.M.GBP.EUR.SP00.A), mean of the monthly averages.
# Source: https://data-api.ecb.europa.eu/service/data/EXR/M.GBP.EUR.SP00.A (accessed 2026-11-12)
GBP_PER_EUR_2025S1 = 0.84232   # January-June 2025
GBP_PER_EUR_2025 = 0.85661     # January-December 2025

# Industrial electricity price, GB, 2025-S1 (EUR/kWh).
# Source: DESNZ, "Gas and electricity prices in the non-domestic sector", table 3.4.2 (prices including
# the Climate Change Levy, excluding VAT), size band "Medium" (2,000-19,999 MWh/yr, as Eurostat band ID).
# Mean of 2025 Q1 (27.276 p/kWh) and Q2 (25.809 p/kWh) = 26.542 p/kWh, published 2026-09-29.
# https://www.gov.uk/government/statistical-data-sets/gas-and-electricity-prices-in-the-non-domestic-sector
# The Climate Change Levy is included because Eurostat includes non-recoverable taxes and levies.
GB_ELEC_PRICE_GBP_PER_KWH_2025S1 = (0.27276237 + 0.2580856) / 2
GB_ELEC_PRICE_2025S1 = {"GB": round(GB_ELEC_PRICE_GBP_PER_KWH_2025S1 / GBP_PER_EUR_2025S1, 4)}   # 0.3151

# Labour cost per hour, GB, 2025, manufacturing (EUR/h).
# Level: Eurostat lc_lci_lev, UK 2016 (last UK value), NACE C, D1_D4_MD5 = 21.8 GBP/h.
# Growth 2016-2025: ONS "Labour costs and labour income, UK" (published 2026-08-18), table 3, average labour
# compensation per hour worked (ALCH) index, section C: 79.4559 (2016) -> 116.1182 (2025).
# https://www.ons.gov.uk/economy/economicoutputandproductivity/productivitymeasures/datasets/labourcostsandlabourshare
# 21.8 x 116.1182 / 79.4559 = 31.86 GBP/h. (The ONS ALCH level itself, 34.18 GBP/h in 2025, is not used:
# in 2016 it was 7 % above the Eurostat level, because the definitions differ.)
GB_LABOUR_COST_GBP_2025 = 21.8 * 116.1182 / 79.4559
GB_LABOUR_COST_2025 = {"GB": round(GB_LABOUR_COST_GBP_2025 / GBP_PER_EUR_2025, 1)}   # 37.2

# Regional analysis: baseline label (EU27 average) and industrial electricity price of each country (EUR/kWh)
REGIONAL_BASELINE = "RER"
REGIONAL_ELEC_PRICE = {**EUROSTAT_ELEC_PRICE_2025S1, **GB_ELEC_PRICE_2025S1}

# Prices of the pre- and post-joining inputs, per ecoinvent unit of each flow (pre_post.ipynb, L4M_R&D.ipynb).
# INDICATIVE PLACEHOLDER PRICES except electricity: replace with supplier quotes. Chemicals are per kg of
# ACTIVE substance, as modelled (ecoinvent "without water" datasets), so they are higher than the diluted
# commercial price.
PREPOST_PRICES = {
    "electricity":        EUROSTAT_ELEC_PRICE_2025S1["RER"],   # EUR/kWh, Eurostat 2025-S1, band ID, EU27 average (0.164)
    "water":              0.004,  # EUR/kg, tap water with discharge (about 4 EUR/m3)
    "sodium_hydroxide":   0.50,   # EUR/kg
    "hydrochloric_acid":  0.25,   # EUR/kg
    "nitric_acid":        0.45,   # EUR/kg
    "abrasive":           1.50,   # EUR/kg, alumina grit
    "polishing_compound": 1.50,   # EUR/kg, alumina proxy
    "grinding_wheel":     2.50,   # EUR/kg, silicon carbide proxy
    "coolant":            2.00,   # EUR/kg, lubricating oil proxy
    "tool_material":      60.0,   # EUR/kg, tungsten carbide
}
# Eurostat labour cost per hour (lc_lci_lev 2025, NACE C): sheet "labour_cost" of this file
LABOUR_COST_FILE = "Input_data/country_data.xlsx"
# KPI calculations of the project (costs per item of each use case, SoA and L4M-solution)
KPI_FILE = "Input_data/KPI_calculations.xlsx"
KPI_COST_SHEETS = ("Comp-usecase1", "Comp-usecase2")   # aluminium and stainless steel use cases
# Use case names of the KPI file -> names of the LCA notebooks (joining_task, workflow_assembly)
KPI_USE_CASE_NAMES = {"Fuel tank pipe": "Fuel tank", "Pharma shelve": "Freeze Dryers Shelf"}
# Order of the use cases in the figures (as in the LCA notebooks; Fusion plant pipe is in the KPI file only)
USE_CASE_ORDER = ("Heat exchanger", "Fuel tank", "Heterogeneous pipe", "Freeze Dryers Shelf", "Battery cooling plate",
                  "Fusion plant pipe")

# Foreground databases that the notebooks write
SOA_DATABASE = "State_of_the_Art"                       # joining_task.ipynb
L4M_SOLUTION_DATABASE = "L4M_solution"                   # joining_task.ipynb
L4M_SOLUTION_TECHNOLOGY = "L4M-solution"                 # Lasers4MaaS solution: technology of its processes (joining and R&D)
CHEM_PREPOST_DATABASE = "Chemical_Pre_and_Post_processes"     # pre_post.ipynb
MECH_PREPOST_DATABASE = "Mechanical_Pre_and_Post_processes"   # pre_post.ipynb
RD_TESTS_DATABASE = "RD_validation_tests"               # rd_tests.ipynb
RD_DATABASE = "L4M_RD_parameter_sets"                   # L4M_R&D.ipynb

# Stems of the result files: lcia.export writes <stem>_LCIA_results.csv and .json
JOINING_STEM = f"{SOA_DATABASE}_{L4M_SOLUTION_DATABASE}"
PREPOST_STEM = f"{CHEM_PREPOST_DATABASE}_{MECH_PREPOST_DATABASE}"
MATERIAL_STEM = "Material_production"
RD_TESTS_STEM = RD_TESTS_DATABASE

# Brightway packages of the R&D study (folder databases/): database name -> package file
PACKAGE_DIR = "databases"
L4M_DATABASE = "L4M system"
METALLURGIC_DATABASE = "Mettalurgic test (CIVAN)"   # spelling as stored in the packages
CT_SCAN_DATABASE = "CT-scan test"                   # needed only to import L4M system
PACKAGE_FILES = {
    CT_SCAN_DATABASE: "CT-scan test.bw2package",
    METALLURGIC_DATABASE: "Metallurgic test (CIVAN).bw2package",
    L4M_DATABASE: "L4M_database.bw2package",
}
