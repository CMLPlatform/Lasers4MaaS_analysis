"""Interactive Plotly figures of the notebooks.

Each function builds the widgets and the figure, and returns a widget box to display.
"""

import textwrap

import ipywidgets as widgets
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from IPython.display import display
from plotly.subplots import make_subplots

from .constants import EU27
from .project import short

GRID = "#e6e9ec"
WIDE = widgets.Layout(width="420px")
STYLE = {"description_width": "90px"}


def wrap(label, width=14):
    """Break a long label over lines, so that tick labels can stay horizontal."""
    return "<br>".join(textwrap.wrap(label, width=width, break_long_words=False)) or label


def dropdown(options, description, value=None, width="420px", label_width="90px"):
    options = list(options)
    return widgets.Dropdown(options=options, value=value if value is not None else options[0],
                            description=description, layout=widgets.Layout(width=width),
                            style={"description_width": label_width})


# ---------------------------------------------------------------------------
# Scenario bars (joining)
# ---------------------------------------------------------------------------

def scenario_bars(table, use_cases, databases, units, technology_of, indicators):
    """Bar per use case and database, with the minimum-maximum range as an error bar.

    `table` is the result of lcia.scenario_table. `databases` are database names.
    """
    techs = sorted({technology_of(p) for p in table["Process"]})
    colors = {t: px.colors.qualitative.D3[i % 10] for i, t in enumerate(techs)}

    def stats(use_case, db_name, indicator):
        rows = table[(table["Key"] == use_case) & table["Database"].str.startswith(db_name)]
        if rows.empty:
            return None
        tech = technology_of(rows.iloc[0]["Process"])
        vals = {s: rows.loc[rows["Scenario"] == s, indicator] for s in ("amount", "minimum", "maximum")}
        if any(v.empty for v in vals.values()):
            return tech, None, None, None
        amount, low, high = (float(vals[s].iloc[0]) for s in ("amount", "minimum", "maximum"))
        return tech, amount, min(low, high, amount), max(low, high, amount)

    n_cols = 3
    n_rows = -(-len(use_cases) // n_cols)
    fig = go.FigureWidget(make_subplots(rows=n_rows, cols=n_cols, subplot_titles=use_cases,
                                        vertical_spacing=0.2, horizontal_spacing=0.08))
    shown, slots = set(), []
    for i, use_case in enumerate(use_cases):
        for db_name in databases:
            s = stats(use_case, db_name, indicators[0])
            tech = s[0] if s else ""
            fig.add_trace(go.Bar(
                x=[wrap(tech, 16)], y=[0], width=0.55, name=tech, marker_color=colors.get(tech),
                legendgroup=tech, showlegend=tech not in shown,
                error_y=dict(type="data", symmetric=False, array=[0], arrayminus=[0], thickness=1.5, width=5),
                customdata=[[0, 0]],
                hovertemplate="<b>%{fullData.name}</b><br>Value: %{y:.4g}<br>Min: %{customdata[0]:.4g}"
                              "<br>Max: %{customdata[1]:.4g}<extra></extra>",
            ), row=i // n_cols + 1, col=i % n_cols + 1)
            shown.add(tech)
            slots.append((len(fig.data) - 1, use_case, db_name))
    fig.update_layout(template="plotly_white", height=330 * n_rows + 120, width=1000, bargap=0.3,
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.08, yanchor="top"),
                      margin=dict(l=70, r=30, t=100, b=90), font=dict(size=12))
    fig.update_yaxes(gridcolor=GRID, title_font_size=10, exponentformat="e")
    fig.update_xaxes(tickfont_size=10, tickangle=0)
    fig.update_annotations(font_size=12)

    def update(indicator):
        with fig.batch_update():
            for idx, use_case, db_name in slots:
                s = stats(use_case, db_name, indicator)
                trace = fig.data[idx]
                if s is None or s[1] is None:
                    trace.y = [None]
                    continue
                _, amount, low, high = s
                trace.y = [amount]
                trace.error_y.array = [high - amount]
                trace.error_y.arrayminus = [amount - low]
                trace.customdata = [[low, high]]
            fig.update_yaxes(title_text=units.get(indicator, "unit"))
            fig.update_layout(title=dict(text=f"<b>{indicator}</b>", x=0.5, xanchor="center", y=0.98,
                                         yanchor="top", font=dict(size=16)))

    w = dropdown(indicators, "Indicator:", width="400px", label_width="initial")
    w.observe(lambda change: update(change["new"]), names="value")
    update(w.value)
    return widgets.VBox([w, fig])


# ---------------------------------------------------------------------------
# Regional explorer: two maps (indicator A and B) and a country scatter of A vs B
# ---------------------------------------------------------------------------

def regional_explorer(table, filters, units, title, baseline="RER", countries=EU27,
                      scatter_on_top=False, height=950, width=None):
    """Interactive maps of a regional table.

    Args:
        table: long table with the columns country, indicator, impact and the filter columns.
        filters: list of (label, column, options, default) dropdowns that select one row set.
        units: {indicator: unit}.
        title: function(dict of filter values) -> figure title.
        baseline: country label of the rows with the electricity as modelled.
    """
    codes = list(countries)
    iso3 = [countries[c] for c in codes]
    indicators = list(dict.fromkeys(table["indicator"]))
    w_a = dropdown(indicators, "Indicator A", indicators[0])
    w_b = dropdown(indicators, "Indicator B", indicators[-1])
    w_filters = {col: dropdown(options, label, default) for label, col, options, default in filters}
    w_view = dropdown(["Absolute", f"Change vs {baseline} (%)"], "View")

    map_row, xy_row = (2, 1) if scatter_on_top else (1, 2)
    specs = [[{"type": "choropleth"}, {"type": "choropleth"}], [{"type": "xy", "colspan": 2}, None]]
    titles = ("A", "B", "")
    if scatter_on_top:
        specs, titles = specs[::-1], ("Country comparison", "A", "B")
    fig = go.FigureWidget(make_subplots(
        rows=2, cols=2, specs=specs, row_heights=[0.42, 0.58] if scatter_on_top else [0.6, 0.4],
        vertical_spacing=0.12 if scatter_on_top else 0.1, horizontal_spacing=0.08 if scatter_on_top else 0.04,
        subplot_titles=titles))
    bar_y, bar_len = (0.255, 0.45) if scatter_on_top else (0.79, 0.42)
    hover = "<b>%{text}</b><br>%{z:.4g}<extra></extra>"
    for col, x in ((1, 0.468 if scatter_on_top else 0.455), (2, 1.01 if scatter_on_top else 1.0)):
        fig.add_trace(go.Choropleth(
            locations=iso3, z=[0] * len(codes), text=codes, hovertemplate=hover,
            colorbar=dict(x=x, y=bar_y, len=bar_len, thickness=14 if scatter_on_top else 12, outlinewidth=0,
                          tickfont=dict(size=10), title=dict(font=dict(size=11))),
            marker=dict(line=dict(color="white", width=0.5))), row=map_row, col=col)
    fig.add_trace(go.Scatter(
        x=[0] * len(codes), y=[0] * len(codes), mode="markers+text", text=codes, textposition="top center",
        textfont=dict(size=10), marker=dict(size=9, color="#1f77b4", line=dict(color="white", width=1)),
        hovertemplate="<b>%{text}</b><br>A: %{x:.4g}<br>B: %{y:.4g}<extra></extra>"), row=xy_row, col=1)
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode="markers+text", text=[baseline], textposition="bottom center", textfont=dict(size=10),
        marker=dict(size=13, symbol="diamond", color="#d62728", line=dict(color="white", width=1)),
        hovertemplate=f"<b>{baseline} baseline</b><br>A: %{{x:.4g}}<br>B: %{{y:.4g}}<extra></extra>"),
        row=xy_row, col=1)
    fig.update_geos(scope="europe", fitbounds="locations", showframe=False, showcountries=True,
                    countrycolor="#c4cad0", showland=True, landcolor="#eceff1", showocean=False,
                    showlakes=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(template="plotly_white", height=height, width=width, showlegend=False, font=dict(size=12),
                      margin=dict(l=70, r=90, t=70, b=50) if scatter_on_top else dict(l=60, r=30, t=60, b=50))
    fig.update_annotations(font_size=13)
    fig.update_xaxes(zeroline=False, gridcolor=GRID)
    fig.update_yaxes(zeroline=False, gridcolor=GRID)
    a_title = 1 if scatter_on_top else 0

    def series(indicator):
        sel = table["indicator"] == indicator
        for col, w in w_filters.items():
            sel &= table[col] == w.value
        d = table[sel].set_index("country")["impact"]
        if w_view.value == "Absolute":
            return d[codes].values, d[baseline], units.get(indicator, "")
        return ((d[codes] / d[baseline] - 1) * 100).values, 0.0, f"% vs {baseline}"

    def update(_=None):
        (za, ra, ua), (zb, rb, ub) = series(w_a.value), series(w_b.value)
        pct = w_view.value != "Absolute"
        with fig.batch_update():
            for trace, z, u, scale in ((fig.data[0], za, ua, "YlOrRd"), (fig.data[1], zb, ub, "GnBu")):
                m = max(abs(z).max(), 1e-12)
                trace.z = z
                trace.colorscale = "RdBu_r" if pct else scale
                trace.zmin, trace.zmax = (-m, m) if pct else (None, None)
                trace.colorbar.title.text = u
            fig.data[2].x, fig.data[2].y = za, zb
            fig.data[3].x, fig.data[3].y = [ra], [rb]
            # explicit ranges (with the baseline point), so that no point falls outside the axes
            for axis, vals, ref in ((fig.layout.xaxis, za, ra), (fig.layout.yaxis, zb, rb)):
                lo, hi = min(vals.min(), ref), max(vals.max(), ref)
                pad = (hi - lo) * 0.08 or abs(hi) * 0.1 or 1.0
                axis.range = [lo - pad, hi + pad]
            fig.layout.annotations[a_title].text = f"<b>A</b>  {short(w_a.value)}"
            fig.layout.annotations[a_title + 1].text = f"<b>B</b>  {short(w_b.value)}"
            fig.layout.xaxis.title.text = f"A: {short(w_a.value)} [{ua}]"
            fig.layout.yaxis.title.text = f"B: {short(w_b.value)} [{ub}]"
            fig.layout.title = dict(text=title({c: w.value for c, w in w_filters.items()}), x=0.01, font=dict(size=15))

    for w in (w_a, w_b, w_view, *w_filters.values()):
        w.observe(update, names="value")
    update()
    return widgets.VBox([widgets.HBox([w_a, w_b]), widgets.HBox(list(w_filters.values())), w_view, fig])


# ---------------------------------------------------------------------------
# Stacked bars with totals that follow the legend
# ---------------------------------------------------------------------------

def _follow_legend(fig, panels):
    """Recalculate the stack totals (and y ranges) from the visible bars after a legend click.

    `panels` is a list of {"bars": trace indices, "total": trace index, "row", "col"}.
    """
    def rescale(*_):
        with fig.batch_update():
            for panel in panels:
                total = fig.data[panel["total"]]
                now = np.zeros(len(total.x))
                for i in panel["bars"]:
                    if fig.data[i].visible in (True, None):
                        now = now + np.asarray(fig.data[i].y, dtype=float)
                total.y = now
                total.text = [f"{t:.3g}" for t in now]
                if "row" in panel:
                    top = now.max()
                    fig.update_yaxes(range=[0, top * 1.15 if top > 0 else 1], row=panel["row"], col=panel["col"])

    for panel in panels:
        for i in panel["bars"]:
            fig.data[i].on_change(rescale, "visible")


# Colour of each workflow step: material green, pre-joining blues, joining orange, post-joining violets.
# Steps that never occur for the same material share a shade.
STEP_COLORS = {
    ("mat", "material production"): "#2a9d6f",
    ("pre", "alkaline_degreasing"): "#2a78d6",
    ("pre", "mechanical_treatment"): "#6fa3e6",
    ("pre", "machining"): "#b3d0f2",
    ("join", "joining"): "#eb6834",
    ("post", "chemical_etching"): "#4b3bb5",
    ("post", "pickling"): "#4b3bb5",
    ("post", "conversion_coating"): "#8576e0",
    ("post", "passivation"): "#8576e0",
    ("post", "grinding_polishing"): "#c4bcf3",
}
STAGE_RANK = {"mat": -1, "pre": 0, "join": 100, "post": 200}


def workflow_bars(table, stage_titles, default_indicator, scenario):
    """Stacked bar per product and joining technology, one segment per workflow step.

    `table` is the result of workflow.workflow_table.
    """
    indicators = list(dict.fromkeys(table["indicator"]))
    products = list(dict.fromkeys(table["product"]))
    step_rank = {k: STAGE_RANK[k[0]] + i + 1 for i, k in enumerate(STEP_COLORS)}
    out = widgets.Output()

    def pretty(step):
        return step.replace("_", " ").capitalize()

    def draw(indicator):
        data = table[table["indicator"] == indicator]
        unit = indicator.split("[")[-1].rstrip("]") if "[" in indicator else ""
        n_cols = 3
        n_rows = -(-len(products) // n_cols)
        fig = make_subplots(rows=n_rows, cols=n_cols, subplot_titles=products,
                            horizontal_spacing=0.07, vertical_spacing=0.16)
        shown, panels, stages_seen = set(), [], []
        for i, product in enumerate(products):
            r, c = divmod(i, n_cols)
            sub = data[data["product"] == product].pivot_table(
                index="technology", columns=["stage", "step"], values="value", aggfunc="sum", sort=False)
            sub = sub[sorted(sub.columns, key=lambda k: STAGE_RANK[k[0]])]
            sub = sub.loc[:, (sub != 0).any(axis=0) | (sub.columns.get_level_values(0) == "join")]
            sub = sub.iloc[sorted(range(len(sub)), key=lambda k: "dynamic" in sub.index[k].lower())]  # DBS on the right
            totals = sub.sum(axis=1)
            names = list(sub.index)
            x = [wrap(n) for n in names]
            bars = []
            for stage, step in sub.columns:
                vals = sub[(stage, step)].values
                share = np.nan_to_num(vals / totals.values * 100)
                fig.add_trace(go.Bar(
                    x=x, y=vals, name=pretty(step),
                    marker=dict(color=STEP_COLORS.get((stage, step), "#999999"), line=dict(color="white", width=1.5)),
                    legendgroup=f"{stage}:{step}", legendrank=step_rank.get((stage, step), 999),
                    showlegend=(stage, step) not in shown,
                    customdata=np.column_stack([share, names]),
                    hovertemplate=f"<b>%{{customdata[1]}}</b><br>{pretty(step)}: %{{y:.3g}} {unit}"
                                  "<br>%{customdata[0]:.1f}% of total<extra></extra>"),
                    row=r + 1, col=c + 1)
                shown.add((stage, step))
                if stage not in stages_seen:
                    stages_seen.append(stage)
                bars.append(len(fig.data) - 1)
            fig.add_trace(go.Scatter(x=x, y=totals.values, mode="text", text=[f"{t:.3g}" for t in totals],
                                     textposition="top center", showlegend=False, hoverinfo="skip",
                                     textfont=dict(size=12)), row=r + 1, col=c + 1)
            panels.append({"row": r + 1, "col": c + 1, "bars": bars, "total": len(fig.data) - 1})
            top = totals.max()
            fig.update_yaxes(title_text=unit if c == 0 else None, rangemode="tozero",
                             range=[0, top * 1.15 if top > 0 else 1], row=r + 1, col=c + 1)
            fig.update_xaxes(tickangle=0, automargin=True, row=r + 1, col=c + 1)

        # Legend headers: traces without data that show the stage title only
        for stage in sorted(stages_seen, key=STAGE_RANK.get):
            fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers", marker=dict(size=0, opacity=0),
                                     name=f"<b>{stage_titles[stage]}</b>", legendgroup=f"header_{stage}",
                                     legendrank=STAGE_RANK[stage], hoverinfo="skip"), row=1, col=1)
        fig.update_layout(barmode="stack", template="plotly_white", height=380 * n_rows + 80, width=1200,
                          title=dict(text=f"{indicator}<br><sup>{scenario} scenario - stacked contribution "
                                          "per process step</sup>", x=0.01),
                          legend=dict(groupclick="togglegroup", orientation="v", x=1.02, y=1, tracegroupgap=12),
                          margin=dict(t=100, r=40), hoverlabel=dict(bgcolor="white"), font=dict(size=12))
        fig.update_annotations(font_size=14)
        fw = go.FigureWidget(fig)
        _follow_legend(fw, panels)
        out.clear_output(wait=True)
        with out:
            display(fw)

    default = next((i for i in indicators if i.startswith(default_indicator)), indicators[0])
    w = dropdown(indicators, "Indicator:", default, width="600px", label_width="initial")
    w.observe(lambda change: draw(change["new"]), names="value")
    draw(w.value)
    return widgets.VBox([w, out])


