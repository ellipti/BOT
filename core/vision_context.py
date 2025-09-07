import json
from dataclasses import asdict, dataclass

import MetaTrader5 as mt5
import pandas as pd

from core.logger import get_logger

logger = get_logger("vision")


@dataclass
class PriceLevel:
    price: float
    type: str  # "support", "resistance", "entry", "stop", "target"
    strength: float  # 0.0 to 1.0
    timeframe: str  # e.g. "H4", "H1", "M15"
    description: str


@dataclass
class TrendLine:
    start_time: str
    end_time: str
    start_price: float
    end_price: float
    type: str  # "up", "down", "channel_upper", "channel_lower"
    timeframe: str
    strength: float


@dataclass
class Pattern:
    type: str  # e.g. "double_top", "head_shoulders", "triangle"
    start_time: str
    end_time: str
    high: float
    low: float
    confidence: float
    timeframe: str


@dataclass
class VisionContext:
    # Market Data
    symbol: str
    timeframe: str
    current_price: float
    high: float
    low: float
    spread: float
    volume: float

    # Technical Indicators
    atr: float
    rsi: float
    macd: dict[str, float]  # {"main": 0, "signal": 0, "hist": 0}
    ma_fast: float
    ma_slow: float

    # Market Structure
    trend_htf: str  # "up", "down", "sideways"
    trend_mtf: str
    trend_ltf: str
    key_levels: list[PriceLevel]
    trendlines: list[TrendLine]
    patterns: list[Pattern]

    # Risk Parameters
    next_news_minutes: int | None
    last_trade_minutes: int | None
    volatility_rank: float  # 0-1 scale

    # Additional Context
    session: str  # "asian", "london", "new_york", "overlap"
    market_phase: str  # "trending", "ranging", "breakout", "reversal"

    def to_json(self) -> str:
        """Convert context to JSON string"""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "VisionContext":
        """Create context from JSON string"""
        data = json.loads(json_str)

        # Convert nested structures
        data["key_levels"] = [PriceLevel(**level) for level in data["key_levels"]]
        data["trendlines"] = [TrendLine(**line) for line in data["trendlines"]]
        data["patterns"] = [Pattern(**pattern) for pattern in data["patterns"]]

        return cls(**data)


def build_vision_context(
    symbol: str,
    timeframe: int = mt5.TIMEFRAME_M15,  # Default to M15
    htf_data: pd.DataFrame | None = None,
    mtf_data: pd.DataFrame | None = None,
    ltf_data: pd.DataFrame | None = None,
) -> VisionContext:
    """
    Build trading context from market data across timeframes

    Args:
        symbol: Trading symbol (e.g. "EURUSD")
        timeframe: Main timeframe for analysis
        htf_data: Higher timeframe data (optional)
        mtf_data: Main timeframe data (optional)
        ltf_data: Lower timeframe data (optional)

    Returns:
        VisionContext object with full market context
    """
    # Get market data if not provided
    if mtf_data is None:
        mtf_data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, timeframe, 0, 100))

    if htf_data is None:
        htf_tf = _get_higher_timeframe(timeframe)
        htf_data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, htf_tf, 0, 100))

    if ltf_data is None:
        ltf_tf = _get_lower_timeframe(timeframe)
        ltf_data = pd.DataFrame(mt5.copy_rates_from_pos(symbol, ltf_tf, 0, 100))

    # Calculate indicators
    current_price = mtf_data.iloc[-1]["close"]
    atr = _calculate_atr(mtf_data)
    rsi = _calculate_rsi(mtf_data["close"])
    macd = _calculate_macd(mtf_data["close"])
    ma_fast = mtf_data["close"].rolling(window=20).mean().iloc[-1]
    ma_slow = mtf_data["close"].rolling(window=50).mean().iloc[-1]

    # Analyze trends
    trend_htf = _analyze_trend(htf_data)
    trend_mtf = _analyze_trend(mtf_data)
    trend_ltf = _analyze_trend(ltf_data)

    # Find key levels
    key_levels = _find_key_levels(htf_data, mtf_data)

    # Detect patterns
    patterns = _detect_patterns(mtf_data)

    # Draw trendlines
    trendlines = _draw_trendlines(mtf_data)

    # Get market phase
    market_phase = _determine_market_phase(mtf_data, patterns, trend_mtf)

    # Get session
    session = _determine_session()

    return VisionContext(
        symbol=symbol,
        timeframe=_timeframe_to_string(timeframe),
        current_price=current_price,
        high=mtf_data["high"].max(),
        low=mtf_data["low"].min(),
        spread=mt5.symbol_info(symbol).spread * mt5.symbol_info(symbol).point,
        volume=mtf_data["tick_volume"].mean(),
        atr=atr,
        rsi=rsi,
        macd=macd,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        trend_htf=trend_htf,
        trend_mtf=trend_mtf,
        trend_ltf=trend_ltf,
        key_levels=key_levels,
        trendlines=trendlines,
        patterns=patterns,
        next_news_minutes=None,  # TODO: Implement news calendar
        last_trade_minutes=None,  # TODO: Implement trade history
        volatility_rank=_calculate_volatility_rank(mtf_data),
        session=session,
        market_phase=market_phase,
    )


