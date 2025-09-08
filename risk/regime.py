"""
Risk Regime Detection System (Prompt-29)
==========================================

Volatility-based regime detection using ATR and return volatility.
Dynamically adjusts RISK_PCT, SL_MULT, and TP_MULT based on market conditions.

Features:
- Normalized ATR calculation (ATR/price)
- Three regime classification: low/normal/high volatility
- Configurable thresholds and parameters
- Regime stability to prevent oscillations
- Metrics integration for monitoring
"""

import logging
import math
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field

from feeds import Candle

logger = logging.getLogger(__name__)

RegimeType = Literal["low", "normal", "high"]


class RegimeParams(BaseModel):
    """Risk parameters for a specific regime"""

    RISK_PCT: float = Field(gt=0, le=0.1, description="Risk percentage per trade")
    SL_MULT: float = Field(gt=0, description="Stop loss ATR multiplier")
    TP_MULT: float = Field(gt=0, description="Take profit ATR multiplier")


class RegimeThresholds(BaseModel):
    """Volatility thresholds for regime classification"""

    low: float = Field(gt=0, description="Low volatility threshold")
    normal: float = Field(gt=0, description="Normal volatility threshold")
    high: float = Field(gt=0, description="High volatility threshold")


class RegimeConfig(BaseModel):
    """Complete regime configuration"""

    active: bool = Field(default=True, description="Enable regime detection")
    atr_window: int = Field(default=14, ge=2, description="ATR calculation window")
    ret_window: int = Field(default=96, ge=10, description="Return volatility window")
    thresholds: RegimeThresholds
    params: dict[RegimeType, RegimeParams]
    default_regime: RegimeType = Field(default="normal", description="Fallback regime")
    min_regime_duration: int = Field(
        default=3, ge=1, description="Min bars before regime change"
    )
    regime_confidence: float = Field(
        default=0.85, ge=0.5, le=1.0, description="Confidence threshold"
    )


def load_regime_config(config_path: str = "configs/risk_regimes.yaml") -> RegimeConfig:
    """Load regime configuration from YAML file"""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Regime config not found: {config_path}, using defaults")
            return RegimeConfig(
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

        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return RegimeConfig(**data)

    except Exception as e:
        logger.error(f"Failed to load regime config: {e}, using defaults")
        return RegimeConfig(
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


def compute_norm_atr(candles: list[Candle], atr_window: int) -> float:
    """
    Compute normalized ATR (ATR/price)

    Args:
        candles: List of OHLC candles (must have at least atr_window+1 candles)
        atr_window: ATR calculation window

    Returns:
        Normalized ATR as ratio (e.g., 0.005 = 0.5%)
    """
    if len(candles) < atr_window + 1:
        logger.warning(
            f"Insufficient candles for ATR: {len(candles)} < {atr_window + 1}"
        )
        return 0.0

    try:
        # Calculate True Range for each candle
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i - 1]

            # True Range = max(H-L, |H-C_prev|, |L-C_prev|)
            hl = current.high - current.low
            hc_prev = abs(current.high - previous.close)
            lc_prev = abs(current.low - previous.close)

            tr = max(hl, hc_prev, lc_prev)
            true_ranges.append(tr)

        # Calculate ATR as simple moving average of True Range
        atr_window = min(atr_window, len(true_ranges))

        recent_trs = true_ranges[-atr_window:]
        atr = sum(recent_trs) / len(recent_trs)

        # Normalize by current close price
        current_price = candles[-1].close
        if current_price <= 0:
            logger.error(f"Invalid current price: {current_price}")
            return 0.0

        normalized_atr = atr / current_price

        logger.debug(
            f"ATR calculation: TR count={len(true_ranges)}, "
            f"ATR={atr:.6f}, price={current_price:.5f}, "
            f"norm_ATR={normalized_atr:.6f}"
        )

        return normalized_atr

    except Exception as e:
        logger.error(f"Error computing normalized ATR: {e}")
        return 0.0


def compute_return_volatility(candles: list[Candle], window: int) -> float:
    """
    Compute return volatility (standard deviation of log returns)

    Args:
        candles: List of OHLC candles
        window: Lookback window for volatility calculation

    Returns:
        Return volatility as standard deviation
    """
    if len(candles) < window + 1:
        return 0.0

    try:
        # Calculate log returns
        log_returns = []
        for i in range(len(candles) - window, len(candles)):
            if i <= 0:
                continue
            current_price = candles[i].close
            prev_price = candles[i - 1].close

            if prev_price <= 0 or current_price <= 0:
                continue

            log_return = math.log(current_price / prev_price)
            log_returns.append(log_return)

        if len(log_returns) < 2:
            return 0.0

        # Calculate standard deviation
        mean_return = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_return) ** 2 for r in log_returns) / (
            len(log_returns) - 1
        )
        std_dev = math.sqrt(variance)

        return std_dev

    except Exception as e:
        logger.error(f"Error computing return volatility: {e}")
        return 0.0


