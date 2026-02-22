import json
import threading
import time
import websocket


class UserWS:
    def __init__(self, cfg: dict, ex, state, tg, on_fill_callback):
        self.cfg = cfg
        self.ex = ex
        self.state = state
        self.tg = tg
        self.on_fill = on_fill_callback

        self._stop = threading.Event()
        self._thread = None
        self._keepalive_thread = None
        self.listen_key = None

    def start(self):
        self.listen_key = self.ex.new_listen_key()
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()

        self._keepalive_thread = threading.Thread(target=self._keepalive, daemon=True)
        self._keepalive_thread.start()

    def stop(self):
        self._stop.set()

    def _keepalive(self):
        while not self._stop.is_set():
            try:
                if self.listen_key:
                    self.ex.keepalive_listen_key(self.listen_key)
            except Exception as e:
                self.tg.send(f"⚠️ UserWS keepalive erro: {e}")
            time.sleep(30 * 60)

    def _run_ws(self):
        backoff = int(self.cfg["ws"].get("reconnect_backoff_sec", 5))
        while not self._stop.is_set():
            try:
                if not self.listen_key:
                    self.listen_key = self.ex.new_listen_key()
                url = f"{self.cfg['exchange']['ws_base']}/{self.listen_key}"
                ws = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                self.tg.send(f"⚠️ UserWS erro: {e}")
            time.sleep(backoff)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            et = data.get("e")

            if et == "ACCOUNT_UPDATE":
                a = data.get("a", {})
                positions = a.get("P", [])
                opens = self.state.state.get("open_positions", {})
                for p in positions:
                    sym = p.get("s")
                    amt = float(p.get("pa", 0.0))
                    ep = float(p.get("ep", 0.0))
                    if not sym:
                        continue
                    if abs(amt) < 1e-12:
                        opens.pop(sym, None)
                    else:
                        opens[sym] = {
                            "side": "LONG" if amt > 0 else "SHORT",
                            "qty": abs(amt),
                            "entry_price": ep,
                        }
                self.state.state["open_positions"] = opens

            elif et == "ORDER_TRADE_UPDATE":
                o = data.get("o", {})
                sym = o.get("s")
                status = o.get("X")
                exec_type = o.get("x")
                order_id = int(o.get("i", 0))
                side = o.get("S")
                filled_qty = float(o.get("z", 0.0))
                avg_price = float(o.get("ap", 0.0))

                if exec_type == "TRADE" and filled_qty > 0 and sym:
                    self.on_fill(sym, order_id, side, filled_qty, avg_price, status)

                if status in ("CANCELED", "EXPIRED", "REJECTED") and sym:
                    pend = self.state.state.get("pending_entries", {})
                    pe = pend.get(sym)
                    if pe and int(pe.get("order_id", 0)) == order_id:
                        pend.pop(sym, None)
                        self.state.state["pending_entries"] = pend

        except Exception:
            pass

    def _on_error(self, ws, error):
        self.tg.send(f"⚠️ UserWS on_error: {error}")

    def _on_close(self, ws, code, msg):
        self.tg.send("⚠️ UserWS desconectou")