def _timeframe_to_string(tf: int) -> str:
    """Convert MT5 timeframe to string representation"""
    tf_map = {
        mt5.TIMEFRAME_M1: "M1",
        mt5.TIMEFRAME_M5: "M5",
        mt5.TIMEFRAME_M15: "M15",
        mt5.TIMEFRAME_M30: "M30",
        mt5.TIMEFRAME_H1: "H1",
        mt5.TIMEFRAME_H4: "H4",
        mt5.TIMEFRAME_D1: "D1",
        mt5.TIMEFRAME_W1: "W1",
        mt5.TIMEFRAME_MN1: "MN1",
    }
    return tf_map.get(tf, str(tf))


def _get_higher_timeframe(tf: int) -> int:
    """Get next higher timeframe"""
    tf_sequence = [
        mt5.TIMEFRAME_M1,
        mt5.TIMEFRAME_M5,
        mt5.TIMEFRAME_M15,
        mt5.TIMEFRAME_M30,
        mt5.TIMEFRAME_H1,
        mt5.TIMEFRAME_H4,
        mt5.TIMEFRAME_D1,
        mt5.TIMEFRAME_W1,
        mt5.TIMEFRAME_MN1,
    ]
    try:
        idx = tf_sequence.index(tf)
        return tf_sequence[idx + 1] if idx < len(tf_sequence) - 1 else tf
    except ValueError:
        return tf


def _get_lower_timeframe(tf: int) -> int:
    """Get next lower timeframe"""
    tf_sequence = [
        mt5.TIMEFRAME_M1,
        mt5.TIMEFRAME_M5,
        mt5.TIMEFRAME_M15,
        mt5.TIMEFRAME_M30,
        mt5.TIMEFRAME_H1,
        mt5.TIMEFRAME_H4,
        mt5.TIMEFRAME_D1,
        mt5.TIMEFRAME_W1,
        mt5.TIMEFRAME_MN1,
    ]
    try:
        idx = tf_sequence.index(tf)
        return tf_sequence[idx - 1] if idx > 0 else tf
    except ValueError:
        return tf


def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range"""
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    tr = pd.DataFrame({"TR1": tr1, "TR2": tr2, "TR3": tr3}).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]

    return atr


def _calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate Relative Strength Index"""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]


def _calculate_macd(prices: pd.Series) -> dict[str, float]:
    """Calculate MACD indicator"""
    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    return {"main": macd.iloc[-1], "signal": signal.iloc[-1], "hist": hist.iloc[-1]}


def _analyze_trend(df: pd.DataFrame) -> str:
    """Determine trend direction"""
    close = df["close"]
    ma20 = close.rolling(window=20).mean()
    ma50 = close.rolling(window=50).mean()

    last_ma20, last_ma50 = ma20.iloc[-1], ma50.iloc[-1]
    prev_ma20, prev_ma50 = ma20.iloc[-2], ma50.iloc[-2]

    if last_ma20 > last_ma50 and prev_ma20 > prev_ma50:
        return "up"
    elif last_ma20 < last_ma50 and prev_ma20 < prev_ma50:
        return "down"
    else:
        return "sideways"


def _find_key_levels(
    htf_data: pd.DataFrame, mtf_data: pd.DataFrame
) -> list[PriceLevel]:
    """Find key support and resistance levels"""
    levels = []

    # TODO: Implement sophisticated S/R detection
    # For now, just use simple high/low levels
    htf_high = htf_data["high"].max()
    htf_low = htf_data["low"].min()
    mtf_high = mtf_data["high"].max()
    mtf_low = mtf_data["low"].min()

    levels.extend(
        [
            PriceLevel(htf_high, "resistance", 0.8, "HTF", "Higher TF High"),
            PriceLevel(htf_low, "support", 0.8, "HTF", "Higher TF Low"),
            PriceLevel(mtf_high, "resistance", 0.6, "MTF", "Main TF High"),
            PriceLevel(mtf_low, "support", 0.6, "MTF", "Main TF Low"),
        ]
    )

    return levels


def _detect_patterns(df: pd.DataFrame) -> list[Pattern]:
    """Detect chart patterns"""
    patterns = []

    # TODO: Implement pattern recognition
    # This is a placeholder that should be replaced with actual pattern detection

    return patterns


def _draw_trendlines(df: pd.DataFrame) -> list[TrendLine]:
    """Identify and draw trendlines"""
    trendlines = []

    # TODO: Implement trendline detection
    # This is a placeholder that should be replaced with actual trendline analysis

    return trendlines


def _determine_market_phase(
    df: pd.DataFrame, patterns: list[Pattern], trend: str
) -> str:
    """Determine current market phase"""
    if trend != "sideways":
        return "trending"

    volatility = df["high"].rolling(20).std().iloc[-1]
    avg_volatility = df["high"].rolling(20).std().mean()

    if volatility > avg_volatility * 1.5:
        return "breakout"
    elif patterns:  # If we have reversal patterns
        return "reversal"
    else:
        return "ranging"


def _determine_session() -> str:
    """Determine current trading session"""
    # TODO: Implement proper session detection based on time
    return "overlap"  # placeholder


def _calculate_volatility_rank(df: pd.DataFrame) -> float:
    """Calculate volatility rank (0-1 scale)"""
    current_atr = _calculate_atr(df)
    atr_series = df.apply(lambda x: _calculate_atr(df.loc[: x.name]), axis=1)
    rank = (atr_series > current_atr).mean()
    return rank
