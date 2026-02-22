import math
import numpy as np


class TradeSelector:
    def __init__(self, cfg, ex, state, tg, scanner, data):
        self.cfg = cfg
        self.ex = ex
        self.state = state
        self.tg = tg
        self.scanner = scanner
        self.data = data

    def _corr_penalty(self, sym: str, df, open_symbols: list[str]) -> float:
        sel = self.cfg.get("selector", {})
        w = int(sel.get("corr_window", 96))
        thr = float(sel.get("corr_penalty_threshold", 0.75))
        factor = float(sel.get("corr_penalty_factor", 0.50))

        if not open_symbols:
            return 1.0

        # returns for candidate
        c = df["close"].values
        if len(c) < w + 2:
            return 1.0
        r = np.diff(np.log(c[-(w+1):] + 1e-12))

        # compute max corr against existing positions
        max_corr = 0.0
        for osym in open_symbols:
            try:
                odf = self.data.get_klines(osym)
                if odf is None:
                    continue
                oc = odf["close"].values
                if len(oc) < w + 2:
                    continue
                orr = np.diff(np.log(oc[-(w+1):] + 1e-12))
                n = min(len(r), len(orr))
                if n < 10:
                    continue
                corr = float(np.corrcoef(r[-n:], orr[-n:])[0, 1])
                if abs(corr) > abs(max_corr):
                    max_corr = corr
            except Exception:
                continue

        if abs(max_corr) >= thr:
            return factor
        return 1.0

    def rank_candidates(self, candidates: list[dict]) -> list[dict]:
        return sorted(candidates, key=lambda x: x["score"], reverse=True)

    def build_candidates(self, universe: list[str], regime, strat, risk) -> list[dict]:
        ucfg = self.cfg["universe"]
        min_vol = float(ucfg["min_quote_volume_usdt"])
        max_spread = float(ucfg["max_spread_bps"])
        cap_scan = int(ucfg.get("max_symbols_scan", 250))

        open_syms = list(self.state.state.get("open_positions", {}).keys())
        pend_syms = list(self.state.state.get("pending_entries", {}).keys())

        # available slots
        max_pos = int(self.cfg["trading"]["max_positions"])
        slots = max_pos - (len(open_syms) + len(pend_syms))
        if slots <= 0:
            return []

        # iterate universe with a cap to limit REST load
        symbols = universe if cap_scan <= 0 else universe[:cap_scan]

        candidates = []
        for sym in symbols:
            if sym in open_syms or sym in pend_syms:
                continue

            ok, qv, spread_bps = self.scanner.execution_filter_ok(sym, min_vol, max_spread)
            if not ok:
                continue

            df = self.data.get_klines(sym)
            if df is None or len(df) < 150:
                continue

            if regime.classify(df) != "RANGE":
                continue

            sig = strat.generate_signal(df)
            if not sig:
                continue

            plan = risk.build_trade_plan(sym, df, sig)
            if not plan:
                continue

            # base score: |z| * sqrt(volume) / (spread+1)
            z = abs(float(plan.get("z", 0.0)))
            score = z * math.sqrt(max(qv, 1.0)) / (spread_bps + 1.0)

            # correlation penalty vs existing open positions
            score *= self._corr_penalty(sym, df, open_syms)

            plan["score"] = float(score)
            candidates.append(plan)

        return candidates, slots
