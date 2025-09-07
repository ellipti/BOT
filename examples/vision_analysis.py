"""
Example usage of the vision-based trading system
"""

import json
from typing import Any

import MetaTrader5 as mt5

from core.vision_context import build_vision_context
from core.vision_schema import TRADE_DECISION_SCHEMA, validate_trade_decision


def analyze_chart_with_context(
    chart_images: list[bytes], symbol: str, timeframe: int
) -> dict[str, Any]:
    """
    Analyze chart images with market context to produce a trade decision

    Args:
        chart_images: List of chart image bytes (main TF, HTF, LTF)
        symbol: Trading symbol
        timeframe: Main timeframe for analysis

    Returns:
        Trade decision conforming to schema
    """
    # Build market context
    context = build_vision_context(symbol, timeframe)

    # Example decision output (this should be replaced with actual analysis)
    current_time = "2025-09-01T10:00:00Z"

    decision = {
        "overlays": {
            "trendlines": [
                {
                    "id": "tl1",
                    "anchor_a": {"time": "2025-09-01T09:00:00Z", "price": context.high},
                    "anchor_b": {"time": "2025-09-01T10:00:00Z", "price": context.low},
                }
            ],
            "channels": [{"id": "ch1", "base": "tl1", "offset_price": context.atr}],
            "zones": [
                {
                    "id": "sr1",
                    "type": "sr",
                    "price_min": context.current_price - context.atr / 2,
                    "price_max": context.current_price + context.atr / 2,
                }
            ],
            "fibonacci": [
                {
                    "id": "fib1",
                    "swing_high": {
                        "time": "2025-09-01T09:00:00Z",
                        "price": context.high,
                    },
                    "swing_low": {"time": "2025-09-01T08:00:00Z", "price": context.low},
                    "levels": [0.236, 0.382, 0.5, 0.618, 0.786],
                }
            ],
            "patterns": [{"id": "p1", "name": "bullish_engulfing", "at": current_time}],
        },
        "decision": "WAIT",
        "reason": "Example decision - waiting for better setup",
        "entry": None,
        "sl": None,
        "tp": None,
        "confidence": 0.0,
        "risk": {"r_multiple": 0.0, "atr": context.atr, "sl_distance": 0.0},
        "guards_ok": {"spread_ok": True, "news_ok": True, "cooldown_ok": True},
        "notes": ["Example note - waiting for confirmation"],
    }

    # Validate decision
    if error := validate_trade_decision(decision):
        raise ValueError(f"Invalid decision format: {error}")

    return decision


def get_schema() -> str:
    """Get the decision schema as a formatted JSON string"""
    return json.dumps(TRADE_DECISION_SCHEMA, indent=2)


# Example usage:
if __name__ == "__main__":
    # Initialize MT5 connection
    if not mt5.initialize():
        raise Exception("Failed to initialize MT5")

    # Example analysis
    try:
        # In real usage, you would load actual chart images here
        dummy_images = [b"dummy_image_data"] * 3

        # Get decision
        decision = analyze_chart_with_context(
            chart_images=dummy_images, symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15
        )

        # Print formatted decision
        print("Trade Decision:")
        print(json.dumps(decision, indent=2))

        print("\nSchema:")
        print(get_schema())

    finally:
        mt5.shutdown()
