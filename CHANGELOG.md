# Changelog

All notable changes to the Trading Bot project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Complete documentation and release preparation
- Comprehensive README with quickstart guide
- Detailed .env.example with full configuration explanations
- Windows service deployment guide
- Production runbook documentation

## [1.0.1] - 2025-09-08

### Fixed

- **Trailing Stops**: Increased minimum step size from 5.0 to 8.0 pips to reduce jitter
- **Trailing Stops**: Enhanced hysteresis threshold from 2.0 to 4.0 pips for stability
- **Trailing Stops**: Improved configuration-driven parameter management

### Performance

- **Dashboard**: Orders page now defaults to last 7 days for faster loading
- **Dashboard**: Added date range filters (24h, 7d, 30d) for better data navigation
- **Observability**: Implemented 120-second alert debouncing to prevent notification spam
- **Observability**: Added SLA monitoring with configurable thresholds

### Changed

- Enhanced trailing stop algorithm with better oscillation prevention
- Improved dashboard user experience with date-based filtering
- Optimized observability system with reduced alert noise

### Added

- New trailing probe test suite validating jitter reduction
- Alert management system with debouncing and SLA monitoring
- Extended dashboard filtering capabilities

## [1.2.0] - 2025-09-07

### Added

- Pre-commit quality gates with automated code formatting
- Black code formatter integration (v25.1.0)
- isort import organizer (v6.0.1)
- Ruff fast Python linter (v0.12.12)
- Bandit security scanner (v1.8.6)
- Comprehensive code quality hooks
- Git pre-commit automation

### Changed

- Updated Ruff configuration to new lint section format
- Enhanced pyproject.toml with quality tool configurations
- Improved development workflow with automated formatting

### Fixed

- Core configuration import structure in core/config.py
- MyPy module detection with utils/**init**.py creation
- Pre-commit hook compatibility on Windows

## [1.1.0] - 2025-09-07

### Added

- GitHub Actions CI/CD pipeline
- Automated testing on multiple Python versions (3.11, 3.12, 3.13)
- Multi-platform testing (Ubuntu, Windows, macOS)
- Dependency caching for faster builds
- Test result reporting and artifact collection
- Security vulnerability scanning with Bandit
- Code coverage reporting

### Changed

- Enhanced project structure for CI/CD compatibility
- Improved error handling in test suites
- Updated development dependencies for better CI integration

### Security

- Added automated security scanning to CI pipeline
- Implemented dependency vulnerability checks

## [1.0.0] - 2025-09-01

### Added

- Complete trading bot implementation with MT5 integration
- Advanced risk management and safety gates
- Multi-recipient Telegram notifications with charts
- Comprehensive backtesting engine with visualization
- Real-time chart generation with technical indicators
- Atomic file I/O for state persistence
- Calendar-based news filtering integration
- Session-based trading controls
- Production-ready logging and audit trails

### Features

- **MT5 Integration**: Both attach and login modes supported
- **Safety Systems**: Daily limits, position limits, loss protection
- **Chart Analysis**: Technical indicators with visual overlays
- **Risk Management**: ATR-based position sizing, cooldown periods
- **Notifications**: Rich Telegram alerts with charts and trade details
- **Backtesting**: Strategy optimization with performance metrics
- **News Filtering**: Trading Economics API integration
- **Audit Trail**: Complete trade logging with CSV export

### Security

- Environment-based configuration management
- Secure credential handling
- Production safety checks
- Dry-run mode for testing

### Performance

- Optimized chart rendering with matplotlib
- Efficient data processing with pandas
- Atomic operations for state management
- Memory-efficient backtesting engine

## [0.9.0] - 2025-08-25

### Added

- Initial project structure and core components
- Basic MT5 connectivity and trading functions
- Fundamental risk management features
- Simple notification system
- Development environment setup

### Changed

- Project reorganization for better maintainability
- Improved error handling and logging

## [0.1.0] - 2025-08-15

### Added

- Initial repository setup
- Basic trading bot framework
- Core dependencies and project structure
- Development documentation

---

## Version Guidelines

### Major Version (X.0.0)

- Breaking changes to API or configuration
- Major feature additions or architectural changes
- Database schema changes requiring migration

### Minor Version (0.X.0)

- New features and enhancements
- New integrations or strategies
- Non-breaking API additions

### Patch Version (0.0.X)

- Bug fixes and small improvements
- Security patches
- Documentation updates
- Performance optimizations

## Release Process

1. Update version in `pyproject.toml`
2. Update this CHANGELOG.md with release notes
3. Create release branch: `git checkout -b release/vX.Y.Z`
4. Run full test suite: `pytest`
5. Run pre-commit checks: `pre-commit run --all-files`
6. Create GitHub release with tag `vX.Y.Z`
7. Merge to main branch
8. Deploy to production environment

## Breaking Changes

When introducing breaking changes, we:

- Provide migration guides in release notes
- Offer backward compatibility when possible
- Give advance notice in previous releases
- Document all changes in upgrade guides

## Support Policy

- **Current Release**: Full support with bug fixes and security updates
- **Previous Minor**: Security fixes only for 6 months
- **Older Releases**: Community support only

For support requests, please open an issue on GitHub with detailed information about your environment and the problem encountered.
