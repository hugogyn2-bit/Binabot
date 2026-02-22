import math
import time


class Scanner:
    def __init__(self, cfg: dict, ex, data, state):
        self.cfg = cfg
        self.ex = ex
        self.data = data
        self.state = state
        self._symbols = None
        self._t24_cache = None
        self._t24_cache_ts = 0

    def _load_exchange_symbols(self):
        info = self.ex.exchange_info()
        symbols = []
        filters = {}
        for s in info.get("symbols", []):
            if s.get("status") != "TRADING":
                continue
            if s.get("contractType") != self.cfg["universe"]["contract_type"]:
                continue
            if s.get("quoteAsset") != self.cfg["universe"]["quote"]:
                continue
            sym = s["symbol"]
            symbols.append(sym)
            fdict = {f["filterType"]: f for f in s.get("filters", [])}
            filters[sym] = fdict

        self._symbols = symbols
        self.state.state["symbol_filters"] = filters
        self.state.save()
        return symbols

    def get_symbols(self):
        if self._symbols is None:
            self._symbols = self._load_exchange_symbols()
        return self._symbols

    def get_filters(self, symbol: str):
        return self.state.state.get("symbol_filters", {}).get(symbol, {})

    def ticker_24h_cached(self, ttl_sec: int = 60):
        now = time.time()
        if self._t24_cache is None or (now - self._t24_cache_ts) > ttl_sec:
            self._t24_cache = self.ex.ticker_24h()
            self._t24_cache_ts = now
        return self._t24_cache

    def execution_filter_ok(self, symbol: str, min_quote_volume: float, max_spread_bps: float) -> tuple[bool, float, float]:
        # returns ok, volume, spread_bps
        t24 = self.ticker_24h_cached()
        tmap = {x["symbol"]: x for x in t24}
        t = tmap.get(symbol)
        if not t:
            return False, 0.0, 1e9

        try:
            qv = float(t.get("quoteVolume", 0.0))
        except Exception:
            qv = 0.0
        if qv < min_quote_volume:
            return False, qv, 1e9

        # prefer WS book
        book = self.state.state.get("last_book", {}).get(symbol)
        if book:
            bid = float(book["bid"])
            ask = float(book["ask"])
        else:
            b = self.ex.book_ticker(symbol)
            bid = float(b["bidPrice"])
            ask = float(b["askPrice"])

        if bid <= 0 or ask <= 0:
            return False, qv, 1e9
        mid = (bid + ask) / 2
        spread_bps = (ask - bid) / mid * 10000.0
        if spread_bps > max_spread_bps:
            return False, qv, spread_bps
        return True, qv, spread_bps
