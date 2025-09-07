import math
from dataclasses import dataclass
from typing import Literal

import MetaTrader5 as mt5

from .logger import get_logger

logger = get_logger("executor")

Side = Literal["BUY", "SELL"]


@dataclass
class ExecSettings:
    risk_per_trade: float
    atr_period: int
    sl_atr_mult: float
    tp_r_mult: float
    dry_run: bool
    magic: int
    order_comment: str
    filling_mode: int | None = None  # mt5.ORDER_FILLING_IOC / FOK / RETURN


class TradeExecutor:
    def __init__(self, settings: ExecSettings):
        self.s = settings

    # --- Helpers ---
    def _pip_round(self, price: float, digits: int) -> float:
        return round(price, digits)

    def _pick_fill_mode(self, sym):
        # Prefer config; else symbol's capability; fallback IOC
        if self.s.filling_mode is not None:
            return self.s.filling_mode
        try:
            if sym.trade_fill_mode in (
                mt5.ORDER_FILLING_FOK,
                mt5.ORDER_FILLING_IOC,
                mt5.ORDER_FILLING_RETURN,
            ):
                return sym.trade_fill_mode
        except Exception:
            pass
        return mt5.ORDER_FILLING_IOC

    def _calc_lot(self, symbol: str, stop_distance_price: float) -> float:
        info = mt5.symbol_info(symbol)
        acc = mt5.account_info()
        if not info or not acc:
            logger.error("symbol/account info missing for lot calc")
            return 0.01

        # ticks for stop distance
        tick_size = info.trade_tick_size or info.point
        tick_value_per_lot = info.trade_tick_value or 0.0
        if tick_value_per_lot <= 0 or tick_size <= 0:
            # conservative fallback
            return max(info.volume_min or 0.01, 0.01)

        ticks = max(stop_distance_price / tick_size, 1e-9)
        risk_ccy = max(acc.balance * self.s.risk_per_trade, 0.0)
        lot = risk_ccy / (ticks * tick_value_per_lot)

        # clamp & step
        vol_step = info.volume_step or 0.01
        vol_min = info.volume_min or 0.01
        vol_max = info.volume_max or 100.0
        lot = math.floor(lot / vol_step) * vol_step
        return float(min(max(lot, vol_min), vol_max))

    # --- Public: place market order ---
    def place(
        self, symbol: str, side: Side, price_hint: float | None, atr_value: float
    ) -> dict:
        sym = mt5.symbol_info(symbol)
        if not sym:
            return {"ok": False, "reason": "symbol_info_none"}

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {"ok": False, "reason": "no_tick"}

        price = tick.ask if side == "BUY" else tick.bid
        digits = sym.digits
        point = sym.point

        # Stop distance from ATR
        stop_dist = max(atr_value * self.s.sl_atr_mult, sym.trade_stops_level * point)
        if stop_dist <= 0:
            return {"ok": False, "reason": "bad_stop_dist"}

        if side == "BUY":
            sl = self._pip_round(price - stop_dist, digits)
            tp = self._pip_round(price + self.s.tp_r_mult * stop_dist, digits)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            sl = self._pip_round(price + stop_dist, digits)
            tp = self._pip_round(price - self.s.tp_r_mult * stop_dist, digits)
            order_type = mt5.ORDER_TYPE_SELL

        lot = self._calc_lot(symbol, abs(price - sl))
        if lot <= 0:
            return {"ok": False, "reason": "lot_calc_zero"}

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": self._pip_round(price, digits),
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": self.s.magic,
            "comment": self.s.order_comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._pick_fill_mode(sym),
        }

        if self.s.dry_run:
            logger.info(f"[DRY] {symbol} {side} lot={lot} @ {price} SL={sl} TP={tp}")
            return {
                "ok": True,
                "dry": True,
                "price": price,
                "sl": sl,
                "tp": tp,
                "lot": lot,
            }

        result = mt5.order_send(request)
        if result is None:
            return {"ok": False, "reason": "order_send_none"}

        if result.retcode == mt5.TRADE_RETCODE_DONE:
            logger.info(
                f"[LIVE] {symbol} {side} lot={lot} @ {price} SL={sl} TP={tp} | ticket={getattr(result, 'order', None)}"
            )
            return {
                "ok": True,
                "dry": False,
                "price": price,
                "sl": sl,
                "tp": tp,
                "lot": lot,
                "ticket": getattr(result, "order", None),
                "deal": getattr(result, "deal", None),
            }
        else:
            logger.error(
                f"order_send failed: retcode={result.retcode}, comment={getattr(result,'comment',None)}"
            )
            return {
                "ok": False,
                "reason": f"retcode={result.retcode}",
                "comment": getattr(result, "comment", None),
            }
