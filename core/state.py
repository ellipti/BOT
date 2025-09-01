import os, json, time
from typing import Dict, Any

STATE_FILE = os.path.join("state", "last_state.json")
os.makedirs("state", exist_ok=True)

def _read() -> Dict[str, Any]:
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write(data: Dict[str, Any]) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    st = _read()
    st.setdefault(symbol, {})
    st[symbol]["last_trade_ts"] = time.time()
    st[symbol]["last_decision"] = decision
    _write(st)
import json, os, time
from typing import Optional

class StateStore:
    def __init__(self, path: str = "last_decision.json"):
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _read(self) -> dict:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write(self, data: dict):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def last_ts(self, symbol: str) -> Optional[float]:
        return self._read().get(symbol, {}).get("ts")

    def set_now(self, symbol: str):
        data = self._read()
        data[symbol] = {"ts": time.time()}
        self._write(data)

    def cooldown_elapsed(self, symbol: str, minutes: int) -> bool:
        ts = self.last_ts(symbol)
        if ts is None:
            return True
        return (time.time() - ts) >= minutes * 60
