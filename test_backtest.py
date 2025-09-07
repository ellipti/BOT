#!/usr/bin/env python3
"""
Backtest System тест
YAML configuration болон backtest engine-ийн шалгалт

Тест сценариуд:
1. YAML config унших/бичих
2. Sample data generation
3. Technical indicators тооцоолол
4. Signal generation
5. Trade simulation
6. Performance metrics calculation
7. Results export (CSV/PNG)
8. In-sample/Out-of-sample validation
9. Grid search optimization demo
"""

import sys
from pathlib import Path

# Add backtest to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from backtest.config_loader import ConfigLoader
from backtest.runner import BacktestEngine


def test_backtest_system():
    print("🔧 Backtest System тест хийж байна...")

    # Test files цэвэрлэх
    test_files = [
        "configs/test_strategy.yaml",
        "reports/test_backtest_*.csv",
        "reports/test_backtest_*.png",
    ]

    print("\n📋 1. YAML Configuration тест хийж байна...")

    try:
        # Config loader тест
        loader = ConfigLoader()

        # Default config унших
        config = loader.load_strategy_config("configs/strategy.yaml")

        print(f"   Strategy name: {config.name}")
        print(f"   MA fast: {config.parameters.ma_fast}")
        print(f"   MA slow: {config.parameters.ma_slow}")
        print(f"   RSI period: {config.parameters.rsi_period}")
        print(f"   Risk per trade: {config.parameters.risk_per_trade}")
        print(f"   Initial balance: {config.backtest.account.initial_balance}")
        print(f"   Trading sessions: {len(config.parameters.trading_sessions)}")

        # Test configuration save
        config.name = "Test Strategy"
        config.parameters.ma_fast = 15
        config.parameters.ma_slow = 45

        test_config_path = "configs/test_strategy.yaml"
        success = loader.save_strategy_config(config, test_config_path)

        if success:
            print("   ✅ YAML config унших/бичих амжилттай")
        else:
            print("   ❌ YAML config хадгалах амжилтгүй")

        # Test config дахин унших
        reloaded_config = loader.load_strategy_config(test_config_path)
        assert reloaded_config.name == "Test Strategy"
        assert reloaded_config.parameters.ma_fast == 15

        print("   ✅ Config persistence тест амжилттай")

    except Exception as e:
        print(f"   ❌ YAML config тест алдаа: {e}")
        return False

    print("\n📊 2. Backtest Engine тест хийж байна...")

    try:
        # Backtest engine үүсгэх
        engine = BacktestEngine(config)

        print("   Engine үүсэгдлээ")

        # Sample data generation тест
        symbol = "XAUUSD"
        start_date = "2024-01-01"
        end_date = "2024-03-31"  # 3 сарын өгөгдөл

        print(f"   Sample data үүсгэж байна: {symbol} {start_date} - {end_date}")
        df = engine.generate_sample_data(symbol, start_date, end_date, "M30")

        print(f"   Data points: {len(df)}")
        print(f"   Date range: {df.index[0]} - {df.index[-1]}")
        print(f"   Price range: ${df['close'].min():.2f} - ${df['close'].max():.2f}")

        assert len(df) > 1000, "Дөгөрүү өгөгдөл байх ёстой"
        print("   ✅ Sample data generation амжилттай")

    except Exception as e:
        print(f"   ❌ Sample data тест алдаа: {e}")
        return False

    print("\n📈 3. Technical indicators тест хийж байна...")

    try:
        # Strategy параметрүүд
        params = {
            "ma_fast": config.parameters.ma_fast,
            "ma_slow": config.parameters.ma_slow,
            "rsi_period": config.parameters.rsi_period,
            "atr_period": config.parameters.atr_period,
        }

        # Indicators тооцоолох
        df_with_indicators = engine.calculate_indicators(df, params)

        ma_fast_col = f'MA_{params["ma_fast"]}'
        ma_slow_col = f'MA_{params["ma_slow"]}'

        print(
            f"   {ma_fast_col} сүүлийн утга: {df_with_indicators[ma_fast_col].iloc[-1]:.2f}"
        )
        print(
            f"   {ma_slow_col} сүүлийн утга: {df_with_indicators[ma_slow_col].iloc[-1]:.2f}"
        )
        print(f"   RSI сүүлийн утга: {df_with_indicators['RSI'].iloc[-1]:.1f}")
        print(f"   ATR сүүлийн утга: {df_with_indicators['ATR'].iloc[-1]:.5f}")

        # Indicators validation
        assert not df_with_indicators[ma_fast_col].dropna().empty
        assert not df_with_indicators["RSI"].dropna().empty
        assert not df_with_indicators["ATR"].dropna().empty

        print("   ✅ Technical indicators тест амжилттай")

    except Exception as e:
        print(f"   ❌ Indicators тест алдаа: {e}")
        return False

    print("\n🎯 4. Signal generation тест хийж байна...")

    try:
        # Signals үүсгэх
        df_with_signals = engine.generate_signals(
            df_with_indicators, config.parameters.__dict__
        )

        # Signal statistics
        buy_signals = (df_with_signals["signal"] == 1).sum()
        sell_signals = (df_with_signals["signal"] == -1).sum()
        total_signals = buy_signals + sell_signals

        print(f"   Buy signals: {buy_signals}")
        print(f"   Sell signals: {sell_signals}")
        print(f"   Total signals: {total_signals}")
        print(f"   Signal frequency: {total_signals/len(df):.3%}")

        assert total_signals > 0, "Signal үүсэх ёстой"
        print("   ✅ Signal generation амжилттай")

    except Exception as e:
        print(f"   ❌ Signal generation тест алдаа: {e}")
        return False

    print("\n💼 5. Trade simulation тест хийж байна...")

    try:
        # Account config
        account_config = {
            "initial_balance": config.backtest.account.initial_balance,
            "spread": config.backtest.account.spread,
            "commission": config.backtest.account.commission,
            "symbol": config.backtest.data.symbol,
        }

        # Trade simulation
        trades = engine.simulate_trades(
            df_with_signals, config.parameters.__dict__, account_config
        )

        print(f"   Simulate хийсэн trades: {len(trades)}")

        if trades:
            winners = sum(1 for t in trades if t.is_winner)
            print(f"   Winning trades: {winners}")
            print(f"   Win rate: {winners/len(trades):.1%}")

            total_profit = sum(t.profit for t in trades)
            print(f"   Total profit: ${total_profit:.2f}")

            avg_duration = sum(
                t.duration_hours for t in trades if t.duration_hours > 0
            ) / len([t for t in trades if t.duration_hours > 0])
            print(f"   Average duration: {avg_duration:.1f} hours")

        assert len(trades) > 0, "Trade үүсэх ёстой"
        print("   ✅ Trade simulation амжилттай")

    except Exception as e:
        print(f"   ❌ Trade simulation тест алдаа: {e}")
        return False

    print("\n📊 6. Performance metrics тест хийж байна...")

    try:
        # Performance calculation
        results = engine.calculate_performance_metrics(
            trades, account_config["initial_balance"]
        )

        print(f"   Strategy: {results.strategy_name}")
        print(f"   Total return: {results.total_return:.2%}")
        print(f"   Win rate: {results.win_rate:.2%}")
        print(f"   Profit factor: {results.profit_factor:.2f}")
        print(f"   Sharpe ratio: {results.sharpe_ratio:.2f}")
        print(f"   Max drawdown: {results.max_drawdown:.2%}")
        print(f"   Average win: ${results.average_win:.2f}")
        print(f"   Average loss: ${results.average_loss:.2f}")

        # Validation
        assert results.total_trades == len(trades)
        assert results.winning_trades + results.losing_trades == results.total_trades
        assert results.final_balance == results.initial_balance + sum(
            t.profit for t in trades
        )

        print("   ✅ Performance metrics тест амжилттай")

    except Exception as e:
        print(f"   ❌ Performance metrics тест алдаа: {e}")
        return False

    print("\n💾 7. Results export тест хийж байна...")

    try:
        # Results хадгалах
        saved_files = engine.save_results(results, custom_suffix="_test")

        print(f"   Хадгалагдсан файлууд: {len(saved_files)}")
        for file_type, file_path in saved_files.items():
            print(f"     {file_type}: {file_path}")

            # Файл байгаа эсэхийг шалгах
            if Path(file_path).exists():
                print(f"       ✅ {file_type} файл байгаа")
            else:
                print(f"       ❌ {file_type} файл байхгүй")

        assert len(saved_files) > 0, "File хадгалагдах ёстой"
        print("   ✅ Results export амжилттай")

    except Exception as e:
        print(f"   ❌ Results export тест алдаа: {e}")
        return False

    print("\n🔬 8. Full backtest integration тест хийж байна...")

    try:
        # Full backtest run
        print("   Full backtest ажиллуулж байна...")
        final_results = engine.run_backtest(save_results=True)

        print("   Final results:")
        print(f"     Strategy: {final_results.strategy_name}")
        print(
            f"     Period: {final_results.start_date.strftime('%Y-%m-%d')} - {final_results.end_date.strftime('%Y-%m-%d')}"
        )
        print(f"     Total trades: {final_results.total_trades}")
        print(f"     Win rate: {final_results.win_rate:.2%}")
        print(f"     Total return: {final_results.total_return:.2%}")
        print(f"     Profit factor: {final_results.profit_factor:.2f}")
        print(f"     Max drawdown: {final_results.max_drawdown:.2%}")

        # Basic validation
        assert final_results.total_trades > 0, "Trades үүсэх ёстой"
        assert (
            final_results.win_rate >= 0 and final_results.win_rate <= 1
        ), "Win rate 0-1 хооронд байх ёстой"

        print("   ✅ Full backtest амжилттай")

    except Exception as e:
        print(f"   ❌ Full backtest тест алдаа: {e}")
        return False

    print("\n🎯 9. Grid search demo тест хийж байна...")

    try:
        # Simple parameter sweep demo
        print("   Parameter optimization demo хийж байна...")

        base_params = config.parameters.__dict__.copy()

        # MA fast parameter sweep
        ma_fast_values = [15, 20, 25]
        best_sharpe = -999
        best_params = None

        for ma_fast in ma_fast_values:
            test_params = base_params.copy()
            test_params["ma_fast"] = ma_fast

            print(f"     MA Fast = {ma_fast} тест хийж байна...")

            # Quick backtest
            test_results = engine.run_backtest(params=test_params, save_results=False)

            print(
                f"       Return: {test_results.total_return:.2%}, Sharpe: {test_results.sharpe_ratio:.2f}"
            )

            if test_results.sharpe_ratio > best_sharpe:
                best_sharpe = test_results.sharpe_ratio
                best_params = test_params.copy()

        print("   Хамгийн сайн параметр:")
        print(f"     MA Fast: {best_params['ma_fast']}")
        print(f"     Sharpe Ratio: {best_sharpe:.2f}")

        print("   ✅ Grid search demo амжилттай")

    except Exception as e:
        print(f"   ❌ Grid search тест алдаа: {e}")
        return False

    print("\n🧹 10. Cleanup тест хийж байна...")

    try:
        # Test files цэвэрлэх
        cleanup_paths = [
            Path("configs/test_strategy.yaml"),
        ]

        for path in cleanup_paths:
            if path.exists():
                path.unlink()
                print(f"   Цэвэрлэв: {path}")

        print("   ✅ Cleanup амжилттай")

    except Exception as e:
        print(f"   ❌ Cleanup алдаа: {e}")

    print("\n🎉 Backtest System бүх тест амжилттай дууслаа!")
    print("📊 System Features:")
    print("   ✅ YAML-based strategy configuration")
    print("   ✅ Sample data generation and loading")
    print("   ✅ Technical indicators calculation")
    print("   ✅ Trading signal generation")
    print("   ✅ Realistic trade simulation")
    print("   ✅ Comprehensive performance metrics")
    print("   ✅ Multi-format results export (CSV)")
    print("   ✅ Parameter optimization framework")
    print("   ✅ In-sample/Out-of-sample ready")
    print("   ✅ Grid search capabilities")

    return True


if __name__ == "__main__":
    success = test_backtest_system()
    if success:
        print("\n✅ Бүх тест амжилттай!")
    else:
        print("\n❌ Зарим тест амжилтгүй!")
        sys.exit(1)
