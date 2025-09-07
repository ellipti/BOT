# 📋 Trading Bot Production Runbook

This runbook provides comprehensive guidance for deploying, monitoring, and maintaining the Trading Bot in production environments.

## 🚀 Production Deployment Guide

### Prerequisites

- Windows 10/11 or Windows Server 2019+
- Python 3.11+ installed and configured
- MetaTrader 5 terminal installed
- Administrative access for service installation
- Stable internet connection
- Sufficient disk space (minimum 10GB recommended)

### Pre-Deployment Checklist

- [ ] Trading Bot tested thoroughly in demo environment
- [ ] All configuration parameters validated
- [ ] Backup and recovery procedures tested
- [ ] Monitoring and alerting configured
- [ ] Emergency contact procedures established
- [ ] Risk management parameters set conservatively

## 🏗️ Deployment Methods

### Method 1: Windows Task Scheduler (Recommended for Simple Deployments)

#### 1. Prepare the Environment

```batch
# Create dedicated directory
mkdir C:\TradingBot
cd C:\TradingBot

# Clone the repository
git clone https://github.com/ellipti/BOT.git .

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt
```

#### 2. Configure Environment

```batch
# Copy and configure .env file
copy .env.example .env
notepad .env
```

Essential production settings:

```bash
# Production Configuration
DRY_RUN=false
ATTACH_MODE=true
LOG_LEVEL=INFO
MAX_TRADES_PER_DAY=3
MAX_DAILY_LOSS_PCT=0.03
TRADING_SESSION=LDN_NY

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your_production_token
TELEGRAM_CHAT_ID=your_production_chat_id
TELEGRAM_SEND_CHARTS=true
```

#### 3. Create Startup Script

Create `C:\TradingBot\run_bot.bat`:

```batch
@echo off
REM Trading Bot Startup Script
REM Timestamp: %date% %time%

cd /d "C:\TradingBot"
echo [%date% %time%] Starting Trading Bot...

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check Python availability
python --version
if errorlevel 1 (
    echo [%date% %time%] ERROR: Python not available
    exit /b 1
)

REM Check MT5 terminal (if in attach mode)
tasklist /fi "imagename eq terminal64.exe" | find "terminal64.exe" >nul
if errorlevel 1 (
    echo [%date% %time%] WARNING: MT5 terminal not running
)

REM Start the bot
echo [%date% %time%] Launching Trading Bot...
python app.py

echo [%date% %time%] Trading Bot session ended
```

#### 4. Configure Task Scheduler

1. **Open Task Scheduler** (taskschd.msc)
2. **Create Basic Task**:
   - Name: "TradingBot"
   - Description: "Automated Trading Bot for MT5"
   - Trigger: Daily
   - Start time: 00:01 (1 minute past midnight)
   - Repeat: Every 5 minutes
   - Duration: 1 day
3. **Action**: Start a program
   - Program: `C:\TradingBot\run_bot.bat`
   - Start in: `C:\TradingBot`
4. **Conditions**:
   - ✅ Start only if computer is on AC power (uncheck for laptop)
   - ✅ Wake computer to run task
5. **Settings**:
   - ✅ Allow task to be run on demand
   - ✅ Run with highest privileges
   - If running task fails, restart every: 1 minute
   - Attempt restart up to: 3 times

#### 5. Test and Verify

```batch
# Test manual execution
C:\TradingBot\run_bot.bat

# Check Task Scheduler history
# Task Scheduler > Task Scheduler Library > TradingBot > History

# Monitor logs
dir C:\TradingBot\logs
```

### Method 2: NSSM Service (Recommended for Production)

#### 1. Download and Install NSSM

```batch
# Download NSSM from https://nssm.cc/download
# Extract to C:\nssm (or your preferred location)
# Add C:\nssm\win64 to PATH environment variable
```

#### 2. Install Service

```batch
# Open Command Prompt as Administrator
cd C:\TradingBot

# Install Trading Bot as Windows Service
nssm install TradingBot "C:\TradingBot\.venv\Scripts\python.exe"
nssm set TradingBot Parameters "C:\TradingBot\app.py"
nssm set TradingBot AppDirectory "C:\TradingBot"
nssm set TradingBot DisplayName "Trading Bot Service"
nssm set TradingBot Description "Automated Trading Bot with MT5 Integration"

# Configure service recovery
nssm set TradingBot AppThrottle 15000
nssm set TradingBot AppRestartDelay 30000
nssm set TradingBot AppExit Default Restart

# Set service to start automatically
nssm set TradingBot Start SERVICE_AUTO_START

# Configure I/O redirection
nssm set TradingBot AppStdout "C:\TradingBot\logs\service_stdout.log"
nssm set TradingBot AppStderr "C:\TradingBot\logs\service_stderr.log"
nssm set TradingBot AppRotateFiles 1
nssm set TradingBot AppRotateOnline 1
nssm set TradingBot AppRotateSeconds 86400
nssm set TradingBot AppRotateBytes 10485760
```

