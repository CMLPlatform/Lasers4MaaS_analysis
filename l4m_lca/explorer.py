"""Interactive, click-to-navigate explorer of a Brightway database."""

import bw2data as bd
import ipywidgets as widgets
import plotly.graph_objects as go
from bw2data import get_activity
from bw2data.errors import UnknownObject
from IPython.display import display


def show_exchanges(database, process_name):
    """Print the exchanges of the process with this name in `database`."""
    process = next((a for a in database if a.get("name") == process_name), None)
    if process is None:
        print(f"Process {process_name!r} not found in {database.name}")
        return
    print(f"\nExchanges for {process_name} in {database.name}:")
    for exc in process.exchanges():
        try:
            name = exc.input.get("name", str(exc["input"]))
        except UnknownObject:
            name = f"Unresolved input {exc['input']!r}"
        print(f"  [{exc.get('type', '?').upper()}] {name}: {exc.get('amount')} {exc.get('unit')}")


def list_foreground(databases, exclude=("ecoinvent", "bio")):
    """Print the activity names of each database whose name does not contain an `exclude` word."""
    for name in databases:
        if not any(word in name for word in exclude):
            print(f"\n{name}:")
            for act in bd.Database(name):
                print(f"  - {act.get('name')}")

_COLORS = {"technosphere": "#2563eb", "production": "#16a34a",
           "biosphere": "#dc2626"}
_MAX_USED_BY = 30  # ecoinvent processes can have thousands of consumers


def _collect_exchanges(activity):
    """Return (inputs, outputs) as lists of dicts for one activity."""
    inputs, outputs = [], []
    for exc in activity.exchanges():
        etype = exc.get("type", "")
        amount = exc.get("amount", 0)
        key = None
        try:
            flow = exc.input
            name = flow.get("name", "Unnamed flow")
            unit = flow.get("unit", "")
            location = flow.get("location", "")
            database = flow.key[0]
            # only process-like exchanges can be navigated to
            if etype in ("technosphere", "production", "substitution") \
                    and flow.key != activity.key:
                key = flow.key
        except UnknownObject:
            name, unit, location = f"Unresolved input {exc.get('input')!r}", "", ""
            database = ""

        item = dict(name=name, amount=amount, unit=unit, type=etype,
                    location=location, database=database, key=key,
                    comment=exc.get("comment", ""))
        if etype == "production":
            outputs.append(item)
        elif etype == "technosphere":
            inputs.append(item)
        else:
            (outputs if amount >= 0 else inputs).append(item)
    return inputs, outputs


def _collect_used_by(activity):
    """Processes that consume this activity's product (downstream).

    Returns (items, total_count); items are capped at _MAX_USED_BY.
    """
    items, seen = [], set()
    try:
        for exc in activity.upstream():
            consumer = exc.output
            if consumer.key in seen or consumer.key == activity.key:
                continue
            seen.add(consumer.key)
            items.append(dict(name=consumer.get("name", "Unnamed"),
                              amount=exc.get("amount", 0),
                              unit=consumer.get("unit", ""),
                              type="technosphere", location=consumer.get("location", ""),
                              database=consumer.key[0], key=consumer.key, comment=""))
    except Exception as err:  # upstream() unavailable or unresolved exchange
        print(f"Could not compute 'used by': {err}")
    items.sort(key=lambda e: e["name"])
    return items[:_MAX_USED_BY], len(items)


def _hover(e):
    return (f"<b>{e['name']}</b><br>{e['amount']:.4g} {e['unit']}"
            f"<br>type: {e['type']}"
            + (f"<br>location: {e['location']}" if e["location"] else "")
            + (f"<br>database: {e['database']}" if e["database"] else "")
            + (f"<br><i>{e['comment'][:200]}</i>" if e["comment"] else ""))


def _build_figure(activity, inputs, outputs):
    center = activity.get("name", str(activity.key))
    c = len(inputs)
    src, tgt, colors, custom = [], [], [], []
    for i, e in enumerate(inputs):
        src.append(i); tgt.append(c)
        colors.append(_COLORS.get(e["type"], "#6b7280") + "55"); custom.append(_hover(e))
    for j, e in enumerate(outputs):
        src.append(c); tgt.append(c + 1 + j)
        colors.append(_COLORS.get(e["type"], "#6b7280") + "55"); custom.append(_hover(e))

    def lab(e):
        return f"{e['name']}<br>{e['amount']:.3g} {e['unit']}"

    # Units differ across flows, so link width is uniform; amounts are in the
    # node labels and hover text.
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=[lab(e) for e in inputs] + [center] + [lab(e) for e in outputs],
                  pad=18, thickness=18,
                  color=["#9ca3af"] * c + ["#2563eb"] + ["#9ca3af"] * len(outputs),
                  customdata=[_hover(e) for e in inputs] + [center] + [_hover(e) for e in outputs],
                  hovertemplate="%{customdata}<extra></extra>"),
        link=dict(source=src, target=tgt, value=[1] * len(src), color=colors,
                  customdata=custom, hovertemplate="%{customdata}<extra></extra>"),
    ))
    n = max(len(inputs), len(outputs), 1)
    fig.update_layout(
        title=f"{center}  <sup>{activity.get('location', '')} · {activity.key[0]}</sup>",
        height=max(400, 45 * n + 150), margin=dict(l=10, r=10, t=70, b=10),
        font_size=11)
    return fig


