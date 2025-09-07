"""
Grid Search Optimization + Chart Demo
Parameter optimization бас chart generation-тай хамт

Онцлогууд:
- Grid search parameter optimization
- Chart generation тус бүр optimization-оор
- Best parameter comparison
- Optimization results visualization
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from backtest.chart_renderer import BacktestChartRenderer
from backtest.config_loader import ConfigLoader
from backtest.runner import BacktestEngine
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)


def test_optimization_with_charts():
    """Grid search optimization + chart generation"""
    print("🔍 Grid Search Optimization + Charts Demo")
    print("=" * 50)

    try:
        # Configuration ачаалах
        config_loader = ConfigLoader()
        config = config_loader.load_strategy_config("configs/strategy.yaml")

        # Grid search идэвхжүүлэх
        config.optimization.enabled = True
        config.optimization.grid = {
            "ma_fast": [10, 15, 20],
            "ma_slow": [40, 50, 60],
            "rsi_oversold": [25, 30],
            "rsi_overbought": [70, 75],
        }
        config.optimization.objective = "sharpe_ratio"

        print(f"📊 Optimization grid: {len(config.optimization.grid)} parameters")

        # Engine үүсгэх
        engine = BacktestEngine(config)

        # Grid search ажиллуулах
        print("🚀 Grid search эхлүүллээ...")
        optimization_results = engine.run_grid_search()

        print(
            f"✅ Grid search дуусав: {len(optimization_results)} combinations тест хийлээ"
        )

        # Best хариу авах
        best_result = max(optimization_results, key=lambda x: x["sharpe_ratio"])
        print("\n🏆 Best Parameters:")
        print(f"   Sharpe Ratio: {best_result['sharpe_ratio']:.3f}")
        print(f"   Parameters: {best_result['parameters']}")
        print(f"   Win Rate: {best_result['win_rate']:.2%}")
        print(f"   Total Return: {best_result['total_return']:.2%}")

        # Best parameters ашиглан backtest + charts
        print("\n📊 Best parameter-ээр chart үүсгэж байна...")

        # Config update хийх
        best_params = best_result["parameters"]
        config.parameters.ma_fast = best_params["ma_fast"]
        config.parameters.ma_slow = best_params["ma_slow"]
        config.parameters.rsi_oversold = best_params["rsi_oversold"]
        config.parameters.rsi_overbought = best_params["rsi_overbought"]

        # Chart нэр
        chart_name = f"optimized_{best_params['ma_fast']}_{best_params['ma_slow']}"

        # Best parameter backtest
        engine_best = BacktestEngine(config)
        results_best = engine_best.run_backtest(save_results=False)

        # Chart үүсгэх
        renderer = BacktestChartRenderer("optimization_charts")
        charts = renderer.render_all_charts(results_best, chart_name)

        print("📸 Charts үүсэгдлээ:")
        for chart_type, path in charts.items():
            print(f"   {chart_type}: {path}")

        # Summary
        print("\n📈 Optimization Summary:")
        print(f"   Total combinations tested: {len(optimization_results)}")
        print(f"   Best Sharpe ratio: {best_result['sharpe_ratio']:.3f}")
        print(
            f"   Improvement over default: {(best_result['sharpe_ratio'] - optimization_results[0]['sharpe_ratio']):.3f}"
        )

        return True

    except Exception as e:
        print(f"❌ Optimization chart test алдаа: {e}")
        logger.error(f"Optimization chart test алдаа: {e}")
        return False


def test_comparison_charts():
    """Strategy comparison charts үүсгэх"""
    print("\n📊 Strategy Comparison Charts")
    print("=" * 40)

    try:
        # Different parameter sets тест хийх
        test_configs = [
            {"ma_fast": 10, "ma_slow": 40, "name": "Fast_MA"},
            {"ma_fast": 20, "ma_slow": 60, "name": "Medium_MA"},
            {"ma_fast": 30, "ma_slow": 80, "name": "Slow_MA"},
        ]

        results = []

        for test_config in test_configs:
            print(f"📈 Testing {test_config['name']}...")

            # Config ачаалах
            config_loader = ConfigLoader()
            config = config_loader.load_strategy_config("configs/strategy.yaml")

            # Parameters солих
            config.parameters.ma_fast = test_config["ma_fast"]
            config.parameters.ma_slow = test_config["ma_slow"]

            # Backtest ажиллуулах
            engine = BacktestEngine(config)
            result = engine.run_backtest(save_results=False)

            # Chart үүсгэх
            renderer = BacktestChartRenderer("comparison_charts")
            charts = renderer.render_all_charts(result, test_config["name"])

            results.append(
                {
                    "name": test_config["name"],
                    "sharpe_ratio": result.sharpe_ratio,
                    "total_return": result.total_return,
                    "win_rate": result.win_rate,
                    "max_drawdown": result.max_drawdown,
                    "charts": charts,
                }
            )

            print(
                f"   ✅ Sharpe: {result.sharpe_ratio:.3f}, Return: {result.total_return:.2%}"
            )

        # Comparison summary
        print("\n🏁 Strategy Comparison Results:")
        for result in results:
            print(
                f"   {result['name']}: Sharpe {result['sharpe_ratio']:.3f}, "
                f"Return {result['total_return']:.2%}, WinRate {result['win_rate']:.1%}"
            )

        # Best strategy
        best_strategy = max(results, key=lambda x: x["sharpe_ratio"])
        print(
            f"\n🏆 Best Strategy: {best_strategy['name']} (Sharpe: {best_strategy['sharpe_ratio']:.3f})"
        )

        return True

    except Exception as e:
        print(f"❌ Comparison chart test алдаа: {e}")
        logger.error(f"Comparison chart test алдаа: {e}")
        return False


if __name__ == "__main__":
    print("🎯 Advanced Chart + Optimization Demo")
    print("=" * 60)

    test_results = []

    # Test 1: Grid search + charts
    test_results.append(test_optimization_with_charts())

    # Test 2: Strategy comparison
    test_results.append(test_comparison_charts())

    # Summary
    print("\n📊 Final Test Summary:")
    print("=" * 30)
    print(f"✅ Passed: {sum(test_results)}")
    print(f"❌ Failed: {len(test_results) - sum(test_results)}")

    if all(test_results):
        print("🎉 Бүх optimization + chart test амжилттай!")
        print("📁 Chart файлууд:")
        print("   📂 optimization_charts/ - Grid search үр дүн")
        print("   📂 comparison_charts/ - Strategy харьцуулалт")
    else:
        print("⚠️ Зарим test амжилтгүй болов")