#### 3. Start and Verify Service

```batch
# Start the service
nssm start TradingBot

# Check service status
nssm status TradingBot
sc query TradingBot

# View service logs
type C:\TradingBot\logs\service_stdout.log
```

#### 4. Service Management Commands

```batch
# Stop service
nssm stop TradingBot

# Restart service
nssm restart TradingBot

# Remove service (if needed)
nssm remove TradingBot confirm

# Edit service configuration
nssm edit TradingBot
```

### Method 3: Docker Deployment (Advanced)

#### 1. Create Dockerfile

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 tradingbot && \
    chown -R tradingbot:tradingbot /app
USER tradingbot

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# Run the application
CMD ["python", "app.py"]
```

#### 2. Docker Compose Configuration

```yaml
version: "3.8"

services:
  trading-bot:
    build: .
    container_name: trading-bot
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./state:/app/state
      - ./charts:/app/charts
      - ./reports:/app/reports
    networks:
      - trading-network
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    container_name: trading-redis
    restart: unless-stopped
    volumes:
      - redis_data:/data
    networks:
      - trading-network

  postgres:
    image: postgres:15-alpine
    container_name: trading-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: trading_bot
      POSTGRES_USER: trading_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - trading-network

volumes:
  redis_data:
  postgres_data:

networks:
  trading-network:
    driver: bridge
```

## 📊 Monitoring and Alerting

### Log Monitoring

#### 1. Log Locations

```batch
# Application logs
C:\TradingBot\logs\trading_bot.log

# Service logs (NSSM)
C:\TradingBot\logs\service_stdout.log
C:\TradingBot\logs\service_stderr.log

# Windows Event Logs
# Event Viewer > Windows Logs > Application
# Look for "TradingBot" source
```

#### 2. Key Metrics to Monitor

- **Trading Performance**:

  - Daily P&L
  - Win rate
  - Number of trades executed
  - Risk metrics (drawdown, exposure)

- **System Health**:

  - CPU usage
  - Memory consumption
  - Disk space
  - Network connectivity

- **Application Status**:
  - Error rates
  - Response times
  - MT5 connection status
  - Telegram notification delivery

#### 3. Automated Monitoring Script

Create `C:\TradingBot\monitor.ps1`:

```powershell
# Trading Bot Monitoring Script
param(
    [string]$AlertEmail = "admin@yourcompany.com",
    [string]$LogPath = "C:\TradingBot\logs\trading_bot.log"
)

# Check if service is running
$service = Get-Service -Name "TradingBot" -ErrorAction SilentlyContinue
if ($service.Status -ne "Running") {
    Send-MailMessage -To $AlertEmail -Subject "ALERT: Trading Bot Service Down" -Body "Trading Bot service is not running. Status: $($service.Status)"
    Write-Host "ALERT: Service is down"
    exit 1
}

