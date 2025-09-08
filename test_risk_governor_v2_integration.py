#!/usr/bin/env python3
"""
Integration test for RiskGovernorV2 - Complete system test
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.events import EventBus, SignalDetected, TradeBlocked, TradeClosed
from risk.governor_v2 import RiskGovernorV2


def test_complete_risk_governance_flow():
    """Test complete RiskGovernorV2 integration flow"""
    print("🧪 RiskGovernorV2 Integration Test")
    print("=" * 50)

    # Setup
    test_dir = tempfile.mkdtemp()
    state_path = os.path.join(test_dir, "test_integration_state.json")

    # Mock settings
    mock_settings = Mock()
    mock_settings.max_consecutive_losses_v2 = 3
    mock_settings.max_trades_per_session = 5
    mock_settings.cooldown_after_loss_min = 30
    mock_settings.news_blackout_map = {
        "high": [45, 45],
        "medium": [20, 20],
        "low": [5, 5],
    }

    with patch("risk.governor_v2.get_settings") as mock_get_settings:
        mock_get_settings.return_value.risk = mock_settings

        # Initialize governor
        governor = RiskGovernorV2(state_path=state_path)

        print("✅ RiskGovernorV2 инициализован")
        print(f"   State: {governor.get_state_summary()}")

        # Test 1: Normal trading allowed
        print("\n📊 Test 1: Normal trading")
        now = datetime.now()
        can_trade, reason = governor.can_trade(now)
        print(f"   Can trade: {can_trade}, Reason: {reason}")
        assert can_trade, "Should allow trading initially"

        # Test 2: Progressive loss streak
        print("\n📊 Test 2: Loss streak progression")
        for i in range(1, 4):
            governor.on_trade_closed(-100.0, now)
            state = governor.get_state_summary()
            print(
                f"   Loss {i}: consecutive_losses={state['consecutive_losses']}, can_trade={state['can_trade_now']}"
            )

        # Should be blocked after 3rd loss
        can_trade, reason = governor.can_trade(now)
        assert not can_trade, "Should be blocked after 3 losses"
        assert (
            "LOSS_STREAK_COOLDOWN" in reason
        ), f"Expected cooldown reason, got: {reason}"
        print(f"   ❌ Blocked: {reason}")

        # Test 3: Cooldown expiry
        print("\n📊 Test 3: Cooldown expiry")
        future = now + timedelta(minutes=31)
        can_trade, reason = governor.can_trade(future)
        print(f"   After 31 minutes: can_trade={can_trade}")
        assert can_trade, "Should be allowed after cooldown"

        # Test 4: Loss streak reset on win
        print("\n📊 Test 4: Loss streak reset")
        governor.on_trade_closed(200.0, now)  # Winning trade
        state = governor.get_state_summary()
        print(f"   After win: consecutive_losses={state['consecutive_losses']}")
        assert state["consecutive_losses"] == 0, "Loss streak should reset"

        # Test 5: Session limit
        print("\n📊 Test 5: Session limit")
        initial_trades = governor.state.trades_today

        # Make trades up to session limit
        for i in range(5 - initial_trades):
            governor.on_trade_closed(50.0, now)

        can_trade, reason = governor.can_trade(now)
        print(f"   After {governor.state.trades_today} trades: can_trade={can_trade}")
        print(f"   Reason: {reason}")
        assert not can_trade, "Should be blocked by session limit"
        assert "SESSION_LIMIT" in reason, f"Expected session limit, got: {reason}"

        # Test 6: News blackout
        print("\n📊 Test 6: News blackout")
        governor.reset_session()  # Reset for blackout test

        governor.apply_news_blackout("high", now)
        can_trade, reason = governor.can_trade(now)
        print(f"   After high impact news: can_trade={can_trade}")
        print(f"   Reason: {reason}")
        assert not can_trade, "Should be blocked by news blackout"
        assert "NEWS_BLACKOUT" in reason, f"Expected blackout reason, got: {reason}"

        # Test 7: Multiple blocking conditions
        print("\n📊 Test 7: Multiple blocking conditions")

        # Clear blackout but keep other conditions
        governor.clear_blackout()

        # Create loss streak without resetting session
        for i in range(3):
            governor.on_trade_closed(-100.0, now)

        state = governor.get_state_summary()
        print(
            f"   After losses: consecutive_losses={state['consecutive_losses']}, trades_today={state['trades_today']}"
        )

        can_trade, reason = governor.can_trade(now)
        print(f"   Multiple conditions: can_trade={can_trade}")
        print(f"   Primary block reason: {reason}")

        # Should be blocked by either loss streak OR session limit
        assert not can_trade, "Should be blocked"

        # Test 8: State summary reporting
        print("\n📊 Test 8: State summary")
        summary = governor.get_state_summary()
        for key, value in summary.items():
            print(f"   {key}: {value}")

        assert "consecutive_losses" in summary
        assert "trades_today" in summary
        assert "blackout_active" in summary
        assert "cooldown_active" in summary

        print("\n🎉 All integration tests passed!")

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)


def test_event_bus_integration():
    """Test EventBus integration with TradeBlocked events"""
    print("\n🔗 EventBus Integration Test")
    print("=" * 30)

    # Create event bus
    bus = EventBus()
    blocked_events = []

    def handle_trade_blocked(event: TradeBlocked):
        blocked_events.append(event)
        print(f"   📨 TradeBlocked event: {event.symbol} {event.side} - {event.reason}")

    bus.subscribe(TradeBlocked, handle_trade_blocked)

    # Test blocking scenario
    test_dir = tempfile.mkdtemp()
    state_path = os.path.join(test_dir, "test_eventbus_state.json")

    mock_settings = Mock()
    mock_settings.max_consecutive_losses_v2 = 2  # Lower for quick testing
    mock_settings.max_trades_per_session = 3
    mock_settings.cooldown_after_loss_min = 15
    mock_settings.news_blackout_map = {"high": [30, 30]}

    with patch("risk.governor_v2.get_settings") as mock_get_settings:
        mock_get_settings.return_value.risk = mock_settings

        governor = RiskGovernorV2(state_path=state_path)
        now = datetime.now()

        # Create loss streak to trigger blocking
        governor.on_trade_closed(-100.0, now)
        governor.on_trade_closed(-100.0, now)

        # Simulate signal processing logic (like in pipeline)
        signal = SignalDetected(
            symbol="XAUUSD", side="BUY", strength=0.8, strategy_id="test"
        )

        can_trade, reason = governor.can_trade(now)

        if not can_trade:
            # Publish TradeBlocked event
            blocked_event = TradeBlocked(
                symbol=signal.symbol,
                side=signal.side,
                reason=reason,
                governor_version="v2",
            )
            bus.publish(blocked_event)

        # Verify event was handled
        assert len(blocked_events) == 1, "Should have received TradeBlocked event"
        assert blocked_events[0].symbol == "XAUUSD"
        assert "LOSS_STREAK_COOLDOWN" in blocked_events[0].reason

        print("✅ EventBus integration working correctly")

    # Cleanup
    import shutil

    shutil.rmtree(test_dir)


if __name__ == "__main__":
    test_complete_risk_governance_flow()
    test_event_bus_integration()
    print("\n🎯 All integration tests completed successfully!")
