# services/vision_context.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Dict, Any, List
import pandas as pd
import MetaTrader5 as mt5

from core.config import get_settings
from core.state import StateStore
from strategies.indicators import atr  # танайд аль хэдийн бий

def _round(x: float | None, d: int) -> float | None:
    return None if x is None else round(float(x), d)

def _bars_compact(df: pd.DataFrame, digits: int, n: int = 200) -> List[Dict[str, Any]]:
    d = df.tail(n)
    out = []
    for _, r in d.iterrows():
        out.append({
            "t": r["time"].to_pydatetime().replace(tzinfo=timezone.utc).isoformat().replace("+00:00","Z"),
            "o": _round(r["open"], digits),
            "h": _round(r["high"], digits),
            "l": _round(r["low"], digits),
            "c": _round(r["close"], digits),
            "v": int(r.get("tick_volume", r.get("real_volume", r.get("volume", 0)))),
        })
    return out

def build_vision_context(
    df: pd.DataFrame,
    symbol: str,
    timeframe_str: str,
    news_high_impact_soon: bool = False
) -> Dict[str, Any]:
    """Vision-д өгөх цөм JSON. Зөвхөн хамгийн хэрэгцээтэй талбарууд."""
    settings = get_settings()
    si = mt5.symbol_info(symbol)
    if si is None:
        raise RuntimeError(f"symbol_info({symbol}) is None")

    tick = mt5.symbol_info_tick(symbol)
    spread = None
    if tick and si:
        spread = abs((tick.ask or 0) - (tick.bid or 0))

    acc = mt5.account_info()
    if acc is None:
        raise RuntimeError("account_info() is None")

    # Индикаторууд (минимал)
    a = float(atr(df, period=settings.atr_period)) if not df.empty else float("nan")
    ma20 = float(df["close"].rolling(20).mean().iloc[-1]) if len(df) >= 20 else float("nan")
    # RSI-г минимаар:
    rsi = float("nan")
    if len(df) >= 16:
        delta = df["close"].diff()
        up = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
        dn = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
        rs = up / dn.replace(0, pd.NA)
        rsi = float(100 - (100 / (1 + rs.iloc[-1])))

    # Guards (spread/news/cooldown)
    state = StateStore()
    cooldown_ok = state.cooldown_elapsed(symbol, settings.cooldown_minutes)

    return {
        "symbol": symbol,
        "timeframe": timeframe_str,
        "now_utc": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "digits": si.digits,
        "point": si.point,
        "tick_value": si.trade_tick_value or 0.0,
        "contract_size": si.trade_contract_size or getattr(si, "contract_size", 0.0),
        "spread": _round(spread, si.digits) if spread is not None else None,
        "account": {
            "equity": float(acc.equity),
            "leverage": int(acc.leverage),
            "currency": acc.currency
        },
        "risk_model": {
            "risk_per_trade": settings.risk_per_trade,
            "sl_atr_mult": settings.sl_atr_mult,
            "tp_r_mult": settings.tp_r_mult,
            "cooldown_minutes": settings.cooldown_minutes
        },
        "indicators": {
            "atr": a,
            "rsi_14": rsi,
            "ma20": ma20
        },
        "bars": _bars_compact(df, digits=si.digits, n=200),
        "guards": {
            "spread_ok": (spread is None) or (spread <= 5 * si.point),
            "news_ok": (not news_high_impact_soon),
            "cooldown_ok": cooldown_ok
        }
    }
