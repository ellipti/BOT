# 🤝 Contributing to AIVO Trading Bot

Thank you for your interest in contributing! This document outlines the development process, coding standards, and quality requirements.

## 🚪 Quality Gates

All contributions must pass **strict quality gates** before being merged:

### ✅ Required Checks

- **Code Formatting**: Black, isort compliance
- **Linting**: Ruff with no violations
- **Type Checking**: MyPy strict mode (no `any` types)
- **Security**: Bandit security scanning
- **Testing**: All tests pass on Windows + Ubuntu, Python 3.11/3.12
- **Dependencies**: Safety vulnerability checks

### 🚫 Merge Blocking

- Any quality gate failure blocks PR merge
- All CI jobs must be green
- No secrets in code/PR diff

## 📝 Commit Style

We use **Conventional Commits** for automated release notes:

### Format

```
<type>(scope): <description>

[optional body]

[optional footer]
```

### Types

- `feat(scope)`: New features
- `fix(scope)`: Bug fixes
- `chore(scope)`: Maintenance, refactoring
- `docs(scope)`: Documentation changes
- `ci(scope)`: CI/CD pipeline changes
- `test(scope)`: Adding or updating tests
- `security(scope)`: Security improvements
- `perf(scope)`: Performance optimizations

### Scopes

- `core`: Core trading logic
- `risk`: Risk management
- `mt5`: MetaTrader 5 integration
- `telegram`: Telegram notifications
- `config`: Configuration management
- `security`: Security & secrets
- `ci`: CI/CD pipeline
- `docs`: Documentation

### Examples

```bash
feat(mt5): add trailing stop loss functionality
fix(risk): correct daily loss calculation bug
chore(deps): update pandas to v2.1.0
docs(readme): update installation instructions
ci(matrix): add Python 3.12 testing
security(keyring): implement OS keyring integration
```

## 🏗️ Development Setup

### 1. Clone and Setup

```bash
git clone https://github.com/ellipti/BOT.git
cd BOT
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
pip install -r requirements-dev.txt
```

### 2. Install Development Tools

```bash
pip install mypy bandit ruff black isort pytest safety
```

### 3. Pre-commit Setup (Optional)

```bash
pip install pre-commit
pre-commit install
```

## 🧪 Testing

### Run All Checks Locally

```bash
# Formatting
black --check .
isort --check-only .

# Linting
ruff check .

# Type checking (strict)
mypy .

# Security scanning
bandit -r . -c .bandit

# Safety check
safety check

# Tests
pytest
```

### Test Structure

- `test_*.py`: Unit tests
- `test_integration_*.py`: Integration tests
- `demo_*.py`: System demonstrations
- Tests must pass on both Windows and Ubuntu

## 🔐 Security Guidelines

### Secrets Management

- **NEVER** commit secrets, API keys, or passwords
- Use `scripts/secret_set.py` to store secrets in OS keyring
- Environment variables only for non-sensitive config
- Test files should use mock/dummy values

### Security Scanning

- Bandit automatically scans for security issues
- Fix all medium+ severity findings
- Document any intentional security exceptions

## 📋 Pull Request Process

### 1. Create Feature Branch

```bash
git checkout -b feat/your-feature-name
# or
git checkout -b fix/issue-description
```

### 2. Development

- Follow coding standards (Black, isort, Ruff)
- Add type hints (MyPy strict mode)
- Include tests for new functionality
- Update documentation as needed

### 3. Pre-submission Checks

```bash
# Run full quality gate locally
black .
isort .
ruff check . --fix
mypy .
bandit -r . -c .bandit
pytest
```

### 4. Submit PR

- Use descriptive PR title following conventional commits
- Fill out the PR template completely
- Ensure all CI checks pass
- Request review from maintainers

## 🏷️ Labeling Convention

PR labels affect automatic release categorization:

### Type Labels

- `feat`/`feature`: New features → Minor version bump
- `fix`/`bug`: Bug fixes → Patch version bump
- `chore`/`refactor`/`docs`: Maintenance → Patch version bump
- `security`: Security fixes → Patch version bump
- `major`/`breaking`: Breaking changes → Major version bump

### Component Labels

- `mt5`: MetaTrader 5 related
- `telegram`: Telegram integration
- `risk`: Risk management
- `config`: Configuration
- `ci`: CI/CD pipeline
- `docs`: Documentation

## 🚀 Release Process

Releases are automated via Release Drafter:

### 1. Development

- Features developed in feature branches
- PRs merged to `main` branch
- Release draft automatically updated

### 2. Release Creation

- Maintainer publishes the draft release
- GitHub Actions builds and uploads release assets
- Deployment pipeline triggers (if configured)

### 3. Version Bumping

- **Patch**: Bug fixes, chores, docs (`v1.0.1`)
- **Minor**: New features (`v1.1.0`)
- **Major**: Breaking changes (`v2.0.0`)

## 🛠️ Development Tools Configuration

### MyPy (Type Checking)

Configuration in `mypy.ini`:

- Strict mode enabled
- No implicit `Any` types allowed
- Missing imports must be declared

### Bandit (Security)

Configuration in `.bandit`:

- Medium severity threshold
- Excludes test files
- Custom rules for trading-specific code

### Ruff (Linting)

Fast Python linter with comprehensive rules:

- Replaces flake8, isort, pyupgrade
- Auto-fixes most issues
- Configured for strict compliance

## 💡 Best Practices

### Code Quality

- Write self-documenting code
- Add docstrings for public functions
- Use descriptive variable names
- Keep functions small and focused

### Type Hints

```python
# Good
def calculate_position_size(balance: float, risk_pct: float) -> float:
    return balance * (risk_pct / 100)

# Avoid
def calculate_position_size(balance, risk_pct):
    return balance * (risk_pct / 100)
```

### Error Handling

- Use specific exception types
- Add logging context
- Fail fast with clear error messages

### Testing

- Test edge cases and error conditions
- Use mock objects for external dependencies
- Keep tests independent and deterministic

## 🆘 Getting Help

- **Issues**: Open GitHub issue with detailed description
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check README and inline documentation
- **Examples**: Review `demo_*.py` files for usage examples

## 📊 Code Review Criteria

Reviewers will check:

### ✅ Must Have

- All CI checks pass (quality gates)
- No secrets in code
- Appropriate test coverage
- Clear commit messages
- Documentation updates (if needed)

### 🔍 Code Quality

- Readable, maintainable code
- Proper error handling
- Performance considerations
- Security best practices

### 🧪 Testing

- Tests cover new functionality
- Edge cases considered
- No flaky tests
- Cross-platform compatibility

---

Thank you for contributing to AIVO Trading Bot! 🚀

Your contributions help make algorithmic trading more accessible and reliable for everyone.
