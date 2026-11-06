# Lasers4MaaS – LCA models

Brightway2 life-cycle assessment of laser joining (State of the Art vs. Dynamic Beam Shaping) and the pre-/post-joining processes around it, for five use cases: Heat exchanger, Fuel tank, Heterogeneous pipe, Freeze Dryers Shelf and Battery cooling plate.

The notebooks run in this order:

```
joining_task.ipynb ─┐
                    ├─> results/*_LCIA_results.json ─> workflow_assembly.ipynb
pre_post.ipynb ─────┘
```

## Tracked files

### `joining_task.ipynb`
Unit processes for the joining step (functional unit: 1 joined unit).

| | |
|---|---|
| **Inputs** | Brightway project `Lasers4MaaS` with the `ecoinvent-3.12-cutoff` and `ecoinvent-3.12-biosphere` databases and the EF v3.1 methods (ecoinvent is imported automatically if missing). <br> Hard-coded in the notebook: joining parameters per use case and technology (power, speed, joint length, gas flow; min/max ranges), `MATERIAL_ASSIGNMENTS`, `COST_FACTORS`, and EU-27 electricity prices (Eurostat). |
| **Processing** | Builds electricity (RER medium-voltage market) and argon exchanges from the parameters. Writes two Brightway databases, `State_of_the_Art` and `Dynamic_Beam_Shaping`. Runs LCIA for the minimum, amount and maximum scenarios across six EF 3.1 indicators and consumable costs. Includes a regional analysis that swaps the RER electricity for each EU member state's market, with interactive map and scatter widgets. |
| **Outputs** | `State_of_the_Art` and `Dynamic_Beam_Shaping` databases in the Brightway project. <br> `results/State_of_the_Art_Dynamic_Beam_Shaping_LCIA_results.csv` and `.json`. <br> Inline comparison plots and the regional maps. |

### `pre_post.ipynb`
Unit processes for the chemical and mechanical pre- and post-joining treatments.

| | |
|---|---|
| **Inputs** | Same Brightway project and ecoinvent databases as above. <br> Hard-coded in the notebook: `CHEM_PREPOST_PARAMS` (alkaline degreasing, chemical etching (aluminium), pickling, passivation; per material), `MECH_PREPOST_PARAMS` (mechanical treatment; per material), `INDUSTRIAL_TANK_SIZES`, U-values for tank heat loss, `COST_FACTORS` (electricity, argon, nitrogen and indicative placeholder prices for water, chemicals, abrasives, coolant and tool material), and EU-27 electricity prices (Eurostat). <br> Ecoinvent flows (electricity, water, NaOH, HCl, HNO3, abrasives and others) are located with `find_ecoinvent_activity`. Several mechanical flows are proxies. |
| **Processing** | Writes the `Chemical_Pre_and_Post_processes` and `Mechanical_Pre_and_Post_processes` databases. Runs LCIA for the minimum, amount and maximum scenarios; results are cached in `results/.cache` (set `FORCE_RECALC = True` to recompute). Includes a regional analysis that swaps the RER electricity for each EU member state's market, with interactive map and scatter widgets. A proxy-check table flags ecoinvent flows that are missing or ambiguous. |
| **Outputs** | `Chemical_Pre_and_Post_processes` and `Mechanical_Pre_and_Post_processes` databases in the Brightway project. <br> `results/Chemical_Pre_and_Post_processes_Mechanical_Pre_and_Post_processes_LCIA_results.csv` and `.json`. |

### `workflow_assembly.ipynb`
Combines the joining and pre-/post-processing results into a full workflow per product. It does not use Brightway.

| | |
|---|---|
| **Inputs** | `results/*LCIA*.json`, produced by `joining_task.ipynb` and `pre_post.ipynb`. <br> `PRODUCT_WORKFLOWS` in the notebook, which sets each product's material, which pre- and post-steps apply, and prototype/production parameters. |
| **Processing** | Looks up each active step's impacts by step, material and scenario. Sums them with the joining impacts for each technology. |
| **Outputs** | Interactive Plotly stacked-bar charts of impact per product and technology (pre, joining and post contributions), shown in the notebook. No files are written. |

### `L4M_R&D.ipynb`
Footprint of identifying one set of optimised welding parameters per use case (Fusion welding, Pharma welding, Battery cooling welding), for a state-of-the-art (SoA) R&D scenario and an L4M-enabled R&D scenario (fewer physical experiments plus digital lab runs, joining with Dynamic Beam Shaping). It does not feed `workflow_assembly.ipynb`.

| | |
|---|---|
| **Inputs** | Same Brightway project and ecoinvent databases as above. <br> `databases/L4M_database.bw2package`, plus `CT-scan test.bw2package` and `Metallurgic test (CIVAN).bw2package` which it links to (imported only if the project lacks them or holds them empty). <br> Hard-coded in the notebook: `DBS_ENERGY_FACTOR` (DBS uses 20% less electricity than the standard laser), `RD_SCENARIOS` (per round: digital runs, optimizations, coupon and prototype tests and verifications per set of parameters; placeholders). |
| **Processing** | Writes the `L4M_RD_parameter_sets` database (6 product systems, reference flow 1 set of optimised parameters). The set is identified in rounds (coupon round 1, coupon round 2, prototype round 1; more can be added): in the L4M-enabled scenario the digital platform investigates parameter sets (`Digital lab processes`) and the successful tests are fed back for an `Optimization` run (electricity, placeholder `OPTIMIZATION_KWH`) before the next physical round; SoA R&D has the same physical rounds without the digital platform. A coupon test = one coupon weld (`001_Physical_Laser welding`, pulling in its cleaned and cut coupons), a prototype test = the use-case welding. Every physical round is verified by cutting, polishing, etching and CT-scanning the joined welds (`04_Cutting`, `07_Polishing`, `08_Etching`, `CT-scan X-ray`; no extra weld or cleaning). Impacts are checked against `bw2calc`. |
| **Outputs** | `L4M_RD_parameter_sets` database. Inline stacked bar (by process, grouped into pre-processing, joining, post-processing, testing and digital lab), Sankey and regional (EU electricity markets plus GB) maps. Cached grid impacts in `results/.cache`. |

## Untracked folders

These are not in git. They hold the data the notebooks depend on.

- `results/`: LCIA outputs, plus `generate_lca_graphs.py` and the report figures.
- `databases/`: Brightway database exports (`.bw2package`).
- `Input_data/`, `data_collection/`: source spreadsheets and cost plots.

## Setup

Python with `bw2data`, `bw2io`, `bw2calc`, `bw2analyzer`, `pandas`, `numpy`, `matplotlib`, `plotly`, `ipywidgets` and `tabulate`. The first run needs an ecoinvent licence to import ecoinvent 3.12 (cutoff).
