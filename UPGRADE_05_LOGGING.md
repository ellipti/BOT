# Upgrade #05 — Advanced Logging System (JSON + Rotating)

## ✅ COMPLETED FEATURES

### 🎯 JSON Structured Logging

- **JSON Formatter**: All logs formatted as structured JSON for ELK Stack compatibility
- **Structured Data**: Support for extra fields and metadata in log entries
- **ISO Timestamps**: Both human-readable and ISO format timestamps
- **Exception Handling**: Full traceback capture with structured exception data

### 🔄 Daily File Rotation

- **Daily Rotation**: New log files created at midnight (UTC)
- **Retention Management**: Configurable retention period (default: 30 days)
- **File Naming**: `app-YYYY-MM-DD.json` and `errors-YYYY-MM-DD.json` format
- **Automatic Cleanup**: Old log files automatically removed after retention period

### 📊 Multi-Level Logging

- **Console Output**: Human-readable format for development
- **JSON Logs**: Machine-readable structured logs for processing
- **Error Separation**: Separate `errors.json` file for warnings and errors
- **Level Filtering**: Different handlers for different log levels

### 🔔 Enhanced Telegram Alerts

- **Rate Limiting**: Prevents spam with 5-minute cooldown per error type
- **Rich Formatting**: Markdown-formatted alerts with module/function info
- **Error Context**: Exception details and stack traces in alerts
- **Configurable**: Can be enabled/disabled via settings

## 📁 File Structure

```
logs/
├── app.json                 # All log levels (JSON format)
├── errors.json             # Warnings/Errors only (JSON format)
├── app-2025-09-07.json     # Rotated daily files
└── errors-2025-09-07.json  # Rotated error files
```

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Logging configuration
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
LOG_DIRECTORY=logs                # Log file directory
LOG_RETENTION_DAYS=30             # Days to keep log files
LOG_TRADE_LOG_ENABLED=true        # Enable trade audit logging

# Telegram error alerts
TELEGRAM_ERROR_ALERTS=true        # Enable Telegram error notifications
```

### Settings Integration

- Integrated with Pydantic Settings system
- Type-safe configuration with validation
- Environment-based configuration support

## 💻 Usage Examples

### Basic Logging

```python
from logging_setup import setup_advanced_logger

logger = setup_advanced_logger("my_module")
logger.info("Application started")
logger.warning("High memory usage detected")
logger.error("Database connection failed")
```

### Structured Logging

```python
logger.info("Trade executed", extra={
    "symbol": "XAUUSD",
    "side": "BUY",
    "lot_size": 0.1,
    "price": 1985.50,
    "profit": 125.30
})
```

### Context Logger

```python
from logging_setup import get_logger_with_context

logger = get_logger_with_context("trading",
    session_id="sess_001",
    account_id="12345"
)
logger.info("Session started")  # Includes context in all logs
```

## 🎯 JSON Log Format

```json
{
  "timestamp": "2025-09-07 20:43:20,553",
  "timestamp_iso": "2025-09-07T12:43:20.553845+00:00",
  "level": "INFO",
  "logger": "trading_bot",
  "module": "app",
  "function": "run_once",
  "line": 120,
  "message": "Trade signal generated",
  "process_id": 25512,
  "thread_id": 7072,
  "extra": {
    "symbol": "XAUUSD",
    "signal": "BUY",
    "confidence": 0.85,
    "atr": 2.45
  }
}
```

## 🔌 Integration Ready

### ELK Stack (Elasticsearch + Logstash + Kibana)

- JSON format compatible with Logstash ingestion
- Structured fields ready for Elasticsearch indexing
- Time-based indexes supported via ISO timestamps
- Rich querying capabilities with nested data

### Sentry Error Tracking

- Exception context and stack traces
- Release and environment tagging ready
- User context and custom tags support
- Automatic error grouping and alerting

### Log Aggregation Services

- Fluentd/Fluent Bit compatible format
- Datadog, New Relic, Splunk ready
- Custom field extraction supported
- Time-series analysis ready

## 🚀 Performance Features

- **Async-Safe**: Thread-safe logging handlers
- **Memory Efficient**: Streaming JSON without loading entire files
- **Disk Management**: Automatic file rotation prevents disk space issues
- **Network Resilient**: Telegram alerts with retry logic and rate limiting

## 🧪 Testing

Run the comprehensive logging test:

```bash
python test_logging.py
```

Test features:

- ✅ Basic logging levels
- ✅ Structured data logging
- ✅ Context preservation
- ✅ Exception handling with traceback
- ✅ JSON file creation and rotation
- ✅ Multi-handler setup validation

## ✨ Result

**Дуулгасан env-д шууд алдаа, --dry-run/--prod горим ялгарах** ✅

The logging system now provides:

- **Distant Monitoring Ready**: JSON logs compatible with ELK/Sentry
- **File Rotation Management**: Daily rotation with configurable retention
- **Level-based Filtering**: Separate files for errors/warnings vs all logs
- **Production Grade**: Rate-limited alerts, structured data, performance optimized

**UPGRADE #05 — ADVANCED LOGGING SYSTEM: ✅ COMPLETED**
