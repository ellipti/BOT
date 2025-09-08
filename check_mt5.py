try:
    import MetaTrader5 as mt5
    print('MT5 module available')
    print(f'MT5 version: {mt5.__version__ if hasattr(mt5, "__version__") else "unknown"}')
except ImportError as e:
    print(f'MT5 not available: {e}')
