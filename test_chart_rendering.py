"""
Chart Rendering Test
PNG chart үүсгэх тест

Test scenarios:
1. Equity curve chart
2. Trade distribution chart
3. Performance dashboard
4. Full chart generation
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from backtest.chart_renderer import BacktestChartRenderer
from backtest.config_loader import ConfigLoader
from backtest.runner import BacktestEngine
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)


def test_chart_generation():
    """Chart generation бүрэн тест"""
    print("🎨 Chart Generation Test...")

    try:
        # 1. Configuration ачаалах
        print("📋 Configuration ачааллаж байна...")
        config_loader = ConfigLoader()
        config = config_loader.load_strategy_config("configs/strategy.yaml")

        # 2. Backtest ажиллуулах
        print("🚀 Backtest эхлүүллээ...")
        engine = BacktestEngine(config)
        results = engine.run_backtest(save_results=False)  # CSV хадгалахгүй

        print(f"✅ Backtest дуусав: {results.total_trades} trades")

        # 3. Chart renderer үүсгэх
        print("📊 Chart renderer үүсгэж байна...")
        chart_dir = "test_charts"
        renderer = BacktestChartRenderer(chart_dir)

        # 4. Тус тусад chart үүсгэх
        print("🎯 Individual charts үүсгэж байна...")

        # Equity curve
        equity_path = renderer.render_equity_curve(results)
        print(f"📈 Equity curve: {equity_path}")

        # Trade distribution
        dist_path = renderer.render_trade_distribution(results)
        print(f"📊 Trade distribution: {dist_path}")

        # Performance dashboard
        dashboard_path = renderer.render_performance_dashboard(results)
        print(f"🎛️ Performance dashboard: {dashboard_path}")

        # 5. Бүх chart нэгэн зэрэг
        print("🎨 Бүх chart нэгэн зэрэг үүсгэж байна...")
        all_charts = renderer.render_all_charts(results, "test_suite")

        print(f"✅ {len(all_charts)} chart үүсэгдлээ:")
        for chart_type, path in all_charts.items():
            print(f"  📸 {chart_type}: {path}")

        return True

    except Exception as e:
        print(f"❌ Chart generation алдаа: {e}")
        logger.error(f"Chart test алдаа: {e}")
        return False


def test_with_yaml_charts():
    """YAML config ашиглан chart generation тест"""
    print("\n🔧 YAML Chart Configuration Test...")

    try:
        # Configuration ачаалах
        config_loader = ConfigLoader()
        config = config_loader.load_strategy_config("configs/strategy.yaml")

        # Chart generation идэвхтэй эсэхийг шалгах
        print(f"📊 Chart generation: {config.backtest.output.generate_charts}")
        print(f"📁 Output directory: {config.backtest.output.output_dir}")

        # Backtest ажиллуулах (charts бас үүсэх ёстой)
        engine = BacktestEngine(config)
        results = engine.run_backtest(save_results=True)  # Charts автоматаар үүсэх

        print(f"✅ YAML chart test дуусав: {results.total_trades} trades")
        return True

    except Exception as e:
        print(f"❌ YAML chart test алдаа: {e}")
        logger.error(f"YAML chart test алдаа: {e}")
        return False


if __name__ == "__main__":
    print("🎨 Chart Rendering Test Suite")
    print("=" * 50)

    test_results = []

    # Test 1: Manual chart generation
    test_results.append(test_chart_generation())

    # Test 2: YAML configuration
    test_results.append(test_with_yaml_charts())

    # Summary
    print("\n📊 Test Summary:")
    print("=" * 30)
    print(f"✅ Passed: {sum(test_results)}")
    print(f"❌ Failed: {len(test_results) - sum(test_results)}")

    if all(test_results):
        print("🎉 Бүх chart test амжилттай!")
    else:
        print("⚠️ Зарим test амжилтгүй болов")
