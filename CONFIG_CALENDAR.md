# Calendar Guard Example Configuration

# .env файлд дараах тохиргоонуудыг нэмнэ үү:

# Economic Calendar Integration

TRADING_CALENDAR_ENABLED=true
TRADING_TRADING_ECONOMICS_API_KEY=your_api_key_here

# Calendar Guard blackout минутуудын тохиргоо:

# EventImportance.LOW: pre=5мин, post=5мин

# EventImportance.MEDIUM: pre=15мин, post=10мин

# EventImportance.HIGH: pre=30мин, post=20мин

# EventImportance.CRITICAL: pre=60мин, post=30мин

# Trading Economics API эсвэл өөр календарь эх үүсвэрээс эдийн засгийн эвентүүдийг татаж авна.

# Жишээ эвентүүд:

# - NFP (Non-Farm Payrolls) - CRITICAL

# - CPI, PPI дата - HIGH

# - GDP өгөгдөл - MEDIUM/HIGH

# - Төв банкуудын мэдэгдэл - CRITICAL

# API түлхүүргүйгээр ч календарь систем ажиллана (offline mode).
