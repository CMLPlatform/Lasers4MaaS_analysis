# Lasers4MaaS – LCA models

Brightway 2.5 life cycle assessment (LCA) of laser joining and of the processes before and after joining.
The study compares State of the Art (SoA) joining with Dynamic Beam Shaping (DBS) for 5 use cases: Heat exchanger, Fuel tank, Heterogeneous pipe, Freeze Dryers Shelf and Battery cooling plate.

## Structure

- The **notebooks** hold the model parameters and show the results.
- The **`l4m_lca` package** holds the calculation code that the notebooks share.
- The **`tests` folder** holds the tests of the package.

Run the notebooks in this order:

```
joining_task.ipynb ─┐  results/*_LCIA_results.json
                    ├─> results/regional_*.csv      ─> workflow_assembly.ipynb
pre_post.ipynb ─────┘

L4M_R&D.ipynb        (independent)
database_explorer.ipynb (independent)
background_comparison.ipynb (after the 3 notebooks above ran with both backgrounds)
```

## Background databases

`joining_task`, `pre_post`, `workflow_assembly` and `L4M_R&D` run with one of 2 background databases. Set `BACKGROUND` in the notebook, or the environment variable `L4M_BACKGROUND`.

| `BACKGROUND` | Project | Database | Results |
|---|---|---|---|
| `"ecoinvent"` (default) | `Lasers4MaaS` | `ecoinvent-3.12-cutoff` | `results/` |
| `"bafu"` | `Lasers4MaaS_BAFU` | `BAFU-2026` | `results/bafu/` |

The profiles are in `l4m_lca/constants.py` (`BACKGROUNDS`). The activity names of each background are parameters in the notebooks.

### BAFU-2026

BAFU-2026 is the free LCI database of the Swiss Federal Administration (EcoSpold v1, exported by openLCA, ecoinvent v2 names). Cite it as "Life Cycle Inventory database of the Swiss Federal Administration, BAFU:2026".

To import it, run `python -m l4m_lca.bafu` one time (optional argument: the folder of the EcoSpold files). The import copies `Lasers4MaaS` to `Lasers4MaaS_BAFU` (for the EF 3.1 methods) and imports BAFU there. `l4m_lca/bafu.py` repairs the openLCA export:

- It adds the EcoSpold01 namespace and normalises the timestamps, dates and empty attributes, then parses without schema validation.
- It maps the openLCA compartments and the old flow names to `ecoinvent-3.12-biosphere`: renames after ecoinvent 3.3, synonyms, ionic forms ("Mercury" → "Mercury II"), water kg → m³, and the parent compartment as a fallback.
- It repairs technosphere links with an empty location, the location "ENTSO", and "cubic meter" vs "normal cubic meter".

**Assumptions:** unspecified "Chromium" is "Chromium III". "Carbon dioxide" and "Carbon monoxide" without origin are fossil. Gas "cubic meter" is "normal cubic meter".

**Import quality:** 96.6% of the biosphere exchanges and 99.99% of the technosphere exchanges link. The rest (mainly resources, noise and PM10) are removed. See `results/bafu/unlinked_exchanges.csv`.

**Limits:** BAFU has no electricity data set for Cyprus and Malta, and no tungsten carbide (tool wear is not modelled with BAFU).

## Notebooks

### `joining_task.ipynb`
Unit processes of the joining step. Functional unit: 1 joined unit.

| | |
|---|---|
| **Parameters** | Joining parameters per use case and technology (power, speed, joint length, gas flow, as min/max ranges), the SoA technology of each use case, `COST_FACTORS`, the background activities and the regional electricity prices. |
| **Processing** | Writes the `State_of_the_Art` and `Dynamic_Beam_Shaping` databases. Calculates the impacts for the minimum, amount and maximum scenarios, and the consumable costs. The regional analysis replaces the RER electricity with the market of each EU member state. |
| **Outputs** | The 2 databases. `results/State_of_the_Art_Dynamic_Beam_Shaping_LCIA_results.csv` and `.json`. `results/regional_joining.csv`. Bar charts and regional maps. |

### `pre_post.ipynb`
Unit processes of the chemical and mechanical treatments before and after joining, per material. Functional unit: 1 execution of the process.

| | |
|---|---|
| **Parameters** | `CHEM_PREPOST_PARAMS`, `MECH_PREPOST_PARAMS`, tank sizes, U-values, bath and heater assumptions, the background activities (`FLOWS`, with the proxies of the mechanical flows) and `COST_FACTORS` (indicative placeholder prices, except electricity). |
| **Processing** | Writes the `Chemical_Pre_and_Post_processes` and `Mechanical_Pre_and_Post_processes` databases. Calculates the scenario impacts, costs and the regional analysis, as in `joining_task.ipynb`. |
| **Outputs** | The 2 databases. `results/Chemical_Pre_and_Post_processes_Mechanical_Pre_and_Post_processes_LCIA_results.csv` and `.json`. `results/regional_prepost.csv`. Regional maps. |

### `workflow_assembly.ipynb`
Adds up material, pre-joining, joining and post-joining for each product and joining technology.

