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
```

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
| **Parameters** | `PRODUCT_WORKFLOWS` (material, enabled steps and part weights of each product), `MATERIAL_MARKETS`, `SCENARIO` and `MATERIAL_CASE`. |
| **Inputs** | The result files of `joining_task.ipynb` and `pre_post.ipynb`. |
| **Outputs** | `results/Material_production_LCIA_results.json`. Stacked bar charts per product. Cumulative regional maps (without the material stage). |

### `L4M_R&D.ipynb`
Footprint of 1 set of optimised welding parameters per use case (Fusion welding, Pharma welding, Battery cooling welding). It compares an SoA R&D scenario with an L4M-enabled R&D scenario (fewer physical experiments, digital lab runs, joining with DBS). See `Diagrams/L4M_RD_parameter_sets.md`.

| | |
|---|---|
| **Parameters** | `DBS_ENERGY_FACTOR`, `OPTIMIZATION_KWH`, `RD_SCENARIOS` (placeholders), the codes of the saved processes, and the plot groups. |
| **Inputs** | `databases/L4M_database.bw2package`, `CT-scan test.bw2package` and `Metallurgic test (CIVAN).bw2package`. The notebook imports them only if the project does not have them. |
| **Outputs** | The `L4M_RD_parameter_sets` database. A stacked bar chart. A Sankey diagram and regional maps (set `SHOW_SANKEY` or `SHOW_REGIONAL` to `True`). The notebook checks all totals against `bw2calc`. |

### `database_explorer.ipynb`
Interactive browser of a Brightway database. Click an input, an output or a consumer to open that process.

## The `l4m_lca` package

| Module | Contents |
|---|---|
| `project` | Open the project, import packages, select the EF 3.1 methods, find activities by exact name and location. |
| `constants` | EU27 country codes, Eurostat electricity prices, scenario names. |
| `ranges` | Min/max ranges and the exchanges made from them. |
| `joining`, `prepost` | Exchange builders of the joining and pre/post processes. |
| `impacts` | The LCIA engine (see below). |
| `lcia`, `regional` | Scenario result tables, regional tables, export. |
| `workflow` | Assembly per product. |
| `rd` | Product systems of the R&D study. |
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
