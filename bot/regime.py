import numpy as np


class RegimeDetector:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.w = int(cfg["regime"]["window"])
        self.max_slope = float(cfg["regime"]["range_max_abs_ema_slope"])
        self.max_dir = float(cfg["regime"]["range_max_directionality"])

    @staticmethod
    def ema(x, span):
        alpha = 2 / (span + 1)
        out = []
        v = x[0]
        for xi in x:
            v = alpha * xi + (1 - alpha) * v
            out.append(v)
        return np.array(out)

    def classify(self, df):
        close = df["close"].values
        if len(close) < self.w + 10:
            return "UNKNOWN"
        x = close[-self.w:]
        r = np.diff(np.log(x + 1e-12))

        ema200 = self.ema(close, 200)
        e = ema200[-self.w:]
        slope = (e[-1] - e[0]) / (e[0] + 1e-12)

        directionality = abs(np.sum(r)) / (np.sum(np.abs(r)) + 1e-12)

        if abs(slope) <= self.max_slope and directionality <= self.max_dir:
            return "RANGE"
        return "TREND"
