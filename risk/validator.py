from typing import Literal

Signal = Literal["BUY", "SELL", "HOLD"]

def validate_signal(raw: Signal, close: float, ma_fast: float, ma_slow: float,
                    rsi: float, atr: float, min_atr: float = 2.0) -> Signal:
    trend_up   = ma_fast > ma_slow
    trend_down = ma_fast < ma_slow
    if raw == "BUY":
        if trend_up and rsi >= 50 and atr >= min_atr and close > ma_fast:
            return "BUY"
        return "HOLD"
    if raw == "SELL":
        if trend_down and rsi <= 50 and atr >= min_atr and close < ma_fast:
            return "SELL"
        return "HOLD"
    return "HOLD"
