## Summary

<!-- Provide a clear and concise description of your changes -->

## Type of Change

<!-- Mark the type of change with an [x] -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] 🚀 New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] � Documentation update
- [ ] 🧪 Test update
- [ ] 🔧 Chore/refactoring
- [ ] 🛡️ Security improvement

## Scope

<!-- Which area of the codebase does this affect? -->

- [ ] Core trading logic
- [ ] Risk management
- [ ] MT5 integration
- [ ] Telegram notifications
- [ ] Configuration
- [ ] Security & secrets
- [ ] CI/CD pipeline
- [ ] Documentation

## Quality Gates Checklist

<!-- All items must be checked before requesting review - PR will be blocked until ALL quality gates pass -->

### 🔍 Code Quality (CI Enforced)

- [ ] Code formatted with Black (CI: `black --check .`)
- [ ] Imports sorted with isort (CI: `isort --check-only .`)
- [ ] No linting errors (CI: `ruff check .`)
- [ ] Strict type checking passes (CI: `mypy .`)
- [ ] No security issues (CI: `bandit -r . -f json`)
- [ ] Dependencies are safe (CI: `safety check`)

### 🧪 Cross-Platform Testing (CI Matrix)

- [ ] Tests pass on **Windows** + Python 3.11
- [ ] Tests pass on **Windows** + Python 3.12
- [ ] Tests pass on **Ubuntu** + Python 3.11
- [ ] Tests pass on **Ubuntu** + Python 3.12
- [ ] All test matrix combinations successful

### � Security Requirements

- [ ] No secrets in code/PR diff
- [ ] Sensitive data uses keyring storage
- [ ] Secret scan passes (CI: automatic)
- [ ] No hardcoded credentials or tokens
- [ ] Proper log redaction for sensitive data

### � Documentation & Testing

- [ ] Code changes are documented with docstrings
- [ ] README updated (if needed)
- [ ] New functionality has unit tests
- [ ] Integration tests updated (if needed)
- [ ] Manual testing completed

## Manual Testing

<!-- Describe how you tested your changes -->

**Test Environment:**

- OS: <!-- Windows/Ubuntu/macOS -->
- Python Version: <!-- 3.11/3.12 -->
- Testing Mode: <!-- DRY_RUN=true/false -->

**Test Steps:**

1.
2.
3.

**Expected Results:**

-

## Screenshots/Logs

<!-- If applicable, add screenshots or log outputs -->

```
Paste relevant logs here
```

## Related Issues

<!-- Link any related issues -->

Closes #<!-- issue number -->
Related to #<!-- issue number -->

## Breaking Changes

<!-- List any breaking changes and migration steps -->

**⚠️ BREAKING CHANGES:**

- **Migration Steps:**

1.
2.

## CI Status Summary

<!-- This section will be auto-populated by CI results -->

- Quality Gates: <!-- Will show ✅ or ❌ -->
- Matrix Tests: <!-- Will show test results across all platforms -->
- Security Scan: <!-- Will show security scan results -->

## Additional Notes

<!-- Any additional information for reviewers -->

---

## �️ Quality Gate Requirements

<!-- These requirements are ENFORCED by CI - PRs cannot merge until ALL pass -->

### Automated Quality Checks

- **Black Formatting**: Code must be formatted (`black .`)
- **isort Import Sorting**: Imports must be sorted (`isort .`)
- **Ruff Linting**: No linting violations (`ruff check .`)
- **MyPy Type Checking**: Strict type checking must pass (`mypy .`)
- **Bandit Security**: No security issues (`bandit -r .`)
- **Safety Dependencies**: All dependencies must be safe (`safety check`)

### Cross-Platform Validation

- **Windows + Python 3.11**: Full test suite must pass
- **Windows + Python 3.12**: Full test suite must pass
- **Ubuntu + Python 3.11**: Full test suite must pass
- **Ubuntu + Python 3.12**: Full test suite must pass

### Security Requirements

- **Secret Scanning**: Automated secret detection must pass
- **Keyring Integration**: Sensitive data must use secure storage
- **Log Redaction**: No sensitive data in logs

---

## Reviewer Checklist

<!-- For maintainers reviewing the PR -->

- [ ] Code follows project conventions and patterns
- [ ] All automated quality gates pass (CI green)
- [ ] Security review completed - no sensitive data exposure
- [ ] Cross-platform compatibility verified
- [ ] Documentation is comprehensive and accurate
- [ ] Breaking changes are properly documented with migration guide
- [ ] Release notes impact considered
- [ ] Manual testing approach is reasonable
