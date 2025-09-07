#!/usr/bin/env python3
"""
Risk Governance Pack - Эрсдэлийн засаглал
Upgrade #07: Өдөр/7 хоногийн max loss, max trades, cooldown, circuit-breaker

Зорилго:
- Өдрийн дээд алдагдал хяналт
- 7 хоногийн дээд алдагдал хяналт
- Дээд арилжааны тоо хяналт
- Cooldown хугацаа хяналт
- Circuit-breaker автомат зогсоолт
- Telegram alerts дэмжлэг
"""

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from config.settings import get_settings
from logging_setup import setup_advanced_logger
from utils.atomic_io import atomic_read_json, atomic_update_json, atomic_write_json

try:
    from .telegram_alerts import send_risk_alert

    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False

    def send_risk_alert(message: str, level: str = "INFO") -> bool:
        return False


# Монгол хэлээр лог
logger = setup_advanced_logger(__name__)


class RiskLevel(Enum):
    """Эрсдэлийн түвшин"""

    LOW = "low"  # Бага эрсдэл
    MEDIUM = "medium"  # Дунд эрсдэл
    HIGH = "high"  # Өндөр эрсдэл
    CRITICAL = "critical"  # Эгзэгтэй эрсдэл


class CircuitBreakerState(Enum):
    """Circuit Breaker төлөв"""

    CLOSED = "closed"  # Хэвийн ажиллагаа
    OPEN = "open"  # Зогсоосон төлөв
    HALF_OPEN = "half_open"  # Шалгалтын төлөв


@dataclass
class RiskMetrics:
    """Эрсдэлийн хэмжүүр"""

    daily_loss: float = 0.0
    weekly_loss: float = 0.0
    daily_trades: int = 0
    weekly_trades: int = 0
    consecutive_losses: int = 0
    last_trade_time: float | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    circuit_breaker_state: CircuitBreakerState = CircuitBreakerState.CLOSED


@dataclass
class TradeDecision:
    """Арилжааны шийдвэр"""

    allowed: bool
    reason: str
    risk_level: RiskLevel
    metrics: RiskMetrics
    warnings: list[str]


