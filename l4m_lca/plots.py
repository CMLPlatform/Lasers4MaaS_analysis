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

from .constants import EU27, L4M_SOLUTION_TECHNOLOGY
from .project import short

GRID = "#e6e9ec"
INK = "#1d2421"

# Accessible colours (validated for colour-vision deficiency on a white background) and textures.
# Colour gives the group (technology or process stage); a texture separates items with the same colour,
# so that no figure relies on colour alone.
TECH_COLORS = {L4M_SOLUTION_TECHNOLOGY: "#2a78d6", "standard laser": "#eb6834", "TIG": "#eda100",
               "controlled atmosphere brazing": "#e87ba4"}
FALLBACK_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#e34948"]
PATTERNS = ["", "/", ".", "x", "\\", "+", "-", "|"]
SEQ_ORANGE = [[0, "#fde3d3"], [0.5, "#eb6834"], [1, "#7a2c0c"]]
SEQ_BLUE = [[0, "#cde2fb"], [0.5, "#3987e5"], [1, "#0d366b"]]
DIVERGING = [[0, "#1c5cab"], [0.5, "#f2f2f0"], [1, "#b23a12"]]


def pattern(shape):
    """Marker pattern of a bar: a light texture in white over the bar colour."""
    return dict(shape=shape, fgcolor="white", fgopacity=0.75, size=9, solidity=0.3)


def label_positions(x, y, near=0.09):
    """Text position of each point label, away from its nearest neighbour, so labels do not overlap.

    `near` is the distance (as a share of the axis ranges) below which two points are neighbours.
    """
    x, y = np.asarray(x, float), np.asarray(y, float)
    sx = (x.max() - x.min()) or 1.0
    sy = (y.max() - y.min()) or 1.0
    u, v = (x - x.min()) / sx, (y - y.min()) / sy
    out = []
    for i in range(len(u)):
        d = np.hypot(u - u[i], v - v[i])
        d[i] = np.inf
        j = int(np.argmin(d)) if len(d) > 1 else i
        if j == i or d[j] > near:
            out.append("top center")
        elif abs(u[j] - u[i]) > abs(v[j] - v[i]):
            out.append("middle left" if u[j] > u[i] else "middle right")
        else:
            out.append("bottom center" if v[j] > v[i] else "top center")
    return out


