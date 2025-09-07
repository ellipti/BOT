"""
Position Sizing and Risk Management
Calculates lot sizes based on account equity, risk percentage, and stop distance.
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    import MetaTrader5 as mt5

logger = logging.getLogger(__name__)


def round_to_step(value: float, step: float, min_v: float, max_v: float) -> float:
    """
    Round value to valid step increment within min/max bounds.

    Args:
        value: Value to round
        step: Step increment (e.g., 0.01 for lots)
        min_v: Minimum allowed value
        max_v: Maximum allowed value

    Returns:
        float: Rounded and constrained value

    Example:
        round_to_step(0.127, 0.01, 0.01, 100.0) -> 0.13
        round_to_step(0.005, 0.01, 0.01, 100.0) -> 0.01 (min)
    """
    if step <= 0:
        raise ValueError(f"Step must be positive, got {step}")

    if min_v > max_v:
        raise ValueError(f"min_v ({min_v}) cannot be greater than max_v ({max_v})")

    # Round to step
    rounded = round(value / step) * step

    # Apply bounds
    result = max(min_v, min(rounded, max_v))

    logger.debug(
        f"round_to_step: {value} -> {rounded} -> {result} (step={step}, bounds=[{min_v}, {max_v}])"
    )
    return result


def calc_sl_tp_by_atr(
    side: str, entry: float, atr: float, sl_mult: float = 1.5, tp_mult: float = 2.0
) -> tuple[float, float]:
    """
    Calculate stop loss and take profit levels based on ATR.

    Args:
        side: Order side ("BUY" or "SELL")
        entry: Entry price
        atr: Average True Range value
        sl_mult: Stop loss multiplier for ATR
        tp_mult: Take profit multiplier for ATR

    Returns:
        tuple[float, float]: (stop_loss, take_profit) prices

    Logic:
        BUY:  SL = entry - (atr × sl_mult), TP = entry + (atr × tp_mult)
        SELL: SL = entry + (atr × sl_mult), TP = entry - (atr × tp_mult)
    """
    if atr <= 0:
        raise ValueError(f"ATR must be positive, got {atr}")

    if entry <= 0:
        raise ValueError(f"Entry price must be positive, got {entry}")

    if sl_mult <= 0 or tp_mult <= 0:
        raise ValueError(
            f"Multipliers must be positive: sl_mult={sl_mult}, tp_mult={tp_mult}"
        )

    side_upper = side.upper()

    if side_upper == "BUY":
        sl = entry - (atr * sl_mult)
        tp = entry + (atr * tp_mult)
    elif side_upper == "SELL":
        sl = entry + (atr * sl_mult)
        tp = entry - (atr * tp_mult)
    else:
        raise ValueError(f"Invalid side: {side}. Must be 'BUY' or 'SELL'")

    logger.debug(
        f"ATR calc: {side} @ {entry:.5f}, ATR={atr:.5f} "
        f"-> SL={sl:.5f} (±{atr*sl_mult:.5f}), TP={tp:.5f} (±{atr*tp_mult:.5f})"
    )

    return sl, tp


def calc_lot_by_risk(
    symbol_info, entry: float, sl: float, equity: float, risk_pct: float
) -> float:
    """
    Calculate position size in lots based on risk management.

    Formula:
        lots = (equity × risk_pct) / (ticks_to_sl × tick_value_per_tick)

    Where:
        ticks_to_sl = |entry - sl| / trade_tick_size
        tick_value_per_tick = trade_tick_value (per 1 lot)

    Args:
        symbol_info: MT5 symbol info object with trading parameters
        entry: Entry price
        sl: Stop loss price
        equity: Account equity
        risk_pct: Risk percentage (e.g., 0.01 for 1%)

    Returns:
        float: Position size in lots, rounded to symbol constraints

    Raises:
        ValueError: If invalid parameters or insufficient data
    """
    if not hasattr(symbol_info, "trade_tick_size"):
        raise ValueError("symbol_info missing trade_tick_size attribute")

    if not hasattr(symbol_info, "trade_tick_value"):
        raise ValueError("symbol_info missing trade_tick_value attribute")

    if not hasattr(symbol_info, "volume_min"):
        raise ValueError("symbol_info missing volume_min attribute")

    if not hasattr(symbol_info, "volume_max"):
        raise ValueError("symbol_info missing volume_max attribute")

    if not hasattr(symbol_info, "volume_step"):
        raise ValueError("symbol_info missing volume_step attribute")

    tick_size = symbol_info.trade_tick_size
    tick_value = symbol_info.trade_tick_value  # USD value per tick per lot
    volume_min = symbol_info.volume_min
    volume_max = symbol_info.volume_max
    volume_step = symbol_info.volume_step

    if tick_size <= 0:
        raise ValueError(f"Invalid tick_size: {tick_size}")

    if tick_value <= 0:
        raise ValueError(f"Invalid tick_value: {tick_value}")

    if equity <= 0:
        raise ValueError(f"Equity must be positive: {equity}")

    if risk_pct <= 0 or risk_pct > 1:
        raise ValueError(f"risk_pct must be between 0 and 1: {risk_pct}")

    # Calculate stop distance in ticks
    stop_distance_price = abs(entry - sl)
    ticks_to_sl = stop_distance_price / tick_size

    if ticks_to_sl <= 0:
        raise ValueError(
            f"Stop distance too small: {stop_distance_price} (tick_size={tick_size})"
        )

    # Calculate risk amount in account currency
    risk_amount = equity * risk_pct

    # Calculate position size
    # lots = risk_amount / (ticks_to_sl * tick_value_per_tick)
    raw_lots = risk_amount / (ticks_to_sl * tick_value)

    # Round to symbol volume constraints
    final_lots = round_to_step(raw_lots, volume_step, volume_min, volume_max)

    logger.info(
        f"Position sizing: equity=${equity:.2f}, risk={risk_pct:.1%} (${risk_amount:.2f}), "
        f"stop_distance={stop_distance_price:.5f} ({ticks_to_sl:.1f} ticks), "
        f"tick_value=${tick_value:.2f} -> {raw_lots:.3f} lots -> {final_lots:.3f} lots (final)"
    )

    return final_lots


def fetch_atr(symbol: str, timeframe: int, period: int = 14) -> float | None:
    """
    Fetch Average True Range (ATR) from MT5 historical data.

    Args:
        symbol: Trading symbol (e.g., "XAUUSD")
        timeframe: MT5 timeframe constant (e.g., mt5.TIMEFRAME_M30)
        period: ATR calculation period (default: 14)

    Returns:
        float: ATR value or None if calculation failed

    Raises:
        ImportError: If MT5 or pandas not available
        RuntimeError: If MT5 not initialized or data unavailable
    """
    try:
        import MetaTrader5 as mt5
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "MT5 and pandas required for ATR calculation. "
            "Install with: pip install MetaTrader5 pandas"
        ) from e

    if not mt5.initialize():
        raise RuntimeError("MT5 not initialized. Call mt5.initialize() first.")

    # Fetch bars (we need period+1 bars to calculate ATR properly)
    bars_needed = period + 20  # Extra buffer for calculation
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars_needed)

    if rates is None or len(rates) < period + 1:
        logger.error(f"Insufficient data for ATR calculation: {symbol} {timeframe}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")

    # Calculate True Range components
    df["hl"] = df["high"] - df["low"]  # High - Low
    df["hcp"] = abs(df["high"] - df["close"].shift(1))  # |High - Previous Close|
    df["lcp"] = abs(df["low"] - df["close"].shift(1))  # |Low - Previous Close|

    # True Range = max(HL, HCP, LCP)
    df["tr"] = df[["hl", "hcp", "lcp"]].max(axis=1)

    # ATR = EMA of True Range
    atr_series = df["tr"].ewm(span=period, adjust=False).mean()

    # Get the most recent ATR value
    current_atr = atr_series.iloc[-1]

    logger.debug(f"ATR({period}) for {symbol}: {current_atr:.5f}")

    return float(current_atr) if pd.notna(current_atr) else None


def get_account_equity() -> float | None:
    """
    Get current account equity from MT5.

    Returns:
        float: Account equity or None if unavailable

    Raises:
        ImportError: If MT5 not available
        RuntimeError: If MT5 not initialized
    """
    try:
        import MetaTrader5 as mt5
    except ImportError as e:
        raise ImportError(
            "MT5 required for account info. " "Install with: pip install MetaTrader5"
        ) from e

    if not mt5.initialize():
        raise RuntimeError("MT5 not initialized. Call mt5.initialize() first.")

    account_info = mt5.account_info()
    if account_info is None:
        logger.error("Cannot retrieve account information from MT5")
        return None

    equity = account_info.equity
    logger.debug(f"Account equity: ${equity:.2f}")

    return equity
