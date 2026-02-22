import time
import numpy as np


class RiskManager:
    def __init__(self, cfg: dict, ex, state, tg):
        self.cfg = cfg
        self.ex = ex
        self.state = state
        self.tg = tg

    def can_trade_today(self) -> bool:
        self.state.reset_day_if_needed()
        eq = self._equity_usdt()
        limit = -eq * float(self.cfg["risk"]["daily_loss_limit_pct"])
        return float(self.state.state.get("day_pnl_usd", 0.0)) > limit

    def is_paused(self) -> bool:
        return time.time() < float(self.state.state.get("pause_until_ts", 0))

    def sleep_pause_window(self):
        time.sleep(10)

    def sleep_until_next_day(self):
        time.sleep(60)

    def _equity_usdt(self) -> float:
        acc = self.ex.account()
        return float(acc.get("totalWalletBalance", acc.get("totalMarginBalance", 0.0)))

    def _atr(self, df, w=14) -> float:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr = []
        for i in range(1, len(close)):
            tr.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
        tr = np.array(tr)
        if len(tr) < w:
            return float(np.mean(tr)) if len(tr) else 0.0
        return float(np.mean(tr[-w:]))

    def build_trade_plan(self, symbol: str, df, signal: dict):
        # skip if already in position or pending
        if symbol in self.state.state.get("open_positions", {}):
            return None
        if symbol in self.state.state.get("pending_entries", {}):
            return None

        equity = self._equity_usdt()
        reserve = equity * float(self.cfg["risk"]["reserve_cash_pct"])
        tradable = max(0.0, equity - reserve)

        risk_usd = equity * float(self.cfg["risk"]["risk_per_trade_pct"])
        if tradable <= 0 or risk_usd <= 0:
            return None

        atr = self._atr(df, int(self.cfg["execution"]["atr_window"]))
        if atr <= 0:
            return None

        sl_dist = float(self.cfg["execution"]["sl_atr_mult"]) * atr
        last = float(df["close"].iloc[-1])

        qty = risk_usd / max(sl_dist, 1e-9)

        # cap notional per symbol
        max_positions = int(self.cfg["trading"]["max_positions"])
        per_asset_cash = tradable / max_positions
        leverage = int(self.cfg["trading"]["leverage"])
        max_notional = per_asset_cash * leverage
        if qty * last > max_notional:
            qty = max_notional / last

        if qty * last < 5:
            return None

        return {
            "symbol": symbol,
            "side": signal["side"],  # BUY/SELL
            "qty": float(qty),
            "last": last,
            "sl_dist": sl_dist,
            "z": float(signal.get("z", 0.0)),
        }

    def record_trade_result(self, pnl_usd: float):
        self.state.reset_day_if_needed()
        self.state.state["day_pnl_usd"] = float(self.state.state.get("day_pnl_usd", 0.0)) + float(pnl_usd)

        if pnl_usd < 0:
            self.state.state["loss_streak"] = int(self.state.state.get("loss_streak", 0)) + 1
            if self.state.state["loss_streak"] >= int(self.cfg["risk"]["loss_streak_pause_count"]):
                pause_m = int(self.cfg["risk"]["loss_streak_pause_minutes"])
                self.state.state["pause_until_ts"] = time.time() + pause_m * 60
                self.tg.send(f"⏸️ Pausando {pause_m} min (loss streak)")
        else:
            self.state.state["loss_streak"] = 0

        self.state.save()