def explore_activity_exchanges(database):
    """Interactive, click-to-navigate explorer for a Brightway database."""
    activities = sorted(database, key=lambda a: a.get("name", ""))
    options = [(f"{a.get('name', a.key)}  [{a.get('location', '')}]", a.key)
               for a in activities]
    all_keys = {k for _, k in options}

    state = {"key": options[0][1] if options else None, "history": []}
    syncing = {"on": False}  # blocks dropdown callbacks while we set it in code

    search = widgets.Text(placeholder="Filter processes…", layout=widgets.Layout(width="250px"))
    dropdown = widgets.Dropdown(options=options, layout=widgets.Layout(width="550px"))
    back_b = widgets.Button(description="⟲ Back", layout=widgets.Layout(width="80px"))
    prev_b = widgets.Button(description="◀ Prev", layout=widgets.Layout(width="80px"))
    next_b = widgets.Button(description="Next ▶", layout=widgets.Layout(width="80px"))
    info = widgets.HTML()
    col_layout = widgets.Layout(width="33%")
    used_box = widgets.VBox(layout=col_layout)
    in_box = widgets.VBox(layout=col_layout)
    out_box = widgets.VBox(layout=col_layout)
    out = widgets.Output()

    def go_to(key, remember=True):
        if remember and state["key"] is not None and key != state["key"]:
            state["history"].append(state["key"])
        state["key"] = key
        render()

    def make_buttons(items, style="info"):
        btns = []
        for e in items:
            text = f"{e['name'][:55]} ({e['amount']:.3g} {e['unit']})"
            if e["key"] is None:
                b = widgets.Button(description=text, disabled=True,
                                   tooltip=f"{e['type']} – not navigable",
                                   layout=widgets.Layout(width="95%"))
            else:
                b = widgets.Button(description=text, button_style=style,
                                   tooltip=f"Go to {e['name']} [{e['database']}]",
                                   layout=widgets.Layout(width="95%"))
                b.on_click(lambda _, k=e["key"]: go_to(k))
            btns.append(b)
        return btns

    def render():
        act = get_activity(state["key"])
        inputs, outputs = _collect_exchanges(act)
        used_by, n_used = _collect_used_by(act)

        # keep the dropdown in sync when the target is inside this database
        syncing["on"] = True
        if state["key"] in {v for _, v in dropdown.options}:
            dropdown.value = state["key"]
        syncing["on"] = False

        more = [widgets.HTML(f"<i>… and {n_used - len(used_by)} more</i>")] \
            if n_used > len(used_by) else []
        used_box.children = ([widgets.HTML(f"<b>← Used by ({n_used}) · click to open</b>")]
                             + make_buttons(used_by, style="warning") + more)
        in_box.children = [widgets.HTML("<b>Inputs · click to open</b>")] + make_buttons(inputs)
        out_box.children = [widgets.HTML("<b>Outputs · click to open</b>")] + make_buttons(outputs)
        back_b.disabled = not state["history"]
        ext = "" if state["key"] in all_keys else \
            f" <span style='color:#b45309'>(external database: {state['key'][0]})</span>"
        info.value = f"<b>Current:</b> {act.get('name')}{ext}"

        out.clear_output(wait=True)
        with out:
            display(_build_figure(act, inputs, outputs))

    def on_dropdown(change):
        if not syncing["on"] and change["new"] is not None:
            go_to(change["new"])

    def on_search(change):
        q = change["new"].lower()
        syncing["on"] = True
        dropdown.options = [o for o in options if q in o[0].lower()]
        syncing["on"] = False
        if dropdown.options:
            go_to(dropdown.options[0][1])

    def step(delta):
        vals = [v for _, v in dropdown.options]
        if state["key"] in vals:
            go_to(vals[(vals.index(state["key"]) + delta) % len(vals)])
        elif vals:
            go_to(vals[0])

    def back(_):
        if state["history"]:
            go_to(state["history"].pop(), remember=False)

    search.observe(on_search, "value")
    dropdown.observe(on_dropdown, "value")
    prev_b.on_click(lambda _: step(-1))
    next_b.on_click(lambda _: step(1))
    back_b.on_click(back)

    display(widgets.VBox([
        widgets.HBox([search, dropdown]),
        widgets.HBox([back_b, prev_b, next_b]),
        info,
        out,
        widgets.HBox([used_box, in_box, out_box], layout=widgets.Layout(width="100%")),
    ]))
    if state["key"] is not None:
        render()