class RegimeDetector:
    """Volatility regime detector with stability features"""

    def __init__(self, config: RegimeConfig | None = None):
        """
        Initialize regime detector

        Args:
            config: Regime configuration (loads from file if None)
        """
        self.cfg = config or load_regime_config()
        self._regime_history: list[RegimeType] = []
        self._regime_start_time: int | None = None

        logger.info(
            f"RegimeDetector initialized: active={self.cfg.active}, "
            f"thresholds={self.cfg.thresholds.model_dump()}"
        )

    def detect(self, candles: list[Candle], symbol: str = "UNKNOWN") -> RegimeType:
        """
        Detect current volatility regime

        Args:
            candles: OHLC candle data
            symbol: Trading symbol for logging

        Returns:
            Current regime: "low", "normal", or "high"
        """
        if not self.cfg.active:
            logger.debug("Regime detection disabled, using default")
            return self.cfg.default_regime

        if len(candles) < max(self.cfg.atr_window + 1, self.cfg.ret_window):
            logger.warning(f"Insufficient candles for regime detection: {len(candles)}")
            return self.cfg.default_regime

        try:
            # Primary: Normalized ATR
            norm_atr = compute_norm_atr(candles, self.cfg.atr_window)

            # Secondary: Return volatility (for validation)
            ret_vol = compute_return_volatility(candles, self.cfg.ret_window)

            # Classify regime based on normalized ATR
            thresholds = self.cfg.thresholds
            if norm_atr < thresholds.low:
                raw_regime = "low"
            elif norm_atr >= thresholds.high:
                raw_regime = "high"
            else:
                raw_regime = "normal"

            # Apply regime stability (prevent oscillations)
            stable_regime = self._apply_stability(raw_regime)

            # Update history
            self._regime_history.append(stable_regime)
            if len(self._regime_history) > 100:  # Keep last 100 readings
                self._regime_history = self._regime_history[-100:]

            logger.info(
                f"Regime detection [{symbol}]: norm_ATR={norm_atr:.6f}, "
                f"ret_vol={ret_vol:.6f}, raw={raw_regime}, stable={stable_regime}"
            )

            return stable_regime

        except Exception as e:
            logger.error(f"Regime detection failed for {symbol}: {e}")
            return self.cfg.default_regime

    def _apply_stability(self, raw_regime: RegimeType) -> RegimeType:
        """Apply regime stability to prevent rapid oscillations"""
        if len(self._regime_history) < self.cfg.min_regime_duration:
            return raw_regime

        # Check if we should maintain current regime
        current_regime = self._regime_history[-1]
        if current_regime == raw_regime:
            return raw_regime

        # Count recent regime consistency
        recent_regimes = self._regime_history[-self.cfg.min_regime_duration :]
        consistency = sum(1 for r in recent_regimes if r == current_regime) / len(
            recent_regimes
        )

        # Require high confidence to change regime
        if consistency >= self.cfg.regime_confidence:
            return raw_regime
        else:
            logger.debug(
                f"Regime stability: keeping {current_regime} "
                f"(consistency={consistency:.2f} < {self.cfg.regime_confidence})"
            )
            return current_regime

    def get_params(self, regime: RegimeType) -> dict[str, float]:
        """
        Get risk parameters for specified regime

        Args:
            regime: Volatility regime

        Returns:
            Dictionary with RISK_PCT, SL_MULT, TP_MULT
        """
        try:
            params = self.cfg.params[regime]
            return {
                "RISK_PCT": params.RISK_PCT,
                "SL_MULT": params.SL_MULT,
                "TP_MULT": params.TP_MULT,
            }
        except KeyError:
            logger.error(f"Unknown regime: {regime}, using default")
            params = self.cfg.params[self.cfg.default_regime]
            return {
                "RISK_PCT": params.RISK_PCT,
                "SL_MULT": params.SL_MULT,
                "TP_MULT": params.TP_MULT,
            }

    def get_regime_summary(self) -> dict:
        """Get summary of recent regime activity"""
        if not self._regime_history:
            return {"current": self.cfg.default_regime, "history_length": 0}

        current = self._regime_history[-1]
        regime_counts = {
            "low": self._regime_history.count("low"),
            "normal": self._regime_history.count("normal"),
            "high": self._regime_history.count("high"),
        }

        return {
            "current": current,
            "history_length": len(self._regime_history),
            "regime_distribution": regime_counts,
            "stability_threshold": self.cfg.regime_confidence,
        }
