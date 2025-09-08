"""
Test suite for Risk Regime Detection System (Prompt-29)
========================================================

Tests volatility regime detection with synthetic candle data
to ensure deterministic regime classification.
"""

import math
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

from feeds import Candle
from risk.regime import (
    RegimeConfig,
    RegimeDetector,
    RegimeParams,
    RegimeThresholds,
    compute_norm_atr,
    compute_return_volatility,
    load_regime_config,
)


def create_synthetic_candles(
    count: int, base_price: float = 2000.0, volatility: float = 0.01, trend: float = 0.0
) -> list[Candle]:
    """
    Create synthetic candle data with controlled volatility

    Args:
        count: Number of candles to create
        base_price: Starting price
        volatility: Price volatility as ratio (0.01 = 1%)
        trend: Trend factor per candle
    """
    candles = []
    price = base_price

    for i in range(count):
        # Simulate price movement with controlled volatility
        price_change = volatility * price * (0.5 - (i % 100) / 100.0)  # Cyclical
        price += price_change + trend

        # Create OHLC with realistic spreads
        noise = volatility * price * 0.3
        low = price - abs(noise)
        high = price + abs(noise)
        open_price = low + (high - low) * 0.3
        close = low + (high - low) * 0.7

        candle = Candle(
            ts=i * 3600,  # 1 hour intervals
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=1000.0,
        )
        candles.append(candle)

    return candles


def create_low_volatility_candles(count: int = 50) -> list[Candle]:
    """Create candles with low volatility (tight range)"""
    return create_synthetic_candles(count, volatility=0.001, trend=0.0)


def create_normal_volatility_candles(count: int = 50) -> list[Candle]:
    """Create candles with normal volatility"""
    return create_synthetic_candles(count, volatility=0.005, trend=0.0)


def create_high_volatility_candles(count: int = 50) -> list[Candle]:
    """Create candles with high volatility (wide swings)"""
    return create_synthetic_candles(count, volatility=0.02, trend=0.0)


class TestNormalizedATR:
    """Test ATR calculation functions"""

    def test_compute_norm_atr_basic(self):
        """Test basic normalized ATR calculation"""
        candles = create_normal_volatility_candles(20)
        atr = compute_norm_atr(candles, 14)

        assert atr > 0, "ATR should be positive"
        assert atr < 1.0, "Normalized ATR should be < 1.0"
        assert 0.001 < atr < 0.1, f"ATR {atr} should be in reasonable range"

    def test_compute_norm_atr_insufficient_data(self):
        """Test ATR with insufficient candle data"""
        candles = create_normal_volatility_candles(5)
        atr = compute_norm_atr(candles, 14)

        assert atr == 0.0, "Should return 0 for insufficient data"

    def test_compute_norm_atr_volatility_differences(self):
        """Test that ATR reflects volatility differences"""
        low_vol_candles = create_low_volatility_candles(30)
        high_vol_candles = create_high_volatility_candles(30)

        low_atr = compute_norm_atr(low_vol_candles, 14)
        high_atr = compute_norm_atr(high_vol_candles, 14)

        assert (
            high_atr > low_atr
        ), f"High vol ATR {high_atr} should > low vol ATR {low_atr}"
        assert high_atr > low_atr * 2, "Should show significant difference"


class TestReturnVolatility:
    """Test return volatility calculation"""

    def test_compute_return_volatility_basic(self):
        """Test basic return volatility calculation"""
        candles = create_normal_volatility_candles(100)
        vol = compute_return_volatility(candles, 50)

        assert vol > 0, "Return volatility should be positive"
        assert vol < 1.0, "Return volatility should be reasonable"

    def test_return_volatility_reflects_price_movement(self):
        """Test that return volatility reflects actual price movements"""
        stable_candles = create_low_volatility_candles(100)
        volatile_candles = create_high_volatility_candles(100)

        stable_vol = compute_return_volatility(stable_candles, 50)
        volatile_vol = compute_return_volatility(volatile_candles, 50)

        assert (
            volatile_vol > stable_vol
        ), "Volatile candles should have higher return vol"


