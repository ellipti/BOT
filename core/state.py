"""
State management with atomic I/O operations
Updated to use Upgrade #06 atomic file operations
"""

import os
import time
from typing import Any

from utils.atomic_io import atomic_read_json, atomic_update_json, atomic_write_json

STATE_FILE = os.path.join("state", "last_state.json")
os.makedirs("state", exist_ok=True)


def _read() -> dict[str, Any]:
    """Read state with atomic operations"""
    return atomic_read_json(STATE_FILE, default={})


def _write(data: dict[str, Any]) -> None:
    """Write state with atomic operations"""
    atomic_write_json(STATE_FILE, data)


def recently_traded(symbol: str, tf_minutes: int, cooldown_mult: float = 1.5) -> bool:
    """Тухайн timeframe*d* cooldown дотор дахин бүү оролт хий."""
    st = _read().get(symbol, {})
    last = st.get("last_trade_ts")
    if not last:
        return False
    elapsed = time.time() - float(last)
    cooldown = tf_minutes * 60 * cooldown_mult
    return elapsed < cooldown


def mark_trade(symbol: str, decision: str) -> None:
    """Mark trade with atomic update operation"""

    def update_trade_state(current_state: dict[str, Any]) -> dict[str, Any]:
        current_state.setdefault(symbol, {})
        current_state[symbol]["last_trade_ts"] = time.time()
        current_state[symbol]["last_decision"] = decision
        return current_state

    atomic_update_json(STATE_FILE, update_trade_state, default={})


class StateStore:
    """Enhanced StateStore with atomic operations"""

    def __init__(self, path: str = "last_decision.json"):
        self.path = path
        # Ensure file exists with atomic operation
        if not os.path.exists(self.path):
            atomic_write_json(self.path, {})

    def _read(self) -> dict:
        """Read state with atomic operations"""
        return atomic_read_json(self.path, default={})

    def _write(self, data: dict):
        """Write state with atomic operations"""
        atomic_write_json(self.path, data)

    def last_ts(self, symbol: str) -> float | None:
        """Get last timestamp for symbol"""
        return self._read().get(symbol, {}).get("ts")

    def set_now(self, symbol: str):
        """Set current timestamp for symbol with atomic update"""

        def update_timestamp(current_data: dict) -> dict:
            current_data[symbol] = {"ts": time.time()}
            return current_data

        atomic_update_json(self.path, update_timestamp, default={})

    def cooldown_elapsed(self, symbol: str, minutes: int) -> bool:
        """Check if cooldown period has elapsed"""
        ts = self.last_ts(symbol)
        if ts is None:
            return True
        return (time.time() - ts) >= minutes * 60
