"""Lasers4MaaS life cycle assessment (LCA) models.

The notebooks hold the model parameters and show the results.
This package holds the calculation code that the notebooks share.

Modules:
    project   Select the background, open the Brightway project, select the impact methods, find activities.
    constants Shared names and reference data: database names, result file stems, packages,
              EU27 (+ GB) country codes, electricity prices, labour cost sources.
    ranges    Min/max parameter ranges and the exchanges made from them.
    joining   Exchanges of the joining processes.
    prepost   Exchanges of the chemical and mechanical pre- and post-joining processes.
    impacts   Linear LCIA engine: foreground walk and background unit impacts.
    costs     Cost indicators (consumable, personnel, nominal OPEX) and labour costs per country.
    lcia      Scenario result tables and their export.
    regional  Impacts with the electricity market of each country.
    workflow  Assembly of material, pre-joining, joining and post-joining per product.
    rd        Product systems of the L4M R&D study, and their contribution tables.
    validation_tests  Unit processes of the R&D validation tests (D13.1).
    bafu      Import of the BAFU-2026 database (openLCA EcoSpold v1) as an alternative background.
    compare   Comparison of the results of two background databases.
    plots     Interactive Plotly figures.
    explorer  Interactive Brightway database explorer.
"""
