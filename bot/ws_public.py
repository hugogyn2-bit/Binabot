import json
import threading
import time
import websocket


class PublicWS:
    def __init__(self, cfg: dict, state, tg):
        self.cfg = cfg
        self.state = state
        self.tg = tg
        self.ws_url = cfg["exchange"]["ws_base"]
        self.streams = cfg["ws"]["public_streams"]
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        backoff = int(self.cfg["ws"].get("reconnect_backoff_sec", 5))
        stream_path = "/".join(self.streams)
        url = f"{self.ws_url}/{stream_path}"

        while not self._stop.is_set():
            try:
                ws = websocket.WebSocketApp(
                    url,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                ws.run_forever(ping_interval=20, ping_timeout=10)
            except Exception as e:
                self.tg.send(f"⚠️ PublicWS erro: {e}")
            time.sleep(backoff)

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            sym = data.get("s")
            if not sym:
                return
            bid = float(data.get("b", 0))
            ask = float(data.get("a", 0))
            if bid <= 0 or ask <= 0:
                return
            self.state.state["last_book"][sym] = {"bid": bid, "ask": ask, "ts": time.time()}
        except Exception:
            pass

    def _on_error(self, ws, error):
        self.tg.send(f"⚠️ PublicWS on_error: {error}")

    def _on_close(self, ws, code, msg):
        self.tg.send("⚠️ PublicWS desconectou")
