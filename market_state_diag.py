import MetaTrader5 as mt5

mt5.initialize()
info = mt5.symbol_info("XAUUSD")
print(
    "Market info:",
    f"\ntrade_mode={info.trade_mode}",
    f"\nselect={info.select}",
    f"\ntrade_exemode={info.trade_exemode}",
    f"\ntrade_calc_mode={info.trade_calc_mode}",
    f"\nsession_deals={info.session_deals}",
    f"\nvisible={info.visible}",
)
mt5.shutdown()