| | |
|---|---|
| **Parameters** | `PRODUCT_WORKFLOWS` (material, enabled steps and part weights of each product), `MATERIAL_MARKETS`, `SCENARIO`, `MATERIAL_CASE` and `INCLUDE_MATERIAL`. |
| **Inputs** | The result files of `joining_task.ipynb` and `pre_post.ipynb`. |
| **Outputs** | `results/Material_production_LCIA_results.json`. Stacked bar charts per product. Cumulative regional maps (without the material stage). |

`INCLUDE_MATERIAL = False` (the current value) removes the material production stage from the workflow table and the bar charts. The notebook still calculates and saves the material results. Set it to `True` to add the material stage.

### `L4M_R&D.ipynb`
Footprint of 1 set of optimised welding parameters per use case (Fusion welding, Pharma welding, Battery cooling welding). It compares an SoA R&D scenario with an L4M-enabled R&D scenario (fewer physical experiments, digital lab runs, joining with DBS). See `Diagrams/L4M_RD_parameter_sets.md`.

| | |
|---|---|
| **Parameters** | `DBS_ENERGY_FACTOR`, `OPTIMIZATION_KWH`, `RD_SCENARIOS` (placeholders), the codes of the saved processes, and the plot groups. |
| **Inputs** | `databases/L4M_database.bw2package`, `CT-scan test.bw2package` and `Metallurgic test (CIVAN).bw2package`. The notebook imports them only if the project does not have them. The packages link to ecoinvent. With `BACKGROUND = "bafu"`, the notebook relinks their ecoinvent inputs to BAFU with `BAFU_LINKS`. Tissue paper has the proxy "Kraft paper, bleached". The BAFU aluminium scrap carries its transport burden, but the ecoinvent cut-off scrap has no burden. The notebook then checks that the packages use only the selected background. |
| **Outputs** | The `L4M_RD_parameter_sets` database. A stacked bar chart. A Sankey diagram and regional maps (set `SHOW_SANKEY` or `SHOW_REGIONAL` to `True`). The notebook checks all totals against `bw2calc`. |

### `database_explorer.ipynb`
Interactive browser of a Brightway database. Click an input, an output or a consumer to open that process.

### `background_comparison.ipynb`
Ratios BAFU / ecoinvent of the joining, pre/post and material results, the impact of 1 unit of the main background inputs, and the BAFU import quality.

## The `l4m_lca` package

| Module | Contents |
|---|---|
| `project` | Open the project, import packages, relink package inputs to another background (`relink_background`), select the EF 3.1 methods, find activities by exact name and location. |
| `constants` | EU27 country codes, Eurostat electricity prices, scenario names. |
| `ranges` | Min/max ranges and the exchanges made from them. |
| `joining`, `prepost` | Exchange builders of the joining and pre/post processes. |
| `impacts` | The LCIA engine (see below). |
| `lcia`, `regional` | Scenario result tables, regional tables, export. |
| `workflow` | Assembly per product, with or without the material stage. |
| `rd` | Product systems of the R&D study. |
| `bafu`, `compare` | Import of BAFU-2026 (`python -m l4m_lca.bafu`), comparison of 2 backgrounds. |
| `plots`, `explorer` | Interactive figures. |

### How the LCIA engine works

The engine walks each foreground process down to its background inputs (ecoinvent activities and biosphere flows).
It calculates the impact of 1 unit of each background input one time, from one factorised ecoinvent LCA.
Then it multiplies by the amounts of the scenario and adds.
An LCA is linear in the foreground amounts, so the result is the same as a regular `bw2calc` LCA. The tests check this.
The engine does not change the stored exchanges, and it does not need a cache.

### Conventions

- **Scenarios.** Each ranged exchange has `minimum`, `amount` (the midpoint) and `maximum`. The minimum uses the low end of every parameter. For joining, that is the lowest power and gas flow during the shortest joining time (fastest speed).
- **Indicators.** `DEFAULT_INDICATORS` selects 8 EF 3.1 methods. "human toxicity: carcinogenic" also selects its "inorganics" and "organics" sub-categories. Each is a separate column.
- **Result files.** The JSON files keep full float precision.

## Tests

```
python -m pytest            # all tests
python -m pytest -m brightway   # only the checks against the real project
```

The unit tests need no Brightway project. The `brightway` tests use the `Lasers4MaaS` project and are skipped if it is missing.

## Untracked folders

These folders are not in git. They hold the data that the notebooks use.

- `results/`: LCIA outputs and report figures. `results/.cache` is no longer used.
- `databases/`: Brightway database exports (`.bw2package`).
- `Input_data/`, `data_collection/`: source spreadsheets and cost plots.

## Setup

1. Create the environment: `conda env create -f environment.yml`.
2. Register the kernel: `python -m ipykernel install --user --name brightway --display-name "Python (brightway)"`.
3. Start the notebooks from this folder, so that `import l4m_lca` works.

The first run needs an ecoinvent licence to import ecoinvent 3.12 (cutoff).
