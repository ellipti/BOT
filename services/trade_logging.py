# services/trade_logging.py
import os, csv
from datetime import datetime, timezone

def append_trade_row(**kw) -> None:
    os.makedirs("trades", exist_ok=True)
    path = os.path.join("trades", "trades.csv")
    is_new = not os.path.exists(path)
    cols = ["time_utc","symbol","side","lot","entry","sl","tp","reason","ticket","dry_run"]
    row = {
        "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": kw.get("symbol"),
        "side": kw.get("side"),
        "lot": kw.get("lot"),
        "entry": kw.get("entry"),
        "sl": kw.get("sl"),
        "tp": kw.get("tp"),
        "reason": kw.get("reason"),
        "ticket": kw.get("ticket"),
        "dry_run": kw.get("dry_run"),
    }
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if is_new:
            w.writeheader()
        w.writerow(row)
