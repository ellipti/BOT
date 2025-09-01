# Trading Bot

This is a MetaTrader 5 trading bot that implements automated trading strategies with Telegram notifications.

## Features

- MetaTrader 5 integration
- Customizable trading strategies
- Telegram notifications
- Logging system
- Configuration management

## Installation

1. Clone the repository
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the bot:
   ```
   python app.py
   ```

## Project Structure

```
├─ app.py              # Main application entry point
├─ requirements.txt    # Python dependencies
├─ .env.example       # Environment variables template
├─ .gitignore        # Git ignore file
├─ README.md         # This file
├─ core/            # Core functionality
│  ├─ config.py    # Configuration management
│  ├─ logger.py    # Logging setup
│  └─ mt5_client.py # MetaTrader 5 client
├─ strategies/      # Trading strategies
│  └─ baseline.py  # Base trading strategy
└─ services/       # External services
   └─ telegram.py  # Telegram notification service
```

## Configuration

See `.env.example` for required configuration parameters.
