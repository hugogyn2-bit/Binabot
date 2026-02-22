import numpy as np


class MeanReversionStrategy:
    def __init__(self, cfg: dict):
        s = cfg["strategy"]
        self.z_window = int(s["z_window"])
        self.entry_z = float(s["entry_z"])
        self.exit_z_partial = float(s["exit_z_partial"])
        self.exit_z_full = float(s["exit_z_full"])
        self.stop_z = float(s["stop_z"])

    @staticmethod
    def ema(x, span):
        alpha = 2 / (span + 1)
        out = []
        v = x[0]
        for xi in x:
            v = alpha * xi + (1 - alpha) * v
            out.append(v)
        return np.array(out)

    def compute_z(self, df) -> float | None:
        close = df["close"].values
        if len(close) < self.z_window + 20:
            return None
        fair = self.ema(close, 20)
        x = close[-self.z_window:]
        f = fair[-self.z_window:]
        spread = x - f
        mu = np.mean(spread)
        sd = np.std(spread) + 1e-12
        z = (spread[-1] - mu) / sd
        return float(z)

    def generate_signal(self, df):
        z = self.compute_z(df)
        if z is None:
            return None
        if z <= -self.entry_z:
            return {"side": "BUY", "z": z}
        if z >= self.entry_z:
            return {"side": "SELL", "z": z}
        return None
