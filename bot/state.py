import json
import os
from datetime import date


class StateStore:
    def __init__(self, path: str):
        self.path = path
        self.state = {
            "day": str(date.today()),
            "day_pnl_usd": 0.0,
            "loss_streak": 0,
            "pause_until_ts": 0,

            "open_positions": {},     # symbol -> {side, qty, entry_price}
            "pending_entries": {},    # symbol -> {order_id, side, qty, created_ts, reprices, sl_dist}
            "last_book": {},          # symbol -> {bid, ask, ts}

            "symbol_filters": {},     # cached exchangeInfo filters for rounding
            "cooldown_until": {},     # symbol -> candle_index
            "candle_index": 0,        # increments each new 15m candle boundary
        }
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.state = json.load(f)

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def reset_day_if_needed(self):
        today = str(date.today())
        if self.state.get("day") != today:
            self.state["day"] = today
            self.state["day_pnl_usd"] = 0.0
            self.state["loss_streak"] = 0
            self.state["pause_until_ts"] = 0
            self.save()
