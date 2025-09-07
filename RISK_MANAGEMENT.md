# ATR-Based Risk Management System

## Overview

The bot now includes a comprehensive quantitative risk management system with ATR-based position sizing and stop-loss/take-profit calculations. This system automatically calculates optimal position sizes based on account equity and risk percentage, while using Average True Range (ATR) to set dynamic stop-losses and take-profits.

## Key Features

### 1. Position Sizing (`core/sizing/sizing.py`)

#### `calc_lot_by_risk(symbol_info, entry, sl, equity, risk_pct)`

Calculates position size in lots based on risk management principles:

```
Formula: lots = (equity × risk_pct) / (ticks_to_sl × tick_value_per_tick)
```

**Parameters:**

- `symbol_info`: MT5 symbol info with trading constraints
- `entry`: Entry price
- `sl`: Stop loss price
- `equity`: Account equity
- `risk_pct`: Risk percentage (e.g., 0.01 for 1%)

**Returns:** Position size in lots, rounded to symbol constraints

### 2. ATR-Based SL/TP Calculation

#### `calc_sl_tp_by_atr(side, entry, atr, sl_mult, tp_mult)`

Calculates stop loss and take profit levels based on ATR:

**Logic:**

- BUY: SL = entry - (atr × sl_mult), TP = entry + (atr × tp_mult)
- SELL: SL = entry + (atr × sl_mult), TP = entry - (atr × tp_mult)

### 3. ATR Fetching

#### `fetch_atr(symbol, timeframe, period=14)`

Fetches Average True Range from MT5 historical data using pandas:

1. Downloads recent price bars
2. Calculates True Range components (HL, HCP, LCP)
3. Computes ATR using exponential moving average
4. Returns current ATR value

### 4. Utility Functions

#### `round_to_step(value, step, min_v, max_v)`

Rounds values to valid trading increments within symbol constraints.

#### `get_account_equity()`

Retrieves current account equity from MT5.

## Configuration

### New Settings (config/settings.py)

```python
class TradingSettings:
    # Risk Management
    risk_percentage: float = 0.01  # 1% of equity per trade
    stop_loss_multiplier: float = 1.5  # ATR multiplier for SL
    take_profit_multiplier: float = 3.0  # ATR multiplier for TP

    # ATR Configuration
    atr_period: int = 14  # ATR calculation period (bars)
    min_atr: float = 1.2  # Minimum ATR required for trading
```

### Environment Variables

- `TRADING_RISK_PERCENTAGE` or `TRADING_RISK_PCT`: Risk per trade (default: 0.01)
- `TRADING_ATR_PERIOD`: ATR calculation period (default: 14)
- `TRADING_SL_MULT`: Stop loss ATR multiplier (default: 1.5)
- `TRADING_TP_MULT`: Take profit ATR multiplier (default: 3.0)
- `TRADING_MIN_ATR`: Minimum ATR for trading (default: 1.2)

## Pipeline Integration

The trading pipeline (`app/pipeline.py`) now includes:

1. **Signal Validation**: Basic signal quality checks
2. **Risk Calculation**: ATR-based position sizing and SL/TP calculation
3. **Risk Approval**: Validates calculated parameters against risk limits
4. **Order Execution**: Executes orders with calculated lots, SL, and TP

### Event Flow

```
SignalDetected → Validated → RiskApproved → OrderPlaced → Execution
```

Each stage now includes:

- ATR fetching and validation
- Position size calculation based on equity and risk percentage
- Dynamic SL/TP levels based on market volatility (ATR)
- Symbol constraint validation (min/max lot sizes, step increments)

## Example Usage

### Manual Position Sizing

```python
from core.sizing.sizing import calc_lot_by_risk, calc_sl_tp_by_atr, fetch_atr

# Get ATR
atr = fetch_atr("XAUUSD", mt5.TIMEFRAME_M30, period=14)

# Calculate SL/TP
entry_price = 2500.00
sl, tp = calc_sl_tp_by_atr("BUY", entry_price, atr, sl_mult=1.5, tp_mult=3.0)

# Calculate position size
equity = 10000.00
risk_pct = 0.01  # 1%
lots = calc_lot_by_risk(symbol_info, entry_price, sl, equity, risk_pct)

print(f"Entry: ${entry_price}, SL: ${sl:.2f}, TP: ${tp:.2f}")
print(f"Position Size: {lots:.3f} lots (Risk: ${equity*risk_pct:.2f})")
```

### Pipeline Integration

```python
from app.pipeline import get_pipeline

# Pipeline automatically handles ATR-based risk management
pipeline = get_pipeline()
await pipeline.start()

# Emit a signal - pipeline calculates everything automatically
signal = SignalEvent("XAUUSD", "BUY", 2500.00, confidence=0.85)
pipeline.emit_signal(signal)
```

## Risk Management Benefits

1. **Consistent Risk**: Each trade risks the same percentage of equity
2. **Dynamic Stops**: SL/TP levels adapt to market volatility via ATR
3. **Position Sizing**: Automatically calculates optimal lot sizes
4. **Symbol Compliance**: Respects broker's min/max lot sizes and step increments
5. **Equity Protection**: Prevents over-leveraging and excessive risk

## Testing

Run the integration test to validate all components:

```bash
python test_risk_integration.py
```

The test validates:

- Position sizing calculations
- ATR-based SL/TP calculations
- Settings integration
- Error handling
- Pipeline integration

## Dependencies

- **pandas**: For ATR calculations
- **MetaTrader5**: For market data and account information
- **pydantic**: For settings validation

## Mathematical Foundation

### Position Sizing Formula

```
lots = risk_amount / (stop_distance_ticks × tick_value_per_lot)

Where:
- risk_amount = equity × risk_percentage
- stop_distance_ticks = |entry - sl| / tick_size
- tick_value_per_lot = symbol's tick value (usually $1 per tick per lot)
```

### ATR Calculation

```
True Range = max(High - Low, |High - Prev_Close|, |Low - Prev_Close|)
ATR = EMA(True Range, period)
```

This system ensures consistent risk management while adapting to market conditions through ATR-based volatility measurements.
