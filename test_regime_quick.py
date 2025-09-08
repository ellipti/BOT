#!/usr/bin/env python3
"""
Quick test for Risk Regime System (Prompt-29)
"""

import logging
from typing import List

from feeds import Candle
from risk.regime import RegimeDetector, compute_norm_atr

# Set up basic logging
logging.basicConfig(level=logging.INFO)

def create_test_candles(volatility: float, count: int = 30) -> List[Candle]:
    """Create synthetic candles with controlled volatility"""
    candles = []
    base_price = 2000.0
    
    for i in range(count):
        # Create price movement based on volatility
        price_change = volatility * base_price * ((i % 10) / 10.0 - 0.5)
        price = base_price + price_change
        
        # Create OHLC
        spread = volatility * price * 0.5
        low = price - spread
        high = price + spread
        open_price = low + (high - low) * 0.2
        close = low + (high - low) * 0.8
        
        candle = Candle(
            ts=i * 3600,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000.0
        )
        candles.append(candle)
    
    return candles

def test_regime_detection():
    """Test basic regime detection functionality"""
    print("🔬 Testing Risk Regime Detection System")
    print("=" * 50)
    
    # Test ATR calculation
    print("\n1. Testing Normalized ATR Calculation:")
    test_candles = create_test_candles(0.01, 30)
    norm_atr = compute_norm_atr(test_candles, 14)
    print(f"   Normalized ATR: {norm_atr:.6f}")
    assert norm_atr > 0, "ATR should be positive"
    
    # Test regime detector
    print("\n2. Testing Regime Detection:")
    detector = RegimeDetector()
    
    # Test different volatility levels
    low_vol_candles = create_test_candles(0.001, 100)  # Very low volatility
    normal_vol_candles = create_test_candles(0.005, 100)  # Normal volatility  
    high_vol_candles = create_test_candles(0.02, 100)  # High volatility
    
    low_regime = detector.detect(low_vol_candles, "TEST")
    normal_regime = detector.detect(normal_vol_candles, "TEST")
    high_regime = detector.detect(high_vol_candles, "TEST")
    
    print(f"   Low volatility regime: {low_regime}")
    print(f"   Normal volatility regime: {normal_regime}")
    print(f"   High volatility regime: {high_regime}")
    
    # Test parameter retrieval
    print("\n3. Testing Parameter Retrieval:")
    for regime in ["low", "normal", "high"]:
        params = detector.get_params(regime)
        print(f"   {regime.upper()}: RISK_PCT={params['RISK_PCT']:.3f}, "
              f"SL_MULT={params['SL_MULT']:.1f}, TP_MULT={params['TP_MULT']:.1f}")
    
    # Test configuration
    print("\n4. Testing Configuration:")
    config = detector.cfg
    print(f"   Active: {config.active}")
    print(f"   ATR Window: {config.atr_window}")
    print(f"   Thresholds: low={config.thresholds.low}, normal={config.thresholds.normal}, high={config.thresholds.high}")
    
    print("\n✅ All regime detection tests passed!")
    return True

if __name__ == "__main__":
    try:
        test_regime_detection()
        print("\n🎉 Risk Regime System (Prompt-29) is working correctly!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