class RiskGovernor:
    """Эрсдэлийн засаглалын үндсэн класс"""

    def __init__(self, data_path: str = "risk/governance_data.json"):
        self.data_path = Path(data_path)
        self.data_path.parent.mkdir(exist_ok=True, parents=True)
        self.settings = get_settings()

        # Үндсэн тохиргоо шалгах
        self._validate_settings()

        logger.info(
            "Эрсдэлийн засаглал эхэллээ",
            extra={
                "data_path": str(self.data_path),
                "max_daily_loss": self.settings.risk.max_daily_loss_percentage,
                "max_weekly_loss": self.settings.risk.max_weekly_loss_percentage,
                "max_daily_trades": self.settings.risk.max_daily_trades,
                "max_weekly_trades": self.settings.risk.max_weekly_trades,
            },
        )

    def _validate_settings(self):
        """Тохиргооны утгуудыг шалгах"""
        required_attrs = [
            "max_daily_loss_percentage",
            "max_weekly_loss_percentage",
            "max_daily_trades",
            "max_weekly_trades",
            "cooldown_minutes",
            "circuit_breaker_loss_threshold",
        ]

        for attr in required_attrs:
            if not hasattr(self.settings.risk, attr):
                raise ValueError(f"Risk тохиргоонд {attr} байхгүй байна")

        logger.debug("Эрсдэлийн тохиргоо баталгаажлаа")

    def _load_data(self) -> dict[str, Any]:
        """Эрсдэлийн өгөгдөл унших"""
        default_data = {
            "daily_metrics": {},
            "weekly_metrics": {},
            "circuit_breaker": {
                "state": CircuitBreakerState.CLOSED.value,
                "triggered_at": None,
                "recovery_time": None,
            },
            "last_reset": {"daily": None, "weekly": None},
        }
        data = atomic_read_json(self.data_path, default=default_data)

        # Ensure all required keys exist
        if "last_reset" not in data:
            data["last_reset"] = {"daily": None, "weekly": None}
        if "circuit_breaker" not in data:
            data["circuit_breaker"] = {
                "state": CircuitBreakerState.CLOSED.value,
                "triggered_at": None,
                "recovery_time": None,
            }

        return data

    def _save_data(self, data: dict[str, Any]):
        """Эрсдэлийн өгөгдөл хадгалах"""
        atomic_write_json(self.data_path, data, backup=True)

    def _get_date_key(self, dt: datetime) -> str:
        """Огнооны түлхүүр үүсгэх"""
        return dt.strftime("%Y-%m-%d")

    def _get_week_key(self, dt: datetime) -> str:
        """7 хоногийн түлхүүр үүсгэх"""
        year, week, _ = dt.isocalendar()
        return f"{year}-W{week:02d}"

    def _reset_daily_metrics_if_needed(self, data: dict[str, Any], current_date: str):
        """Өдрийн хэмжүүрийг шинэчлэх шаардлагатай бол"""
        last_daily_reset = data["last_reset"]["daily"]

        if last_daily_reset != current_date:
            # Шинэ өдөр эхэлсэн
            data["daily_metrics"] = {
                "loss": 0.0,
                "trades": 0,
                "consecutive_losses": 0,
                "last_trade_time": None,
            }
            data["last_reset"]["daily"] = current_date
            logger.info(
                "Өдрийн хэмжүүрийг дахин тохируулсан", extra={"date": current_date}
            )

    def _reset_weekly_metrics_if_needed(self, data: dict[str, Any], current_week: str):
        """7 хоногийн хэмжүүрийг шинэчлэх шаардлагатай бол"""
        last_weekly_reset = data["last_reset"]["weekly"]

        if last_weekly_reset != current_week:
            # Шинэ 7 хоног эхэлсэн
            data["weekly_metrics"] = {"loss": 0.0, "trades": 0}
            data["last_reset"]["weekly"] = current_week
            logger.info(
                "7 хоногийн хэмжүүрийг дахин тохируулсан", extra={"week": current_week}
            )

    def get_current_metrics(self, symbol: str = "XAUUSD") -> RiskMetrics:
        """Одоогийн эрсдэлийн хэмжүүрийг авах"""
        now = datetime.now(UTC)
        current_date = self._get_date_key(now)
        current_week = self._get_week_key(now)

        def update_metrics(data: dict[str, Any]) -> dict[str, Any]:
            self._reset_daily_metrics_if_needed(data, current_date)
            self._reset_weekly_metrics_if_needed(data, current_week)
            return data

        data = atomic_update_json(
            self.data_path,
            update_metrics,
            default={
                "daily_metrics": {"loss": 0.0, "trades": 0, "consecutive_losses": 0},
                "weekly_metrics": {"loss": 0.0, "trades": 0},
                "circuit_breaker": {"state": CircuitBreakerState.CLOSED.value},
                "last_reset": {"daily": current_date, "weekly": current_week},
            },
        )

        daily = data["daily_metrics"]
        weekly = data["weekly_metrics"]
        cb_state = CircuitBreakerState(data["circuit_breaker"]["state"])

        # Эрсдэлийн түвшин тодорхойлох
        risk_level = self._calculate_risk_level(daily["loss"], weekly["loss"])

        return RiskMetrics(
            daily_loss=daily["loss"],
            weekly_loss=weekly["loss"],
            daily_trades=daily["trades"],
            weekly_trades=weekly["trades"],
            consecutive_losses=daily.get("consecutive_losses", 0),
            last_trade_time=daily.get("last_trade_time"),
            risk_level=risk_level,
            circuit_breaker_state=cb_state,
        )

    def _calculate_risk_level(self, daily_loss: float, weekly_loss: float) -> RiskLevel:
        """Эрсдэлийн түвшинийг тооцоолох"""
        daily_threshold = self.settings.risk.max_daily_loss_percentage
        weekly_threshold = self.settings.risk.max_weekly_loss_percentage

        # Хувийг тооцоолох
        daily_pct = (daily_loss / daily_threshold) * 100 if daily_threshold > 0 else 0
        weekly_pct = (
            (weekly_loss / weekly_threshold) * 100 if weekly_threshold > 0 else 0
        )

        max_pct = max(daily_pct, weekly_pct)

        if max_pct >= 90:
            return RiskLevel.CRITICAL
        elif max_pct >= 70:
            return RiskLevel.HIGH
        elif max_pct >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def check_trade_allowed(
        self, symbol: str = "XAUUSD", trade_size: float = 0.01
    ) -> TradeDecision:
        """Арилжаа хийхийг зөвшөөрөх эсэхийг шалгах"""
        metrics = self.get_current_metrics(symbol)
        warnings = []

        # Circuit breaker шалгах
        if metrics.circuit_breaker_state == CircuitBreakerState.OPEN:
            return TradeDecision(
                allowed=False,
                reason="Circuit breaker идэвхтэй - автомат зогсоолтод орсон",
                risk_level=metrics.risk_level,
                metrics=metrics,
                warnings=warnings,
            )

        # Өдрийн дээд алдагдал шалгах
        if metrics.daily_loss >= self.settings.risk.max_daily_loss_percentage:
            return TradeDecision(
                allowed=False,
                reason=f"Өдрийн дээд алдагдал хэтэрсэн: {metrics.daily_loss:.2f}%",
                risk_level=metrics.risk_level,
                metrics=metrics,
                warnings=warnings,
            )

        # 7 хоногийн дээд алдагдал шалгах
        if metrics.weekly_loss >= self.settings.risk.max_weekly_loss_percentage:
            return TradeDecision(
                allowed=False,
                reason=f"7 хоногийн дээд алдагдал хэтэрсэн: {metrics.weekly_loss:.2f}%",
                risk_level=metrics.risk_level,
                metrics=metrics,
                warnings=warnings,
            )

        # Өдрийн дээд арилжааны тоо шалгах
        if metrics.daily_trades >= self.settings.risk.max_daily_trades:
            return TradeDecision(
                allowed=False,
                reason=f"Өдрийн дээд арилжааны тоо хэтэрсэн: {metrics.daily_trades}",
                risk_level=metrics.risk_level,
                metrics=metrics,
                warnings=warnings,
            )

        # 7 хоногийн дээд арилжааны тоо шалгах
        if metrics.weekly_trades >= self.settings.risk.max_weekly_trades:
            return TradeDecision(
                allowed=False,
                reason=f"7 хоногийн дээд арилжааны тоо хэтэрсэн: {metrics.weekly_trades}",
                risk_level=metrics.risk_level,
                metrics=metrics,
                warnings=warnings,
            )

        # Cooldown хугацаа шалгах
        if metrics.last_trade_time:
            time_since_last = time.time() - metrics.last_trade_time
            cooldown_seconds = self.settings.risk.cooldown_minutes * 60

            if time_since_last < cooldown_seconds:
                remaining = cooldown_seconds - time_since_last
                return TradeDecision(
                    allowed=False,
                    reason=f"Cooldown хугацаа дуусаагүй: {remaining/60:.1f} минут үлдлээ",
                    risk_level=metrics.risk_level,
                    metrics=metrics,
                    warnings=warnings,
                )

        # Анхааруулгууд нэмэх
        if metrics.risk_level == RiskLevel.HIGH:
            warnings.append("Өндөр эрсдэлтэй түвшинд хүрчээ")
            if self.settings.risk.alert_on_high_risk:
                self._send_telegram_alert(
                    f"⚠️ ӨНДӨР ЭРСДЭЛ\n"
                    f"Өдрийн алдагдал: {metrics.daily_loss:.2f}%\n"
                    f"7 хоногийн алдагдал: {metrics.weekly_loss:.2f}%\n"
                    f"Арилжаа зөвшөөрөгдсөн боловч анхаарна уу!",
                    "WARNING",
                )
        elif metrics.risk_level == RiskLevel.MEDIUM:
            warnings.append("Дунд эрсдэлтэй түвшинд хүрчээ")
            if self.settings.risk.alert_on_medium_risk:
                self._send_telegram_alert(
                    f"⚠️ ДУНД ЭРСДЭЛ\n"
                    f"Өдрийн алдагдал: {metrics.daily_loss:.2f}%\n"
                    f"7 хоногийн алдагдал: {metrics.weekly_loss:.2f}%",
                    "INFO",
                )

        return TradeDecision(
            allowed=True,
            reason="Эрсдэлийн бүх шалгуур хангагдсан",
            risk_level=metrics.risk_level,
            metrics=metrics,
            warnings=warnings,
        )

    def record_trade_result(
        self, symbol: str, profit_loss: float, was_win: bool
    ) -> None:
        """Арилжааны үр дүнг бүртгэх"""
        now = datetime.now(UTC)
        current_date = self._get_date_key(now)
        current_week = self._get_week_key(now)

        def update_trade_result(data: dict[str, Any]) -> dict[str, Any]:
            # Ensure all required keys exist
            if "last_reset" not in data:
                data["last_reset"] = {"daily": None, "weekly": None}
            if "circuit_breaker" not in data:
                data["circuit_breaker"] = {
                    "state": CircuitBreakerState.CLOSED.value,
                    "triggered_at": None,
                    "recovery_time": None,
                }
            if "daily_metrics" not in data:
                data["daily_metrics"] = {}
            if "weekly_metrics" not in data:
                data["weekly_metrics"] = {}

            self._reset_daily_metrics_if_needed(data, current_date)
            self._reset_weekly_metrics_if_needed(data, current_week)

            # Өдрийн хэмжүүр шинэчлэх
            daily = data["daily_metrics"]
            daily["trades"] += 1
            daily["loss"] += abs(profit_loss) if not was_win else 0
            daily["last_trade_time"] = time.time()

            # Дараалсан алдагдал тоолох
            if not was_win:
                daily["consecutive_losses"] = daily.get("consecutive_losses", 0) + 1
            else:
                daily["consecutive_losses"] = 0

            # 7 хоногийн хэмжүүр шинэчлэх
            weekly = data["weekly_metrics"]
            weekly["trades"] += 1
            weekly["loss"] += abs(profit_loss) if not was_win else 0

            # Circuit breaker шалгах
            if (
                daily["loss"] >= self.settings.risk.circuit_breaker_loss_threshold
                or daily["consecutive_losses"] >= 5
            ):
                data["circuit_breaker"]["state"] = CircuitBreakerState.OPEN.value
                data["circuit_breaker"]["triggered_at"] = time.time()
                data["circuit_breaker"]["recovery_time"] = time.time() + (
                    4 * 3600
                )  # 4 цаг

                logger.warning(
                    "Circuit breaker идэвхжлээ",
                    extra={
                        "daily_loss": daily["loss"],
                        "consecutive_losses": daily["consecutive_losses"],
                        "symbol": symbol,
                    },
                )

                # Telegram alert илгээх
                self._send_telegram_alert(
                    f"🚨 CIRCUIT BREAKER ИДЭВХТЭЙ\n"
                    f"Тэмдэгт: {symbol}\n"
                    f"Өдрийн алдагдал: {daily['loss']:.2f}%\n"
                    f"Дараалсан алдагдал: {daily['consecutive_losses']}\n"
                    f"Арилжаа 4 цагаар зогссон",
                    "CRITICAL",
                )

            return data

        atomic_update_json(self.data_path, update_trade_result)

        logger.info(
            "Арилжааны үр дүн бүртгэгдлээ",
            extra={
                "symbol": symbol,
                "profit_loss": profit_loss,
                "was_win": was_win,
                "date": current_date,
            },
        )

    def _send_telegram_alert(self, message: str, level: str = "WARNING") -> None:
        """Telegram alert илгээх"""
        if not self.settings.risk.enable_telegram_alerts:
            logger.debug("Telegram alerts идэвхгүй байна")
            return

        try:
            if ALERTS_AVAILABLE:
                success = send_risk_alert(message, level)
                if success:
                    logger.info(
                        "Risk alert амжилттай илгээлээ",
                        extra={"message_preview": message[:50] + "...", "level": level},
                    )
                else:
                    logger.warning("Risk alert илгээх амжилтгүй боллоо")
            else:
                logger.warning("Telegram alerts систем байхгүй")
        except Exception as e:
            logger.error(
                "Telegram alert илгээхэд алдаа гарлаа", extra={"error": str(e)}
            )

    def reset_circuit_breaker(self) -> bool:
        """Circuit breaker-г дахин тохируулах"""

        def reset_cb(data: dict[str, Any]) -> dict[str, Any]:
            cb = data["circuit_breaker"]
            recovery_time = cb.get("recovery_time")

            if recovery_time and time.time() >= recovery_time:
                cb["state"] = CircuitBreakerState.CLOSED.value
                cb["triggered_at"] = None
                cb["recovery_time"] = None
                logger.info("Circuit breaker дахин тохируулагдлаа")
                return data

            return data

        data = atomic_update_json(self.data_path, reset_cb)
        return data["circuit_breaker"]["state"] == CircuitBreakerState.CLOSED.value

    def get_risk_report(self) -> dict[str, Any]:
        """Эрсдэлийн тайлан авах"""
        metrics = self.get_current_metrics()

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "risk_level": metrics.risk_level.value,
            "circuit_breaker_active": metrics.circuit_breaker_state
            == CircuitBreakerState.OPEN,
            "daily_metrics": {
                "loss_percentage": metrics.daily_loss,
                "trades_count": metrics.daily_trades,
                "consecutive_losses": metrics.consecutive_losses,
                "limit_usage": {
                    "loss": (
                        metrics.daily_loss
                        / self.settings.risk.max_daily_loss_percentage
                    )
                    * 100,
                    "trades": (
                        metrics.daily_trades / self.settings.risk.max_daily_trades
                    )
                    * 100,
                },
            },
            "weekly_metrics": {
                "loss_percentage": metrics.weekly_loss,
                "trades_count": metrics.weekly_trades,
                "limit_usage": {
                    "loss": (
                        metrics.weekly_loss
                        / self.settings.risk.max_weekly_loss_percentage
                    )
                    * 100,
                    "trades": (
                        metrics.weekly_trades / self.settings.risk.max_weekly_trades
                    )
                    * 100,
                },
            },
        }
