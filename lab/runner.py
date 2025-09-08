"""
Strategy Lab - Parameter Grid Backtesting Runner

Loads parameter combinations from YAML, runs backtests in parallel,
and generates comprehensive results with CSV output and Markdown reports.
"""

import argparse
import logging
import time
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from itertools import product

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from feeds.factory import create_feed 
from safety_gate import Guard


logger = logging.getLogger(__name__)


@dataclass
class BacktestParams:
    """Single backtest parameter combination"""
    symbol: str
    timeframe: int
    atr_period: int
    risk_pct: float
    sl_mult: float
    tp_mult: float
    
    def __str__(self) -> str:
        return f"{self.symbol}_{self.timeframe}m_atr{self.atr_period}_r{self.risk_pct:.1%}_sl{self.sl_mult}_tp{self.tp_mult}"


@dataclass  
class BacktestResult:
    """Backtest execution result"""
    params: BacktestParams
    success: bool
    error: str | None = None
    
    # Performance metrics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # P&L metrics
    final_balance: float = 0.0
    total_pnl: float = 0.0
    profit_factor: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    
    # Quality metrics
    sharpe_proxy: float = 0.0
    avg_trade_pnl: float = 0.0
    
    # Execution info
    duration_ms: int = 0
    bars_processed: int = 0


