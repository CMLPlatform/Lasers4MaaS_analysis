"""Min/max parameter ranges and the Brightway exchanges made from them."""


def bounds(value):
    """Return (low, high) of a {"min", "max"} range, or (value, value) for a number."""
    if isinstance(value, dict):
        return float(value["min"]), float(value["max"])
    value = float(value)
    return value, value


def as_key(node_or_key):
    """Return the key of a Brightway node, or the value itself if it is a key already."""
    return getattr(node_or_key, "key", node_or_key)


def production(database_name, code, amount=1):
    """Production exchange of a new process."""
    return {"input": (database_name, code), "amount": amount, "type": "production"}


def ranged_exchange(input_, low, high, always_ranged=True):
    """Technosphere exchange with amount = midpoint, and minimum/maximum for the scenarios.

    With `always_ranged=False`, a range with low == high gives a plain exchange
    (no minimum, maximum or uncertainty type).
    """
    if low > high:
        raise ValueError(f"Range of {input_!r} has minimum {low} above maximum {high}")
    exchange = {"input": as_key(input_), "amount": (low + high) / 2, "type": "technosphere"}
    if always_ranged or low != high:
        exchange.update({"minimum": low, "maximum": high, "uncertainty_type": 1})
    return exchange
