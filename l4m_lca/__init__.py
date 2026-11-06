"""Lasers4MaaS life cycle assessment (LCA) models.

The notebooks hold the model parameters and show the results.
This package holds the calculation code that the notebooks share.

Modules:
    project   Open the Brightway project, select the impact methods, find activities.
    constants Reference data: EU27 country codes, Eurostat electricity prices.
    ranges    Min/max parameter ranges and the exchanges made from them.
    joining   Exchanges of the joining processes.
    prepost   Exchanges of the chemical and mechanical pre- and post-joining processes.
    impacts   Linear LCIA engine: foreground walk and background unit impacts.
    lcia      Scenario result tables and their export.
    regional  Impacts with the electricity market of each country.
    workflow  Assembly of material, pre-joining, joining and post-joining per product.
    rd        Product systems of the L4M R&D study.
    plots     Interactive Plotly figures.
    explorer  Interactive Brightway database explorer.
"""
