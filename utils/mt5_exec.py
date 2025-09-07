import time
from logging import getLogger
from math import isfinite
from typing import Any

import MetaTrader5 as mt5

logger = getLogger("exec")

RETCODE_OK = {mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED}


def place_market(
    symbol: str,
    side: str,
    lot: float,
    sl: float | None,
    tp: float | None,
    retries=2,
    pause=0.7,
):
    # Check market state first
    info = mt5.symbol_info(symbol)
    if not info or not info.select:
        logger.error(f"Failed to get/select {symbol}")
        return {"ok": False, "retcode": mt5.TRADE_RETCODE_INVALID_SYMBOL}

    # Trade mode: 0=disabled, 1=long only, 2=short only, 4=full
    if info.trade_mode != 4:
        logger.error(
            f"Market is not fully tradeable for {symbol} (trade_mode={info.trade_mode})"
        )
        return {"ok": False, "retcode": mt5.TRADE_RETCODE_MARKET_CLOSED}

    # Get current market price for fallback
    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        logger.error("Failed to get market price")
        return {"ok": False, "retcode": None}
    entry = tick.ask if side == "BUY" else tick.bid

    order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
    # Get current price for request
    tick = mt5.symbol_info_tick(symbol)
    entry = tick.ask if side == "BUY" else tick.bid

    # Market order with all required fields
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "deviation": 20,
        # Price/stops
        "price": entry,
        "sl": sl,
        "tp": tp,
        # Required fields
        "magic": 0,
        "comment": "bot trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }

    for i in range(retries + 1):
        res = mt5.order_send(req)
        if res and res.retcode in RETCODE_OK:
            return {"ok": True, "ticket": res.order, "retcode": res.retcode, "lot": lot}
        logger.warning(
            f"order_send fail (attempt {i+1}/{retries+1}) retcode={getattr(res,'retcode',None)}"
        )
        # Handle invalid stops error with fallback
        if getattr(res, "retcode", None) == 10027 and i == retries:
            logger.info("Attempting fallback execution (separate SL/TP)")
            return place_with_fallback(symbol, side, lot, entry, sl or 0.0, tp or 0.0)
        time.sleep(pause)
    return {"ok": False, "retcode": getattr(res, "retcode", None)}


def compute_stops(
    symbol: str, side: str, entry: float, sl_points: float, tp_points: float
) -> tuple[float, float]:
    """Convert stop/take profit points to absolute prices based on symbol specs."""
    info = mt5.symbol_info(symbol)
    point = info.point
    digits = info.digits
    stop_dist = (info.trade_stops_level or 0) * point
    # BUY: SL доош, TP дээш; SELL: эсрэгээр
    if side == "BUY":
        sl = entry - max(sl_points, stop_dist)
        tp = entry + max(tp_points, stop_dist)
    else:
        sl = entry + max(sl_points, stop_dist)
        tp = entry - max(tp_points, stop_dist)
    # Digits-д тааруулж тоймлоё
    sl = round(sl, digits)
    tp = round(tp, digits)
    # sanity
    if not (isfinite(sl) and isfinite(tp)):
        raise ValueError("Invalid SL/TP computed")
    # хэт ойр байвал багахан нэмэгдүүлж/хасъя
    if side == "BUY":
        if entry - sl < stop_dist:
            sl = round(entry - stop_dist, digits)
        if tp - entry < stop_dist:
            tp = round(entry + stop_dist, digits)
    else:
        if sl - entry < stop_dist:
            sl = round(entry + stop_dist, digits)
        if entry - tp < stop_dist:
            tp = round(entry - stop_dist, digits)
    return sl, tp


def place_with_fallback(
    symbol: str,
    side: str,
    volume: float,
    entry: float,
    sl_price: float,
    tp_price: float,
    deviation: int = 30,
) -> dict[str, Any]:
    """Place order with fallback for brokers that reject combined SL/TP placement."""
    order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
    # Market order with mandatory fields
    req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "deviation": deviation,
        # Required fields
        "price": entry,  # Request price
        "magic": 0,  # Expert ID
        "comment": "force trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_FOK,
    }
    r = mt5.order_send(req)
    if r and r.retcode in RETCODE_OK:
        # set SL/TP afterwards
        pos = mt5.positions_get(ticket=r.order) or mt5.positions_get(symbol=symbol)
        if pos:
            ticket = pos[0].ticket
            mod = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
                "sl": sl_price,
                "tp": tp_price,
            }
            mt5.order_send(mod)
        return {"ok": True, "ticket": r.order, "retcode": r.retcode}
    return {"ok": False, "retcode": getattr(r, "retcode", None)}
