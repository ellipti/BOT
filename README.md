# 🤖 Advanced Trading Bot

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

A production-ready automated trading bot for MetaTrader 5 with advanced risk management, real-time notifications, and comprehensive backtesting capabilities.

## ✨ Key Features

- 🔌 **MT5 Integration**: Both attach and headless modes supported
- 🛡️ **Advanced Safety**: Daily limits, position limits, loss protection, news filtering
- 📊 **Smart Analytics**: Technical indicators with visual chart generation
- 💬 **Rich Notifications**: Multi-recipient Telegram alerts with charts and trade details
- 🔍 **Comprehensive Backtesting**: Strategy optimization with performance metrics and visualization
- 🔐 **Security First**: Environment-based configuration, secure credential handling
- 📈 **Production Ready**: Atomic operations, audit trails, 24/7 service deployment
- 🧪 **Quality Assured**: Pre-commit hooks, automated testing, code quality gates

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+** (recommended: 3.12.5)
- **MetaTrader 5** terminal installed
- **Windows OS** (primary support)
- **Virtual environment** support

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/ellipti/BOT.git
cd BOT

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For development (includes testing/linting tools):
pip install -r requirements-dev.txt
```

### 2. Configuration

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
# (see Configuration section below for details)
notepad .env
```

### 3. First Run (Paper Trading)

```bash
# Test MT5 connection
python app.py --diag

# Run in dry-run mode (no real trades)
python app.py

# Test Telegram notifications
python app.py --teletest

# Force a test trade signal
python app.py --force BUY
```

### 4. Production Deployment

```bash
# After thorough testing, enable live trading
# Set DRY_RUN=false in .env file

# Run the bot
python app.py

# Or deploy as Windows service (see Production Deployment section)
```

## ⚙️ Configuration

The bot uses environment variables for configuration. Copy `.env.example` to `.env` and customize:

### Essential Settings

```bash
# MetaTrader 5 Connection
ATTACH_MODE=true                    # Connect to running MT5 terminal
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# Trading Strategy
SYMBOL=XAUUSD                       # Trading instrument
TF_MIN=30                          # 30-minute timeframe
RISK_PCT=0.01                      # 1% risk per trade

# Safety Controls
DRY_RUN=true                       # Paper trading mode
MAX_TRADES_PER_DAY=3               # Daily trade limit
MAX_DAILY_LOSS_PCT=0.05            # 5% daily loss limit

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Complete Configuration Guide

See [.env.example](./.env.example) for comprehensive configuration options with detailed explanations.

## 🎯 Trading Strategy

The bot implements a baseline strategy with:

- **MA Crossover**: Fast/slow moving average signals
- **RSI Filter**: Momentum confirmation (20-80 range)
- **ATR Position Sizing**: Volatility-based risk management
- **News Avoidance**: Economic calendar integration
- **Session Filtering**: Trade only during high-liquidity sessions

### Risk Management

- **Stop Loss**: 1.5x ATR distance (configurable)
- **Take Profit**: 3.0x ATR distance (2:1 risk-reward)
- **Position Sizing**: Percentage-based risk calculation
- **Daily Limits**: Prevent overtrading and excessive losses
- **Cooldown Periods**: Minimum time between trades

## 📊 Backtesting

```bash
# Run comprehensive backtest
python test_backtest.py

# Generate optimization charts
python test_optimization_charts.py

# View results in reports/ directory
ls reports/
```

### Backtest Features

- **Historical Analysis**: Test strategies on past data
- **Performance Metrics**: Win rate, profit factor, max drawdown
- **Visual Reports**: Equity curves, trade distribution, performance dashboard
- **Parameter Optimization**: Find optimal strategy settings

## 💬 Telegram Integration

Set up rich notifications with charts and trade details:

1. **Create Bot**: Message @BotFather on Telegram
2. **Get Token**: Save the bot token from BotFather
3. **Get Chat ID**: Message @userinfobot to get your chat ID
4. **Configure**: Add token and chat ID to .env file

### Notification Features

- 📈 **Trade Alerts**: Entry, exit, and update notifications
- 📊 **Performance Charts**: Technical analysis with overlays
- 🚨 **Error Alerts**: System issues and failures
- 📋 **Daily Summaries**: Performance reports and statistics

## 🏗️ Production Deployment

### Method 1: Windows Task Scheduler

Create a batch file `run_bot.bat`:

```batch
@echo off
cd /d "D:\BOT\BOT"
call .venv\Scripts\activate.bat
python app.py
```

Schedule in Task Scheduler:

1. Open Task Scheduler → Create Basic Task
2. Set trigger: Daily, repeat every 1 minute
3. Action: Start program → `D:\BOT\BOT\run_bot.bat`
4. Configure: Run with highest privileges
5. Settings: Allow task to be run on demand

### Method 2: NSSM (Non-Sucking Service Manager)

```bash
# Download and install NSSM
# https://nssm.cc/download

# Install as Windows service
nssm install TradingBot "D:\BOT\BOT\.venv\Scripts\python.exe"
nssm set TradingBot Parameters "D:\BOT\BOT\app.py"
nssm set TradingBot AppDirectory "D:\BOT\BOT"
nssm set TradingBot DisplayName "Trading Bot Service"
nssm set TradingBot Description "Automated Trading Bot with MT5 Integration"

# Start the service
nssm start TradingBot

# Check status
nssm status TradingBot
```

### Method 3: Docker (Advanced)

```dockerfile
# Dockerfile example
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "app.py"]
```

## 🧪 Development

### Code Quality

The project uses automated code quality tools:

```bash
# Format code
black .
isort .

# Lint code
ruff check .

# Security scan
bandit -r .

