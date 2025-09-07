# Log Redaction System Documentation

## Overview

The log redaction system provides security protection against accidental logging of sensitive information such as API keys, passwords, tokens, and other credentials. This is implemented through a logging filter that automatically detects and masks sensitive data patterns before they are written to log files or output streams.

## Architecture

### Core Components

1. **RedactionFilter Class** (`logging_setup.py`)

   - Python logging filter that processes log messages
   - Applies regex patterns to detect sensitive data
   - Replaces sensitive values with `****` markers
   - Tracks redaction statistics

2. **Sensitive Key Patterns**
   - 17 base sensitive keys: `token`, `api_key`, `password`, `secret`, `mt5_password`, `telegram_token`, `te_api_key`, `bot_token`, `auth_token`, `access_token`, `refresh_token`, `private_key`, `certificate`, `credential`, `login`, `pin`, `otp`
   - 4 additional specialized patterns for JWT tokens, Bearer tokens, API keys, and URLs with credentials
   - **Total: 21+ redaction patterns**

### Pattern Matching Strategy

The redaction system uses compiled regex patterns to detect:

1. **Key-Value Pairs**: `key=value` or `key: value` formats
2. **JWT Tokens**: Patterns starting with `eyJ` (Base64 JWT header)
3. **Bearer Tokens**: `Bearer <token>` format
4. **API Keys**: Common API key formats (`sk_`, `AIza`, etc.)
5. **URLs with Credentials**: `https://user:password@host` format

## Security Features

### What Gets Redacted

✅ **Protected Patterns:**

```
telegram_token=1234567890:AAABBBCCCdddEEE          → telegram_token=****
TE_API_KEY=sk_live_9cA7xZQ12abcdef               → TE_API_KEY=****
password=MySecretPassword123                      → password=****
secret: A1b2C3d4E5f6g7h8i9j0                     → secret: ****
Bearer abc123xyz789token                          → Bearer ****
https://user:password123@api.example.com         → https://user:****@api.example.com
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload   → eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.****
```

### What Stays Unchanged

✅ **Normal Log Messages:**

```
User logged in successfully
Processing EURUSD order for 0.1 lots
Connection to broker established
API endpoint /api/v1/orders called
Token validation completed successfully
Order ID 12345 executed at price 1.0950
```

### Limitations

⚠️ **Current Limitations:**

- Secrets embedded in sentences without key=value format may not be caught
- Very short values (< 6 characters) are not redacted to avoid false positives
- Custom secret formats not covered by existing patterns

## Test Coverage

### Comprehensive Unit Tests (`tests/test_logging_redaction.py`)

The test suite provides comprehensive coverage with **13 test cases**:

#### 1. Core Functionality Tests

- ✅ `test_sensitive_data_redaction` - Validates core sensitive patterns are masked
- ✅ `test_normal_strings_not_redacted` - Ensures no false positives
- ✅ `test_redaction_patterns_compilation` - Verifies all 21+ patterns compile correctly

#### 2. Format Variation Tests

- ✅ `test_redaction_with_different_formats` - Tests various key=value formats
- ✅ `test_sentence_embedded_secrets` - Documents behavior with embedded secrets
- ✅ `test_redaction_with_log_formatting` - Tests with Python string formatting

#### 3. Specialized Pattern Tests

- ✅ `test_jwt_token_redaction` - JWT token handling
- ✅ `test_url_credential_redaction` - URL credential masking
- ✅ `test_edge_cases` - Boundary conditions and special cases

#### 4. System Integration Tests

- ✅ `test_redaction_statistics` - Validates redaction counting works
- ✅ `test_redaction_filter_robustness` - Error handling and resilience
- ✅ `test_comprehensive_coverage` - End-to-end validation
- ✅ `test_redaction_masks_sensitive_values` - Integration test with pytest fixtures

### Test Validation Results

All 13 tests pass successfully:

```bash
tests\test_logging_redaction.py .............  [100%]
====================================== 13 passed ======================================
```

## Usage Examples

### Basic Integration

```python
import logging
from logging_setup import RedactionFilter

# Set up logger with redaction
logger = logging.getLogger("secure_app")
handler = logging.StreamHandler()
handler.addFilter(RedactionFilter())
logger.addHandler(handler)

# These will be automatically redacted:
logger.info("telegram_token=1234567890:AAABBBCCCdddEEE")  # → telegram_token=****
logger.info("API key: sk_live_abcdefghijk123456")          # → API key: sk_live_****
logger.info("Bearer eyJhbGciOiJIUzI1...")                 # → Bearer ****
```

### Statistics Monitoring

```python
redaction_filter = RedactionFilter()
handler.addFilter(redaction_filter)

# After logging sensitive data
stats = redaction_filter.get_redaction_stats()
print(f"Total redactions: {stats['total_redactions']}")
print(f"Active patterns: {stats['patterns_active']}")
```

### Validation Script

Run the included validation script to see redaction in action:

```bash
python validate_log_redaction.py
```

This demonstrates live redaction of various sensitive patterns and shows statistics.

## Security Best Practices

### ✅ Recommended Patterns

1. **Always use key=value format** for sensitive configuration
2. **Prefix sensitive variables** with recognizable names (api_key, token, secret)
3. **Validate redaction** in development and testing environments
4. **Monitor redaction statistics** for unexpected patterns

### ⚠️ Security Considerations

1. **Log review**: Regularly audit logs for any unredacted sensitive data
2. **Pattern updates**: Update patterns when new secret formats are introduced
3. **False negatives**: Be aware that non-standard formats may not be caught
4. **Performance**: Redaction adds minimal overhead but consider impact on high-volume logging

## Implementation Details

### RedactionFilter Logic

```python
def filter(self, record: logging.LogRecord) -> bool:
    original_msg = record.getMessage()
    redacted_msg = original_msg

    # Apply all patterns
    for pattern in REDACTION_PATTERNS:
        if pattern.search(redacted_msg):
            self.redaction_count += 1
            redacted_msg = pattern.sub(r"\1****", redacted_msg)

    # Update record if redaction occurred
    if redacted_msg != original_msg:
        record.msg = redacted_msg
        record.args = ()
        record.redacted = True

    return True  # Always allow the record
```

### Pattern Structure

Each pattern uses capture groups:

- `\1` - Preserves the key part (e.g., "api_key=")
- `****` - Replaces the secret value

Example pattern:

```python
re.compile(rf"({key}\s*[=:]\s*)([A-Za-z0-9_\-:.+/]{{6,}})", re.IGNORECASE)
```

## Maintenance

### Adding New Patterns

1. Add sensitive keys to `SENSITIVE_KEYS` list
2. For complex formats, add custom regex to `REDACTION_PATTERNS`
3. Add corresponding test cases
4. Update documentation

### Testing Changes

```bash
# Run redaction tests
python -m pytest tests/test_logging_redaction.py -v

# Validate with demo script
python validate_log_redaction.py
```

## Compliance and Auditing

This redaction system helps satisfy:

- **PCI DSS** requirements for protecting payment card data
- **GDPR** requirements for protecting personal data
- **SOC 2** logging security controls
- **General security best practices** for secret management

The comprehensive test suite provides auditable proof that sensitive data patterns are properly protected in log output.