class StrategyLabRunner:
    """Main strategy lab backtesting engine"""
    
    def __init__(self, config_path: str = "lab/params.yaml"):
        """Initialize lab runner with configuration"""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.settings = get_settings()
        
        # Ensure output directories exist
        self.output_dir = Path(self.config["output"]["results_file"]).parent
        self.charts_dir = Path(self.config["output"]["charts_dir"])
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self) -> dict[str, Any]:
        """Load parameter grid configuration from YAML"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            logger.info(f"Loaded config from {self.config_path}")
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load config from {self.config_path}: {e}")
    
    def generate_parameter_grid(self) -> list[BacktestParams]:
        """Generate all parameter combinations from config"""
        symbols = self.config["symbols"]
        timeframes = self.config["timeframes"]
        atr_periods = self.config["atr_period"]
        
        # Handle range parameters
        risk_pcts = self._generate_range(self.config["risk_pct"])
        sl_mults = self._generate_range(self.config["sl_mult"])  
        tp_mults = self._generate_range(self.config["tp_mult"])
        
        # Generate all combinations
        combinations = list(product(
            symbols, timeframes, atr_periods, 
            risk_pcts, sl_mults, tp_mults
        ))
        
        # Convert to BacktestParams objects
        params_list = []
        for combo in combinations:
            params = BacktestParams(
                symbol=combo[0],
                timeframe=combo[1], 
                atr_period=combo[2],
                risk_pct=combo[3],
                sl_mult=combo[4],
                tp_mult=combo[5]
            )
            params_list.append(params)
            
        logger.info(f"Generated {len(params_list)} parameter combinations")
        return params_list
    
    def _generate_range(self, range_config: dict | list) -> list[float]:
        """Generate numeric range from config (handles both list and range format)"""
        if isinstance(range_config, list):
            return range_config
            
        # Range format: {start: 0.01, end: 0.05, step: 0.01}
        start = range_config["start"]
        end = range_config["end"] 
        step = range_config["step"]
        
        values = []
        current = start
        while current <= end + (step / 2):  # Add small epsilon for floating point
            values.append(round(current, 6))  # Round to avoid floating point issues
            current += step
            
        return values
    
    def run_grid_search(self, max_workers: int = 4) -> list[BacktestResult]:
        """Execute parameter grid search with parallel processing"""
        params_list = self.generate_parameter_grid()
        
        logger.info(f"Starting grid search with {len(params_list)} combinations using {max_workers} workers")
        
        results = []
        total_start = time.time()
        
        # Process in parallel
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all jobs
            future_to_params = {
                executor.submit(run_single_backtest, params, self.config): params 
                for params in params_list
            }
            
            # Collect results as they complete
            for i, future in enumerate(as_completed(future_to_params), 1):
                params = future_to_params[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    if result.success:
                        logger.info(f"[{i}/{len(params_list)}] OK {params} -> WR: {result.win_rate:.1%}, PF: {result.profit_factor:.2f}")
                    else:
                        logger.warning(f"[{i}/{len(params_list)}] FAIL {params} -> Error: {result.error}")
                        
                except Exception as e:
                    logger.error(f"[{i}/{len(params_list)}] ERROR {params} -> Exception: {e}")
                    results.append(BacktestResult(params=params, success=False, error=str(e)))
        
        total_time = time.time() - total_start
        successful = sum(1 for r in results if r.success)
        
        logger.info(f"Grid search completed in {total_time:.1f}s: {successful}/{len(results)} successful")
        
        return results
    
    def save_results_csv(self, results: list[BacktestResult]) -> None:
        """Save results to CSV file"""
        csv_path = Path(self.config["output"]["results_file"])
        
        # Convert results to DataFrame
        data = []
        for result in results:
            row = {
                # Parameters
                "symbol": result.params.symbol,
                "timeframe": result.params.timeframe,
                "atr_period": result.params.atr_period,
                "risk_pct": result.params.risk_pct,
                "sl_mult": result.params.sl_mult,
                "tp_mult": result.params.tp_mult,
                
                # Results
                "success": result.success,
                "error": result.error or "",
                
                # Performance
                "total_trades": result.total_trades,
                "winning_trades": result.winning_trades,
                "losing_trades": result.losing_trades,
                "win_rate": result.win_rate,
                
                # P&L
                "final_balance": result.final_balance,
                "total_pnl": result.total_pnl,
                "profit_factor": result.profit_factor,
                
                # Risk
                "max_drawdown": result.max_drawdown,
                "max_drawdown_pct": result.max_drawdown_pct,
                
                # Quality
                "sharpe_proxy": result.sharpe_proxy,
                "avg_trade_pnl": result.avg_trade_pnl,
                
                # Execution
                "duration_ms": result.duration_ms,
                "bars_processed": result.bars_processed
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        df.to_csv(csv_path, index=False)
        
        logger.info(f"Results saved to {csv_path} ({len(df)} rows)")
        
    def generate_summary_report(self, results: list[BacktestResult]) -> None:
        """Generate Markdown summary report"""
        md_path = Path(self.config["output"]["summary_file"])
        top_n = self.config["output"]["top_n_results"]
        
        # Filter successful results and sort by profit factor
        successful_results = [r for r in results if r.success and r.total_trades > 0]
        top_results = sorted(successful_results, key=lambda r: r.profit_factor, reverse=True)[:top_n]
        
        # Generate markdown content
        md_content = f"""# Strategy Lab Backtest Results

## Summary

- **Total Combinations**: {len(results)}
- **Successful Tests**: {len(successful_results)}
- **Failed Tests**: {len(results) - len(successful_results)}
- **Success Rate**: {len(successful_results)/len(results)*100:.1f}%

## Top {top_n} Performing Strategies

| Rank | Symbol | TF | ATR | Risk% | SL | TP | Trades | Win Rate | Profit Factor | Max DD% | Total P&L |
|------|--------|----|-----|-------|----|----|--------|----------|---------------|---------|-----------|
"""
        
        for i, result in enumerate(top_results, 1):
            md_content += f"| {i} | {result.params.symbol} | {result.params.timeframe}m | {result.params.atr_period} | {result.params.risk_pct:.1%} | {result.params.sl_mult} | {result.params.tp_mult} | {result.total_trades} | {result.win_rate:.1%} | {result.profit_factor:.2f} | {result.max_drawdown_pct:.1%} | ${result.total_pnl:.2f} |\n"
        
        if top_results:
            best = top_results[0]
            md_content += f"""

## Best Strategy Details