def grouped_stacked_bars(stack, indicators, default, units, process_types, title):
    """Stacked bar per (use case, scenario), one segment per process, grouped by process type.

    Args:
        stack: function(indicator) -> DataFrame (rows: (use case, scenario), columns: process labels).
        process_types: {type: {process label: colour}} (legend order).
        title: function(indicator) -> figure title.
    """
    fig = go.FigureWidget()

    def draw(_=None):
        d = stack(w.value)
        unknown = [c for c in d.columns if not any(c in procs for procs in process_types.values())]
        if unknown:
            raise ValueError(f"Processes without a type in process_types: {unknown}")
        unit = units.get(w.value, "")
        x = [[uc for uc, _ in d.index], [sc for _, sc in d.index]]
        tot = d.sum(axis=1)
        with fig.batch_update():
            fig.data = []
            for ptype, procs in process_types.items():
                first = True
                for proc, color in procs.items():
                    if proc not in d.columns:
                        continue
                    fig.add_bar(x=x, y=d[proc], name=proc, legendgroup=ptype,
                                legendgrouptitle_text=f"<b>{ptype}</b>" if first else None,
                                marker=dict(color=color, line=dict(color="white", width=1)),
                                customdata=(d[proc] / tot * 100),
                                hovertemplate=f"<b>%{{x}}</b><br>{ptype}: {proc}<br>%{{y:.3g}} {unit} "
                                              "(%{customdata:.1f}% of total)<extra></extra>")
                    first = False
            fig.add_scatter(x=x, y=tot, mode="text", text=[f"{t:.3g}" for t in tot], textposition="top center",
                            showlegend=False, hoverinfo="skip")
            fig.update_layout(barmode="relative", template="plotly_white", height=900, width=1260, font=dict(size=14),
                              title=dict(text=title(w.value), x=0.01, font=dict(size=15)),
                              yaxis=dict(title=unit, gridcolor=GRID),
                              legend=dict(groupclick="toggleitem", tracegroupgap=14),
                              margin=dict(l=70, r=20, t=80, b=50))
        _follow_legend(fig, [{"bars": list(range(len(fig.data) - 1)), "total": len(fig.data) - 1}])

    w = dropdown(indicators, "Indicator", default, width="520px", label_width="80px")
    w.observe(draw, names="value")
    draw()
    return widgets.VBox([w, fig])


