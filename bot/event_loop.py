import time


class EventLoop:
    def __init__(self, cfg, state, tg, data, scanner, regime, strat, risk, selector, execu):
        self.cfg = cfg
        self.state = state
        self.tg = tg
        self.data = data
        self.scanner = scanner
        self.regime = regime
        self.strat = strat
        self.risk = risk
        self.selector = selector
        self.execu = execu

    def run(self):
        # load universe once; refresh occasionally could be added
        universe = self.scanner.get_symbols()

        while True:
            if not self.risk.can_trade_today():
                self.tg.send("🛑 Daily loss atingido. Pausando.")
                self.risk.sleep_until_next_day()
                continue
            if self.risk.is_paused():
                self.risk.sleep_pause_window()
                continue

            # reprice pending entries frequently
            self.execu.maybe_reprice_entries()

            # tick
            time.sleep(2)

            # new candle boundary
            if not self._is_new_candle_boundary():
                continue

            # increment candle index (for cooldown)
            self.state.state["candle_index"] = int(self.state.state.get("candle_index", 0)) + 1
            self.state.save()

            # build candidates across universe
            result = self.selector.build_candidates(universe, self.regime, self.strat, self.risk)
            if not result:
                continue

            candidates, slots = result
            if not candidates:
                continue

            ranked = self.selector.rank_candidates(candidates)

            # place up to available slots
            placed = 0
            for plan in ranked:
                if placed >= slots:
                    break
                self.execu.place_entry(plan)
                placed += 1

    def _is_new_candle_boundary(self) -> bool:
        tf = self.cfg["trading"]["timeframe"]
        step = 900 if tf == "15m" else 60
        now = int(time.time())
        return (now % step) in (0, 1, 2)
