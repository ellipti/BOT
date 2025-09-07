"""
Эдийн засгийн календарь системийн буфер/кэш
Calendar Guard - Эдийн засгийн мэдээний эвентүүдийн дараах blackout window удирдлага

Trading Economics API ашиглан эдийн засгийн календарыг татаж авч,
өндөр нөлөөт эвентүүдийн өмнө/дараах цаг хугацааг тодорхойлж байна.

Онцлогууд:
- Trading Economics API integration with retry/backoff
- Local TTL кэш систем
- Blackout window тооцоолол
- Event-ийн өмнөх/дараах хугацааны удирдлага
- Монгол хэлний лог системийн дэмжлэг
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, NamedTuple

import requests

from config.settings import get_settings
from utils.atomic_io import atomic_read_json, atomic_update_json, setup_advanced_logger

# Лог систем тохиргоо
logger = setup_advanced_logger(__name__)


class EventImportance(Enum):
    """Эвентийн ач холбогдлын түвшин"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BlackoutStatus(Enum):
    """Blackout window-ийн төлөв"""

    CLEAR = "clear"  # Арилжаа боломжтой
    PRE_EVENT = "pre_event"  # Event-ийн өмнө
    POST_EVENT = "post_event"  # Event-ийн дараа
    ACTIVE_EVENT = "active"  # Event явагдаж байна


@dataclass
class EconomicEvent:
    """Эдийн засгийн эвентийн мэдээлэл"""

    id: str
    title: str
    country: str
    category: str
    importance: EventImportance
    datetime: datetime
    forecast: str | None = None
    previous: str | None = None
    actual: str | None = None
    currency: str | None = None
    unit: str | None = None


@dataclass
class BlackoutWindow:
    """Blackout window-ийн мэдээлэл"""

    event: EconomicEvent
    start_time: datetime
    end_time: datetime
    status: BlackoutStatus
    reason: str


class CalendarGuardResult(NamedTuple):
    """Calendar Guard шалгалтын үр дүн"""

    allowed: bool
    status: BlackoutStatus
    reason: str
    next_clear_time: datetime | None = None
    active_blackouts: list[BlackoutWindow] = None