# Check recent log entries for errors
$recentErrors = Get-Content $LogPath | Select-String "ERROR" | Select-Object -Last 10
if ($recentErrors.Count -gt 5) {
    Send-MailMessage -To $AlertEmail -Subject "ALERT: High Error Rate in Trading Bot" -Body "Recent errors detected:`n$($recentErrors -join "`n")"
    Write-Host "ALERT: High error rate detected"
}

# Check disk space
$disk = Get-WmiObject -Class Win32_LogicalDisk -Filter "DeviceID='C:'"
$freeSpaceGB = [math]::Round($disk.FreeSpace / 1GB, 2)
if ($freeSpaceGB -lt 5) {
    Send-MailMessage -To $AlertEmail -Subject "ALERT: Low Disk Space" -Body "Free space on C: drive: $freeSpaceGB GB"
    Write-Host "ALERT: Low disk space: $freeSpaceGB GB"
}

Write-Host "Monitoring check completed successfully"
```

Schedule this script to run every 15 minutes using Task Scheduler.

### Performance Dashboards

#### 1. Key Performance Indicators (KPIs)

```
┌─────────────────────────────────────────────────────┐
│ 📊 Trading Bot Performance Dashboard               │
├─────────────────────────────────────────────────────┤
│ Daily P&L: +$234.56 (2.34%)                       │
│ Total Trades: 3/3 limit                           │
│ Win Rate: 66.7% (2W / 1L)                         │
│ Current Drawdown: 1.2%                            │
│ Max Daily Drawdown: 3.5%                          │
├─────────────────────────────────────────────────────┤
│ System Status: ✅ Online                           │
│ MT5 Connection: ✅ Connected                       │
│ Last Trade: 14:30 UTC                             │
│ Next Check: 15:00 UTC                             │
├─────────────────────────────────────────────────────┤
│ Risk Metrics:                                      │
│ • Position Size: 0.1 lots                         │
│ • Account Exposure: 1.2%                          │
│ • Margin Used: 3.4%                               │
│ • Free Margin: $4,850.00                          │
└─────────────────────────────────────────────────────┘
```

#### 2. Daily Report Template

Create automated daily reports:

```
📈 Trading Bot Daily Report - September 7, 2025

PERFORMANCE SUMMARY:
├─ Total Trades: 2
├─ Winning Trades: 1 (50.0%)
├─ Daily P&L: +$89.50 (+0.89%)
├─ Cumulative P&L: +$1,245.67 (+12.46%)
└─ Max Drawdown: 2.1%

TRADE DETAILS:
1. XAUUSD BUY @ 1945.50 → SELL @ 1952.30 (+$68.00)
2. XAUUSD SELL @ 1955.20 → COVER @ 1960.10 (-$49.00)

RISK METRICS:
├─ Account Balance: $10,245.67
├─ Equity: $10,189.23
├─ Margin Level: 1,234%
└─ Risk per Trade: 1.0%

SYSTEM STATUS:
├─ Service Uptime: 23h 45m
├─ MT5 Connection: Stable
├─ Telegram Alerts: 4 sent
└─ Errors: 0

NEXT ACTIONS:
• Continue monitoring market conditions
• Review strategy performance weekly
• Update risk parameters if needed
```

## 🚨 Emergency Procedures

### Emergency Shutdown

#### 1. Immediate Stop (Manual)

```batch
# Stop Windows Service
net stop TradingBot

# Or via NSSM
nssm stop TradingBot

# Kill all Python processes (emergency)
taskkill /f /im python.exe
```

#### 2. Market Emergency Response

1. **High Volatility Event**:

   - Monitor positions closely
   - Consider reducing position sizes
   - Increase stop-loss levels temporarily
   - Halt new position openings

2. **News Event Impact**:

   - Pause trading until volatility subsides
   - Review open positions
   - Adjust risk parameters if necessary
   - Document event for future reference

3. **Technical Issues**:
   - Switch to manual trading if critical
   - Backup current state
   - Investigate and resolve issues
   - Test thoroughly before resuming

#### 3. Emergency Contact List

```
Primary On-Call: John Doe <john@company.com> +1-555-0123
Secondary: Jane Smith <jane@company.com> +1-555-0124
Broker Support: +1-800-BROKER-1
IT Support: +1-555-0125
```

### Disaster Recovery

#### 1. Backup Procedures

**Daily Automated Backup**:

```batch
@echo off
REM Daily backup script
set BACKUP_DIR=D:\TradingBot_Backups\%date:~-4,4%%date:~-10,2%%date:~-7,2%
mkdir "%BACKUP_DIR%"

REM Backup critical files
xcopy "C:\TradingBot\state\*" "%BACKUP_DIR%\state\" /s /i /y
xcopy "C:\TradingBot\.env" "%BACKUP_DIR%\" /y
xcopy "C:\TradingBot\logs\*" "%BACKUP_DIR%\logs\" /s /i /y

REM Backup database (if applicable)
REM sqlcmd -S localhost -E -Q "BACKUP DATABASE TradingBot TO DISK='%BACKUP_DIR%\trading_bot.bak'"

echo Backup completed: %BACKUP_DIR%
```

**Cloud Backup** (PowerShell):

```powershell
# Upload to cloud storage (Azure/AWS/GCloud)
# Example for Azure Blob Storage
$storageAccount = "yourstorageaccount"
$containerName = "trading-bot-backups"
$backupFile = "trading_bot_backup_$(Get-Date -Format 'yyyyMMdd').zip"

# Create zip archive
Compress-Archive -Path "C:\TradingBot\state\*" -DestinationPath "C:\temp\$backupFile"

# Upload to cloud (requires Azure CLI or SDK)
# az storage blob upload --account-name $storageAccount --container-name $containerName --name $backupFile --file "C:\temp\$backupFile"
```

#### 2. Recovery Procedures

**Full System Recovery**:

1. Install Python and dependencies on new system
2. Restore application files from Git repository
3. Restore configuration files from backup
4. Restore state files from most recent backup
5. Verify MT5 connection and credentials
6. Test in dry-run mode before going live
7. Monitor closely for 24 hours after recovery

**State Recovery Only**:

1. Stop trading bot service
2. Backup current state (if corrupted)
3. Restore state files from backup
4. Verify state file integrity
5. Restart service and monitor

## 🔧 Maintenance Procedures

### Regular Maintenance Tasks

#### Daily (Automated)

- [ ] Health check monitoring
- [ ] Log file rotation
- [ ] Performance metrics collection
- [ ] Backup state files
- [ ] Check system resources

#### Weekly (Manual)

- [ ] Review trading performance
- [ ] Analyze log files for warnings
- [ ] Update risk parameters if needed
- [ ] Check for software updates
- [ ] Verify backup integrity

#### Monthly (Manual)

- [ ] Full system backup
- [ ] Security audit (credentials, access)
- [ ] Performance optimization review
- [ ] Documentation updates
- [ ] Strategy review and backtesting

### Software Updates

#### 1. Update Procedure

```batch
# 1. Create backup
C:\TradingBot\scripts\backup.bat

# 2. Stop service
nssm stop TradingBot

# 3. Update code
cd C:\TradingBot
git fetch origin
git checkout main
git pull origin main

# 4. Update dependencies
.venv\Scripts\activate.bat
pip install -r requirements.txt --upgrade

# 5. Test in dry-run mode
echo DRY_RUN=true > .env.test
python app.py --config .env.test

# 6. If tests pass, restart service
nssm start TradingBot
```

#### 2. Rollback Procedure

```batch
# 1. Stop service
nssm stop TradingBot

# 2. Rollback code
git checkout <previous_version_tag>

# 3. Restore dependencies
pip install -r requirements.txt --force-reinstall

# 4. Restore configuration
copy C:\TradingBot_Backups\latest\.env C:\TradingBot\.env

# 5. Restart service
nssm start TradingBot
```

### Configuration Management

#### 1. Environment-Specific Configs

```
C:\TradingBot\configs\
├── production.env      # Live trading configuration
├── staging.env         # Testing environment
├── development.env     # Development settings
└── emergency.env       # Emergency/safe mode settings
```

#### 2. Configuration Validation

```python
# config_validator.py
import os
from typing import List

def validate_config(env_file: str) -> List[str]:
    """Validate trading bot configuration"""
    errors = []

    # Load environment file
    with open(env_file, 'r') as f:
        config = dict(line.strip().split('=', 1)
                     for line in f if line.strip() and not line.startswith('#'))

    # Required settings
    required = ['SYMBOL', 'RISK_PCT', 'TELEGRAM_BOT_TOKEN']
    for key in required:
        if key not in config:
            errors.append(f"Missing required setting: {key}")

    # Risk validation
    if 'RISK_PCT' in config:
        risk = float(config['RISK_PCT'])
        if risk > 0.05:  # 5% max risk
            errors.append(f"Risk too high: {risk*100}% (max 5%)")

    # Dry run check for production
    if env_file.endswith('production.env'):
        if config.get('DRY_RUN', 'true').lower() == 'true':
            errors.append("Production config has DRY_RUN=true")

    return errors

# Usage
errors = validate_config('C:\TradingBot\.env')
if errors:
    print("Configuration errors found:")
    for error in errors:
        print(f"  - {error}")
else:
    print("Configuration validation passed")
```

## 🎯 Performance Optimization

### System Optimization

#### 1. Windows Performance Settings

```batch
REM Disable Windows Defender real-time scanning for trading directory
powershell -Command "Add-MpPreference -ExclusionPath 'C:\TradingBot'"

REM Set high performance power plan
powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

REM Disable automatic updates during trading hours
REM Use Group Policy Editor (gpedit.msc) to configure update hours
```

#### 2. Process Priority

```batch
REM Set high priority for trading bot process
wmic process where name="python.exe" CALL setpriority "above normal"
```

#### 3. Memory Optimization

- Monitor memory usage with Process Monitor
- Configure appropriate Python garbage collection
- Implement memory profiling for large backtests
- Use memory-mapped files for large datasets

### Application Optimization

#### 1. Chart Generation

```python
# Optimize chart generation
GENERATE_CHARTS=false  # Disable in production for performance
CHART_CACHE_SIZE=100   # Limit chart cache
CHART_DPI=72          # Lower DPI for smaller files
```

#### 2. Database Optimization

```python
# SQLite optimization
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=memory;
```

## 📋 Troubleshooting Guide

### Common Issues and Solutions

#### 1. Service Won't Start

**Symptoms**: NSSM service fails to start, Task Scheduler task fails

**Diagnosis**:

```batch
# Check service status
nssm status TradingBot

# Check event logs
eventvwr.msc
# Navigate to Windows Logs > Application
# Look for TradingBot errors

# Test manual execution
cd C:\TradingBot
.venv\Scripts\activate.bat
python app.py --diag
```

**Solutions**:

- Verify Python installation and virtual environment
- Check file permissions (service account access)
- Validate .env configuration
- Ensure MT5 terminal is running (attach mode)
- Check network connectivity

#### 2. MT5 Connection Issues

**Symptoms**: "MT5 connection failed", "Terminal not available"

**Diagnosis**:

```batch
# Check MT5 process
tasklist | findstr terminal64.exe

# Test MT5 Python package
python -c "import MetaTrader5 as mt5; print(mt5.initialize())"
```

**Solutions**:

- Restart MT5 terminal
- Verify login credentials
- Check broker server status
- Switch between attach/login modes
- Update MT5 terminal version

#### 3. Telegram Notifications Not Working

**Symptoms**: No Telegram messages received

**Diagnosis**:

```batch
# Test Telegram configuration
python app.py --teletest

# Check network connectivity
ping api.telegram.org
```

**Solutions**:

- Verify bot token and chat ID
- Check bot permissions in chat
- Test with @userinfobot to confirm chat ID
- Review firewall/proxy settings
- Check Telegram API rate limits

#### 4. High Memory Usage

**Symptoms**: System becomes slow, memory usage increases over time

**Diagnosis**:

```python
# Memory profiling
pip install memory-profiler
python -m memory_profiler app.py
```

**Solutions**:

- Restart service daily (scheduled task)
- Implement memory monitoring
- Optimize chart generation settings
- Clear old log files regularly
- Use memory-efficient data structures

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# .env configuration for debugging
LOG_LEVEL=DEBUG
DEBUG_ENABLED=true

# Additional debug outputs
MT5_DEBUG=true
TELEGRAM_DEBUG=true
CHART_DEBUG=true
```

Debug log analysis:

```python
# log_analyzer.py
import re
from collections import Counter

def analyze_logs(log_file: str):
    """Analyze log patterns for troubleshooting"""
    with open(log_file, 'r') as f:
        logs = f.readlines()

    # Count error types
    errors = [line for line in logs if 'ERROR' in line]
    error_patterns = Counter(re.findall(r'ERROR.*?:', '\n'.join(errors)))

    print(f"Total log entries: {len(logs)}")
    print(f"Error entries: {len(errors)}")
    print("\nTop error patterns:")
    for pattern, count in error_patterns.most_common(5):
        print(f"  {pattern}: {count}")

    # Memory usage trends
    memory_lines = [line for line in logs if 'Memory usage' in line]
    if memory_lines:
        print(f"\nMemory usage entries: {len(memory_lines)}")
        print("Latest memory usage:", memory_lines[-1].strip())

# Usage
analyze_logs('C:\\TradingBot\\logs\\trading_bot.log')
```

---

## ✅ Production Checklist

Before going live with real money:

### Pre-Production Testing

- [ ] All features tested in demo environment
- [ ] Backtesting completed with satisfactory results
- [ ] Risk management parameters validated
- [ ] Emergency procedures tested
- [ ] Monitoring and alerting configured
- [ ] Backup and recovery procedures verified

### Configuration Review

- [ ] `DRY_RUN=false` set only after thorough testing
- [ ] Conservative risk settings applied
- [ ] Production credentials configured
- [ ] Telegram notifications working
- [ ] Log levels appropriate for production

### Infrastructure Setup

- [ ] Service deployment method chosen and tested
- [ ] Monitoring scripts deployed
- [ ] Backup procedures automated
- [ ] Emergency contact list updated
- [ ] Documentation current and accessible

### Go-Live Process

- [ ] Deploy during low-volatility period
- [ ] Monitor closely for first 24 hours
- [ ] Verify first trades execute correctly
- [ ] Confirm all alerts and notifications working
- [ ] Document any issues for future reference

---

This runbook provides comprehensive guidance for production deployment and maintenance. Regular updates should be made based on operational experience and lessons learned.
