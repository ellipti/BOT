"""Debug trailing stop calculations"""

import time
from unittest.mock import MagicMock

from config.settings import get_settings
from risk.trailing import TrailingStopManager

def test_debug():
    settings = get_settings()
    mock_mt5 = MagicMock()
    
    # Mock symbol info for XAUUSD (Gold)
    symbol_info = MagicMock()
    symbol_info.point = 0.01  # Gold has 2-digit precision typically
    mock_mt5.symbol_info.return_value = symbol_info
    
    trailing_manager = TrailingStopManager(mock_mt5, settings)
    
    # Create position for minimum step test
    position = MagicMock()
    position.ticket = 12345
    position.symbol = "XAUUSD"
    position.price_open = 2500.0
    position.price_current = 2504.0
    position.sl = 2502.0
    position.type = 0  # BUY
    position.volume = 0.1
    
    print(f"Minimum step test setup:")
    print(f"  Position: entry={position.price_open}, current={position.price_current}, sl={position.sl}")
    print(f"  Point: {symbol_info.point}")
    
    trailing_step_pips = 5.0
    trailing_buffer_pips = 3.0
    
    # Calculate expected values
    trailing_buffer = trailing_buffer_pips * symbol_info.point
    proposed_sl = position.price_current - trailing_buffer
    step_in_price = proposed_sl - position.sl
    step_in_pips = step_in_price / symbol_info.point
    min_step_threshold = trailing_step_pips * symbol_info.point
    
    print(f"  Trailing buffer: {trailing_buffer_pips} pips = {trailing_buffer}")
    print(f"  Proposed SL: {proposed_sl}")
    print(f"  Step in price: {step_in_price}")
    print(f"  Step in pips: {step_in_pips}")
    print(f"  Min step threshold: {trailing_step_pips} pips = {min_step_threshold}")
    print(f"  Step requirement met: {step_in_price >= min_step_threshold}")
    
    # Test the actual function
    new_sl = trailing_manager.compute_trailing_sl(
        position=position,
        trailing_step_pips=trailing_step_pips,
        trailing_buffer_pips=trailing_buffer_pips,
        use_atr=False,
        hysteresis_pips=1.0,
    )
    
    print(f"  Actual result: {new_sl}")

if __name__ == "__main__":
    test_debug()
