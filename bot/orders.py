import math


def _to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def extract_tick_step(filters: dict):
    tick = None
    step = None
    pf = filters.get("PRICE_FILTER")
    lf = filters.get("LOT_SIZE")
    if pf:
        tick = _to_float(pf.get("tickSize"))
    if lf:
        step = _to_float(lf.get("stepSize"))
    return tick or 0.0, step or 0.0


def round_price(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return math.floor(price / tick) * tick


def round_qty(qty: float, step: float) -> float:
    if step <= 0:
        return qty
    return math.floor(qty / step) * step