class CalendarGuard:
    """
    Эдийн засгийн календарь систем
    Өндөр нөлөөт эвентүүдийн blackout window удирдлага
    """

    def __init__(self, settings=None):
        """Calendar Guard-ийг эхлүүлэх"""
        self.settings = settings or get_settings()
        self.cache_path = Path("state") / "economic_calendar.json"
        self.cache_path.parent.mkdir(exist_ok=True)

        # Blackout window тохиргоо (минутаар)
        self.pre_event_minutes = {
            EventImportance.LOW: 5,
            EventImportance.MEDIUM: 15,
            EventImportance.HIGH: 30,
            EventImportance.CRITICAL: 60,
        }

        self.post_event_minutes = {
            EventImportance.LOW: 5,
            EventImportance.MEDIUM: 10,
            EventImportance.HIGH: 20,
            EventImportance.CRITICAL: 30,
        }

        # API тохиргоо
        self.api_key = getattr(self.settings, "trading_economics_api_key", None)
        self.base_url = "https://api.tradingeconomics.com"
        self.cache_ttl = 3600  # 1 цаг
        self.max_retries = 3
        self.backoff_factor = 2

        logger.info("Эдийн засгийн календарь систем эхэллээ")

    def _get_cache_data(self) -> dict[str, Any]:
        """Кэш өгөгдөл унших"""
        default_data = {
            "events": [],
            "last_update": 0,
            "api_calls": 0,
            "last_api_call": 0,
        }
        return atomic_read_json(self.cache_path, default=default_data)

    def _save_cache_data(self, data: dict[str, Any]):
        """Кэш өгөгдөл хадгалах"""

        def update_cache(current_data: dict[str, Any]) -> dict[str, Any]:
            current_data.update(data)
            return current_data

        atomic_update_json(self.cache_path, update_cache)

    def _is_cache_valid(self) -> bool:
        """Кэш хүчинтэй эсэхийг шалгах"""
        cache_data = self._get_cache_data()
        last_update = cache_data.get("last_update", 0)
        current_time = time.time()

        is_valid = (current_time - last_update) < self.cache_ttl

        if not is_valid:
            logger.debug(
                f"Кэш хуучирсан: {current_time - last_update:.0f} секунд өнгөрсөн"
            )

        return is_valid

    async def _fetch_events_with_retry(self) -> list[dict[str, Any]]:
        """Retry/backoff-тэй API дуудлага"""
        if not self.api_key:
            logger.warning("Trading Economics API түлхүүр байхгүй")
            return []

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"API дуудлага оролдлого {attempt + 1}/{self.max_retries}")

                # Today + 7 days эвентүүдийг татах
                today = datetime.now(UTC).strftime("%Y-%m-%d")
                future_date = (datetime.now(UTC) + timedelta(days=7)).strftime(
                    "%Y-%m-%d"
                )

                url = f"{self.base_url}/calendar"
                params = {
                    "c": self.api_key,
                    "d1": today,
                    "d2": future_date,
                    "f": "json",
                }

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()

                events_data = response.json()

                # API дуудлага тоо шинэчлэх
                cache_data = self._get_cache_data()
                cache_data["api_calls"] += 1
                cache_data["last_api_call"] = time.time()

                logger.info(f"API-аас {len(events_data)} эвент татаж авлаа")
                return events_data

            except requests.exceptions.RequestException as e:
                wait_time = self.backoff_factor**attempt
                logger.warning(f"API дуудлага амжилтгүй (оролдлого {attempt + 1}): {e}")

                if attempt < self.max_retries - 1:
                    logger.debug(f"{wait_time} секунд хүлээж байна...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("API дуудлагын бүх оролдлого амжилтгүй боллоо")

            except Exception as e:
                logger.error(f"API дуудлагын алдаа: {e}")
                break

        return []

    def _parse_event_data(self, event_data: dict[str, Any]) -> EconomicEvent | None:
        """API өгөгдлөөс EconomicEvent үүсгэх"""
        try:
            # Event importance тодорхойлох
            importance_mapping = {
                "1": EventImportance.LOW,
                "2": EventImportance.MEDIUM,
                "3": EventImportance.HIGH,
                "high": EventImportance.HIGH,
                "medium": EventImportance.MEDIUM,
                "low": EventImportance.LOW,
            }

            importance_str = str(event_data.get("Importance", "1")).lower()
            importance = importance_mapping.get(importance_str, EventImportance.LOW)

            # Огноог parse хийх
            date_str = event_data.get("Date", "")
            if not date_str:
                return None

            # ISO format-д хөрвүүлэх
            try:
                event_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                if event_dt.tzinfo is None:
                    event_dt = event_dt.replace(tzinfo=UTC)
            except:
                logger.warning(f"Огноо parse хийх боломжгүй: {date_str}")
                return None

            return EconomicEvent(
                id=str(event_data.get("CalendarId", "")),
                title=event_data.get("Event", ""),
                country=event_data.get("Country", ""),
                category=event_data.get("Category", ""),
                importance=importance,
                datetime=event_dt,
                forecast=event_data.get("Forecast"),
                previous=event_data.get("Previous"),
                actual=event_data.get("Actual"),
                currency=event_data.get("Currency"),
                unit=event_data.get("Unit"),
            )

        except Exception as e:
            logger.warning(f"Event parse хийх алдаа: {e}")
            return None

    async def update_calendar(self, force_update: bool = False) -> bool:
        """Эдийн засгийн календарь шинэчлэх"""
        if not force_update and self._is_cache_valid():
            logger.debug("Кэш хүчинтэй байгаа - шинэчлэх шаардлагагүй")
            return True

        logger.info("Эдийн засгийн календарь шинэчилж байна...")

        try:
            # API-аас эвентүүд татах
            raw_events = await self._fetch_events_with_retry()

            if not raw_events:
                logger.warning("API-аас эвент авч чадсангүй")
                return False

            # Эвентүүдийг parse хийх
            parsed_events = []
            for raw_event in raw_events:
                event = self._parse_event_data(raw_event)
                if event:
                    parsed_events.append(
                        {
                            "id": event.id,
                            "title": event.title,
                            "country": event.country,
                            "category": event.category,
                            "importance": event.importance.value,
                            "datetime": event.datetime.isoformat(),
                            "forecast": event.forecast,
                            "previous": event.previous,
                            "actual": event.actual,
                            "currency": event.currency,
                            "unit": event.unit,
                        }
                    )

            # Кэшд хадгалах
            cache_data = self._get_cache_data()
            cache_data["events"] = parsed_events
            cache_data["last_update"] = time.time()
            self._save_cache_data(cache_data)

            logger.info(
                f"Эдийн засгийн календарь амжилттай шинэчлэгдлээ: {len(parsed_events)} эвент"
            )
            return True

        except Exception as e:
            logger.error(f"Календарь шинэчлэх алдаа: {e}")
            return False

    def _get_cached_events(self) -> list[EconomicEvent]:
        """Кэшээс эвентүүд авах"""
        cache_data = self._get_cache_data()
        events = []

        for event_data in cache_data.get("events", []):
            try:
                event = EconomicEvent(
                    id=event_data["id"],
                    title=event_data["title"],
                    country=event_data["country"],
                    category=event_data["category"],
                    importance=EventImportance(event_data["importance"]),
                    datetime=datetime.fromisoformat(event_data["datetime"]),
                    forecast=event_data.get("forecast"),
                    previous=event_data.get("previous"),
                    actual=event_data.get("actual"),
                    currency=event_data.get("currency"),
                    unit=event_data.get("unit"),
                )
                events.append(event)
            except Exception as e:
                logger.warning(f"Cached event parse хийх алдаа: {e}")

        return events

    def _calculate_blackout_window(
        self, event: EconomicEvent, current_time: datetime
    ) -> BlackoutWindow | None:
        """Event-ийн blackout window тооцоолох"""
        pre_minutes = self.pre_event_minutes.get(event.importance, 15)
        post_minutes = self.post_event_minutes.get(event.importance, 10)

        start_time = event.datetime - timedelta(minutes=pre_minutes)
        end_time = event.datetime + timedelta(minutes=post_minutes)

        # Blackout window дотор эсэхийг шалгах
        if current_time < start_time:
            return None  # Хараахан blackout эхлээгүй

        if current_time > end_time:
            return None  # Blackout дууссан

        # Status тодорхойлох
        if current_time < event.datetime:
            status = BlackoutStatus.PRE_EVENT
            reason = f"'{event.title}' эвентийн өмнөх {pre_minutes} минутын хугацаа"
        elif current_time <= event.datetime + timedelta(
            minutes=5
        ):  # Event явагдаж байх 5 минут
            status = BlackoutStatus.ACTIVE_EVENT
            reason = f"'{event.title}' эвент идэвхтэй байна"
        else:
            status = BlackoutStatus.POST_EVENT
            reason = f"'{event.title}' эвентийн дараах {post_minutes} минутын хугацаа"

        return BlackoutWindow(
            event=event,
            start_time=start_time,
            end_time=end_time,
            status=status,
            reason=reason,
        )

    async def check_trading_allowed(
        self, target_currencies: list[str] = None
    ) -> CalendarGuardResult:
        """Арилжаа хийх боломжтой эсэхийг шалгах"""
        current_time = datetime.now(UTC)

        # Календарь шинэчлэх (кэш хүчинтэй бол шинэчлэхгүй)
        await self.update_calendar()

        # Кэшээс эвентүүд авах
        events = self._get_cached_events()

        if not events:
            logger.debug("Эдийн засгийн эвент байхгүй")
            return CalendarGuardResult(
                allowed=True,
                status=BlackoutStatus.CLEAR,
                reason="Эдийн засгийн эвент алга",
                active_blackouts=[],
            )

        # Currency filter хэрэглэх
        if target_currencies:
            target_currencies = [c.upper() for c in target_currencies]
            filtered_events = [
                e
                for e in events
                if not e.currency or e.currency.upper() in target_currencies
            ]
        else:
            filtered_events = events

        # Blackout window-уудыг тооцоолох
        active_blackouts = []
        next_clear_time = None

        for event in filtered_events:
            blackout = self._calculate_blackout_window(event, current_time)
            if blackout:
                active_blackouts.append(blackout)
                logger.debug(
                    f"Идэвхтэй blackout: {event.title} ({blackout.status.value})"
                )

        # Дараагийн clear time тооцоолох
        if active_blackouts:
            next_clear_time = min(blackout.end_time for blackout in active_blackouts)

        # Үр дүн тодорхойлох
        if active_blackouts:
            # Хамгийн чухал blackout-г сонгох
            priority_blackout = max(
                active_blackouts,
                key=lambda b: (
                    b.event.importance.value == "critical",
                    b.event.importance.value == "high",
                    b.event.importance.value == "medium",
                ),
            )

            logger.warning(f"Арилжаа хориглогдсон: {priority_blackout.reason}")

            return CalendarGuardResult(
                allowed=False,
                status=priority_blackout.status,
                reason=priority_blackout.reason,
                next_clear_time=next_clear_time,
                active_blackouts=active_blackouts,
            )

        logger.debug("Эдийн засгийн календарь: арилжаа боломжтой")
        return CalendarGuardResult(
            allowed=True,
            status=BlackoutStatus.CLEAR,
            reason="Эдийн засгийн хориг алга",
            active_blackouts=[],
        )

    def get_upcoming_events(self, hours: int = 24) -> list[EconomicEvent]:
        """Ирэх N цагийн эвентүүдийг авах"""
        current_time = datetime.now(UTC)
        end_time = current_time + timedelta(hours=hours)

        events = self._get_cached_events()
        upcoming = [
            event for event in events if current_time <= event.datetime <= end_time
        ]

        # Importance болон цаг дарааллаар эрэмбэлэх
        upcoming.sort(
            key=lambda e: (
                e.datetime,
                e.importance.value != "critical",
                e.importance.value != "high",
            )
        )

        return upcoming

    def get_calendar_status(self) -> dict[str, Any]:
        """Календарийн төлөв авах"""
        cache_data = self._get_cache_data()
        current_time = time.time()

        return {
            "cache_valid": self._is_cache_valid(),
            "last_update": cache_data.get("last_update", 0),
            "time_since_update": current_time - cache_data.get("last_update", 0),
            "events_count": len(cache_data.get("events", [])),
            "api_calls": cache_data.get("api_calls", 0),
            "last_api_call": cache_data.get("last_api_call", 0),
            "cache_ttl": self.cache_ttl,
            "api_configured": bool(self.api_key),
        }


# Async wrapper функцууд
async def check_calendar_guard(currencies: list[str] = None) -> CalendarGuardResult:
    """Calendar Guard шалгах async wrapper"""
    guard = CalendarGuard()
    return await guard.check_trading_allowed(currencies)


def get_calendar_guard_sync(currencies: list[str] = None) -> CalendarGuardResult:
    """Calendar Guard шалгах sync wrapper"""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, create new task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, check_calendar_guard(currencies))
                return future.result()
        else:
            return loop.run_until_complete(check_calendar_guard(currencies))
    except RuntimeError:
        # No event loop, create new one
        return asyncio.run(check_calendar_guard(currencies))
