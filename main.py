import os
from dotenv import load_dotenv

from bot.logger import setup_logging
from bot.state import StateStore
from bot.telegram import Telegram
from bot.binance_futures import BinanceFutures
from bot.data import DataClient
from bot.scanner import Scanner
from bot.regime import RegimeDetector
from bot.strategy import MeanReversionStrategy
from bot.risk import RiskManager
from bot.executor import Executor
from bot.event_loop import EventLoop
from bot.ws_public import PublicWS
from bot.ws_user import UserWS
from bot.selector import TradeSelector
from bot.utils import load_yaml


def main():
    load_dotenv()
    cfg = load_yaml("config.yaml")
    setup_logging()

    state = StateStore("state.json")
    tg = Telegram(
        token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.getenv("TELEGRAM_CHAT_ID", "")
    )

    api_key = os.getenv("BINANCE_API_KEY", "")
    api_secret = os.getenv("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        raise RuntimeError("Configure BINANCE_API_KEY e BINANCE_API_SECRET no .env")

    ex = BinanceFutures(cfg, api_key, api_secret)
    data = DataClient(cfg, ex)
    scanner = Scanner(cfg, ex, data, state)
    regime = RegimeDetector(cfg)
    strat = MeanReversionStrategy(cfg)
    risk = RiskManager(cfg, ex, state, tg)
    selector = TradeSelector(cfg, ex, state, tg, scanner, data)

    execu = Executor(cfg, ex, state, tg, scanner)

    # Sync initial positions
    execu.sync_open_positions()

    # Public WS (book)
    pubws = PublicWS(cfg, state, tg)
    pubws.start()

    # User WS (fills)
    userws = UserWS(cfg, ex, state, tg, on_fill_callback=execu.on_fill)
    userws.start()

    tg.send("🤖 Bot QUANT iniciado: universe-scan MR (15m) + fills via user stream")

    loop = EventLoop(cfg, state, tg, data, scanner, regime, strat, risk, selector, execu)
    loop.run()


if __name__ == "__main__":
    main()
