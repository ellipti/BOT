import os
from datetime import datetime, timezone
import pandas as pd
from core.config import get_settings
from core.logger import setup_logger
from core.mt5_client import MT5Client
from strategies.indicators import atr, rsi
from safety_gate import Guard
from strategies.baseline import ma_crossover_signal
from core.state import StateStore
from core.trade_executor import TradeExecutor, ExecSettings
from services.telegram import TelegramClient
from services.vision_context import build_vision_context
from services.chart_renderer import render_chart_with_overlays

logger = setup_logger()

def run_once():
    settings = get_settings()
    mt5c = MT5Client()
    if not mt5c.connect(
        login=settings.mt5_login if not settings.using_attach_mode else 0,
        password=settings.mt5_password if not settings.using_attach_mode else "",
        server=settings.mt5_server if not settings.using_attach_mode else "",
        path=settings.mt5_path,
        attach_mode=settings.using_attach_mode,
    ):
        logger.error("MT5 холбогдож чадсангүй. Terminal нээж login хийсэн эсэхийг шалгана уу.")
        return
        
    # Make sure charts directory exists
    os.makedirs("charts", exist_ok=True)
        
    # Дансны мэдээлэл харуулах
    mt5c.account_snapshot()

    tg = None
    if settings.telegram_token and settings.telegram_chat_id and TelegramClient:
        tg = TelegramClient(settings.telegram_token, settings.telegram_chat_id)

    # Executor + State
    ex = TradeExecutor(ExecSettings(
        risk_per_trade=settings.risk_per_trade,
        atr_period=settings.atr_period,
        sl_atr_mult=settings.sl_atr_mult,
        tp_r_mult=settings.tp_r_mult,
        dry_run=settings.dry_run,
        magic=settings.magic_number,
        order_comment=settings.order_comment,
        filling_mode=settings.filling_mode,
    ))
    state = StateStore()

    for sym in settings.symbols:
        df = mt5c.get_rates(sym, settings.timeframe_str, count=800)
        if df.empty:
            logger.warning(f"{sym} хосын түүх хоосон байна")
            continue

        # 1) Давхардахаас сэргийлсэн timestamp (timezone-aware UTC)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]   # ж: 20250901_012245_137

        # 2) Файлын нэр
        out_png_rel = f"charts/{sym}_{settings.timeframe_str}_{ts}.png"

        # 3) Рендер (overlays одоохондоо mock байж болно)
        from services.chart_renderer import render_chart_with_overlays
        overlays = {"trendlines": [], "zones": [], "fibonacci": []}
        out_png = render_chart_with_overlays(df.tail(200), overlays, out_png_rel, f"{sym} {settings.timeframe_str}")
        logger.info(f"Chart saved: {out_png}")

        # Legacy signal generation for comparison
        sig = ma_crossover_signal(df)   # BUY / SELL / HOLD
        last_close = df["close"].iloc[-1]
        a = atr(df, period=settings.atr_period)

        base_msg = f"[{sym}] close={last_close:.2f} | atr={a:.5f} | signal={sig['signal']} | {sig['reason']}"
        logger.info(base_msg)

        # --- Safety gate: filter decision, compute ma/rsi and position sizing ---
        # ensure MA values for guard
        df["MA20"] = df["close"].rolling(window=20).mean()
        df["MA50"] = df["close"].rolling(window=50).mean()
        ma20 = float(df["MA20"].iloc[-1]) if not df["MA20"].isna().all() else float("nan")
        ma50 = float(df["MA50"].iloc[-1]) if not df["MA50"].isna().all() else float("nan")
        rsi14 = rsi(df["close"], period=14)
        raw_signal = sig["signal"]

        snap = mt5c.account_snapshot()
        account_balance = float(snap.get("balance", 0.0)) if isinstance(snap, dict) else 0.0

        guard = Guard(
            symbol=sym,
            timeframe_min=30,       # M30
            session="LDN_NY",
            cooldown_mult=2.0,
            min_atr=2.0,
            risk_pct=0.01,
            sl_mult=1.5,
            tp_mult=3.0,
            enable_news=True,
            news_window_min=60,
        )

        decision = guard.filter_decision(
            raw_signal=raw_signal,
            close=last_close,
            ma_fast=ma20,
            ma_slow=ma50,
            rsi=rsi14,
            atr=a,
            balance_usd=account_balance,
            now_utc=datetime.now(timezone.utc),
        )

        logger.info(
            f"[{sym}] decision={decision.action} | lot={decision.lot} | SL={decision.sl_points:.2f} | TP={decision.tp_points:.2f} | reason={decision.reason}"
        )

        if decision.action in ("BUY", "SELL"):
            # Safety gate-approved: execute order via executor
            res = ex.place(symbol=sym, side=decision.action, price_hint=last_close, atr_value=a)
            if res.get("ok"):
                guard.mark_trade(decision.action)
                logger.info("Trade placed and cooldown marked by safety gate.")
                if tg:
                    t = "DRY" if res.get("dry") else f"TICKET {res.get('ticket')}"
                    tg.send(f"{base_msg}\n→ {t} | lot={res.get('lot')} | SL={res.get('sl')} | TP={res.get('tp')}")
            else:
                logger.error(f"Ордер биелүүлж чадсангүй (safety gate): {res}")
        else:
            logger.info("No trade after safety gate.")

        # Legacy automatic placement disabled to avoid duplicate orders.
        # If you want to re-enable legacy logic, uncomment and adapt the block below.
        # if sig["signal"] in ("BUY", "SELL"):
        #     if not state.cooldown_elapsed(sym, settings.cooldown_minutes):
        #         logger.info(f"{sym} хос дээр хүлээх хугацаа (cooldown) үргэлжилж байна.")
        #         continue
        #     res = ex.place(symbol=sym, side=sig["signal"], price_hint=last_close, atr_value=a)
        #     if res.get("ok"):
        #         state.set_now(sym)
        #         if tg:
        #             t = "DRY" if res.get("dry") else f"TICKET {res.get('ticket')}"
        #             tg.send(f"{base_msg}\n→ {t} | lot={res.get('lot')} | SL={res.get('sl')} | TP={res.get('tp')}")
        #     else:
        #         logger.error(f"Ордер биелүүлж чадсангүй: {res}")

    mt5c.shutdown()

if __name__ == "__main__":
    run_once()
