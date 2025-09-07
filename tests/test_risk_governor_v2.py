#!/usr/bin/env python3
"""
Tests for RiskGovernorV2 - Loss Streak, Dynamic Blackout, Cooldown
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import get_settings
from risk.governor_v2 import RiskGovernorV2, RiskState


class TestRiskGovernorV2(unittest.TestCase):
    """Test RiskGovernorV2 functionality"""

    def setUp(self):
        """Set up test fixtures"""
        # Create temporary directory for test state files
        self.test_dir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.test_dir, "test_risk_state.json")

        # Mock settings
        self.mock_settings = Mock()
        self.mock_settings.max_consecutive_losses_v2 = 3
        self.mock_settings.max_trades_per_session = 5
        self.mock_settings.cooldown_after_loss_min = 30
        self.mock_settings.news_blackout_map = {
            "high": [45, 45],
            "medium": [20, 20],
            "low": [5, 5],
        }

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil

        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @patch("risk.governor_v2.get_settings")
    def test_initialization(self, mock_get_settings):
        """Test RiskGovernorV2 initialization"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)

        self.assertEqual(governor.state.consecutive_losses, 0)
        self.assertEqual(governor.state.trades_today, 0)
        self.assertIsNone(governor.state.blackout_until)
        self.assertIsNotNone(governor.state.current_date)

    @patch("risk.governor_v2.get_settings")
    def test_can_trade_initial_state(self, mock_get_settings):
        """Test can_trade returns True in initial state"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        can_trade, reason = governor.can_trade(now)

        self.assertTrue(can_trade)
        self.assertIsNone(reason)

    @patch("risk.governor_v2.get_settings")
    def test_session_trade_limit(self, mock_get_settings):
        """Test session trade limit blocking"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Reach session limit
        for i in range(5):
            governor.on_trade_closed(100.0, now)  # 5 winning trades

        can_trade, reason = governor.can_trade(now)

        self.assertFalse(can_trade)
        self.assertIn("SESSION_LIMIT", reason)
        self.assertIn("5/5", reason)

    @patch("risk.governor_v2.get_settings")
    def test_loss_streak_cooldown(self, mock_get_settings):
        """Test loss streak triggers cooldown"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Create 3 consecutive losses
        for i in range(3):
            governor.on_trade_closed(-100.0, now)

        # Should be blocked due to loss streak
        can_trade, reason = governor.can_trade(now)

        self.assertFalse(can_trade)
        self.assertIn("LOSS_STREAK_COOLDOWN", reason)
        self.assertIn("үлдсэн:", reason)

    @patch("risk.governor_v2.get_settings")
    def test_loss_streak_cooldown_expires(self, mock_get_settings):
        """Test loss streak cooldown expires after time"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Create 3 consecutive losses
        for i in range(3):
            governor.on_trade_closed(-100.0, now)

        # Should be blocked immediately after losses
        can_trade, reason = governor.can_trade(now)
        self.assertFalse(can_trade)

        # Should be allowed after cooldown period
        future = now + timedelta(minutes=31)  # 31 minutes > 30 minute cooldown
        can_trade, reason = governor.can_trade(future)

        self.assertTrue(can_trade)
        self.assertIsNone(reason)

    @patch("risk.governor_v2.get_settings")
    def test_loss_streak_reset_on_win(self, mock_get_settings):
        """Test loss streak resets on winning trade"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Create 2 consecutive losses
        governor.on_trade_closed(-100.0, now)
        governor.on_trade_closed(-100.0, now)

        self.assertEqual(governor.state.consecutive_losses, 2)

        # Win should reset loss streak
        governor.on_trade_closed(150.0, now)

        self.assertEqual(governor.state.consecutive_losses, 0)
        self.assertIsNone(governor.state.last_loss_ts)

    @patch("risk.governor_v2.get_settings")
    def test_news_blackout_high_impact(self, mock_get_settings):
        """Test high impact news blackout"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Apply high impact blackout
        governor.apply_news_blackout("high", now)

        # Should be blocked
        can_trade, reason = governor.can_trade(now)

        self.assertFalse(can_trade)
        self.assertIn("NEWS_BLACKOUT", reason)
        self.assertIn("үлдсэн:", reason)

    @patch("risk.governor_v2.get_settings")
    def test_news_blackout_expires(self, mock_get_settings):
        """Test news blackout expires after duration"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Apply medium impact blackout (40 minutes total)
        governor.apply_news_blackout("medium", now)

        # Should be blocked initially
        can_trade, reason = governor.can_trade(now)
        self.assertFalse(can_trade)

        # Should be allowed after blackout period
        future = now + timedelta(minutes=41)  # 41 > 40 minutes
        can_trade, reason = governor.can_trade(future)

        self.assertTrue(can_trade)
        self.assertIsNone(reason)

    @patch("risk.governor_v2.get_settings")
    def test_daily_reset(self, mock_get_settings):
        """Test daily counters reset on new day"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Make some trades
        governor.on_trade_closed(100.0, now)
        governor.on_trade_closed(-50.0, now)

        self.assertEqual(governor.state.trades_today, 2)
        self.assertEqual(governor.state.consecutive_losses, 1)

        # Simulate new day by changing current_date
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        governor.state.current_date = yesterday

        # Check daily reset triggers
        governor._check_daily_reset()

        self.assertEqual(governor.state.trades_today, 0)
        # consecutive_losses should NOT reset on daily reset
        self.assertEqual(governor.state.consecutive_losses, 1)

    @patch("risk.governor_v2.get_settings")
    def test_state_persistence(self, mock_get_settings):
        """Test state persists across instances"""
        mock_get_settings.return_value.risk = self.mock_settings

        # Create governor and make some trades
        governor1 = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        governor1.on_trade_closed(-100.0, now)
        governor1.on_trade_closed(-100.0, now)

        self.assertEqual(governor1.state.consecutive_losses, 2)
        self.assertEqual(governor1.state.trades_today, 2)

        # Create new governor instance - should load persisted state
        governor2 = RiskGovernorV2(state_path=self.state_path)

        self.assertEqual(governor2.state.consecutive_losses, 2)
        self.assertEqual(governor2.state.trades_today, 2)

    @patch("risk.governor_v2.get_settings")
    def test_get_state_summary(self, mock_get_settings):
        """Test state summary reporting"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Create some state
        governor.on_trade_closed(-100.0, now)
        governor.apply_news_blackout("high", now)

        summary = governor.get_state_summary()

        self.assertIn("consecutive_losses", summary)
        self.assertIn("trades_today", summary)
        self.assertIn("session_limit", summary)
        self.assertIn("session_usage_pct", summary)
        self.assertIn("cooldown_active", summary)
        self.assertIn("blackout_active", summary)
        self.assertIn("can_trade_now", summary)

        self.assertEqual(summary["consecutive_losses"], 1)
        self.assertEqual(summary["trades_today"], 1)
        self.assertTrue(summary["blackout_active"])
        self.assertFalse(summary["can_trade_now"])

    @patch("risk.governor_v2.get_settings")
    def test_manual_reset_methods(self, mock_get_settings):
        """Test manual reset methods for admin/testing"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Create some state
        governor.on_trade_closed(-100.0, now)
        governor.on_trade_closed(-100.0, now)
        governor.apply_news_blackout("high", now)

        # Test manual resets
        governor.clear_loss_streak()
        self.assertEqual(governor.state.consecutive_losses, 0)

        governor.clear_blackout()
        self.assertIsNone(governor.state.blackout_until)

        governor.reset_session()
        self.assertEqual(governor.state.trades_today, 0)

    @patch("risk.governor_v2.get_settings")
    def test_complex_scenario(self, mock_get_settings):
        """Test complex multi-factor blocking scenario"""
        mock_get_settings.return_value.risk = self.mock_settings

        governor = RiskGovernorV2(state_path=self.state_path)
        now = datetime.now()

        # Reach session limit with losses
        for i in range(4):
            governor.on_trade_closed(-100.0, now)  # 4 losses (not quite limit)

        # One more trade reaches session limit
        governor.on_trade_closed(50.0, now)  # Win resets loss streak but reaches limit

        can_trade, reason = governor.can_trade(now)

        # Should be blocked by session limit, not loss streak (since last was win)
        self.assertFalse(can_trade)
        self.assertIn("SESSION_LIMIT", reason)
        self.assertIn("5/5", reason)


if __name__ == "__main__":
    unittest.main()