**Parameters:**
- Symbol: {best.params.symbol}
- Timeframe: {best.params.timeframe} minutes
- ATR Period: {best.params.atr_period}
- Risk Per Trade: {best.params.risk_pct:.1%}
- Stop Loss: {best.params.sl_mult}x ATR
- Take Profit: {best.params.tp_mult}x ATR

**Performance:**
- Total Trades: {best.total_trades}
- Win Rate: {best.win_rate:.1%}
- Profit Factor: {best.profit_factor:.2f}
- Final Balance: ${best.final_balance:,.2f}
- Total P&L: ${best.total_pnl:,.2f}
- Max Drawdown: {best.max_drawdown_pct:.1%}
- Sharpe Proxy: {best.sharpe_proxy:.2f}
- Avg Trade P&L: ${best.avg_trade_pnl:.2f}

"""
        
        # Add parameter analysis
        if successful_results:
            md_content += """## Parameter Analysis

### Win Rate by Symbol
"""
            # Group by symbol and calculate average win rates
            symbol_stats = {}
            for result in successful_results:
                symbol = result.params.symbol
                if symbol not in symbol_stats:
                    symbol_stats[symbol] = []
                symbol_stats[symbol].append(result.win_rate)
                    
            for symbol, win_rates in symbol_stats.items():
                avg_wr = sum(win_rates) / len(win_rates)
                md_content += f"- **{symbol}**: {avg_wr:.1%} (n={len(win_rates)})\n"
                
        md_content += f"""
## Configuration Used

```yaml
{yaml.dump(self.config, default_flow_style=False)}
```

