import pandas as pd
from safety_gate import Guard
from settings import settings

def run_bt(df: pd.DataFrame):
    g = Guard(symbol=settings.SYMBOL, timeframe_min=settings.TF_MIN,
             session=settings.SESSION, cooldown_mult=settings.COOLDOWN_MULT,
             min_atr=settings.MIN_ATR, risk_pct=settings.RISK_PCT,
             sl_mult=settings.SL_MULT, tp_mult=settings.TP_MULT,
             enable_news=False)
    
    bal, wins, losses = 10000.0, 0, 0
    pf_num = pf_den = 0.0
    last_side = None
    
    for _, r in df.iterrows():
        raw = r["raw_signal"]  # таны стратеги бэлдэнэ
        d = g.filter_decision(raw, r["close"], r["ma20"], r["ma50"], r["rsi14"], r["atr"], bal)
        if d.action in ("BUY","SELL"):
            # энгийн симуляц: tp/sl хүртэл ATR-аар дүгнэнэ (placeholder)
            rr = 2.0  # TP/SL=2:1 гэж төсөөлөв
            wins += 1
            bal *= 1 + settings.RISK_PCT*rr  # маш бүдүүн
            pf_num += rr
            last_side = d.action
        else:
            # no trade
            pass
    
    print(f"BT summary: balance≈{bal:.2f} | trades={wins+losses} | winners={wins} | PF≈{pf_num/max(1,(wins+losses-wins)):.2f}")

if __name__ == "__main__":
    # df = load_your_data(...)  
    # df нь ['time','open','high','low','close','ma20','ma50','rsi14','atr','raw_signal'] гэх баганатай байхаар бэлдэнэ
    pass
