import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> float:
    if df.empty or len(df) < period + 2:
        return np.nan
    d = df.copy()
    hl = (d["high"] - d["low"]).abs()
    hc = (d["high"] - d["close"].shift(1)).abs()
    lc = (d["low"] - d["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]


def ma(series: pd.Series, period: int = 20) -> pd.Series:
    return series.rolling(period).mean()


def rsi(series: pd.Series, period: int = 14) -> float:
    if len(series) < period + 2:
        return float("nan")
    delta = series.diff()
    gain = (delta.clip(lower=0)).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / (loss.replace(0, np.nan))
    return float(100 - (100 / (1 + rs.iloc[-1])))


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    if len(series) < slow + signal + 5:
        return {"value": np.nan, "signal": np.nan, "hist": np.nan}
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return {
        "value": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "hist": float(hist.iloc[-1]),
    }