---
*Generated by Strategy Lab at {time.strftime('%Y-%m-%d %H:%M:%S')}*
"""
        
        # Save markdown report
        with open(md_path, 'w') as f:
            f.write(md_content)
            
        logger.info(f"Summary report saved to {md_path}")


def run_single_backtest(params: BacktestParams, config: dict[str, Any]) -> BacktestResult:
    """
    Execute single backtest for given parameters (runs in separate process)
    
    This function needs to be at module level for multiprocessing to work
    """
    start_time = time.time()
    
    try:
        # Initialize settings with custom parameters
        settings = get_settings()
        
        # Override trading settings with test parameters
        settings.trading.symbol = params.symbol
        settings.trading.timeframe_minutes = params.timeframe
        settings.trading.atr_period = params.atr_period
        settings.trading.risk_percentage = params.risk_pct
        settings.trading.stop_loss_multiplier = params.sl_mult
        settings.trading.take_profit_multiplier = params.tp_mult
        
        # Create backtest feed
        settings.feed.feed_kind = "backtest"  # Set to backtest mode
        settings.feed.backtest_data_dir = config["data"]["data_dir"]  # Set data directory
        
        feed = create_feed(settings)
        
        # Get historical data
        timeframe_str = f"M{params.timeframe}"  # Convert minutes to MT5 format
        min_bars = config["data"]["min_bars"]
        candles = feed.get_ohlcv(params.symbol, timeframe_str, min_bars)
        
        if len(candles) < min_bars:
            return BacktestResult(
                params=params,
                success=False,
                error=f"Insufficient data: got {len(candles)}, need {min_bars}"
            )
        
        # Convert candles to DataFrame for processing
        df_data = []
        for candle in candles:
            df_data.append({
                'ts': candle.ts,
                'open': candle.open,
                'high': candle.high, 
                'low': candle.low,
                'close': candle.close,
                'volume': candle.volume
            })
        
        df = pd.DataFrame(df_data)
        
        # Add technical indicators
        df = add_technical_indicators(df, params.atr_period)
        
        # Initialize safety gate/strategy
        guard = Guard(
            symbol=params.symbol,
            timeframe_min=params.timeframe,
            session=settings.trading.session,
            cooldown_mult=settings.trading.cooldown_multiplier,
            min_atr=settings.trading.min_atr,
            risk_pct=params.risk_pct,
            sl_mult=params.sl_mult,
            tp_mult=params.tp_mult,
            enable_news=False
        )
        
        # Run backtest simulation
        result = simulate_backtest(df, guard, config["backtest"])
        
        # Calculate execution time
        duration_ms = int((time.time() - start_time) * 1000)
        result.duration_ms = duration_ms
        result.bars_processed = len(df)
        result.params = params  # Set the parameters reference
        
        return result
        
    except Exception as e:
        return BacktestResult(
            params=params,
            success=False,
            error=str(e),
            duration_ms=int((time.time() - start_time) * 1000)
        )


def add_technical_indicators(df: pd.DataFrame, atr_period: int) -> pd.DataFrame:
    """Add technical indicators required for strategy"""
    df = df.copy()
    
    # Simple moving averages
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma50'] = df['close'].rolling(window=50).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi14'] = 100 - (100 / (1 + rs))
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close = (df['low'] - df['close'].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = true_range.rolling(window=atr_period).mean()
    
    # Simple trend signal (placeholder - replace with your strategy)
    df['raw_signal'] = "NONE"
    
    # Simple golden cross strategy as example
    df.loc[(df['ma20'] > df['ma50']) & (df['ma20'].shift() <= df['ma50'].shift()), 'raw_signal'] = "BUY"
    df.loc[(df['ma20'] < df['ma50']) & (df['ma20'].shift() >= df['ma50'].shift()), 'raw_signal'] = "SELL"
    
    return df


def simulate_backtest(df: pd.DataFrame, guard: Guard, config: dict) -> BacktestResult:
    """Simulate backtest execution and calculate performance metrics"""
    initial_balance = config["initial_balance"]
    balance = initial_balance
    trades = []
    equity_curve = [balance]
    
    position = None  # Current position: {'side': 'BUY'/'SELL', 'entry_price': float, 'sl': float, 'tp': float, 'risk_amount': float}
    
    for i, row in df.iterrows():
        # Skip if not enough data for indicators
        if pd.isna(row['ma20']) or pd.isna(row['ma50']) or pd.isna(row['atr']):
            equity_curve.append(balance)
            continue
            
        current_price = row['close']
        
        # Check for position exit first
        if position is not None:
            exit_reason = None
            exit_price = current_price
            
            # Check stop loss
            if (position['side'] == 'BUY' and current_price <= position['sl']) or \
               (position['side'] == 'SELL' and current_price >= position['sl']):
                exit_reason = 'SL'
                exit_price = position['sl']
            
            # Check take profit  
            elif (position['side'] == 'BUY' and current_price >= position['tp']) or \
                 (position['side'] == 'SELL' and current_price <= position['tp']):
                exit_reason = 'TP'
                exit_price = position['tp']
            
            # Close position if exit triggered
            if exit_reason:
                if position['side'] == 'BUY':
                    pnl = (exit_price - position['entry_price']) * (position['risk_amount'] / position['entry_price'])
                else:  # SELL
                    pnl = (position['entry_price'] - exit_price) * (position['risk_amount'] / position['entry_price'])
                
                balance += pnl
                
                trades.append({
                    'entry_price': position['entry_price'],
                    'exit_price': exit_price,
                    'side': position['side'],
                    'pnl': pnl,
                    'exit_reason': exit_reason
                })
                
                position = None
        
        # Check for new entry if no position
        if position is None:
            raw_signal = row['raw_signal']
            decision = guard.filter_decision(
                raw_signal, current_price, row['ma20'], row['ma50'], row['rsi14'], row['atr'], balance
            )
            
            if decision.action in ('BUY', 'SELL'):
                atr = row['atr']
                risk_amount = balance * guard.risk_pct
                
                # Calculate stop loss and take profit
                if decision.action == 'BUY':
                    sl_price = current_price - (atr * guard.sl_mult)
                    tp_price = current_price + (atr * guard.tp_mult)
                else:  # SELL
                    sl_price = current_price + (atr * guard.sl_mult)  
                    tp_price = current_price - (atr * guard.tp_mult)
                
                position = {
                    'side': decision.action,
                    'entry_price': current_price,
                    'sl': sl_price,
                    'tp': tp_price,
                    'risk_amount': risk_amount
                }
        
        equity_curve.append(balance)
    
    # Force close any remaining position
    if position is not None:
        current_price = df['close'].iloc[-1]
        if position['side'] == 'BUY':
            pnl = (current_price - position['entry_price']) * (position['risk_amount'] / position['entry_price'])
        else:
            pnl = (position['entry_price'] - current_price) * (position['risk_amount'] / position['entry_price'])
            
        balance += pnl
        trades.append({
            'entry_price': position['entry_price'],
            'exit_price': current_price,
            'side': position['side'],
            'pnl': pnl,
            'exit_reason': 'EOD'
        })
    
    # Calculate performance metrics
    return calculate_performance_metrics(trades, initial_balance, balance, equity_curve)


def calculate_performance_metrics(trades: list, initial_balance: float, final_balance: float, equity_curve: list) -> BacktestResult:
    """Calculate comprehensive performance metrics from trade history"""
    if not trades:
        return BacktestResult(
            params=None,  # Will be set by caller
            success=True,
            total_trades=0,
            final_balance=final_balance
        )
    
    # Basic trade statistics
    total_trades = len(trades)
    winning_trades = sum(1 for t in trades if t['pnl'] > 0)
    losing_trades = total_trades - winning_trades
    win_rate = winning_trades / total_trades if total_trades > 0 else 0
    
    # P&L metrics
    total_pnl = final_balance - initial_balance
    gross_profit = sum(t['pnl'] for t in trades if t['pnl'] > 0)
    gross_loss = abs(sum(t['pnl'] for t in trades if t['pnl'] < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0
    avg_trade_pnl = total_pnl / total_trades if total_trades > 0 else 0
    
    # Drawdown calculation
    peak = initial_balance
    max_drawdown = 0
    
    for balance in equity_curve:
        if balance > peak:
            peak = balance
        drawdown = peak - balance
        if drawdown > max_drawdown:
            max_drawdown = drawdown
    
    max_drawdown_pct = (max_drawdown / peak) if peak > 0 else 0
    
    # Sharpe proxy (simplified)
    if len(equity_curve) > 1:
        returns = pd.Series(equity_curve).pct_change().dropna()
        sharpe_proxy = returns.mean() / returns.std() if returns.std() > 0 else 0
        sharpe_proxy = sharpe_proxy * (252**0.5)  # Annualized approximation
    else:
        sharpe_proxy = 0
    
    return BacktestResult(
        params=None,  # Will be set by caller
        success=True,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        final_balance=final_balance,
        total_pnl=total_pnl,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_proxy=sharpe_proxy,
        avg_trade_pnl=avg_trade_pnl
    )


def main():
    """Main entry point for command line usage"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('lab/out/run.log')
        ]
    )
    
    # Command line interface
    parser = argparse.ArgumentParser(description="Strategy Lab Parameter Grid Backtesting")
    parser.add_argument("--config", default="lab/params.yaml", help="Configuration file path")  
    parser.add_argument("--max-jobs", type=int, default=4, help="Maximum parallel jobs")
    parser.add_argument("--output-csv", help="Output CSV file (overrides config)")
    parser.add_argument("--output-md", help="Output Markdown file (overrides config)")
    
    args = parser.parse_args()
    
    try:
        # Initialize runner
        runner = StrategyLabRunner(args.config)
        
        # Override output paths if specified
        if args.output_csv:
            runner.config["output"]["results_file"] = args.output_csv
        if args.output_md:
            runner.config["output"]["summary_file"] = args.output_md
        
        logger.info("Starting Strategy Lab backtest grid...")
        
        # Run grid search
        results = runner.run_grid_search(max_workers=args.max_jobs)
        
        # Save results
        runner.save_results_csv(results)
        runner.generate_summary_report(results)
        
        # Summary stats
        successful = sum(1 for r in results if r.success)
        logger.info(f"Completed: {successful}/{len(results)} successful backtests")
        
    except Exception as e:
        logger.error(f"Strategy Lab failed: {e}")
        raise


if __name__ == "__main__":
    main()