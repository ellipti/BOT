"""
Strategy Lab Visualization Module

Creates equity curve charts and performance visualizations for backtest results
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from config.settings import get_settings
from feeds.factory import create_feed

from .runner import BacktestParams, BacktestResult

logger = logging.getLogger(__name__)

# Set style for better looking charts
plt.style.use("seaborn-v0_8-darkgrid")
sns.set_palette("husl")


class LabVisualizer:
    """Visualization engine for strategy lab results"""

    def __init__(self, output_dir: str = "lab/out/charts"):
        """Initialize visualizer with output directory"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_best_equity_curve(
        self, best_result: BacktestResult, config: dict[str, Any]
    ) -> str:
        """
        Plot equity curve for the best performing strategy

        Args:
            best_result: Best backtest result
            config: Lab configuration

        Returns:
            Path to saved chart file
        """
        if not best_result or not best_result.success:
            raise ValueError("No valid result provided for equity curve plotting")

        # Re-run the backtest to get detailed equity curve data
        equity_data = self._get_detailed_equity_curve(best_result.params, config)

        if not equity_data:
            raise ValueError("Could not generate equity curve data")

        # Create the plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), height_ratios=[3, 1])

        # Main equity curve
        dates = equity_data["dates"]
        equity = equity_data["equity_curve"]
        drawdown = equity_data["drawdown_curve"]

        ax1.plot(dates, equity, linewidth=2, label="Equity", color="#2E86C1")
        ax1.fill_between(dates, equity, alpha=0.3, color="#2E86C1")

        # Mark trade entry/exit points
        if "trades" in equity_data and equity_data["trades"]:
            trade_dates = [t["date"] for t in equity_data["trades"]]
            trade_equity = [t["equity_after"] for t in equity_data["trades"]]

            # Winning vs losing trades
            winning_dates = [t["date"] for t in equity_data["trades"] if t["pnl"] > 0]
            winning_equity = [
                t["equity_after"] for t in equity_data["trades"] if t["pnl"] > 0
            ]
            losing_dates = [t["date"] for t in equity_data["trades"] if t["pnl"] <= 0]
            losing_equity = [
                t["equity_after"] for t in equity_data["trades"] if t["pnl"] <= 0
            ]

            ax1.scatter(
                winning_dates,
                winning_equity,
                color="green",
                marker="^",
                s=50,
                label="Winning Trades",
                alpha=0.7,
            )
            ax1.scatter(
                losing_dates,
                losing_equity,
                color="red",
                marker="v",
                s=50,
                label="Losing Trades",
                alpha=0.7,
            )

        ax1.set_title(
            f"Equity Curve - {best_result.params}", fontsize=14, fontweight="bold"
        )
        ax1.set_ylabel("Account Balance ($)", fontsize=12)
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=1))

        # Drawdown chart
        ax2.fill_between(dates, drawdown, 0, color="red", alpha=0.5, label="Drawdown")
        ax2.plot(dates, drawdown, color="darkred", linewidth=1)
        ax2.set_ylabel("Drawdown (%)", fontsize=12)
        ax2.set_xlabel("Date", fontsize=12)
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Format x-axis for drawdown chart
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))

        # Add performance stats text box
        stats_text = f"""Performance Summary:
Total Trades: {best_result.total_trades}
Win Rate: {best_result.win_rate:.1%}
Profit Factor: {best_result.profit_factor:.2f}
Max Drawdown: {best_result.max_drawdown_pct:.1%}
Final Balance: ${best_result.final_balance:,.2f}
Total P&L: ${best_result.total_pnl:,.2f}"""

        ax1.text(
            0.02,
            0.98,
            stats_text,
            transform=ax1.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
            fontsize=10,
            fontfamily="monospace",
        )

        plt.tight_layout()

        # Save the chart
        chart_filename = f"best_equity_curve_{best_result.params.symbol}_{best_result.params.timeframe}m.png"
        chart_path = self.output_dir / chart_filename

        plt.savefig(chart_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Equity curve chart saved to {chart_path}")
        return str(chart_path)

    def plot_parameter_heatmaps(self, results: list[BacktestResult]) -> list[str]:
        """
        Create heatmaps showing parameter performance relationships

        Args:
            results: List of backtest results

        Returns:
            List of paths to saved heatmap files
        """
        successful_results = [r for r in results if r.success and r.total_trades > 0]

        if len(successful_results) < 10:
            logger.warning("Not enough successful results for meaningful heatmaps")
            return []

        # Convert results to DataFrame
        df_data = []
        for result in successful_results:
            df_data.append(
                {
                    "symbol": result.params.symbol,
                    "timeframe": result.params.timeframe,
                    "atr_period": result.params.atr_period,
                    "risk_pct": result.params.risk_pct,
                    "sl_mult": result.params.sl_mult,
                    "tp_mult": result.params.tp_mult,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                    "sharpe_proxy": result.sharpe_proxy,
                    "total_pnl": result.total_pnl,
                }
            )

        df = pd.DataFrame(df_data)
        chart_paths = []

        # 1. Risk % vs SL Multiplier heatmap (Profit Factor)
        if len(df["risk_pct"].unique()) > 1 and len(df["sl_mult"].unique()) > 1:
            fig, ax = plt.subplots(figsize=(10, 8))

            pivot_data = (
                df.groupby(["risk_pct", "sl_mult"])["profit_factor"].mean().unstack()
            )
            sns.heatmap(
                pivot_data,
                annot=True,
                fmt=".2f",
                cmap="RdYlGn",
                ax=ax,
                cbar_kws={"label": "Profit Factor"},
            )

            ax.set_title(
                "Profit Factor by Risk % and Stop Loss Multiplier",
                fontsize=14,
                fontweight="bold",
            )
            ax.set_xlabel("Stop Loss Multiplier (ATR)", fontsize=12)
            ax.set_ylabel("Risk Per Trade (%)", fontsize=12)

            chart_path = self.output_dir / "heatmap_risk_sl_pf.png"
            plt.savefig(chart_path, dpi=300, bbox_inches="tight")
            plt.close()
            chart_paths.append(str(chart_path))

        # 2. SL vs TP Multiplier heatmap (Win Rate)
        if len(df["sl_mult"].unique()) > 1 and len(df["tp_mult"].unique()) > 1:
            fig, ax = plt.subplots(figsize=(10, 8))

            pivot_data = df.groupby(["sl_mult", "tp_mult"])["win_rate"].mean().unstack()
            sns.heatmap(
                pivot_data,
                annot=True,
                fmt=".1%",
                cmap="Blues",
                ax=ax,
                cbar_kws={"label": "Win Rate"},
            )

            ax.set_title(
                "Win Rate by Stop Loss and Take Profit Multipliers",
                fontsize=14,
                fontweight="bold",
            )
            ax.set_xlabel("Take Profit Multiplier (ATR)", fontsize=12)
            ax.set_ylabel("Stop Loss Multiplier (ATR)", fontsize=12)

            chart_path = self.output_dir / "heatmap_sl_tp_wr.png"
            plt.savefig(chart_path, dpi=300, bbox_inches="tight")
            plt.close()
            chart_paths.append(str(chart_path))

        # 3. Symbol vs Timeframe performance matrix
        if len(df["symbol"].unique()) > 1 and len(df["timeframe"].unique()) > 1:
            fig, ax = plt.subplots(figsize=(10, 6))

            pivot_data = (
                df.groupby(["symbol", "timeframe"])["total_pnl"].mean().unstack()
            )
            sns.heatmap(
                pivot_data,
                annot=True,
                fmt=".0f",
                cmap="RdYlGn",
                ax=ax,
                cbar_kws={"label": "Average Total P&L ($)"},
            )

            ax.set_title(
                "Average P&L by Symbol and Timeframe", fontsize=14, fontweight="bold"
            )
            ax.set_xlabel("Timeframe (minutes)", fontsize=12)
            ax.set_ylabel("Symbol", fontsize=12)

            chart_path = self.output_dir / "heatmap_symbol_tf_pnl.png"
            plt.savefig(chart_path, dpi=300, bbox_inches="tight")
            plt.close()
            chart_paths.append(str(chart_path))

        logger.info(f"Generated {len(chart_paths)} parameter heatmaps")
        return chart_paths

    def plot_performance_distribution(self, results: list[BacktestResult]) -> str:
        """
        Plot distribution of key performance metrics

        Args:
            results: List of backtest results

        Returns:
            Path to saved distribution chart
        """
        successful_results = [r for r in results if r.success and r.total_trades > 0]

        if len(successful_results) < 5:
            raise ValueError("Not enough successful results for distribution analysis")

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))

        # Extract metrics
        win_rates = [r.win_rate * 100 for r in successful_results]
        profit_factors = [
            r.profit_factor for r in successful_results if r.profit_factor < 10
        ]  # Remove outliers
        max_dds = [r.max_drawdown_pct * 100 for r in successful_results]
        total_pnls = [r.total_pnl for r in successful_results]

        # Win Rate distribution
        ax1.hist(win_rates, bins=20, alpha=0.7, color="skyblue", edgecolor="black")
        ax1.axvline(
            sum(win_rates) / len(win_rates),
            color="red",
            linestyle="--",
            label=f"Mean: {sum(win_rates)/len(win_rates):.1f}%",
        )
        ax1.set_xlabel("Win Rate (%)")
        ax1.set_ylabel("Frequency")
        ax1.set_title("Win Rate Distribution")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Profit Factor distribution
        ax2.hist(
            profit_factors, bins=20, alpha=0.7, color="lightgreen", edgecolor="black"
        )
        ax2.axvline(
            sum(profit_factors) / len(profit_factors),
            color="red",
            linestyle="--",
            label=f"Mean: {sum(profit_factors)/len(profit_factors):.2f}",
        )
        ax2.set_xlabel("Profit Factor")
        ax2.set_ylabel("Frequency")
        ax2.set_title("Profit Factor Distribution")
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Max Drawdown distribution
        ax3.hist(max_dds, bins=20, alpha=0.7, color="lightcoral", edgecolor="black")
        ax3.axvline(
            sum(max_dds) / len(max_dds),
            color="red",
            linestyle="--",
            label=f"Mean: {sum(max_dds)/len(max_dds):.1f}%",
        )
        ax3.set_xlabel("Max Drawdown (%)")
        ax3.set_ylabel("Frequency")
        ax3.set_title("Maximum Drawdown Distribution")
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Total P&L distribution
        ax4.hist(total_pnls, bins=20, alpha=0.7, color="gold", edgecolor="black")
        ax4.axvline(
            sum(total_pnls) / len(total_pnls),
            color="red",
            linestyle="--",
            label=f"Mean: ${sum(total_pnls)/len(total_pnls):.0f}",
        )
        ax4.set_xlabel("Total P&L ($)")
        ax4.set_ylabel("Frequency")
        ax4.set_title("Total P&L Distribution")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()

        chart_path = self.output_dir / "performance_distributions.png"
        plt.savefig(chart_path, dpi=300, bbox_inches="tight")
        plt.close()

        logger.info(f"Performance distribution chart saved to {chart_path}")
        return str(chart_path)

    def _get_detailed_equity_curve(
        self, params: BacktestParams, config: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Re-run backtest to get detailed equity curve data for visualization

        Args:
            params: Backtest parameters
            config: Lab configuration

        Returns:
            Dictionary with equity curve data or None if failed
        """
        try:
            from config.settings import get_settings
            from feeds.factory import create_feed
            from safety_gate import Guard

            from .runner import (
                add_technical_indicators,
                run_single_backtest,
                simulate_backtest,
            )

            # Initialize settings
            settings = get_settings()
            settings.trading.symbol = params.symbol
            settings.trading.timeframe_minutes = params.timeframe
            settings.trading.atr_period = params.atr_period
            settings.trading.risk_percentage = params.risk_pct
            settings.trading.stop_loss_multiplier = params.sl_mult
            settings.trading.take_profit_multiplier = params.tp_mult

            # Get data
            feed = create_feed(
                "backtest", settings, data_dir=config["data"]["data_dir"]
            )
            timeframe_str = f"M{params.timeframe}"
            candles = feed.get_ohlcv(
                params.symbol, timeframe_str, config["data"]["min_bars"]
            )

            # Convert to DataFrame
            df_data = []
            for candle in candles:
                df_data.append(
                    {
                        "ts": candle.ts,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                    }
                )

            df = pd.DataFrame(df_data)
            df = add_technical_indicators(df, params.atr_period)

            # Convert timestamps to dates
            df["date"] = pd.to_datetime(df["ts"], unit="s")

            # Run detailed simulation to get equity curve
            initial_balance = config["backtest"]["initial_balance"]
            balance = initial_balance
            equity_curve = [balance]
            dates = [df["date"].iloc[0]]
            drawdown_curve = [0]
            trades_detail = []

            peak_equity = balance
            position = None

            guard = Guard(
                symbol=params.symbol,
                timeframe_min=params.timeframe,
                session=settings.trading.session,
                cooldown_mult=settings.trading.cooldown_multiplier,
                min_atr=settings.trading.min_atr,
                risk_pct=params.risk_pct,
                sl_mult=params.sl_mult,
                tp_mult=params.tp_mult,
                enable_news=False,
            )

            for i, row in df.iterrows():
                if pd.isna(row["ma20"]) or pd.isna(row["ma50"]) or pd.isna(row["atr"]):
                    equity_curve.append(balance)
                    dates.append(row["date"])

                    # Update drawdown
                    peak_equity = max(peak_equity, balance)
                    drawdown_pct = ((peak_equity - balance) / peak_equity) * 100
                    drawdown_curve.append(drawdown_pct)
                    continue

                current_price = row["close"]

                # Position management (same logic as simulate_backtest)
                if position is not None:
                    exit_reason = None
                    exit_price = current_price

                    if (
                        position["side"] == "BUY" and current_price <= position["sl"]
                    ) or (
                        position["side"] == "SELL" and current_price >= position["sl"]
                    ):
                        exit_reason = "SL"
                        exit_price = position["sl"]
                    elif (
                        position["side"] == "BUY" and current_price >= position["tp"]
                    ) or (
                        position["side"] == "SELL" and current_price <= position["tp"]
                    ):
                        exit_reason = "TP"
                        exit_price = position["tp"]

                    if exit_reason:
                        if position["side"] == "BUY":
                            pnl = (exit_price - position["entry_price"]) * (
                                position["risk_amount"] / position["entry_price"]
                            )
                        else:
                            pnl = (position["entry_price"] - exit_price) * (
                                position["risk_amount"] / position["entry_price"]
                            )

                        balance += pnl

                        trades_detail.append(
                            {
                                "date": row["date"],
                                "side": position["side"],
                                "entry_price": position["entry_price"],
                                "exit_price": exit_price,
                                "pnl": pnl,
                                "equity_after": balance,
                                "exit_reason": exit_reason,
                            }
                        )

                        position = None

                # New entries
                if position is None:
                    decision = guard.filter_decision(
                        row["raw_signal"],
                        current_price,
                        row["ma20"],
                        row["ma50"],
                        row["rsi14"],
                        row["atr"],
                        balance,
                    )

                    if decision.action in ("BUY", "SELL"):
                        atr = row["atr"]
                        risk_amount = balance * guard.risk_pct

                        if decision.action == "BUY":
                            sl_price = current_price - (atr * guard.sl_mult)
                            tp_price = current_price + (atr * guard.tp_mult)
                        else:
                            sl_price = current_price + (atr * guard.sl_mult)
                            tp_price = current_price - (atr * guard.tp_mult)

                        position = {
                            "side": decision.action,
                            "entry_price": current_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "risk_amount": risk_amount,
                        }

                # Update equity curve
                equity_curve.append(balance)
                dates.append(row["date"])

                # Update drawdown
                peak_equity = max(peak_equity, balance)
                drawdown_pct = ((peak_equity - balance) / peak_equity) * 100
                drawdown_curve.append(drawdown_pct)

            return {
                "dates": dates,
                "equity_curve": equity_curve,
                "drawdown_curve": drawdown_curve,
                "trades": trades_detail,
            }

        except Exception as e:
            logger.error(f"Failed to generate detailed equity curve: {e}")
            return None


def create_visualizations(
    results: list[BacktestResult], config: dict[str, Any]
) -> dict[str, str]:
    """
    Create all visualization charts for lab results

    Args:
        results: List of backtest results
        config: Lab configuration

    Returns:
        Dictionary mapping chart types to file paths
    """
    visualizer = LabVisualizer(config["output"]["charts_dir"])
    chart_paths = {}

    try:
        # Find best result
        successful_results = [r for r in results if r.success and r.total_trades > 0]

        if successful_results:
            best_result = max(successful_results, key=lambda r: r.profit_factor)

            # Create equity curve for best strategy
            try:
                chart_paths["equity_curve"] = visualizer.plot_best_equity_curve(
                    best_result, config
                )
            except Exception as e:
                logger.error(f"Failed to create equity curve: {e}")

            # Create performance distributions
            try:
                chart_paths["distributions"] = visualizer.plot_performance_distribution(
                    successful_results
                )
            except Exception as e:
                logger.error(f"Failed to create performance distributions: {e}")

            # Create parameter heatmaps
            try:
                heatmap_paths = visualizer.plot_parameter_heatmaps(successful_results)
                for i, path in enumerate(heatmap_paths):
                    chart_paths[f"heatmap_{i+1}"] = path
            except Exception as e:
                logger.error(f"Failed to create parameter heatmaps: {e}")

        logger.info(f"Generated {len(chart_paths)} visualization charts")

    except Exception as e:
        logger.error(f"Visualization creation failed: {e}")

    return chart_paths


if __name__ == "__main__":
    # Example usage - load results and create visualizations
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m lab.visualize <results_csv_path>")
        sys.exit(1)

    results_csv = sys.argv[1]

    try:
        # Load results from CSV
        df = pd.read_csv(results_csv)

        # Convert back to BacktestResult objects (simplified)
        results = []
        for _, row in df.iterrows():
            if row["success"]:
                params = BacktestParams(
                    symbol=row["symbol"],
                    timeframe=int(row["timeframe"]),
                    atr_period=int(row["atr_period"]),
                    risk_pct=float(row["risk_pct"]),
                    sl_mult=float(row["sl_mult"]),
                    tp_mult=float(row["tp_mult"]),
                )

                result = BacktestResult(
                    params=params,
                    success=True,
                    total_trades=int(row["total_trades"]),
                    winning_trades=int(row["winning_trades"]),
                    losing_trades=int(row["losing_trades"]),
                    win_rate=float(row["win_rate"]),
                    final_balance=float(row["final_balance"]),
                    total_pnl=float(row["total_pnl"]),
                    profit_factor=float(row["profit_factor"]),
                    max_drawdown=float(row["max_drawdown"]),
                    max_drawdown_pct=float(row["max_drawdown_pct"]),
                    sharpe_proxy=float(row["sharpe_proxy"]),
                    avg_trade_pnl=float(row["avg_trade_pnl"]),
                )
                results.append(result)

        # Create basic config
        config = {
            "data": {"data_dir": "data", "min_bars": 200},
            "backtest": {"initial_balance": 10000.0},
            "output": {"charts_dir": "lab/out/charts"},
        }

        # Generate visualizations
        chart_paths = create_visualizations(results, config)

        print(f"Generated {len(chart_paths)} charts:")
        for chart_type, path in chart_paths.items():
            print(f"  {chart_type}: {path}")

    except Exception as e:
        print(f"Visualization failed: {e}")
        sys.exit(1)