def sankey(links_of, systems, indicators, default, units, totals, root_name):
    """Sankey of where the impact of a product system comes from.

    Args:
        links_of: function(system, indicator) -> (labels, sources, targets, values).
        systems: {option label: system}.
        totals: function(system, indicator) -> net total.
        root_name: function(system) -> name of the root node (coloured orange).
    """
    w_sys = dropdown(list(systems), "System", width="520px", label_width="80px")
    w_ind = dropdown(indicators, "Indicator", default, width="520px", label_width="80px")
    fig = go.FigureWidget(go.Sankey(node=dict(pad=14, thickness=14), link=dict(source=[], target=[], value=[])))

    def draw(_=None):
        system = systems[w_sys.value]
        labels, src, tgt, val = links_of(system, w_ind.value)
        unit = units.get(w_ind.value, "")
        colors = ["#2a78d6" if lab.endswith(("[input]", "[flow]")) else
                  ("#eb6834" if lab == root_name(system) else "#8a8a85") for lab in labels]
        with fig.batch_update():
            t = fig.data[0]
            t.node.label, t.node.color = labels, colors
            t.link.source, t.link.target, t.link.value = src, tgt, val
            t.link.color = "rgba(138,138,133,0.3)"
            t.valueformat, t.valuesuffix = ".3g", f" {unit}"
            fig.update_layout(template="plotly_white", height=620, font=dict(size=11),
                              margin=dict(l=10, r=10, t=60, b=10),
                              title=dict(text=f"{w_sys.value}: {short(w_ind.value)}, net total "
                                              f"{totals(system, w_ind.value):.4g} {unit}", x=0.01, font=dict(size=15)))

    for w in (w_sys, w_ind):
        w.observe(draw, names="value")
    draw()
    return widgets.VBox([w_sys, w_ind, fig])


