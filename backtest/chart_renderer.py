"""
Backtest Chart Renderer
Backtest үр дүнг PNG chart-аар харуулах систем

Онцлогууд:
- Equity curve visualization
- Drawdown chart
- Monthly returns heatmap
- Trade distribution histogram
- Win/Loss ratio charts
- Performance metrics dashboard
"""

from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from backtest.runner import BacktestResults, Trade
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)

# Set style
plt.style.use("seaborn-v0_8")
sns.set_palette("husl")


class BacktestChartRenderer:
    """Backtest chart rendering систем"""

    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Chart settings
        self.figsize = (12, 8)
        self.dpi = 100
        self.color_profit = "#2E8B57"  # Sea Green
        self.color_loss = "#DC143C"  # Crimson
        self.color_equity = "#4169E1"  # Royal Blue
        self.color_drawdown = "#FF4500"  # Orange Red

        logger.info("Chart Renderer эхлүүллээ")

    def render_equity_curve(
        self, results: BacktestResults, save_path: str = None
    ) -> str:
        """Equity curve chart үүсгэх"""
        if not results.equity_curve:
            logger.warning("Equity curve өгөгдөл байхгүй")
            return ""

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

        # Equity curve data бэлтгэх
        dates = [point[0] for point in results.equity_curve]
        equity = [point[1] for point in results.equity_curve]

        # Equity curve
        ax1.plot(dates, equity, color=self.color_equity, linewidth=2, label="Equity")
        ax1.axhline(
            y=results.initial_balance,
            color="gray",
            linestyle="--",
            alpha=0.7,
            label="Initial Balance",
        )
        ax1.set_title(
            f"{results.strategy_name} - Equity Curve", fontsize=16, fontweight="bold"
        )
        ax1.set_ylabel("Account Balance ($)", fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend()

        # Format x-axis
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Drawdown calculation ба chart
        peak = results.initial_balance
        drawdown = []
        for eq in equity:
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100
            drawdown.append(dd)

        ax2.fill_between(
            dates, drawdown, 0, color=self.color_drawdown, alpha=0.3, label="Drawdown"
        )
        ax2.plot(dates, drawdown, color=self.color_drawdown, linewidth=1)
        ax2.set_title("Drawdown (%)", fontsize=14)
        ax2.set_ylabel("Drawdown (%)", fontsize=12)
        ax2.set_xlabel("Date", fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.invert_yaxis()  # Drawdown-г доошоо харуулах

        # Format x-axis
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        # Performance stats text box
        stats_text = (
            f"Total Return: {results.total_return:.2%}\n"
            f"Win Rate: {results.win_rate:.2%}\n"
            f"Profit Factor: {results.profit_factor:.2f}\n"
            f"Sharpe Ratio: {results.sharpe_ratio:.2f}\n"
            f"Max Drawdown: {results.max_drawdown:.2%}\n"
            f"Total Trades: {results.total_trades}"
        )

        ax1.text(
            0.02,
            0.98,
            stats_text,
            transform=ax1.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
            fontsize=10,
        )

        plt.tight_layout()

        # Save chart
        if not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = (
                self.output_dir
                / f"equity_curve_{results.strategy_name.replace(' ', '_')}_{timestamp}.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()

        logger.info(f"Equity curve chart хадгалагдлаа: {save_path}")
        return str(save_path)

    def render_trade_distribution(
        self, results: BacktestResults, save_path: str = None
    ) -> str:
        """Trade distribution charts үүсгэх"""
        if not results.trades:
            logger.warning("Trade өгөгдөл байхгүй")
            return ""

        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

        # Profit/Loss distribution
        profits = [trade.profit for trade in results.trades]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p < 0]

        # Histogram - Profit/Loss distribution
        ax1.hist(profits, bins=30, alpha=0.7, color="skyblue", edgecolor="black")
        ax1.axvline(0, color="red", linestyle="--", linewidth=2)
        ax1.set_title("Profit/Loss Distribution", fontsize=14, fontweight="bold")
        ax1.set_xlabel("Profit/Loss ($)")
        ax1.set_ylabel("Frequency")
        ax1.grid(True, alpha=0.3)

        # Win/Loss pie chart
        win_count = len(winning_trades)
        loss_count = len(losing_trades)

        ax2.pie(
            [win_count, loss_count],
            labels=[f"Wins ({win_count})", f"Losses ({loss_count})"],
            colors=[self.color_profit, self.color_loss],
            autopct="%1.1f%%",
            startangle=90,
        )
        ax2.set_title("Win/Loss Ratio", fontsize=14, fontweight="bold")

        # Trade duration distribution
        durations = [
            trade.duration_hours for trade in results.trades if trade.duration_hours > 0
        ]
        if durations:
            ax3.hist(
                durations, bins=20, alpha=0.7, color="lightcoral", edgecolor="black"
            )
            ax3.set_title("Trade Duration Distribution", fontsize=14, fontweight="bold")
            ax3.set_xlabel("Duration (hours)")
            ax3.set_ylabel("Frequency")
            ax3.grid(True, alpha=0.3)

        # Monthly returns bar chart
        monthly_profits = self._calculate_monthly_profits(results.trades)
        if monthly_profits:
            months = list(monthly_profits.keys())
            values = list(monthly_profits.values())
            colors = [self.color_profit if v > 0 else self.color_loss for v in values]

            ax4.bar(range(len(months)), values, color=colors, alpha=0.7)
            ax4.set_title("Monthly P&L", fontsize=14, fontweight="bold")
            ax4.set_xlabel("Month")
            ax4.set_ylabel("Profit/Loss ($)")
            ax4.set_xticks(range(len(months)))
            ax4.set_xticklabels([m.strftime("%Y-%m") for m in months], rotation=45)
            ax4.grid(True, alpha=0.3)
            ax4.axhline(0, color="black", linestyle="-", alpha=0.5)

        plt.tight_layout()

        # Save chart
        if not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = (
                self.output_dir
                / f"trade_distribution_{results.strategy_name.replace(' ', '_')}_{timestamp}.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()

        logger.info(f"Trade distribution chart хадгалагдлаа: {save_path}")
        return str(save_path)

    def render_performance_dashboard(
        self, results: BacktestResults, save_path: str = None
    ) -> str:
        """Performance metrics dashboard үүсгэх"""
        fig = plt.figure(figsize=(16, 10))

        # Create grid layout
        gs = fig.add_gridspec(3, 4, height_ratios=[1, 1, 1], width_ratios=[1, 1, 1, 1])

        # Title
        fig.suptitle(
            f"{results.strategy_name} - Performance Dashboard",
            fontsize=20,
            fontweight="bold",
        )

        # Key metrics table
        ax_metrics = fig.add_subplot(gs[0, :2])
        metrics_data = [
            ["Total Return", f"{results.total_return:.2%}"],
            ["Win Rate", f"{results.win_rate:.2%}"],
            ["Profit Factor", f"{results.profit_factor:.2f}"],
            ["Sharpe Ratio", f"{results.sharpe_ratio:.2f}"],
            ["Max Drawdown", f"{results.max_drawdown:.2%}"],
            ["Total Trades", f"{results.total_trades}"],
            ["Avg Win", f"${results.average_win:.2f}"],
            ["Avg Loss", f"${results.average_loss:.2f}"],
        ]

        ax_metrics.axis("tight")
        ax_metrics.axis("off")
        table = ax_metrics.table(
            cellText=metrics_data,
            colLabels=["Metric", "Value"],
            cellLoc="center",
            loc="center",
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.5)
        ax_metrics.set_title("Key Metrics", fontsize=14, fontweight="bold")

        # Risk metrics
        ax_risk = fig.add_subplot(gs[0, 2:])
        risk_data = [
            ["Winning Trades", f"{results.winning_trades}"],
            ["Losing Trades", f"{results.losing_trades}"],
            ["Largest Win", f"${results.largest_win:.2f}"],
            ["Largest Loss", f"${results.largest_loss:.2f}"],
            ["Avg Duration", f"{results.average_trade_duration:.1f}h"],
            ["Start Date", results.start_date.strftime("%Y-%m-%d")],
            ["End Date", results.end_date.strftime("%Y-%m-%d")],
            ["Initial Balance", f"${results.initial_balance:.2f}"],
        ]

        ax_risk.axis("tight")
        ax_risk.axis("off")
        risk_table = ax_risk.table(
            cellText=risk_data,
            colLabels=["Risk Metric", "Value"],
            cellLoc="center",
            loc="center",
        )
        risk_table.auto_set_font_size(False)
        risk_table.set_fontsize(12)
        risk_table.scale(1.2, 1.5)
        ax_risk.set_title("Risk Analysis", fontsize=14, fontweight="bold")

        # Monthly performance heatmap
        if results.trades:
            monthly_data = self._create_monthly_heatmap_data(results.trades)
            if len(monthly_data) > 0:
                ax_heatmap = fig.add_subplot(gs[1, :])

                # Convert to DataFrame for heatmap
                df_monthly = pd.DataFrame(monthly_data)
                if not df_monthly.empty:
                    # Pivot table for heatmap
                    pivot_table = df_monthly.pivot_table(
                        values="profit",
                        index="year",
                        columns="month",
                        aggfunc="sum",
                        fill_value=0,
                    )

                    # Create heatmap
                    sns.heatmap(
                        pivot_table,
                        annot=True,
                        fmt=".0f",
                        cmap="RdYlGn",
                        center=0,
                        ax=ax_heatmap,
                        cbar_kws={"label": "Monthly Profit ($)"},
                    )
                    ax_heatmap.set_title(
                        "Monthly Performance Heatmap", fontsize=14, fontweight="bold"
                    )
                    ax_heatmap.set_xlabel("Month")
                    ax_heatmap.set_ylabel("Year")

        # Equity curve mini
        if results.equity_curve:
            ax_equity = fig.add_subplot(gs[2, :2])
            dates = [point[0] for point in results.equity_curve]
            equity = [point[1] for point in results.equity_curve]

            ax_equity.plot(dates, equity, color=self.color_equity, linewidth=2)
            ax_equity.axhline(
                y=results.initial_balance, color="gray", linestyle="--", alpha=0.7
            )
            ax_equity.set_title("Equity Curve", fontsize=12, fontweight="bold")
            ax_equity.set_ylabel("Balance ($)")
            ax_equity.grid(True, alpha=0.3)
            ax_equity.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            plt.setp(ax_equity.xaxis.get_majorticklabels(), rotation=45)

        # Win/Loss statistics pie chart
        if results.trades:
            ax_winloss = fig.add_subplot(gs[2, 2:])
            win_count = results.winning_trades
            loss_count = results.losing_trades

            if win_count + loss_count > 0:
                ax_winloss.pie(
                    [win_count, loss_count],
                    labels=[f"Wins\n{win_count}", f"Losses\n{loss_count}"],
                    colors=[self.color_profit, self.color_loss],
                    autopct="%1.1f%%",
                    startangle=90,
                )
                ax_winloss.set_title(
                    "Win/Loss Distribution", fontsize=12, fontweight="bold"
                )

        plt.tight_layout()

        # Save chart
        if not save_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = (
                self.output_dir
                / f"dashboard_{results.strategy_name.replace(' ', '_')}_{timestamp}.png"
            )

        plt.savefig(save_path, dpi=self.dpi, bbox_inches="tight")
        plt.close()

        logger.info(f"Performance dashboard хадгалагдлаа: {save_path}")
        return str(save_path)

    def _calculate_monthly_profits(self, trades: list[Trade]) -> dict[datetime, float]:
        """Monthly profit тооцоолох"""
        monthly_profits = {}

        for trade in trades:
            if trade.exit_time:
                # Month key үүсгэх
                month_key = datetime(trade.exit_time.year, trade.exit_time.month, 1)

                if month_key not in monthly_profits:
                    monthly_profits[month_key] = 0

                monthly_profits[month_key] += trade.profit

        return dict(sorted(monthly_profits.items()))

    def _create_monthly_heatmap_data(self, trades: list[Trade]) -> list[dict]:
        """Monthly heatmap өгөгдөл бэлтгэх"""
        data = []

        for trade in trades:
            if trade.exit_time:
                data.append(
                    {
                        "year": trade.exit_time.year,
                        "month": trade.exit_time.month,
                        "profit": trade.profit,
                    }
                )

        return data

    def render_all_charts(
        self, results: BacktestResults, base_name: str = None
    ) -> dict[str, str]:
        """Бүх chart үүсгэх"""
        if not base_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"{results.strategy_name.replace(' ', '_')}_{timestamp}"

        chart_files = {}

        try:
            # Equity curve
            equity_path = self.output_dir / f"{base_name}_equity.png"
            chart_files["equity"] = self.render_equity_curve(results, str(equity_path))

            # Trade distribution
            dist_path = self.output_dir / f"{base_name}_distribution.png"
            chart_files["distribution"] = self.render_trade_distribution(
                results, str(dist_path)
            )

            # Performance dashboard
            dashboard_path = self.output_dir / f"{base_name}_dashboard.png"
            chart_files["dashboard"] = self.render_performance_dashboard(
                results, str(dashboard_path)
            )

            logger.info(f"Бүх chart үүсэгдлээ: {len(chart_files)} файл")
            return chart_files

        except Exception as e:
            logger.error(f"Chart rendering алдаа: {e}")
            return chart_files


# Convenience functions
def create_backtest_charts(
    results: BacktestResults, output_dir: str = "reports"
) -> dict[str, str]:
    """Backtest charts үүсгэх convenience function"""
    renderer = BacktestChartRenderer(output_dir)
    return renderer.render_all_charts(results)
