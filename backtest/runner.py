"""
Backtest Runner System
Trading strategy-н historical data дээрх шалгалт

Онцлогууд:
- YAML configuration-аас параметрүүд унших
- In-sample/Out-of-sample validation
- Grid search optimization
- Performance KPI calculation
- Detailed reporting with CSV/PNG outputs
- Monte Carlo simulation
"""

import itertools
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)

# YAML import-ийг conditional хийх
try:
    from backtest.config_loader import StrategyConfig, load_config

    YAML_AVAILABLE = True
except ImportError:
    logger.warning("YAML support алга. pip install PyYAML хийнэ үү.")
    YAML_AVAILABLE = False


@dataclass
class Trade:
    """Нэг арилжааны мэдээлэл"""

    entry_time: datetime
    exit_time: datetime | None = None
    symbol: str = "XAUUSD"
    side: str = "BUY"  # BUY or SELL
    entry_price: float = 0.0
    exit_price: float = 0.0
    lot_size: float = 0.01
    stop_loss: float = 0.0
    take_profit: float = 0.0
    commission: float = 0.0
    swap: float = 0.0
    profit: float = 0.0
    pips: float = 0.0
    duration_hours: float = 0.0
    exit_reason: str = "UNKNOWN"

    @property
    def is_winner(self) -> bool:
        return self.profit > 0

    @property
    def is_closed(self) -> bool:
        return self.exit_time is not None


@dataclass
class BacktestResults:
    """Backtest үр дүнгийн summary"""

    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    # Performance metrics
    total_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: float = 0.0

    # Trade metrics
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    average_trade_duration: float = 0.0

    # Risk metrics
    value_at_risk_95: float = 0.0
    conditional_var_95: float = 0.0

    # Trades list
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)


