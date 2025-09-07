"""
YAML Configuration Loader
Trading Strategy болон Backtest параметрийн удирдлага

Онцлогууд:
- YAML файлаас strategy параметрүүд унших
- Parameter validation and type checking
- Grid search параметрийн бэлтгэл
- Environment variable substitution
- Configuration inheritance and overrides
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path
from typing import Any

import yaml

from logging_setup import setup_advanced_logger

logger = setup_advanced_logger(__name__)


@dataclass
class TradingSession:
    """Trading session тохиргоо"""

    name: str
    start: time
    end: time
    enabled: bool = True


@dataclass
class StrategyParameters:
    """Strategy параметрийн класс"""

    # Moving Average параметрүүд
    ma_fast: int = 20
    ma_slow: int = 50
    ma_type: str = "sma"

    # RSI параметрүүд
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0

    # ATR параметрүүд
    atr_period: int = 14
    atr_multiplier_sl: float = 2.0
    atr_multiplier_tp: float = 3.0
    min_atr_threshold: float = 0.0001

    # Risk management
    risk_per_trade: float = 0.01
    max_open_positions: int = 1

    # Trading sessions
    trading_sessions: list[TradingSession] = field(default_factory=list)

    def __post_init__(self):
        """Parameter validation"""
        if self.ma_fast >= self.ma_slow:
            raise ValueError("ma_fast ба ma_slow-с бага байх ёстой")

        if not 0 < self.risk_per_trade <= 0.1:
            raise ValueError("risk_per_trade 0-1 хооронд байх ёстой (10% хүртэл)")

        if self.rsi_oversold >= self.rsi_overbought:
            raise ValueError("RSI oversold < overbought байх ёстой")


@dataclass
class BacktestData:
    """Backtest өгөгдлийн тохиргоо"""

    symbol: str = "XAUUSD"
    timeframe: str = "M30"
    start_date: str = "2024-01-01"
    end_date: str = "2024-12-31"


@dataclass
class BacktestAccount:
    """Backtest дансны тохиргоо"""

    initial_balance: float = 10000.0
    commission: float = 0.0
    spread: float = 2.0
    leverage: int = 100


@dataclass
class BacktestRisk:
    """Backtest эрсдэлийн тохиргоо"""

    max_daily_loss: float = 0.05
    max_weekly_loss: float = 0.15
    cooldown_minutes: int = 30


@dataclass
class BacktestValidation:
    """Backtest validation тохиргоо"""

    in_sample_ratio: float = 0.7
    out_sample_ratio: float = 0.3
    min_trades: int = 100


@dataclass
class BacktestOutput:
    """Backtest output тохиргоо"""

    generate_charts: bool = True
    save_csv: bool = True
    output_dir: str = "reports"


@dataclass
class BacktestConfig:
    """Backtest тохиргооны бүрэн класс"""

    data: BacktestData = field(default_factory=BacktestData)
    account: BacktestAccount = field(default_factory=BacktestAccount)
    risk: BacktestRisk = field(default_factory=BacktestRisk)
    validation: BacktestValidation = field(default_factory=BacktestValidation)
    output: BacktestOutput = field(default_factory=BacktestOutput)


@dataclass
class OptimizationGrid:
    """Grid search параметрүүд"""

    enabled: bool = False
    grid: dict[str, list[int | float]] = field(default_factory=dict)
    objective: str = "sharpe_ratio"
    constraints: dict[str, float] = field(default_factory=dict)


@dataclass
class ReportingConfig:
    """Тайлангийн тохиргоо"""

    formats: list[str] = field(default_factory=lambda: ["csv", "png"])
    metrics: list[str] = field(default_factory=list)
    charts: dict[str, bool] = field(default_factory=dict)
    template: str = "default"
    title_prefix: str = "Backtest Report"


@dataclass
class StrategyConfig:
    """Strategy тохиргооны бүрэн класс"""

    name: str = "Unknown Strategy"
    description: str = ""
    version: str = "1.0"
    parameters: StrategyParameters = field(default_factory=StrategyParameters)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    optimization: OptimizationGrid = field(default_factory=OptimizationGrid)
    reporting: ReportingConfig = field(default_factory=ReportingConfig)


class ConfigLoader:
    """YAML Configuration файл унших систем"""

    def __init__(self):
        self.config_dir = Path("configs")
        self.config_dir.mkdir(exist_ok=True)

    def _substitute_env_vars(self, config_dict: dict[str, Any]) -> dict[str, Any]:
        """Environment variable substitution"""

        def substitute_value(value):
            if (
                isinstance(value, str)
                and value.startswith("${")
                and value.endswith("}")
            ):
                env_var = value[2:-1]
                default_value = None

                if ":" in env_var:
                    env_var, default_value = env_var.split(":", 1)

                return os.getenv(env_var, default_value)
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            else:
                return value

        return substitute_value(config_dict)

    def _parse_time_string(self, time_str: str) -> time:
        """Time string-г time object болгох"""
        try:
            return datetime.strptime(time_str, "%H:%M").time()
        except ValueError:
            logger.warning(f"Time format буруу: {time_str}, default 00:00 ашиглана")
            return time(0, 0)

    def _create_trading_sessions(
        self, sessions_data: list[dict]
    ) -> list[TradingSession]:
        """Trading session objects үүсгэх"""
        sessions = []
        for session_data in sessions_data:
            session = TradingSession(
                name=session_data.get("name", "Unknown"),
                start=self._parse_time_string(session_data.get("start", "00:00")),
                end=self._parse_time_string(session_data.get("end", "23:59")),
                enabled=session_data.get("enabled", True),
            )
            sessions.append(session)
        return sessions

    def load_strategy_config(
        self, config_path: str = "configs/strategy.yaml"
    ) -> StrategyConfig:
        """Strategy configuration унших"""
        config_file = Path(config_path)

        if not config_file.exists():
            logger.warning(f"Configuration файл олдсонгүй: {config_path}")
            return StrategyConfig()

        try:
            with open(config_file, encoding="utf-8") as f:
                raw_config = yaml.safe_load(f)

            # Environment variable substitution
            config_data = self._substitute_env_vars(raw_config)

            # Strategy section унших
            strategy_data = config_data.get("strategy", {})
            params_data = strategy_data.get("parameters", {})

            # Trading sessions parse хийх
            sessions_data = params_data.get("trading_sessions", [])
            trading_sessions = self._create_trading_sessions(sessions_data)

            # Strategy parameters үүсгэх
            strategy_params = StrategyParameters(
                ma_fast=params_data.get("ma_fast", 20),
                ma_slow=params_data.get("ma_slow", 50),
                ma_type=params_data.get("ma_type", "sma"),
                rsi_period=params_data.get("rsi_period", 14),
                rsi_oversold=float(params_data.get("rsi_oversold", 30)),
                rsi_overbought=float(params_data.get("rsi_overbought", 70)),
                atr_period=params_data.get("atr_period", 14),
                atr_multiplier_sl=float(params_data.get("atr_multiplier_sl", 2.0)),
                atr_multiplier_tp=float(params_data.get("atr_multiplier_tp", 3.0)),
                min_atr_threshold=float(params_data.get("min_atr_threshold", 0.0001)),
                risk_per_trade=float(params_data.get("risk_per_trade", 0.01)),
                max_open_positions=params_data.get("max_open_positions", 1),
                trading_sessions=trading_sessions,
            )

            # Backtest configuration
            backtest_data = config_data.get("backtest", {})

            # Backtest Data
            data_config = backtest_data.get("data", {})
            bt_data = BacktestData(
                symbol=data_config.get("symbol", "XAUUSD"),
                timeframe=data_config.get("timeframe", "M30"),
                start_date=data_config.get("start_date", "2024-01-01"),
                end_date=data_config.get("end_date", "2024-12-31"),
            )

            # Backtest Account
            account_config = backtest_data.get("account", {})
            bt_account = BacktestAccount(
                initial_balance=float(account_config.get("initial_balance", 10000.0)),
                commission=float(account_config.get("commission", 0.0)),
                spread=float(account_config.get("spread", 2.0)),
                leverage=account_config.get("leverage", 100),
            )

            # Backtest Risk
            risk_config = backtest_data.get("risk", {})
            bt_risk = BacktestRisk(
                max_daily_loss=float(risk_config.get("max_daily_loss", 0.05)),
                max_weekly_loss=float(risk_config.get("max_weekly_loss", 0.15)),
                cooldown_minutes=risk_config.get("cooldown_minutes", 30),
            )

            # Backtest Validation
            validation_config = backtest_data.get("validation", {})
            bt_validation = BacktestValidation(
                in_sample_ratio=float(validation_config.get("in_sample_ratio", 0.7)),
                out_sample_ratio=float(validation_config.get("out_sample_ratio", 0.3)),
                min_trades=validation_config.get("min_trades", 100),
            )

            # Backtest Output
            output_config = backtest_data.get("output", {})
            bt_output = BacktestOutput(
                generate_charts=output_config.get("generate_charts", True),
                save_csv=output_config.get("save_csv", True),
                output_dir=output_config.get("output_dir", "reports"),
            )

            backtest_config = BacktestConfig(
                data=bt_data,
                account=bt_account,
                risk=bt_risk,
                validation=bt_validation,
                output=bt_output,
            )

            # Optimization configuration
            optimization_data = config_data.get("optimization", {})
            optimization_config = OptimizationGrid(
                enabled=optimization_data.get("enabled", False),
                grid=optimization_data.get("grid", {}),
                objective=optimization_data.get("objective", "sharpe_ratio"),
                constraints=optimization_data.get("constraints", {}),
            )

            # Reporting configuration
            reporting_data = config_data.get("reporting", {})
            reporting_config = ReportingConfig(
                formats=reporting_data.get("formats", ["csv", "png"]),
                metrics=reporting_data.get("metrics", []),
                charts=reporting_data.get("charts", {}),
                template=reporting_data.get("template", "default"),
                title_prefix=reporting_data.get("title_prefix", "Backtest Report"),
            )

            # Final StrategyConfig үүсгэх
            config = StrategyConfig(
                name=strategy_data.get("name", "Unknown Strategy"),
                description=strategy_data.get("description", ""),
                version=strategy_data.get("version", "1.0"),
                parameters=strategy_params,
                backtest=backtest_config,
                optimization=optimization_config,
                reporting=reporting_config,
            )

            logger.info(f"Strategy configuration '{config.name}' амжилттай уншигдлаа")
            return config

        except yaml.YAMLError as e:
            logger.error(f"YAML parse алдаа: {e}")
            return StrategyConfig()
        except Exception as e:
            logger.error(f"Configuration унших алдаа: {e}")
            return StrategyConfig()

    def save_strategy_config(
        self,
        config: StrategyConfig,
        output_path: str = "configs/strategy_generated.yaml",
    ) -> bool:
        """Strategy configuration YAML файлд хадгалах"""
        try:
            # Convert to dictionary for YAML output
            config_dict = {
                "strategy": {
                    "name": config.name,
                    "description": config.description,
                    "version": config.version,
                    "parameters": {
                        "ma_fast": config.parameters.ma_fast,
                        "ma_slow": config.parameters.ma_slow,
                        "ma_type": config.parameters.ma_type,
                        "rsi_period": config.parameters.rsi_period,
                        "rsi_oversold": config.parameters.rsi_oversold,
                        "rsi_overbought": config.parameters.rsi_overbought,
                        "atr_period": config.parameters.atr_period,
                        "atr_multiplier_sl": config.parameters.atr_multiplier_sl,
                        "atr_multiplier_tp": config.parameters.atr_multiplier_tp,
                        "min_atr_threshold": config.parameters.min_atr_threshold,
                        "risk_per_trade": config.parameters.risk_per_trade,
                        "max_open_positions": config.parameters.max_open_positions,
                        "trading_sessions": [
                            {
                                "name": session.name,
                                "start": session.start.strftime("%H:%M"),
                                "end": session.end.strftime("%H:%M"),
                                "enabled": session.enabled,
                            }
                            for session in config.parameters.trading_sessions
                        ],
                    },
                },
                "backtest": {
                    "data": {
                        "symbol": config.backtest.data.symbol,
                        "timeframe": config.backtest.data.timeframe,
                        "start_date": config.backtest.data.start_date,
                        "end_date": config.backtest.data.end_date,
                    },
                    "account": {
                        "initial_balance": config.backtest.account.initial_balance,
                        "commission": config.backtest.account.commission,
                        "spread": config.backtest.account.spread,
                        "leverage": config.backtest.account.leverage,
                    },
                    "risk": {
                        "max_daily_loss": config.backtest.risk.max_daily_loss,
                        "max_weekly_loss": config.backtest.risk.max_weekly_loss,
                        "cooldown_minutes": config.backtest.risk.cooldown_minutes,
                    },
                    "validation": {
                        "in_sample_ratio": config.backtest.validation.in_sample_ratio,
                        "out_sample_ratio": config.backtest.validation.out_sample_ratio,
                        "min_trades": config.backtest.validation.min_trades,
                    },
                },
                "optimization": {
                    "enabled": config.optimization.enabled,
                    "grid": config.optimization.grid,
                    "objective": config.optimization.objective,
                    "constraints": config.optimization.constraints,
                },
                "reporting": {
                    "formats": config.reporting.formats,
                    "metrics": config.reporting.metrics,
                    "charts": config.reporting.charts,
                    "template": config.reporting.template,
                    "title_prefix": config.reporting.title_prefix,
                },
            }

            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    config_dict,
                    f,
                    default_flow_style=False,
                    indent=2,
                    allow_unicode=True,
                )

            logger.info(f"Configuration файл хадгалагдлаа: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Configuration хадгалах алдаа: {e}")
            return False


# Convenience functions
def load_config(config_path: str = "configs/strategy.yaml") -> StrategyConfig:
    """Strategy configuration унших convenience function"""
    loader = ConfigLoader()
    return loader.load_strategy_config(config_path)


def save_config(
    config: StrategyConfig, output_path: str = "configs/strategy_generated.yaml"
) -> bool:
    """Strategy configuration хадгалах convenience function"""
    loader = ConfigLoader()
    return loader.save_strategy_config(config, output_path)
