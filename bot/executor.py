import time
from bot.orders import extract_tick_step, round_price, round_qty


class Executor:
    def __init__(self, cfg: dict, ex, state, tg, scanner):
        self.cfg = cfg
        self.ex = ex
        self.state = state
        self.tg = tg
        self.scanner = scanner

    def sync_open_positions(self):
        pr = self.ex.position_risk()
        opens = {}
        for p in pr:
            amt = float(p.get("positionAmt", 0.0))
            if abs(amt) < 1e-12:
                continue
            sym = p["symbol"]
            entry = float(p.get("entryPrice", 0.0))
            side = "LONG" if amt > 0 else "SHORT"
            opens[sym] = {"side": side, "qty": abs(amt), "entry_price": entry}
        self.state.state["open_positions"] = opens
        self.state.save()

    def place_entry(self, plan: dict):
        sym = plan["symbol"]
        side = plan["side"]
        qty = float(plan["qty"])
        last = float(plan["last"])

        if sym in self.state.state.get("open_positions", {}):
            return
        if sym in self.state.state.get("pending_entries", {}):
            return

        # cooldown
        ci = int(self.state.state.get("candle_index", 0))
        cd = self.state.state.get("cooldown_until", {}).get(sym, -1)
        if ci < int(cd):
            return

        if self.cfg["trading"]["isolated"]:
            self.ex.set_margin_type(sym, "ISOLATED")
        self.ex.set_leverage(sym, int(self.cfg["trading"]["leverage"]))

        book = self.state.state.get("last_book", {}).get(sym)
        if not book:
            b = self.ex.book_ticker(sym)
            bid = float(b["bidPrice"]); ask = float(b["askPrice"])
        else:
            bid = float(book["bid"]); ask = float(book["ask"])

        bps = float(self.cfg["execution"]["maker_price_bps"]) / 10000.0
        if side == "BUY":
            price = min(last, bid * (1 + bps))
        else:
            price = max(last, ask * (1 - bps))

        filters = self.scanner.get_filters(sym)
        tick, step = extract_tick_step(filters)
        price = round_price(price, tick)
        qty = round_qty(qty, step)
        if qty <= 0:
            return

        o = self.ex.new_order(
            symbol=sym,
            side=side,
            type="LIMIT",
            timeInForce="GTC",
            quantity=f"{qty:.8f}",
            price=f"{price:.8f}",
            newOrderRespType="RESULT"
        )
        order_id = int(o.get("orderId"))
        self.state.state["pending_entries"][sym] = {
            "order_id": order_id,
            "side": side,
            "qty": qty,
            "created_ts": time.time(),
            "reprices": 0,
            "sl_dist": float(plan["sl_dist"]),
        }
        self.state.save()
        self.tg.send(f"📥 ENTRY {sym} {side} qty={qty:.6f} @ {price:.6f} (id={order_id})")

    def maybe_reprice_entries(self):
        pend = self.state.state.get("pending_entries", {})
        if not pend:
            return

        now = time.time()
        timeout = int(self.cfg["execution"]["entry_timeout_seconds"])
        reprice_sec = int(self.cfg["execution"]["maker_reprice_seconds"])
        max_reprices = int(self.cfg["execution"]["max_reprices"])

        for sym, pe in list(pend.items()):
            age = now - float(pe["created_ts"])
            if age < reprice_sec:
                continue

            if age >= timeout:
                try:
                    self.ex.cancel_order(sym, int(pe["order_id"]))
                except Exception:
                    pass
                pend.pop(sym, None)
                self.tg.send(f"⌛ ENTRY timeout → cancel {sym}")
                continue

            if int(pe.get("reprices", 0)) >= max_reprices:
                continue

            try:
                self.ex.cancel_order(sym, int(pe["order_id"]))
            except Exception:
                pass

            side = pe["side"]
            qty = float(pe["qty"])

            book = self.state.state.get("last_book", {}).get(sym)
            if not book:
                b = self.ex.book_ticker(sym)
                bid = float(b["bidPrice"]); ask = float(b["askPrice"])
            else:
                bid = float(book["bid"]); ask = float(book["ask"])

            bps = float(self.cfg["execution"]["maker_price_bps"]) / 10000.0
            price = bid * (1 + bps) if side == "BUY" else ask * (1 - bps)

            filters = self.scanner.get_filters(sym)
            tick, step = extract_tick_step(filters)
            price = round_price(price, tick)
            qty = round_qty(qty, step)
            if qty <= 0:
                pend.pop(sym, None)
                continue

            o = self.ex.new_order(
                symbol=sym,
                side=side,
                type="LIMIT",
                timeInForce="GTC",
                quantity=f"{qty:.8f}",
                price=f"{price:.8f}",
                newOrderRespType="RESULT"
            )
            pe["order_id"] = int(o.get("orderId"))
            pe["created_ts"] = now
            pe["reprices"] = int(pe.get("reprices", 0)) + 1
            pend[sym] = pe
            self.tg.send(f"♻️ REPRICE {sym} id={pe['order_id']} @ {price:.6f} (n={pe['reprices']})")

        self.state.state["pending_entries"] = pend
        self.state.save()

    def on_fill(self, sym: str, order_id: int, side: str, filled_qty: float, avg_price: float, status: str):
        # Entry fill?
        pend = self.state.state.get("pending_entries", {})
        pe = pend.get(sym)
        if pe and int(pe.get("order_id", 0)) == int(order_id):
            sl_dist = float(pe.get("sl_dist", 0.0))
            pend.pop(sym, None)
            self.state.state["pending_entries"] = pend

            # cooldown after fill
            cd_candles = int(self.cfg.get("selector", {}).get("cooldown_candles", 8))
            ci = int(self.state.state.get("candle_index", 0))
            self.state.state["cooldown_until"][sym] = ci + cd_candles

            self.state.save()

            # Sync and arm SL/TP
            self.sync_open_positions()
            pos = self.state.state.get("open_positions", {}).get(sym)
            if not pos:
                return

            entry = float(pos["entry_price"]) or float(avg_price)
            pos_side = pos["side"]
            qty_live = float(pos["qty"])

            if pos_side == "LONG":
                sl_price = entry - sl_dist
                tp_price = entry + sl_dist * 0.8
                exit_side = "SELL"
            else:
                sl_price = entry + sl_dist
                tp_price = entry - sl_dist * 0.8
                exit_side = "BUY"

            filters = self.scanner.get_filters(sym)
            tick, step = extract_tick_step(filters)
            sl_price = round_price(sl_price, tick)
            tp_price = round_price(tp_price, tick)
            qty_live = round_qty(qty_live, step)

            try:
                self.ex.new_order(
                    symbol=sym,
                    side=exit_side,
                    type="STOP_MARKET",
                    stopPrice=f"{sl_price:.8f}",
                    closePosition="true",
                    workingType="MARK_PRICE"
                )
                self.ex.new_order(
                    symbol=sym,
                    side=exit_side,
                    type="TAKE_PROFIT_MARKET",
                    stopPrice=f"{tp_price:.8f}",
                    reduceOnly="true",
                    quantity=f"{qty_live:.8f}",
                    workingType="MARK_PRICE"
                )
                self.tg.send(f"✅ FILLED {sym} entry≈{entry:.6f} | SL@{sl_price:.6f} TP@{tp_price:.6f}")
            except Exception as e:
                self.tg.send(f"❌ erro armando SL/TP {sym}: {e}")

            return

        # If it's not an entry fill, ignore (you can extend for exits + PnL)
