import os
from datetime import datetime, timedelta

import requests

API_KEY = os.getenv("TE_API_KEY", "")  # Trading Economics key (optional)

SYMBOL_COUNTRIES = {
    "XAUUSD": ["United States"],
    "EURUSD": ["Euro Area", "Germany", "France", "Italy", "Spain"],
    "GBPUSD": ["United Kingdom"],
}


def has_high_impact_news(symbol: str, now: datetime, window_min: int = 60) -> bool:
    if not API_KEY:
        return False  # API key өгөөгүй бол шүүлтүүрийг алгасна
    countries = SYMBOL_COUNTRIES.get(symbol, ["United States"])
    d1 = (now - timedelta(minutes=window_min)).strftime("%Y-%m-%dT%H:%M")
    d2 = (now + timedelta(minutes=window_min)).strftime("%Y-%m-%dT%H:%M")
    url = (
        "https://api.tradingeconomics.com/calendar?"
        f"importance=3&d1={d1}&d2={d2}&c={','.join(countries)}&format=json"
    )
    try:
        r = requests.get(url, headers={"Authorization": f"Client {API_KEY}"}, timeout=8)
        r.raise_for_status()
        events = r.json() if isinstance(r.json(), list) else []
        return len(events) > 0
    except Exception:
        return False