# Run all quality checks
pre-commit run --all-files
```

### Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test categories
pytest -m "not slow"           # Skip slow tests
pytest -m integration          # Integration tests only
pytest -m unit                # Unit tests only
```

### Adding Dependencies

```bash
# Add to requirements.in (production) or requirements-dev.in (development)
echo "new-package==1.0.0" >> requirements.in

# Compile locked versions
pip-compile requirements.in
pip-compile requirements-dev.in

# Install updated dependencies
pip-sync requirements-dev.txt
```

## 📁 Project Structure

```
├── app.py                    # Main application entry point
├── safety_gate.py           # Trading safety features & limits
├── logging_setup.py         # Centralized logging configuration
├── .env.example             # Environment configuration template
├── pyproject.toml           # Project metadata and tool configuration
├── requirements*.txt        # Locked dependencies
├──
├── core/                    # Core trading engine
│   ├── config.py           # Configuration management
│   ├── logger.py           # Logging utilities
│   ├── mt5_client.py       # MetaTrader 5 integration
│   ├── trade_executor.py   # Order execution logic
│   ├── state.py           # Persistent state management
│   └── vision_*.py        # Chart analysis and vision context
├──
├── services/               # External service integrations
│   ├── telegram_*.py      # Telegram notifications
│   ├── chart_renderer.py  # Technical chart generation
│   └── vision_context.py  # Market context analysis
├──
├── strategies/            # Trading strategies
│   ├── baseline.py       # Default MA crossover + RSI strategy
│   └── indicators.py    # Technical analysis indicators
├──
├── risk/                 # Risk management
│   ├── governor.py      # Risk oversight and limits
│   ├── validator.py     # Signal validation
│   └── session.py       # Trading session management
├──
├── integrations/         # External API integrations
│   └── calendar.py      # Economic calendar (Trading Economics)
├──
├── backtest/            # Backtesting engine
│   ├── runner.py       # Backtest execution
│   ├── chart_renderer.py # Performance visualization
│   └── config_loader.py # Strategy configuration
├──
├── utils/               # Utilities
│   ├── mt5_exec.py     # MT5 execution helpers
│   └── atomic_io.py    # Atomic file operations
├──
├── state/              # Persistent data
│   ├── limits.json    # Trading limits state
│   └── *.json.backup  # State backups
├──
├── logs/              # Application logs
├── charts/            # Generated technical charts
├── reports/           # Backtest and performance reports
└── configs/           # Strategy configurations
```

## 🔐 Security Considerations

### Environment Security

- ✅ Never commit `.env` files to version control
- ✅ Use strong, unique passwords for MT5 accounts
- ✅ Regularly rotate Telegram bot tokens
- ✅ Monitor logs for suspicious activity

### Trading Security

- ✅ Always start with `DRY_RUN=true`
- ✅ Test extensively before live trading
- ✅ Start with small position sizes
- ✅ Use conservative risk settings initially
- ✅ Monitor performance daily

### Production Security

- ✅ Run with minimal system privileges
- ✅ Use dedicated MT5 demo accounts for testing
- ✅ Implement proper backup procedures
- ✅ Set up monitoring and alerting

## 📈 Performance Optimization

### System Requirements

- **CPU**: Multi-core processor (chart generation is CPU-intensive)
- **RAM**: 4GB+ (8GB recommended for backtesting)
- **Storage**: SSD recommended for faster I/O operations
- **Network**: Stable internet connection for MT5 and APIs

### Optimization Tips

- Use 30-minute or higher timeframes for reduced CPU usage
- Disable chart generation (`GENERATE_CHARTS=false`) for better performance
- Implement proper log rotation to prevent disk space issues
- Monitor memory usage during backtesting operations

## 🆘 Troubleshooting

### Common Issues

**MT5 Connection Failed**

```bash
# Check MT5 terminal is running (attach mode)
# Verify credentials (login mode)
python app.py --diag
```

**Telegram Notifications Not Working**

```bash
# Test Telegram configuration
python app.py --teletest

# Check bot token and chat ID in .env
```

**Trading Not Executing**

```bash
# Verify DRY_RUN setting
# Check daily limits not exceeded
# Ensure trading session is active
# Review safety gate logs
```

**Performance Issues**

```bash
# Disable chart generation temporarily
# Check available disk space
# Monitor CPU and memory usage
# Review log file sizes
```

### Getting Help

1. **Check Logs**: Review `logs/` directory for error details
2. **Run Diagnostics**: Use `python app.py --diag`
3. **GitHub Issues**: Report bugs with detailed environment info
4. **Documentation**: See inline code comments and docstrings

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**⚠️ Trading Disclaimer**: This software is for educational purposes. Trading involves substantial risk. Past performance is not indicative of future results. Always test thoroughly before live trading.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with tests
4. Run quality checks (`pre-commit run --all-files`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines (enforced by Black)
- Add tests for new functionality
- Update documentation for user-facing changes
- Use semantic commit messages
- Ensure all quality checks pass

---

## 📊 Status Dashboard

| Component        | Status    | Version | Coverage |
| ---------------- | --------- | ------- | -------- |
| Core Engine      | ✅ Stable | 1.2.0   | 85%      |
| MT5 Integration  | ✅ Stable | 1.2.0   | 90%      |
| Risk Management  | ✅ Stable | 1.2.0   | 95%      |
| Telegram Alerts  | ✅ Stable | 1.2.0   | 80%      |
| Backtesting      | ✅ Stable | 1.2.0   | 85%      |
| Chart Generation | ✅ Stable | 1.2.0   | 75%      |

**Last Updated**: September 7, 2025
**Next Release**: v1.3.0 (Enhanced AI integration)

Made with ❤️ for the trading community
