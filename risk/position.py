def calc_lot(balance_usd: float, risk_pct: float, atr_points: float, sl_mult: float,
             tick_value_per_lot: float = 1.0, point_value: float = 0.1) -> float:
    """
    XAUUSD жишээ: 1 point = $0.01; ихэнх брокер дээр 1 lot = $1/tick (~$1 per 0.1 move).
    Тодорхой бус бол өөрийн брокерийн tick_value_per_lot, point_value-г тааруул.
    """
    risk_usd = balance_usd * risk_pct
    sl_points = atr_points * sl_mult
    sl_usd_per_lot = (sl_points / point_value) * tick_value_per_lot
    if sl_usd_per_lot <= 0:
        return 0.01
    lot = max(risk_usd / sl_usd_per_lot, 0.01)
    return round(lot, 2)
