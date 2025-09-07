import MetaTrader5 as mt5
mt5.initialize()
info = mt5.symbol_info("XAUUSD")
tick = mt5.symbol_info_tick("XAUUSD")

print("Market state:", "trade_mode=", info.trade_mode, "(4=full)", "select=", info.select)
print("Specs:", "digits=", info.digits, "point=", info.point, "stops_level=", info.trade_stops_level,
      "vol_min=", info.volume_min, "vol_step=", info.volume_step)
print("Price:", "bid=", tick.bid, "ask=", tick.ask, "last=", info.last)
mt5.shutdown()
