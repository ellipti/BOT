# Trading Bot

MT5-based automated trading bot with safety features and audit capabilities.

## Setup

### Prerequisites

- Python 3.11+
- MetaTrader 5 terminal
- Virtual environment support

### Installation

1. Clone the repository:

```bash
git clone https://github.com/ellipti/BOT.git
cd BOT
```

2. Create and activate virtual environment:

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

3. Install dependencies:

```bash
# Production environment
pip install -r requirements.txt

# Development environment (includes testing/linting tools)
pip install -r requirements-dev.txt
```

### Configuration

1. Create `.env` file with your settings:

```bash
# Example .env configuration
MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_LOGIN=942138
MT5_PASSWORD=your_password
MT5_SERVER=MOTForex-Demo-1
ATTACH_MODE=true

SYMBOL=XAUUSD
TF_MIN=30
RISK_PCT=0.01
SL_MULT=1.5
TP_MULT=3.0
DRY_RUN=true

TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Running

```bash
# Run the bot
python app.py

# Force a trade (testing)
python app.py --force BUY

# Run diagnostics
python app.py --diag

# Test Telegram
python app.py --teletest
```

## Development

### Adding Dependencies

1. Add new dependencies to `requirements.in` (production) or `requirements-dev.in` (development)
2. Compile locked versions:

```bash
pip-compile requirements.in
pip-compile requirements-dev.in
```

3. Install updated dependencies:

```bash
pip-sync requirements-dev.txt
```

### Testing

```bash
pytest
```

### Code Quality

```bash
black .          # Format code
isort .          # Sort imports
flake8 .         # Lint code
mypy .           # Type checking
```

## Features

- **MT5 Integration**: Both attach and headless modes
- **Safety Gates**: Position limits, daily limits, loss protection
- **Trade Audit**: CSV logging of all trades
- **Telegram Notifications**: Multi-recipient support with charts
- **Chart Generation**: Technical analysis with overlays
- **Force Trading**: CLI override for testing
- **Reproducible Builds**: Locked dependencies with pip-tools

## Safety Features

- Daily trade limits (MAX_TRADES_PER_DAY)
- Daily loss limits (MAX_DAILY_LOSS_PCT)
- Position count limits (MAX_OPEN_POSITIONS)
- Session time validation
- Cooldown periods between trades
- News event filtering (Trading Economics)
- ATR-based position sizing

## Project Structure

```
├── app.py                 # Main application
├── settings.py           # Configuration management (Pydantic)
├── safety_gate.py        # Trading safety features & limits
├── core/                 # Core MT5 client & logging
├── services/             # External integrations (Telegram, charts)
├── strategies/           # Trading strategies & indicators
├── utils/                # Utilities (order execution)
├── state/                # Persistent state files
└── requirements*.txt     # Dependencies (pip-tools)
```
