#!/usr/bin/env python3
"""
Test broker switching in live system to validate swap-ability.
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from config.settings import get_settings, ApplicationSettings
from adapters import create_broker
from core.broker import OrderRequest, Side

def test_broker_switching():
    """Test switching between paper and MT5 brokers"""
    print("🔄 Testing broker swap-ability...")
    
    # Test 1: Paper broker
    print("\n📝 Test 1: Paper Broker")
    settings = get_settings()
    original_kind = settings.broker_kind
    
    # Force paper broker
    settings.broker_kind = "paper"
    
    broker_paper = create_broker(settings)
    print(f"🏭 Broker type: {type(broker_paper).__name__}")
    
    broker_paper.connect()
    print(f"🔗 Connected: {broker_paper.is_connected()}")
    
    # Place a test order
    request = OrderRequest(
        client_order_id="switch_test_paper",
        symbol="EURUSD",
        side=Side.BUY,
        qty=0.1,
        order_type="MARKET"
    )
    
    result = broker_paper.place_order(request)
    print(f"📝 Paper order: accepted={result.accepted}")
    
    positions = broker_paper.positions()
    print(f"📊 Paper positions: {len(positions)}")
    
    # Test 2: MT5 broker (will fallback to paper if MT5 not available)
    print("\n🏗️ Test 2: MT5 Broker (with fallback)")
    settings.broker_kind = "mt5"
    
    broker_mt5 = create_broker(settings)
    print(f"🏭 Broker type: {type(broker_mt5).__name__}")
    
    try:
        broker_mt5.connect()
        print(f"🔗 Connected: {broker_mt5.is_connected()}")
        
        # Try to place order (this will test if interface is compatible)
        request2 = OrderRequest(
            client_order_id="switch_test_mt5",
            symbol="EURUSD", 
            side=Side.SELL,
            qty=0.1,
            order_type="MARKET"
        )
        
        result2 = broker_mt5.place_order(request2)
        print(f"📝 MT5/Fallback order: accepted={result2.accepted}")
        
        positions2 = broker_mt5.positions()
        print(f"📊 MT5/Fallback positions: {len(positions2)}")
        
    except Exception as e:
        print(f"❌ MT5 connection failed (expected): {e}")
    
    # Test 3: Verify interface compatibility
    print("\n🔍 Test 3: Interface Compatibility Check")
    
    brokers = [broker_paper, broker_mt5]
    required_methods = ['connect', 'is_connected', 'place_order', 'cancel', 'positions']
    
    for i, broker in enumerate(brokers, 1):
        print(f"   Broker {i} ({type(broker).__name__}):")
        for method in required_methods:
            has_method = hasattr(broker, method)
            print(f"     ✅ {method}: {has_method}" if has_method else f"     ❌ {method}: {has_method}")
    
    # Restore original settings
    settings.broker_kind = original_kind
    
    print("\n✅ Broker switching test completed!")
    print(f"📋 Original broker kind restored: {original_kind}")

if __name__ == "__main__":
    test_broker_switching()
