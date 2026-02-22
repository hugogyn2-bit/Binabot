# Binance Quant Mean-Reversion Bot (USDT-M Futures) — Event-driven + Universe Scan

**What it does**
- Scans **all USDT-M Perpetual** symbols on Binance Futures.
- Filters for execution quality (min 24h quote volume + max spread).
- Detects **RANGE** regime (mean reversion only).
- Computes **z-score** mean-reversion signal (against EMA20).
- Ranks candidates by a score that favors stronger signal + liquidity and penalizes spread/correlation.
- Opens up to **max_positions (default 4)**, one per symbol (One-way mode).
- Uses **Public WS** for bookTicker and **User Data Stream** for fills.
- Places entry as **LIMIT** with **cancel & reprice**.
- Arms **SL/TP (MARK_PRICE triggers)** only after fill is confirmed.

## Quickstart (Oracle VM)
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git
git clone <your repo url>
cd binance-quant-mr-bot

python3 -m venv botenv
source botenv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # add keys + telegram

python main.py
```

## Run as systemd service
Edit the paths if needed, then:
```bash
sudo cp systemd/tradingbot.service /etc/systemd/system/tradingbot.service
sudo systemctl daemon-reload
sudo systemctl enable tradingbot
sudo systemctl start tradingbot
journalctl -u tradingbot -f
```

## Safety notes
- Binance API: **Futures enabled**, **Withdrawals disabled**, **IP whitelist** (Oracle VM public IP).
- Start with **leverage=3**, **risk_per_trade_pct=0.005**, **daily_loss_limit_pct=0.03**.
- This is a template. Test on testnet/paper before real money.