def paired_maps(value, use_cases, scenarios, indicators, default, units, countries, baseline, title):
    """Two maps side by side (one per scenario) with a shared colour scale.

    `value(use case, scenario, country, indicator)` returns the impact. The `baseline`
    country label gives the impact as modelled.
    """
    codes = list(countries)
    iso3 = [countries[c] for c in codes]
    w_ind = dropdown(indicators, "Indicator", default)
    w_uc = dropdown(use_cases, "Use case")
    w_view = dropdown(["Absolute", "Change vs as modelled (%)"], "View")
    fig = go.FigureWidget(make_subplots(rows=1, cols=2, specs=[[{"type": "choropleth"}, {"type": "choropleth"}]],
                                        subplot_titles=tuple(scenarios), horizontal_spacing=0.04))
    for col, x in ((1, 0.46), (2, 1.0)):
        fig.add_trace(go.Choropleth(locations=iso3, z=[0] * len(codes), text=codes,
                                    hovertemplate="<b>%{text}</b><br>%{z:.4g}<extra></extra>",
                                    colorbar=dict(x=x, len=0.8, thickness=12, outlinewidth=0, tickfont=dict(size=10)),
                                    marker=dict(line=dict(color="white", width=0.5))), row=1, col=col)
    fig.update_geos(scope="europe", fitbounds="locations", showframe=False, showcountries=True, countrycolor="#c4cad0",
                    showland=True, landcolor="#eceff1", showocean=False, showlakes=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(template="plotly_white", height=520, font=dict(size=12), margin=dict(l=20, r=20, t=80, b=20))

    def update(_=None):
        pct = w_view.value != "Absolute"
        zs = []
        for sc in scenarios:
            z = np.array([value(w_uc.value, sc, c, w_ind.value) for c in codes])
            base = value(w_uc.value, sc, baseline, w_ind.value)
            zs.append((z / base - 1) * 100 if pct else z)
        lim = max(np.abs(np.concatenate(zs)).max(), 1e-12)
        lo, hi = (-lim, lim) if pct else (min(z.min() for z in zs), max(z.max() for z in zs))
        unit = "% vs as modelled" if pct else units.get(w_ind.value, "")
        with fig.batch_update():
            for trace, z in zip(fig.data, zs):
                trace.z, trace.zmin, trace.zmax = z, lo, hi
                trace.colorscale = "RdBu_r" if pct else "YlOrRd"
                trace.colorbar.title.text = unit
            fig.layout.title = dict(text=title(w_uc.value, w_ind.value), x=0.01, font=dict(size=15))

    for w in (w_ind, w_uc, w_view):
        w.observe(update, names="value")
    update()
    return widgets.VBox([widgets.HBox([w_ind, w_uc]), w_view, fig])