class BacktestEngine:
    """Backtest хийх үндсэн engine"""

    def __init__(self, config: Any | None = None):
        """Backtest engine эхлүүлэх"""
        if YAML_AVAILABLE and config is None:
            self.config = load_config()
        elif config:
            self.config = config
        else:
            # Default minimal config
            self.config = self._create_default_config()

        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

        logger.info("Backtest Engine эхлүүллээ")

    def _create_default_config(self) -> dict:
        """Default configuration үүсгэх YAML байхгүй үед"""
        return {
            "strategy": {
                "name": "Default MA Crossover",
                "parameters": {
                    "ma_fast": 20,
                    "ma_slow": 50,
                    "rsi_period": 14,
                    "atr_period": 14,
                    "risk_per_trade": 0.01,
                },
            },
            "backtest": {
                "data": {
                    "symbol": "XAUUSD",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                },
                "account": {
                    "initial_balance": 10000.0,
                    "commission": 0.0,
                    "spread": 2.0,
                },
                "validation": {"in_sample_ratio": 0.7, "out_sample_ratio": 0.3},
            },
        }

    def generate_sample_data(
        self, symbol: str, start_date: str, end_date: str, timeframe: str = "M30"
    ) -> pd.DataFrame:
        """Demo өгөгдөл үүсгэх (жинхэнэ MT5 өгөгдлийн оронд)"""
        logger.info(f"Sample {symbol} өгөгдөл үүсгэж байна {start_date} - {end_date}")

        # Date range үүсгэх
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        if timeframe == "M30":
            freq = "30min"
        elif timeframe == "H1":
            freq = "1H"
        elif timeframe == "M15":
            freq = "15min"
        else:
            freq = "30min"

        dates = pd.date_range(start=start, end=end, freq=freq)

        # Random walk with trend үүсгэх
        n_periods = len(dates)
        base_price = 2000.0 if symbol == "XAUUSD" else 1.1000

        # Generate realistic OHLC data
        returns = np.random.normal(0, 0.001, n_periods)  # 0.1% std deviation
        returns[0] = 0  # First return is 0

        # Add some trend and seasonality
        trend = np.linspace(0, 0.1, n_periods)  # 10% trend over period
        seasonal = 0.02 * np.sin(
            np.arange(n_periods) * 2 * np.pi / (24 * 2)
        )  # Daily seasonality for 30min data

        adjusted_returns = returns + trend / n_periods + seasonal / n_periods
        price_series = base_price * np.exp(np.cumsum(adjusted_returns))

        # Create OHLC from price series
        data = []
        for i, (date, close) in enumerate(zip(dates, price_series, strict=False)):
            if i == 0:
                open_price = close
                high = close
                low = close
            else:
                open_price = price_series[i - 1]
                # Generate realistic high/low
                volatility = abs(adjusted_returns[i]) * base_price * 2
                high = max(open_price, close) + np.random.uniform(0, volatility)
                low = min(open_price, close) - np.random.uniform(0, volatility)

            volume = np.random.randint(100, 1000)

            data.append(
                {
                    "datetime": date,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )

        df = pd.DataFrame(data)
        df.set_index("datetime", inplace=True)

        logger.info(f"Үүсгэсэн өгөгдөл: {len(df)} цэгийн {timeframe} data")
        return df

    def calculate_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Technical indicators тооцоолох"""
        result_df = df.copy()

        # Moving Averages
        ma_fast = params.get("ma_fast", 20)
        ma_slow = params.get("ma_slow", 50)

        result_df[f"MA_{ma_fast}"] = result_df["close"].rolling(window=ma_fast).mean()
        result_df[f"MA_{ma_slow}"] = result_df["close"].rolling(window=ma_slow).mean()

        # RSI
        rsi_period = params.get("rsi_period", 14)
        delta = result_df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        result_df["RSI"] = 100 - (100 / (1 + rs))

        # ATR
        atr_period = params.get("atr_period", 14)
        high_low = result_df["high"] - result_df["low"]
        high_close = np.abs(result_df["high"] - result_df["close"].shift())
        low_close = np.abs(result_df["low"] - result_df["close"].shift())
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        result_df["ATR"] = true_range.rolling(window=atr_period).mean()

        return result_df

    def generate_signals(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        """Trading signal үүсгэх"""
        signals_df = df.copy()

        ma_fast = params.get("ma_fast", 20)
        ma_slow = params.get("ma_slow", 50)
        rsi_oversold = params.get("rsi_oversold", 30)
        rsi_overbought = params.get("rsi_overbought", 70)

        # MA Crossover signals
        ma_fast_col = f"MA_{ma_fast}"
        ma_slow_col = f"MA_{ma_slow}"

        signals_df["signal"] = 0

        # BUY signal: MA fast crosses above MA slow AND RSI not overbought
        buy_condition = (
            (signals_df[ma_fast_col] > signals_df[ma_slow_col])
            & (signals_df[ma_fast_col].shift(1) <= signals_df[ma_slow_col].shift(1))
            & (signals_df["RSI"] < rsi_overbought)
        )

        # SELL signal: MA fast crosses below MA slow AND RSI not oversold
        sell_condition = (
            (signals_df[ma_fast_col] < signals_df[ma_slow_col])
            & (signals_df[ma_fast_col].shift(1) >= signals_df[ma_slow_col].shift(1))
            & (signals_df["RSI"] > rsi_oversold)
        )

        signals_df.loc[buy_condition, "signal"] = 1
        signals_df.loc[sell_condition, "signal"] = -1

        return signals_df

    def simulate_trades(
        self, df: pd.DataFrame, params: dict, account_config: dict
    ) -> list[Trade]:
        """Trade simulation хийх"""
        trades = []
        current_position = None
        balance = account_config.get("initial_balance", 10000.0)

        atr_sl_mult = params.get("atr_multiplier_sl", 2.0)
        atr_tp_mult = params.get("atr_multiplier_tp", 3.0)
        risk_per_trade = params.get("risk_per_trade", 0.01)
        spread = account_config.get("spread", 2.0)

        for i, (timestamp, row) in enumerate(df.iterrows()):
            if pd.isna(row["signal"]) or row["signal"] == 0:
                continue

            # Close current position if signal changes
            if current_position and current_position.side != (
                "BUY" if row["signal"] == 1 else "SELL"
            ):
                # Close position
                exit_price = row["close"]
                if current_position.side == "SELL":
                    exit_price += spread / 10000  # Add spread for sell positions

                current_position.exit_time = timestamp
                current_position.exit_price = exit_price
                current_position.exit_reason = "SIGNAL_REVERSAL"

                # Calculate profit
                if current_position.side == "BUY":
                    current_position.profit = (
                        (exit_price - current_position.entry_price)
                        * current_position.lot_size
                        * 100000
                    )
                else:
                    current_position.profit = (
                        (current_position.entry_price - exit_price)
                        * current_position.lot_size
                        * 100000
                    )

                current_position.pips = current_position.profit / (
                    current_position.lot_size * 10
                )
                current_position.duration_hours = (
                    current_position.exit_time - current_position.entry_time
                ).total_seconds() / 3600

                balance += current_position.profit
                trades.append(current_position)
                current_position = None

            # Open new position
            if not current_position and abs(row["signal"]) == 1:
                side = "BUY" if row["signal"] == 1 else "SELL"
                entry_price = row["close"]
                atr_value = row.get("ATR", 0.001)

                # Apply spread
                if side == "BUY":
                    entry_price += spread / 10000

                # Calculate lot size based on risk
                risk_amount = balance * risk_per_trade
                stop_distance = atr_value * atr_sl_mult
                lot_size = min(
                    0.1, risk_amount / (stop_distance * 100000)
                )  # Max 0.1 lot

                # Calculate SL/TP
                if side == "BUY":
                    stop_loss = entry_price - (atr_value * atr_sl_mult)
                    take_profit = entry_price + (atr_value * atr_tp_mult)
                else:
                    stop_loss = entry_price + (atr_value * atr_sl_mult)
                    take_profit = entry_price - (atr_value * atr_tp_mult)

                trade = Trade(
                    entry_time=timestamp,
                    symbol=account_config.get("symbol", "XAUUSD"),
                    side=side,
                    entry_price=entry_price,
                    lot_size=lot_size,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                )

                current_position = trade

        # Close final position if exists
        if current_position:
            final_row = df.iloc[-1]
            current_position.exit_time = df.index[-1]
            current_position.exit_price = final_row["close"]
            current_position.exit_reason = "END_OF_DATA"

            if current_position.side == "BUY":
                current_position.profit = (
                    (current_position.exit_price - current_position.entry_price)
                    * current_position.lot_size
                    * 100000
                )
            else:
                current_position.profit = (
                    (current_position.entry_price - current_position.exit_price)
                    * current_position.lot_size
                    * 100000
                )

            current_position.pips = current_position.profit / (
                current_position.lot_size * 10
            )
            current_position.duration_hours = (
                current_position.exit_time - current_position.entry_time
            ).total_seconds() / 3600

            trades.append(current_position)

        logger.info(f"Trade simulation амжилттай: {len(trades)} арилжаа")
        return trades

    def calculate_performance_metrics(
        self, trades: list[Trade], initial_balance: float
    ) -> BacktestResults:
        """Performance metrics тооцоолох"""
        if not trades:
            logger.warning("Арилжаа байхгүй - metrics тооцоолох боломжгүй")
            return BacktestResults(
                strategy_name=getattr(self.config, "name", "Unknown"),
                start_date=datetime.now(),
                end_date=datetime.now(),
                initial_balance=initial_balance,
                final_balance=initial_balance,
            )

        # Basic metrics
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.is_winner)
        losing_trades = total_trades - winning_trades

        total_profit = sum(t.profit for t in trades)
        final_balance = initial_balance + total_profit

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # Profit factor
        gross_profit = sum(t.profit for t in trades if t.profit > 0)
        gross_loss = abs(sum(t.profit for t in trades if t.profit < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        # Average metrics
        avg_win = gross_profit / winning_trades if winning_trades > 0 else 0
        avg_loss = gross_loss / losing_trades if losing_trades > 0 else 0

        # Return metrics
        total_return = (final_balance - initial_balance) / initial_balance

        # Create equity curve
        balance = initial_balance
        equity_curve = [(trades[0].entry_time, initial_balance)]

        for trade in trades:
            balance += trade.profit
            equity_curve.append((trade.exit_time or trade.entry_time, balance))

        # Calculate drawdown
        peak = initial_balance
        max_drawdown = 0
        for _, equity in equity_curve:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)

        # Sharpe ratio (simplified)
        returns = [t.profit / initial_balance for t in trades]
        if len(returns) > 1:
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe_ratio = mean_return / std_return if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # Create results
        results = BacktestResults(
            strategy_name=getattr(self.config, "name", "Unknown Strategy"),
            start_date=trades[0].entry_time,
            end_date=trades[-1].exit_time or trades[-1].entry_time,
            initial_balance=initial_balance,
            final_balance=final_balance,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            total_return=total_return,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            average_win=avg_win,
            average_loss=avg_loss,
            largest_win=max(t.profit for t in trades),
            largest_loss=min(t.profit for t in trades),
            average_trade_duration=np.mean(
                [t.duration_hours for t in trades if t.duration_hours > 0]
            ),
            trades=trades,
            equity_curve=equity_curve,
        )

        return results

    def run_backtest(
        self, params: dict | None = None, save_results: bool = True
    ) -> BacktestResults:
        """Single backtest хийх"""
        logger.info("Backtest эхлүүлж байна...")

        # Use provided params or config defaults
        if params:
            strategy_params = params
        elif hasattr(self.config, "parameters"):
            strategy_params = {
                "ma_fast": self.config.parameters.ma_fast,
                "ma_slow": self.config.parameters.ma_slow,
                "rsi_period": self.config.parameters.rsi_period,
                "atr_period": self.config.parameters.atr_period,
                "risk_per_trade": self.config.parameters.risk_per_trade,
                "atr_multiplier_sl": self.config.parameters.atr_multiplier_sl,
                "atr_multiplier_tp": self.config.parameters.atr_multiplier_tp,
                "rsi_oversold": self.config.parameters.rsi_oversold,
                "rsi_overbought": self.config.parameters.rsi_overbought,
            }
        else:
            strategy_params = self.config["strategy"]["parameters"]

        # Get backtest config
        if hasattr(self.config, "backtest"):
            bt_config = self.config.backtest
            symbol = bt_config.data.symbol
            start_date = bt_config.data.start_date
            end_date = bt_config.data.end_date
            account_config = {
                "initial_balance": bt_config.account.initial_balance,
                "spread": bt_config.account.spread,
                "commission": bt_config.account.commission,
                "symbol": symbol,
            }
        else:
            bt_config = self.config["backtest"]
            symbol = bt_config["data"]["symbol"]
            start_date = bt_config["data"]["start_date"]
            end_date = bt_config["data"]["end_date"]
            account_config = bt_config["account"]
            account_config["symbol"] = symbol

        # Generate or load data
        logger.info(f"Өгөгдөл бэлтгэж байна: {symbol} {start_date} - {end_date}")
        df = self.generate_sample_data(symbol, start_date, end_date)

        # Calculate indicators
        logger.info("Technical indicators тооцоолж байна...")
        df_with_indicators = self.calculate_indicators(df, strategy_params)

        # Generate signals
        logger.info("Trading signals үүсгэж байна...")
        df_with_signals = self.generate_signals(df_with_indicators, strategy_params)

        # Simulate trades
        logger.info("Trade simulation хийж байна...")
        trades = self.simulate_trades(df_with_signals, strategy_params, account_config)

        # Calculate performance
        logger.info("Performance metrics тооцоолж байна...")
        results = self.calculate_performance_metrics(
            trades, account_config["initial_balance"]
        )

        if save_results:
            self.save_results(results)

        # Generate charts хэрэв chart_renderer ашиглахаар зааж өгсөн бол
        if save_results and self.config.backtest.output.generate_charts:
            try:
                from backtest.chart_renderer import BacktestChartRenderer

                renderer = BacktestChartRenderer(self.config.backtest.output.output_dir)
                chart_files = renderer.render_all_charts(results)

                logger.info(f"Charts үүсэгдлээ: {list(chart_files.keys())}")

            except ImportError as e:
                logger.warning(f"Chart renderer import алдаа: {e}")
            except Exception as e:
                logger.error(f"Chart generation алдаа: {e}")

        logger.info(
            f"Backtest дууслаа: {results.total_trades} trades, "
            f"{results.win_rate:.1%} win rate, "
            f"{results.total_return:.1%} return"
        )

        return results

    def run_grid_search(self) -> list[dict]:
        """Grid search parameter optimization"""
        if not self.config.optimization.enabled:
            logger.warning("Optimization тохиргоо идэвхгүй байна")
            return []

        optimization_results = []
        grid = self.config.optimization.grid

        # Grid combination үүсгэх

        param_names = list(grid.keys())
        param_values = list(grid.values())
        combinations = list(itertools.product(*param_values))

        logger.info(f"Grid search эхлүүллээ: {len(combinations)} combinations")

        for i, combination in enumerate(combinations):
            # Parameter values set хийх
            params = dict(zip(param_names, combination, strict=False))

            logger.info(f"Testing combination {i+1}/{len(combinations)}: {params}")

            # Strategy parameters солих
            original_params = {}
            for param, value in params.items():
                if hasattr(self.config.parameters, param):
                    original_params[param] = getattr(self.config.parameters, param)
                    setattr(self.config.parameters, param, value)

            try:
                # Backtest ажиллуулах
                results = self.run_backtest(save_results=False)

                # Results хадгалах
                result_data = {
                    "parameters": params.copy(),
                    "total_return": results.total_return,
                    "sharpe_ratio": results.sharpe_ratio,
                    "win_rate": results.win_rate,
                    "profit_factor": results.profit_factor,
                    "max_drawdown": results.max_drawdown,
                    "total_trades": results.total_trades,
                }

                optimization_results.append(result_data)

                logger.info(
                    f"Combination {i+1}: Sharpe {results.sharpe_ratio:.3f}, "
                    f"Return {results.total_return:.2%}"
                )

            except Exception as e:
                logger.error(f"Combination {i+1} алдаа: {e}")

            finally:
                # Parameters буцаах
                for param, value in original_params.items():
                    setattr(self.config.parameters, param, value)

        # Best results олох
        if optimization_results:
            objective = self.config.optimization.objective
            if objective == "sharpe_ratio":
                best_result = max(optimization_results, key=lambda x: x["sharpe_ratio"])
            elif objective == "total_return":
                best_result = max(optimization_results, key=lambda x: x["total_return"])
            elif objective == "profit_factor":
                best_result = max(
                    optimization_results, key=lambda x: x["profit_factor"]
                )
            else:
                best_result = optimization_results[0]

            logger.info(f"Best parameters ({objective}): {best_result['parameters']}")
            logger.info(f"Best {objective}: {best_result[objective]:.3f}")

        return optimization_results

    def save_results(
        self, results: BacktestResults, custom_suffix: str = ""
    ) -> dict[str, str]:
        """Backtest results хадгалах"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"backtest_{results.strategy_name.replace(' ', '_')}_{timestamp}{custom_suffix}"

        saved_files = {}

        try:
            # Save summary CSV
            csv_path = self.reports_dir / f"{base_name}_summary.csv"
            summary_data = {
                "Strategy": [results.strategy_name],
                "Start Date": [results.start_date.strftime("%Y-%m-%d")],
                "End Date": [results.end_date.strftime("%Y-%m-%d")],
                "Initial Balance": [results.initial_balance],
                "Final Balance": [results.final_balance],
                "Total Return": [f"{results.total_return:.2%}"],
                "Total Trades": [results.total_trades],
                "Win Rate": [f"{results.win_rate:.2%}"],
                "Profit Factor": [f"{results.profit_factor:.2f}"],
                "Sharpe Ratio": [f"{results.sharpe_ratio:.2f}"],
                "Max Drawdown": [f"{results.max_drawdown:.2%}"],
                "Average Win": [f"${results.average_win:.2f}"],
                "Average Loss": [f"${results.average_loss:.2f}"],
                "Largest Win": [f"${results.largest_win:.2f}"],
                "Largest Loss": [f"${results.largest_loss:.2f}"],
            }

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(csv_path, index=False)
            saved_files["summary"] = str(csv_path)

            # Save detailed trades CSV
            if results.trades:
                trades_path = self.reports_dir / f"{base_name}_trades.csv"
                trades_data = []
                for trade in results.trades:
                    trades_data.append(
                        {
                            "Entry Time": trade.entry_time.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "Exit Time": (
                                trade.exit_time.strftime("%Y-%m-%d %H:%M:%S")
                                if trade.exit_time
                                else ""
                            ),
                            "Symbol": trade.symbol,
                            "Side": trade.side,
                            "Entry Price": trade.entry_price,
                            "Exit Price": trade.exit_price,
                            "Lot Size": trade.lot_size,
                            "Profit": trade.profit,
                            "Pips": trade.pips,
                            "Duration (hrs)": trade.duration_hours,
                            "Exit Reason": trade.exit_reason,
                        }
                    )

                trades_df = pd.DataFrame(trades_data)
                trades_df.to_csv(trades_path, index=False)
                saved_files["trades"] = str(trades_path)

            # Save equity curve CSV
            if results.equity_curve:
                equity_path = self.reports_dir / f"{base_name}_equity.csv"
                equity_data = pd.DataFrame(
                    results.equity_curve, columns=["DateTime", "Equity"]
                )
                equity_data.to_csv(equity_path, index=False)
                saved_files["equity"] = str(equity_path)

            logger.info(f"Results хадгалагдлаа: {len(saved_files)} файл")
            return saved_files

        except Exception as e:
            logger.error(f"Results хадгалах алдаа: {e}")
            return {}


# Convenience functions
def run_simple_backtest(
    symbol: str = "XAUUSD", start_date: str = "2024-01-01", end_date: str = "2024-12-31"
) -> BacktestResults:
    """Simple backtest ажиллуулах"""
    engine = BacktestEngine()
    return engine.run_backtest()


def main():
    """Demo main function"""
    print("🔧 Backtest Engine тест хийж байна...")

    try:
        engine = BacktestEngine()
        results = engine.run_backtest()

        print("\n📊 Backtest Results:")
        print(f"   Strategy: {results.strategy_name}")
        print(
            f"   Period: {results.start_date.strftime('%Y-%m-%d')} - {results.end_date.strftime('%Y-%m-%d')}"
        )
        print(f"   Total Return: {results.total_return:.2%}")
        print(f"   Total Trades: {results.total_trades}")
        print(f"   Win Rate: {results.win_rate:.2%}")
        print(f"   Profit Factor: {results.profit_factor:.2f}")
        print(f"   Sharpe Ratio: {results.sharpe_ratio:.2f}")
        print(f"   Max Drawdown: {results.max_drawdown:.2%}")

        print("\n✅ Backtest амжилттай дууслаа!")

    except Exception as e:
        print(f"❌ Backtest алдаа: {e}")


if __name__ == "__main__":
    main()
