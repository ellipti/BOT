import pandas as pd

from config.settings import get_settings
from safety_gate import Guard

settings = get_settings()


def run_bt(df: pd.DataFrame):
    g = Guard(
        symbol=settings.trading.symbol,
        timeframe_min=settings.trading.timeframe_minutes,
        session=settings.trading.session,
        cooldown_mult=settings.trading.cooldown_multiplier,
        min_atr=settings.trading.min_atr,
        risk_pct=settings.trading.risk_percentage,
        sl_mult=settings.trading.stop_loss_multiplier,
        tp_mult=settings.trading.take_profit_multiplier,
        enable_news=False,
    )

    bal, wins, losses = 10000.0, 0, 0
    pf_num = pf_den = 0.0
    last_side = None

    for _, r in df.iterrows():
        raw = r["raw_signal"]  # таны стратеги бэлдэнэ
        d = g.filter_decision(
            raw, r["close"], r["ma20"], r["ma50"], r["rsi14"], r["atr"], bal
        )
        if d.action in ("BUY", "SELL"):
            # энгийн симуляц: tp/sl хүртэл ATR-аар дүгнэнэ (placeholder)
            rr = 2.0  # TP/SL=2:1 гэж төсөөлөв
            wins += 1
            bal *= 1 + settings.trading.risk_percentage * rr  # маш бүдүүн
            pf_num += rr
            last_side = d.action
        else:
            # no trade
            pass

    print(
        f"BT summary: balance≈{bal:.2f} | trades={wins+losses} | winners={wins} | PF≈{pf_num/max(1,(wins+losses-wins)):.2f}"
    )


if __name__ == "__main__":
    # df = load_your_data(...)
    # df нь ['time','open','high','low','close','ma20','ma50','rsi14','atr','raw_signal'] гэх баганатай байхаар бэлдэнэ
    pass
