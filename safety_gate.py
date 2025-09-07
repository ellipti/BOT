from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from config.settings import get_settings
from utils.atomic_io import atomic_read_json, atomic_update_json, atomic_write_json

# ---- Тохиргоо (анхдагч) -----------------------------------------------------
UB_TZ = ZoneInfo("Asia/Ulaanbaatar")
settings = get_settings()


class LimitsManager:
    """Enhanced LimitsManager with atomic I/O operations"""

    def __init__(self, path: str = "state/limits.json"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def _load(self) -> dict:
        """Load limits data with atomic read"""
        return atomic_read_json(self.path, default={})

    def _save(self, data: dict) -> None:
        """Save limits data with atomic write"""
        atomic_write_json(self.path, data)

    def _key(self, date_str: str, symbol: str) -> str:
        return f"{date_str}:{symbol}"

    def get_state(self, symbol: str, now_utc: datetime) -> dict:
        d = self._load()
        key = self._key(now_utc.strftime("%Y-%m-%d"), symbol)
        return d.get(key, {"trades": 0, "baseline_equity": None, "blocked": False})

    def set_state(self, symbol: str, now_utc: datetime, state: dict) -> None:
        """Set state with atomic update operation"""
        key = self._key(now_utc.strftime("%Y-%m-%d"), symbol)

        def update_limits_state(current_data: dict) -> dict:
            current_data[key] = state
            return current_data

        atomic_update_json(self.path, update_limits_state, default={})

    def ensure_baseline(self, symbol: str, now_utc: datetime, equity: float) -> None:
        """Ensure baseline equity is set with atomic operation"""
        key = self._key(now_utc.strftime("%Y-%m-%d"), symbol)

        def set_baseline_if_missing(current_data: dict) -> dict:
            if key not in current_data:
                current_data[key] = {
                    "trades": 0,
                    "baseline_equity": None,
                    "blocked": False,
                }
            if (
                current_data[key].get("baseline_equity") is None
                and equity
                and equity > 0
            ):
                current_data[key]["baseline_equity"] = float(equity)
            return current_data

        atomic_update_json(self.path, set_baseline_if_missing, default={})

    def mark_trade(self, symbol: str, now_utc: datetime) -> None:
        """Mark trade with atomic increment operation"""
        key = self._key(now_utc.strftime("%Y-%m-%d"), symbol)

        def increment_trade_count(current_data: dict) -> dict:
            if key not in current_data:
                current_data[key] = {
                    "trades": 0,
                    "baseline_equity": None,
                    "blocked": False,
                }
            current_data[key]["trades"] = int(current_data[key].get("trades", 0)) + 1
            return current_data

        atomic_update_json(self.path, increment_trade_count, default={})

    def check_limits(
        self, symbol: str, now_utc: datetime, open_positions: int, equity: float
    ) -> tuple[bool, str]:
        if not settings.safety.limits_enabled:
            return True, ""
        s = self.get_state(symbol, now_utc)
        # 1) Хэрэв өмнө нь зогсоосон бол өнөөдөр HOLD
        if s.get("blocked"):
            return False, "Daily limits reached (blocked)"
        # 2) Нээлттэй байрлалын дээд
        if open_positions >= settings.safety.max_open_positions:
            return (
                False,
                f"Max open positions {open_positions}/{settings.safety.max_open_positions}",
            )
        # 3) Өдрийн гүйлгээний дээд
        trades = int(s.get("trades", 0))
        if trades >= settings.safety.max_trades_per_day:
            return (
                False,
                f"Max trades per day {trades}/{settings.safety.max_trades_per_day}",
            )
        # 4) Өдрийн алдагдлын дээд
        base = s.get("baseline_equity")
        if base is None and equity and equity > 0:
            self.ensure_baseline(symbol, now_utc, equity)
            base = equity
        if base:
            dd = max(0.0, (float(base) - float(equity)) / float(base) * 100.0)
            if dd >= settings.safety.max_daily_loss_percentage:
                s["blocked"] = True
                self.set_state(symbol, now_utc, s)
                return (
                    False,
                    f"Daily loss hit: {dd:.2f}% ≥ {settings.safety.max_daily_loss_percentage}%",
                )
        return True, ""


# XAUUSD-н түгээмэл гэрээний хэмжээ: 1 lot = 100 oz  →  $1 үнэ = ~$100/lot PnL
USD_PER_LOT_PER_USD_MOVE = settings.trading.usd_per_lot_per_usd_move

TE_API_KEY = os.getenv("TE_API_KEY", "")  # Trading Economics (optional)
try:
    import requests  # optional
except Exception:
    requests = None

# ---- Дотоод state -----------------------------------------------------------
STATE_FILE = os.path.join("state", "last_state.json")
os.makedirs("state", exist_ok=True)


def _read_state() -> dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_state(d: dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ---- Төрөл тодорхойлолт -----------------------------------------------------
Signal = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Decision:
    action: Signal
    reason: str
    lot: float = 0.0
    sl_points: float = 0.0
    tp_points: float = 0.0


# ---- Гол ангилал ------------------------------------------------------------
class Guard:
    """
    Trade-safety gate:
      - Сешн цонх
      - Давхардал/cooldown
      - Улаан мэдээ (Trading Economics, optional)
      - Шийдвэр баталгаажуулалт (MA20/50, RSI, ATR)
      - ATR-д суурилсан лот тооцоолол
    """

    def __init__(
        self,
        symbol: str,
        timeframe_min: int,
        session: Literal["TOKYO", "LDN_NY", "ANY"] = "LDN_NY",
        cooldown_mult: float = 2.0,
        min_atr: float = 2.0,
        risk_pct: float = 0.01,
        sl_mult: float = 1.5,
        tp_mult: float = 3.0,
        news_window_min: int = 60,
        enable_news: bool = True,
    ) -> None:
        self.symbol = symbol
        self.tf_min = timeframe_min
        self.session = session
        self.cooldown_mult = cooldown_mult
        self.min_atr = min_atr
        self.risk_pct = risk_pct
        self.sl_mult = sl_mult
        self.tp_mult = tp_mult
        self.news_window_min = news_window_min
        self.enable_news = enable_news
        self.limits = LimitsManager()

    # ---------- Нийтийн API ----------
    def filter_decision(
        self,
        raw_signal: Signal,
        close: float,
        ma_fast: float,
        ma_slow: float,
        rsi: float,
        atr: float,
        balance_usd: float,
        now_utc: datetime | None = None,
        open_positions: int = 0,
        equity_usd: float | None = None,
    ) -> Decision:
        """Шийдвэрийг бүх хамгаалалтаар шүүж, лот/SL/TP бэлдэнэ."""
        now_utc = now_utc or datetime.now(UTC)

        # --- Check daily limits first ---
        ok, reason = self.limits.check_limits(
            self.symbol, now_utc, open_positions, equity_usd or balance_usd
        )
        if not ok:
            return Decision(action="HOLD", reason=f"Limits: {reason}")

        # 1) Сешн
        if not self._in_session(now_utc):
            return Decision("HOLD", "Out of session window")

        # 2) Давхардал/cooldown
        if self._cooldown_active():
            return Decision("HOLD", "Cooldown active")

        # 3) Улаан мэдээ (optional)
        if self.enable_news and self._has_high_impact_news(now_utc):
            return Decision("HOLD", "Red news window")

        # 4) Тренд/осцилляторын шалгуур
        gated = self._validate_signal(raw_signal, close, ma_fast, ma_slow, rsi, atr)
        if gated != "BUY" and gated != "SELL":
            return Decision("HOLD", f"Filtered: {raw_signal} → HOLD")

        # 5) Лот, SL/TP (ATR дээр)
        sl_pts = atr * self.sl_mult
        tp_pts = atr * self.tp_mult
        lot = self._calc_lot(balance_usd=balance_usd, atr=atr, sl_mult=self.sl_mult)

        if lot <= 0:
            return Decision("HOLD", "Lot computed ≤ 0")

        return Decision(gated, "OK", lot=lot, sl_points=sl_pts, tp_points=tp_pts)

    def mark_trade(self, action: Signal) -> None:
        st = _read_state()
        st.setdefault(self.symbol, {})
        st[self.symbol]["last_trade_ts"] = time.time()
        st[self.symbol]["last_decision"] = action
        _write_state(st)

    # ---------- Дотоод логик ----------
    def _in_session(self, now_utc: datetime) -> bool:
        if self.session == "ANY":
            return True
        now = now_utc.astimezone(UB_TZ).time()
        if self.session == "TOKYO":
            return (9, 0) <= (now.hour, now.minute) <= (12, 0)
        # LDN_NY: 16:00–02:00 UB (шөнийн гүүрлэлт)
        return now.hour >= 16 or now.hour <= 2

    def _cooldown_active(self) -> bool:
        st = _read_state().get(self.symbol, {})
        last = st.get("last_trade_ts")
        if not last:
            return False
        elapsed = time.time() - float(last)
        cooldown = self.tf_min * 60 * self.cooldown_mult
        return elapsed < cooldown

    def _has_high_impact_news(self, now_utc: datetime) -> bool:
        if not TE_API_KEY or requests is None:
            return False
        countries = {
            "XAUUSD": ["United States"],
            "EURUSD": ["Euro Area", "Germany", "France", "Italy", "Spain"],
            "GBPUSD": ["United Kingdom"],
        }.get(self.symbol, ["United States"])
        d1 = (now_utc - timedelta(minutes=self.news_window_min)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        d2 = (now_utc + timedelta(minutes=self.news_window_min)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        url = (
            "https://api.tradingeconomics.com/calendar?"
            f"importance=3&d1={d1}&d2={d2}&c={','.join(countries)}&format=json"
        )
        try:
            # Trading Economics expects the raw API key in the Authorization header
            r = requests.get(url, headers={"Authorization": TE_API_KEY}, timeout=8)
            r.raise_for_status()
            data = r.json()
            return isinstance(data, list) and len(data) > 0
        except Exception:
            return False

    def _validate_signal(
        self,
        raw: Signal,
        close: float,
        ma_fast: float,
        ma_slow: float,
        rsi: float,
        atr: float,
    ) -> Signal:
        if atr < self.min_atr:
            return "HOLD"
        trend_up = ma_fast > ma_slow
        trend_dn = ma_fast < ma_slow
        if raw == "BUY":
            return (
                "BUY"
                if (trend_up and rsi >= 49 and close >= ma_fast - 0.2 * atr)
                else "HOLD"
            )
        if raw == "SELL":
            return (
                "SELL"
                if (trend_dn and rsi <= 51 and close <= ma_fast + 0.2 * atr)
                else "HOLD"
            )
        return "HOLD"

    def _calc_lot(self, balance_usd: float, atr: float, sl_mult: float) -> float:
        risk_usd = balance_usd * self.risk_pct
        sl_usd_per_lot = atr * sl_mult * USD_PER_LOT_PER_USD_MOVE
        if sl_usd_per_lot <= 0:
            return 0.01
        lot = max(risk_usd / sl_usd_per_lot, 0.01)
        # 2 орон хүртэл тоймлох (ихэнх брокерийн min step=0.01)
        return round(lot, 2)
