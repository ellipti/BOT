#!/usr/bin/env python3
"""
Risk Governance V2 - Loss Streak, Dynamic Blackout, Cooldown
Advanced risk management with stateful counters and news blackout integration
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import get_settings
from utils.atomic_io import atomic_read_json, atomic_write_json

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Stateful risk counters - persistable via atomic I/O"""

    consecutive_losses: int = 0
    trades_today: int = 0
    last_loss_ts: str | None = None  # ISO format timestamp
    session_start_ts: str | None = None  # ISO format timestamp
    blackout_until: str | None = None  # ISO format timestamp
    last_trade_ts: str | None = None  # ISO format timestamp
    current_date: str | None = None  # Track date for daily reset

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON persistence"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RiskState":
        """Create from dictionary loaded from JSON"""
        return cls(**data)


class RiskGovernorV2:
    """
    Advanced risk governance with loss streak tracking and dynamic blackout

    Features:
    - Consecutive loss tracking with cooldown
    - Daily trade session limits
    - Dynamic news blackout based on impact level
    - Persistent state management via atomic I/O
    - Integration with EventBus for notifications
    """

    def __init__(self, state_path: str = "state/risk_state_v2.json"):
        self.state_path = Path(state_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings = get_settings().risk

        # Load persistent state
        self.state = self._load_state()

        # Reset daily counters if new day
        self._check_daily_reset()

        logger.info(
            "RiskGovernorV2 инициализован",
            extra={
                "state_path": str(self.state_path),
                "consecutive_losses": self.state.consecutive_losses,
                "trades_today": self.state.trades_today,
                "blackout_until": self.state.blackout_until,
            },
        )

    def _load_state(self) -> RiskState:
        """Load risk state from persistent storage"""
        try:
            data = atomic_read_json(self.state_path, default={})
            state = RiskState.from_dict(data)
            logger.debug("Risk state уншигдлаа", extra={"state": state.to_dict()})
            return state
        except Exception as e:
            logger.warning(f"Risk state унших алдаа: {e}, шинэ state үүсгэнэ")
            return RiskState()

    def _persist(self) -> None:
        """Persist current state to storage atomically"""
        try:
            atomic_write_json(self.state_path, self.state.to_dict())
            logger.debug(
                "Risk state хадгалагдлаа", extra={"state": self.state.to_dict()}
            )
        except Exception as e:
            logger.error(f"Risk state хадгалах алдаа: {e}")

    def _check_daily_reset(self) -> None:
        """Reset daily counters if new day started"""
        current_date = datetime.now().strftime("%Y-%m-%d")

        if self.state.current_date != current_date:
            logger.info(f"Шинэ өдөр: {current_date}, daily counters reset хийнэ")
            self.state.trades_today = 0
            self.state.session_start_ts = datetime.now().isoformat()
            self.state.current_date = current_date
            self._persist()

    def can_trade(self, now: datetime) -> tuple[bool, str | None]:
        """
        Check if trading is allowed at given time

        Args:
            now: Current datetime

        Returns:
            Tuple of (allowed: bool, reason: str|None)
            If not allowed, reason contains blocking reason
        """
        self._check_daily_reset()

        # Check blackout period
        if self.state.blackout_until:
            try:
                blackout_end = datetime.fromisoformat(self.state.blackout_until)
                if now < blackout_end:
                    remaining = blackout_end - now
                    return (
                        False,
                        f"NEWS_BLACKOUT (үлдсэн: {remaining.total_seconds()/60:.1f} мин)",
                    )
            except Exception as e:
                logger.warning(f"Blackout timestamp парс хийх алдаа: {e}")
                self.state.blackout_until = None  # Clear invalid timestamp

        # Check session trade limit
        if self.state.trades_today >= self.settings.max_trades_per_session:
            return (
                False,
                f"SESSION_LIMIT ({self.state.trades_today}/{self.settings.max_trades_per_session})",
            )

        # Check consecutive losses cooldown
        if self.state.consecutive_losses >= self.settings.max_consecutive_losses_v2:
            if self.state.last_loss_ts:
                try:
                    last_loss = datetime.fromisoformat(self.state.last_loss_ts)
                    cooldown_end = last_loss + timedelta(
                        minutes=self.settings.cooldown_after_loss_min
                    )
                    if now < cooldown_end:
                        remaining = cooldown_end - now
                        return (
                            False,
                            f"LOSS_STREAK_COOLDOWN (үлдсэн: {remaining.total_seconds()/60:.1f} мин)",
                        )
                except Exception as e:
                    logger.warning(f"Last loss timestamp парс хийх алдаа: {e}")

        return True, None

    def apply_news_blackout(self, impact: str, now: datetime) -> None:
        """
        Apply news blackout based on event impact level

        Args:
            impact: Event impact level ('high', 'medium', 'low')
            now: Current datetime
        """
        blackout_config = self.settings.news_blackout_map.get(impact.lower(), [5, 5])
        pre_minutes, post_minutes = blackout_config

        # For simplicity, we apply total blackout duration from now
        # In real implementation, you'd want pre/post event timing
        total_blackout_minutes = pre_minutes + post_minutes
        blackout_end = now + timedelta(minutes=total_blackout_minutes)

        self.state.blackout_until = blackout_end.isoformat()
        self._persist()

        logger.warning(
            f"News blackout идэвхжлээ: impact={impact}, хугацаа={total_blackout_minutes}мин",
            extra={
                "impact": impact,
                "blackout_minutes": total_blackout_minutes,
                "blackout_until": self.state.blackout_until,
            },
        )

    def on_trade_closed(self, pnl: float, now: datetime) -> None:
        """
        Record trade result and update risk counters

        Args:
            pnl: Trade P&L (positive = profit, negative = loss)
            now: Current datetime when trade closed
        """
        self._check_daily_reset()

        # Update trade count
        self.state.trades_today += 1
        self.state.last_trade_ts = now.isoformat()

        # Update loss streak
        if pnl < 0:
            # Loss
            self.state.consecutive_losses += 1
            self.state.last_loss_ts = now.isoformat()
            logger.info(
                f"Алдагдалтай арилжаа: PnL={pnl}, consecutive_losses={self.state.consecutive_losses}"
            )
        # Profit - reset loss streak
        elif self.state.consecutive_losses > 0:
            logger.info(
                f"Ашигтай арилжаа: PnL={pnl}, loss streak reset ({self.state.consecutive_losses}→0)"
            )
            self.state.consecutive_losses = 0
            self.state.last_loss_ts = None

        self._persist()

        # Log current state
        logger.info(
            "Арилжааны үр дүн бүртгэгдлээ",
            extra={
                "pnl": pnl,
                "trades_today": self.state.trades_today,
                "consecutive_losses": self.state.consecutive_losses,
                "session_limit": self.settings.max_trades_per_session,
            },
        )

    def get_state_summary(self) -> dict:
        """Get current risk state summary for reporting"""
        self._check_daily_reset()

        # Calculate cooldown status
        cooldown_active = False
        cooldown_remaining_min = 0

        if (
            self.state.consecutive_losses >= self.settings.max_consecutive_losses_v2
            and self.state.last_loss_ts
        ):
            try:
                last_loss = datetime.fromisoformat(self.state.last_loss_ts)
                cooldown_end = last_loss + timedelta(
                    minutes=self.settings.cooldown_after_loss_min
                )
                now = datetime.now()
                if now < cooldown_end:
                    cooldown_active = True
                    cooldown_remaining_min = (cooldown_end - now).total_seconds() / 60
            except Exception:
                pass

        # Calculate blackout status
        blackout_active = False
        blackout_remaining_min = 0

        if self.state.blackout_until:
            try:
                blackout_end = datetime.fromisoformat(self.state.blackout_until)
                now = datetime.now()
                if now < blackout_end:
                    blackout_active = True
                    blackout_remaining_min = (blackout_end - now).total_seconds() / 60
            except Exception:
                pass

        return {
            "consecutive_losses": self.state.consecutive_losses,
            "trades_today": self.state.trades_today,
            "session_limit": self.settings.max_trades_per_session,
            "session_usage_pct": (
                self.state.trades_today / self.settings.max_trades_per_session
            )
            * 100,
            "cooldown_active": cooldown_active,
            "cooldown_remaining_min": round(cooldown_remaining_min, 1),
            "blackout_active": blackout_active,
            "blackout_remaining_min": round(blackout_remaining_min, 1),
            "can_trade_now": self.can_trade(datetime.now())[0],
            "last_trade_ts": self.state.last_trade_ts,
            "current_date": self.state.current_date,
        }

    def reset_session(self) -> None:
        """Manually reset daily session counters (for testing/admin)"""
        logger.info("Manual session reset орьцүүлээ")
        self.state.trades_today = 0
        self.state.session_start_ts = datetime.now().isoformat()
        self.state.current_date = datetime.now().strftime("%Y-%m-%d")
        self._persist()

    def clear_loss_streak(self) -> None:
        """Manually clear loss streak (for testing/admin)"""
        logger.info(f"Manual loss streak clear: {self.state.consecutive_losses}→0")
        self.state.consecutive_losses = 0
        self.state.last_loss_ts = None
        self._persist()

    def clear_blackout(self) -> None:
        """Manually clear news blackout (for testing/admin)"""
        if self.state.blackout_until:
            logger.info(f"Manual blackout clear: {self.state.blackout_until}→None")
            self.state.blackout_until = None
            self._persist()