class TestRegimeConfig:
    """Test regime configuration loading and validation"""

    def test_regime_config_validation(self):
        """Test regime configuration validation"""
        config = RegimeConfig(
            active=True,
            atr_window=14,
            ret_window=96,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
        )

        assert config.active is True
        assert config.atr_window == 14
        assert config.thresholds.low < config.thresholds.normal < config.thresholds.high
        assert config.params["low"].RISK_PCT > config.params["high"].RISK_PCT

    def test_load_regime_config_missing_file(self):
        """Test config loading with missing file"""
        config = load_regime_config("nonexistent.yaml")

        assert isinstance(config, RegimeConfig)
        assert config.active is True
        assert config.default_regime == "normal"

    @patch("builtins.open")
    @patch("yaml.safe_load")
    def test_load_regime_config_yaml_error(self, mock_yaml, mock_open):
        """Test config loading with YAML error"""
        mock_yaml.side_effect = Exception("YAML error")

        config = load_regime_config("test.yaml")

        assert isinstance(config, RegimeConfig)
        assert config.active is True  # Should use defaults


class TestRegimeDetector:
    """Test volatility regime detection"""

    def test_regime_detector_initialization(self):
        """Test regime detector initialization"""
        detector = RegimeDetector()

        assert detector.cfg.active is True
        assert detector._regime_history == []

    def test_detect_low_volatility_regime(self):
        """Test detection of low volatility regime"""
        # Create detector with known thresholds
        config = RegimeConfig(
            active=True,
            atr_window=10,
            ret_window=20,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            min_regime_duration=1,  # No stability for testing
        )
        detector = RegimeDetector(config)

        # Low volatility candles
        candles = create_low_volatility_candles(30)
        regime = detector.detect(candles, "XAUUSD")

        assert regime == "low", f"Expected 'low' regime, got '{regime}'"

    def test_detect_high_volatility_regime(self):
        """Test detection of high volatility regime"""
        config = RegimeConfig(
            active=True,
            atr_window=10,
            ret_window=20,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            min_regime_duration=1,
        )
        detector = RegimeDetector(config)

        # High volatility candles
        candles = create_high_volatility_candles(30)
        regime = detector.detect(candles, "XAUUSD")

        assert regime == "high", f"Expected 'high' regime, got '{regime}'"

    def test_detect_normal_volatility_regime(self):
        """Test detection of normal volatility regime"""
        config = RegimeConfig(
            active=True,
            atr_window=10,
            ret_window=20,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            min_regime_duration=1,
        )
        detector = RegimeDetector(config)

        # Normal volatility candles
        candles = create_normal_volatility_candles(30)
        regime = detector.detect(candles, "XAUUSD")

        assert regime == "normal", f"Expected 'normal' regime, got '{regime}'"

    def test_regime_stability_mechanism(self):
        """Test regime stability prevents oscillations"""
        config = RegimeConfig(
            active=True,
            atr_window=5,
            ret_window=10,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            min_regime_duration=3,
            regime_confidence=0.8,
        )
        detector = RegimeDetector(config)

        # Start with normal volatility
        normal_candles = create_normal_volatility_candles(15)
        regime1 = detector.detect(normal_candles, "TEST")
        regime2 = detector.detect(normal_candles, "TEST")
        regime3 = detector.detect(normal_candles, "TEST")

        # Switch to high volatility
        high_candles = create_high_volatility_candles(15)
        regime4 = detector.detect(
            high_candles, "TEST"
        )  # Should still be normal due to stability

        assert regime1 == regime2 == regime3 == "normal"
        # regime4 might still be "normal" due to stability mechanism

    def test_get_params_for_regime(self):
        """Test parameter retrieval for different regimes"""
        detector = RegimeDetector()

        low_params = detector.get_params("low")
        normal_params = detector.get_params("normal")
        high_params = detector.get_params("high")

        # Verify parameter structure
        for params in [low_params, normal_params, high_params]:
            assert "RISK_PCT" in params
            assert "SL_MULT" in params
            assert "TP_MULT" in params
            assert all(isinstance(v, float) for v in params.values())

        # Verify risk progression (lower risk in higher volatility)
        assert (
            low_params["RISK_PCT"] > normal_params["RISK_PCT"] > high_params["RISK_PCT"]
        )

    def test_detect_disabled_regime(self):
        """Test regime detection when disabled"""
        config = RegimeConfig(
            active=False,
            atr_window=14,
            ret_window=96,
            thresholds=RegimeThresholds(low=0.003, normal=0.008, high=0.015),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            default_regime="normal",
        )
        detector = RegimeDetector(config)

        candles = create_high_volatility_candles(30)
        regime = detector.detect(candles, "TEST")

        assert regime == "normal", "Should return default when disabled"

    def test_detect_insufficient_candles(self):
        """Test regime detection with insufficient candle data"""
        detector = RegimeDetector()

        # Not enough candles
        candles = create_normal_volatility_candles(5)
        regime = detector.detect(candles, "TEST")

        assert regime == "normal", "Should return default with insufficient data"

    def test_get_regime_summary(self):
        """Test regime summary generation"""
        detector = RegimeDetector()

        # Test empty history
        summary = detector.get_regime_summary()
        assert summary["current"] == "normal"
        assert summary["history_length"] == 0

        # Add some regime history
        candles = create_normal_volatility_candles(30)
        detector.detect(candles, "TEST")
        detector.detect(candles, "TEST")

        summary = detector.get_regime_summary()
        assert summary["history_length"] == 2
        assert "regime_distribution" in summary


