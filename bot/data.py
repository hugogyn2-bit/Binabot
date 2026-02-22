import time
import pandas as pd


class DataClient:
    def __init__(self, cfg: dict, ex):
        self.cfg = cfg
        self.ex = ex
        self.tf = cfg["trading"]["timeframe"]
        self.limit = int(cfg["trading"]["lookback_klines"])

    def get_klines(self, symbol: str) -> pd.DataFrame | None:
        kl = self.ex.klines(symbol, self.tf, self.limit)
        if not kl:
            return None
        df = pd.DataFrame(kl, columns=[
            "open_time","open","high","low","close","volume",
            "close_time","quote_volume","trades","taker_base","taker_quote","ignore"
        ])
        for c in ["open","high","low","close","volume","quote_volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df.set_index("open_time", inplace=True)
        return df.dropna()

    def sleep_to_next_candle(self):
        tf = self.tf
        step = 900 if tf == "15m" else 60
        now = int(time.time())
        sleep = step - (now % step) + 2
        time.sleep(sleep)
