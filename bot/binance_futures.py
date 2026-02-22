import time
import hmac
import hashlib
import urllib.parse
import requests


class BinanceFutures:
    def __init__(self, cfg: dict, api_key: str, api_secret: str):
        self.cfg = cfg
        self.api_key = api_key
        self.api_secret = api_secret.encode("utf-8")
        self.base = cfg["exchange"]["base_url"]
        self.recv_window = int(cfg["exchange"].get("recv_window", 5000))

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.recv_window
        qs = urllib.parse.urlencode(params, doseq=True)
        sig = hmac.new(self.api_secret, qs.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = sig
        return params

    def _headers(self):
        return {"X-MBX-APIKEY": self.api_key}

    # ---------- Public ----------
    def exchange_info(self) -> dict:
        r = requests.get(f"{self.base}/fapi/v1/exchangeInfo", timeout=10)
        r.raise_for_status()
        return r.json()

    def ticker_24h(self) -> list:
        r = requests.get(f"{self.base}/fapi/v1/ticker/24hr", timeout=10)
        r.raise_for_status()
        return r.json()

    def book_ticker(self, symbol: str) -> dict:
        r = requests.get(f"{self.base}/fapi/v1/ticker/bookTicker", params={"symbol": symbol}, timeout=10)
        r.raise_for_status()
        return r.json()

    def klines(self, symbol: str, interval: str, limit: int) -> list:
        r = requests.get(
            f"{self.base}/fapi/v1/klines",
            params={"symbol": symbol, "interval": interval, "limit": limit},
            timeout=10
        )
        r.raise_for_status()
        return r.json()

    # ---------- User Data Stream ----------
    def new_listen_key(self) -> str:
        r = requests.post(f"{self.base}/fapi/v1/listenKey", headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()["listenKey"]

    def keepalive_listen_key(self, listen_key: str):
        r = requests.put(
            f"{self.base}/fapi/v1/listenKey",
            headers=self._headers(),
            params={"listenKey": listen_key},
            timeout=10
        )
        r.raise_for_status()
        return r.json()

    # ---------- Private ----------
    def account(self) -> dict:
        params = self._sign({})
        r = requests.get(f"{self.base}/fapi/v2/account", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def position_risk(self) -> list:
        params = self._sign({})
        r = requests.get(f"{self.base}/fapi/v2/positionRisk", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def open_orders(self, symbol: str) -> list:
        params = self._sign({"symbol": symbol})
        r = requests.get(f"{self.base}/fapi/v1/openOrders", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def set_leverage(self, symbol: str, leverage: int):
        params = self._sign({"symbol": symbol, "leverage": leverage})
        r = requests.post(f"{self.base}/fapi/v1/leverage", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def set_margin_type(self, symbol: str, marginType: str):
        params = self._sign({"symbol": symbol, "marginType": marginType})
        r = requests.post(f"{self.base}/fapi/v1/marginType", params=params, headers=self._headers(), timeout=10)
        # error 400 common: already set
        if r.status_code in (200, 400):
            try:
                return r.json()
            except Exception:
                return {"status_code": r.status_code}
        r.raise_for_status()
        return r.json()

    def new_order(self, **kwargs) -> dict:
        params = self._sign(kwargs)
        r = requests.post(f"{self.base}/fapi/v1/order", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def cancel_order(self, symbol: str, orderId: int) -> dict:
        params = self._sign({"symbol": symbol, "orderId": orderId})
        r = requests.delete(f"{self.base}/fapi/v1/order", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()

    def cancel_all(self, symbol: str) -> dict:
        params = self._sign({"symbol": symbol})
        r = requests.delete(f"{self.base}/fapi/v1/allOpenOrders", params=params, headers=self._headers(), timeout=10)
        r.raise_for_status()
        return r.json()