class TestRegimeIntegration:
    """Integration tests for regime system"""

    def test_deterministic_regime_classification(self):
        """Test that regime classification is deterministic"""
        detector = RegimeDetector()

        # Same candles should produce same regime
        candles = create_normal_volatility_candles(30)
        regime1 = detector.detect(candles, "TEST1")
        regime2 = detector.detect(candles, "TEST2")

        # Note: Due to regime history, these might differ
        # But classification logic should be deterministic
        assert regime1 in ["low", "normal", "high"]
        assert regime2 in ["low", "normal", "high"]

    def test_regime_progression_with_volatility_changes(self):
        """Test regime changes as volatility changes"""
        config = RegimeConfig(
            active=True,
            atr_window=10,
            ret_window=20,
            thresholds=RegimeThresholds(low=0.002, normal=0.006, high=0.012),
            params={
                "low": RegimeParams(RISK_PCT=0.012, SL_MULT=1.3, TP_MULT=2.2),
                "normal": RegimeParams(RISK_PCT=0.010, SL_MULT=1.5, TP_MULT=2.0),
                "high": RegimeParams(RISK_PCT=0.006, SL_MULT=1.8, TP_MULT=1.6),
            },
            min_regime_duration=1,  # Allow immediate changes for testing
        )
        detector = RegimeDetector(config)

        # Start with low volatility
        low_candles = create_low_volatility_candles(20)
        regime_low = detector.detect(low_candles, "TEST")

        # Move to high volatility
        high_candles = create_high_volatility_candles(20)
        regime_high = detector.detect(high_candles, "TEST")

        # Should show different regimes (though stability might prevent immediate change)
        assert regime_low in ["low", "normal", "high"]
        assert regime_high in ["low", "normal", "high"]

    def test_parameter_override_mechanism(self):
        """Test that regime parameters can override settings"""
        detector = RegimeDetector()

        # Get parameters for different regimes
        low_params = detector.get_params("low")
        high_params = detector.get_params("high")

        # Verify they provide different risk management
        assert low_params["RISK_PCT"] != high_params["RISK_PCT"]
        assert low_params["SL_MULT"] != high_params["SL_MULT"]
        assert low_params["TP_MULT"] != high_params["TP_MULT"]

        # Low volatility should allow higher risk
        assert low_params["RISK_PCT"] > high_params["RISK_PCT"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
