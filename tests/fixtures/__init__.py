"""
Test fixtures for MT5-less testing strategy.

This module provides fixtures and utilities for testing without MT5 dependency:
- FakeBroker for complete broker simulation
- Mock MT5 module for unit testing
- Helper functions for test setup
"""

from .fake_broker import FakeBrokerAdapter, FakeBrokerConnection

__all__ = ["FakeBrokerAdapter", "FakeBrokerConnection"]