def for_print(fig, width=1000, height=None, base=18):
    """Resize a figure and its text for a report page (text width about 16 cm).

    Sets every font to at least `base` - 2 px, so that the text stays at 8 pt or more when the
    figure fills the text width.
    """
    fig = go.Figure(fig)
    fig.update_layout(width=width, height=height or fig.layout.height, font=dict(size=base, color=INK),
                      legend=dict(font=dict(size=base - 1)), hoverlabel=dict(font_size=base - 2))
    if fig.layout.title and fig.layout.title.text:
        fig.update_layout(title_font_size=base + 2)
    fig.update_xaxes(tickfont_size=base - 2, title_font_size=base - 1)
    fig.update_yaxes(tickfont_size=base - 2, title_font_size=base - 1)
    fig.update_annotations(font_size=base)
    for t in fig.data:
        if getattr(t, "textfont", None) is not None and t.type in ("scatter", "bar"):
            t.textfont.size = base - 2
        if t.type == "choropleth":
            t.colorbar.tickfont.size = base - 2
            t.colorbar.title.font.size = base - 2
        if t.type == "scatter" and t.marker is not None and t.marker.size:
            t.marker.size = max(t.marker.size, 10)
    return fig
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
    others = iter(c for c in FALLBACK_COLORS if c not in TECH_COLORS.values())
    colors = {t: TECH_COLORS.get(t) or next(others) for t in techs}
    hatch = {t: "" if t == L4M_SOLUTION_TECHNOLOGY else "/" for t in techs}  # L4M-solution solid, state of the art hatched

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
                x=[wrap(tech, 16)], y=[0], width=0.55, name=tech,
                marker=dict(color=colors.get(tech), pattern=pattern(hatch.get(tech, "")),
                            line=dict(color=colors.get(tech), width=1)),
                legendgroup=tech, showlegend=tech not in shown,
                error_y=dict(type="data", symmetric=False, array=[0], arrayminus=[0], thickness=1.5, width=6, color=INK),
                customdata=[[0, 0]],
                hovertemplate="<b>%{fullData.name}</b><br>Value: %{y:.4g}<br>Min: %{customdata[0]:.4g}"
                              "<br>Max: %{customdata[1]:.4g}<extra></extra>",
            ), row=i // n_cols + 1, col=i % n_cols + 1)
            shown.add(tech)
            slots.append((len(fig.data) - 1, use_case, db_name))
    fig.update_layout(template="plotly_white", height=330 * n_rows + 120, width=1000, bargap=0.3,
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.08, yanchor="top"),
                      margin=dict(l=70, r=30, t=100, b=90), font=dict(size=14, color=INK))
    fig.update_yaxes(gridcolor=GRID, title_font_size=13, exponentformat="e")
    fig.update_xaxes(tickfont_size=13, tickangle=0)
    fig.update_annotations(font_size=14)

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
    codes = [c for c in countries if c in set(table["country"])]  # countries without data are left out
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
                          tickfont=dict(size=12), title=dict(font=dict(size=12))),
            marker=dict(line=dict(color="white", width=0.5))), row=map_row, col=col)
    fig.add_trace(go.Scatter(
        x=[0] * len(codes), y=[0] * len(codes), mode="markers+text", text=codes, textposition="top center",
        textfont=dict(size=12, color=INK), marker=dict(size=10, color="#2a78d6", line=dict(color="white", width=1.5)),
        hovertemplate="<b>%{text}</b><br>A: %{x:.4g}<br>B: %{y:.4g}<extra></extra>"), row=xy_row, col=1)
    fig.add_trace(go.Scatter(
        x=[0], y=[0], mode="markers+text", text=[baseline], textposition="middle right",
        textfont=dict(size=12, color=INK, weight="bold"),
        marker=dict(size=14, symbol="diamond", color=INK, line=dict(color="white", width=1.5)),
        hovertemplate=f"<b>{baseline} baseline</b><br>A: %{{x:.4g}}<br>B: %{{y:.4g}}<extra></extra>"),
        row=xy_row, col=1)
    fig.update_geos(scope="europe", fitbounds="locations", showframe=False, showcountries=True,
                    countrycolor="#c4cad0", showland=True, landcolor="#eceff1", showocean=False,
                    showlakes=False, bgcolor="rgba(0,0,0,0)")
    fig.update_layout(template="plotly_white", height=height, width=width, showlegend=False, font=dict(size=14, color=INK),
                      margin=dict(l=70, r=90, t=70, b=50) if scatter_on_top else dict(l=60, r=30, t=60, b=50))
    fig.update_annotations(font_size=15)
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
            for trace, z, u, scale in ((fig.data[0], za, ua, SEQ_ORANGE), (fig.data[1], zb, ub, SEQ_BLUE)):
                m = max(abs(z).max(), 1e-12)
                trace.z = z
                trace.colorscale = DIVERGING if pct else scale
                trace.zmin, trace.zmax = (-m, m) if pct else (None, None)
                trace.colorbar.title.text = u
            fig.data[2].x, fig.data[2].y = za, zb
            fig.data[3].x, fig.data[3].y = [ra], [rb]
            pos = label_positions(np.append(za, ra), np.append(zb, rb))
            fig.data[2].textposition, fig.data[3].textposition = pos[:-1], pos[-1]
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
    Leave out "row" and "col" for a figure with one y axis.
    The y range covers the positive and the negative stacks of the visible bars.
    """
    def rescale(*_):
        with fig.batch_update():
            for panel in panels:
                total = fig.data[panel["total"]]
                n = len(total.y)  # not total.x: a multi-level x axis is a list of levels
                pos = np.zeros(n)
                neg = np.zeros(n)
                for i in panel["bars"]:
                    if fig.data[i].visible in (True, None):
                        y = np.nan_to_num(np.asarray(fig.data[i].y, dtype=float))
                        pos = pos + np.clip(y, 0, None)
                        neg = neg + np.clip(y, None, 0)
                now = pos + neg
                total.y = now
                total.text = [f"{t:.3g}" for t in now]
                top, bottom = max(pos.max(initial=0), 0), min(neg.min(initial=0), 0)
                span = (top - bottom) or 1
                where = {"row": panel["row"], "col": panel["col"]} if "row" in panel else {}
                fig.update_yaxes(range=[bottom - 0.05 * span if bottom < 0 else 0, top + 0.15 * span], **where)

    for panel in panels:
        for i in panel["bars"]:
            fig.data[i].on_change(rescale, "visible")
    rescale()


# Colour of each workflow stage (material yellow, pre-joining blue, joining orange, post-joining aqua)
# and a texture per step within the stage. 
STEP_COLORS = {
    ("mat", "material production"): "#eda100",
    ("pre", "alkaline_degreasing"): "#2a78d6",
    ("pre", "mechanical_treatment"): "#2a78d6",
    ("pre", "machining"): "#2a78d6",
    ("join", "joining"): "#eb6834",
    ("post", "chemical_etching"): "#1baf7a",
    ("post", "pickling"): "#1baf7a",
    ("post", "conversion_coating"): "#1baf7a",
    ("post", "passivation"): "#1baf7a",
    ("post", "grinding_polishing"): "#1baf7a",
}
STEP_PATTERNS = {
    ("pre", "alkaline_degreasing"): "",
    ("pre", "mechanical_treatment"): "/",
    ("pre", "machining"): ".",
    ("post", "chemical_etching"): "",
    ("post", "pickling"): "x",
    ("post", "conversion_coating"): "-",
    ("post", "passivation"): "/",
    ("post", "grinding_polishing"): ".",
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
            sub = sub.iloc[sorted(range(len(sub)), key=lambda k: L4M_SOLUTION_TECHNOLOGY in sub.index[k])]  # L4M-solution on the right
            totals = sub.sum(axis=1)
            names = list(sub.index)
            x = [wrap(n) for n in names]
            bars = []
            for stage, step in sub.columns:
                vals = sub[(stage, step)].values
                share = np.nan_to_num(vals / totals.values * 100)
                fig.add_trace(go.Bar(
                    x=x, y=vals, name=pretty(step),
                    marker=dict(color=STEP_COLORS.get((stage, step), "#999999"), line=dict(color="white", width=1.5),
                                pattern=pattern(STEP_PATTERNS.get((stage, step), ""))),
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
                                     textfont=dict(size=13, color=INK)), row=r + 1, col=c + 1)
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
                          margin=dict(t=100, r=40), hoverlabel=dict(bgcolor="white"), font=dict(size=14, color=INK))
        fig.update_annotations(font_size=15)
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

    One checkbox per use case includes or excludes its bars. Processes with no impact in the
    included use cases are left out of the legend.
    """
    fig = go.FigureWidget()
    use_cases = list(dict.fromkeys(uc for uc, _ in stack(default).index))
    w_uc = {uc: widgets.Checkbox(value=True, description=uc, indent=False, layout=widgets.Layout(width="auto"))
            for uc in use_cases}

    def draw(_=None):
        d = stack(w.value)
        unknown = [c for c in d.columns if not any(c in procs for procs in process_types.values())]
        if unknown:
            raise ValueError(f"Processes without a type in process_types: {unknown}")
        d = d[[uc in {u for u, box in w_uc.items() if box.value} for uc, _ in d.index]]
        d = d.loc[:, (d != 0).any()]
        unit = units.get(w.value, "")
        x = [[uc for uc, _ in d.index], [sc for _, sc in d.index]]
        tot = d.sum(axis=1)
        with fig.batch_update():
            fig.data = []
            for ptype, procs in process_types.items():
                first = True
                for k, (proc, color) in enumerate(procs.items()):
                    if proc not in d.columns:
                        continue
                    fig.add_bar(x=x, y=d[proc], name=proc, legendgroup=ptype,
                                legendgrouptitle_text=f"<b>{ptype}</b>" if first else None,
                                marker=dict(color=color, line=dict(color="white", width=1),
                                            pattern=pattern(PATTERNS[k % len(PATTERNS)])),
                                customdata=(d[proc] / tot * 100),
                                hovertemplate=f"<b>%{{x}}</b><br>{ptype}: {proc}<br>%{{y:.3g}} {unit} "
                                              "(%{customdata:.1f}% of total)<extra></extra>")
                    first = False
            fig.add_scatter(x=x, y=tot, mode="text", text=[f"{t:.3g}" for t in tot], textposition="top center",
                            showlegend=False, hoverinfo="skip")
            fig.update_layout(barmode="relative", template="plotly_white", height=900, width=1260, font=dict(size=14, color=INK),
                              title=dict(text=title(w.value), x=0.01, font=dict(size=15)),
                              yaxis=dict(title=unit, gridcolor=GRID),
                              legend=dict(groupclick="toggleitem", tracegroupgap=14),
                              margin=dict(l=70, r=20, t=80, b=50))
        _follow_legend(fig, [{"bars": list(range(len(fig.data) - 1)), "total": len(fig.data) - 1}])

    w = dropdown(indicators, "Indicator", default, width="520px", label_width="80px")
    w.observe(draw, names="value")
    for box in w_uc.values():
        box.observe(draw, names="value")
    draw()
    w_label = widgets.Label("Use cases:", layout=widgets.Layout(width="80px"))
    return widgets.VBox([w, widgets.HBox([w_label, *w_uc.values()], layout=widgets.Layout(gap="16px")), fig])


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
