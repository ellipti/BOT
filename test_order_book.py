"""
Test suite for OrderBook SQLite-based order state management

Validates:
- Order creation and lifecycle transitions
- Partial fill aggregation with correct average prices
- Cancel/reject workflows
- Stop loss/take profit updates
- Thread safety and concurrent operations
- Database integrity and cleanup
"""

import os
import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from core.executor.order_book import OrderBook, OrderInfo, OrderStatus


class TestOrderBook:
    """Test suite for OrderBook functionality"""

    def test_basic_order_lifecycle(self):
        """Test basic order creation through completion"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)
            coid = "TEST_001"

            # 1. Create pending order
            book.create_pending(coid, "EURUSD", "BUY", 1.0, sl=1.1000, tp=1.1200)

            order = book.get_order(coid)
            assert order is not None
            assert order.coid == coid
            assert order.symbol == "EURUSD"
            assert order.side == "BUY"
            assert order.qty == 1.0
            assert order.filled_qty == 0.0
            assert order.status == OrderStatus.PENDING
            assert order.sl == 1.1000
            assert order.tp == 1.1200
            assert abs(order.remaining_qty - 1.0) < 1e-9
            assert not order.is_fully_filled

            # 2. Accept order
            book.upsert_on_accept(coid, "EURUSD", "BUY", 1.0, "MT5_12345")

            order = book.get_order(coid)
            assert order.status == OrderStatus.ACCEPTED
            assert order.broker_order_id == "MT5_12345"

            # 3. Partial fill
            updated = book.mark_partial(coid, 0.3, 1.1100)
            assert updated.filled_qty == 0.3
            assert updated.avg_fill_price == 1.1100
            assert updated.status == OrderStatus.PARTIAL
            assert abs(updated.remaining_qty - 0.7) < 1e-9
            assert not updated.is_fully_filled
            assert abs(updated.fill_percentage - 0.3) < 1e-9

            # 4. Another partial fill
            updated = book.mark_partial(coid, 0.4, 1.1050)
            assert updated.filled_qty == 0.7
            # Average: (0.3 * 1.1100 + 0.4 * 1.1050) / 0.7
            expected_avg = (0.3 * 1.1100 + 0.4 * 1.1050) / 0.7
            assert abs(updated.avg_fill_price - expected_avg) < 1e-9
            assert updated.status == OrderStatus.PARTIAL
            assert abs(updated.remaining_qty - 0.3) < 1e-9

            # 5. Complete fill
            updated = book.mark_partial(coid, 0.3, 1.1025)
            assert updated.filled_qty == 1.0
            assert updated.status == OrderStatus.FILLED
            assert abs(updated.remaining_qty - 0.0) < 1e-9
            assert updated.is_fully_filled
            assert abs(updated.fill_percentage - 1.0) < 1e-9

            # Verify fills history
            fills = book.get_fills(coid)
            assert len(fills) == 3
            assert fills[0] == (0.3, 1.1100, fills[0][2])  # qty, price, ts
            assert fills[1] == (0.4, 1.1050, fills[1][2])
            assert fills[2] == (0.3, 1.1025, fills[2][2])

        finally:
            os.unlink(db_path)

    def test_order_cancellation(self):
        """Test order cancellation workflow"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)
            coid = "CANCEL_TEST"

            # Create and accept order
            book.create_pending(coid, "GBPUSD", "SELL", 0.5)
            book.upsert_on_accept(coid, "GBPUSD", "SELL", 0.5, "MT5_999")

            # Partial fill
            book.mark_partial(coid, 0.2, 1.2500)

            order = book.get_order(coid)
            assert order.status == OrderStatus.PARTIAL
            assert order.filled_qty == 0.2

            # Cancel order
            book.mark_cancelled(coid)

            order = book.get_order(coid)
            assert order.status == OrderStatus.CANCELLED
            assert order.filled_qty == 0.2  # Filled qty preserved

            # Try to cancel non-existent order
            book.mark_cancelled("NON_EXISTENT")  # Should not raise

        finally:
            os.unlink(db_path)

    def test_stop_updates(self):
        """Test stop loss and take profit updates"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)
            coid = "STOPS_TEST"

            # Create order with initial stops
            book.create_pending(coid, "USDJPY", "BUY", 2.0, sl=110.00, tp=112.00)

            order = book.get_order(coid)
            assert order.sl == 110.00
            assert order.tp == 112.00

            # Update only stop loss
            success = book.update_stops(coid, sl=110.50)
            assert success

            order = book.get_order(coid)
            assert order.sl == 110.50
            assert order.tp == 112.00  # Unchanged

            # Update only take profit
            success = book.update_stops(coid, tp=111.75)
            assert success

            order = book.get_order(coid)
            assert order.sl == 110.50  # Unchanged
            assert order.tp == 111.75

            # Update both
            success = book.update_stops(coid, sl=110.25, tp=111.50)
            assert success

            order = book.get_order(coid)
            assert order.sl == 110.25
            assert order.tp == 111.50

            # Update non-existent order
            success = book.update_stops("NON_EXISTENT", sl=100.0)
            assert not success

        finally:
            os.unlink(db_path)

    def test_active_orders_filtering(self):
        """Test filtering of active vs terminal orders"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)

            # Create various orders
            book.create_pending("PENDING_1", "EUR/USD", "BUY", 1.0)
            book.create_pending("PENDING_2", "GBP/USD", "SELL", 0.5)

            book.upsert_on_accept("ACCEPTED_1", "USD/JPY", "BUY", 2.0, "MT5_001")

            book.create_pending("PARTIAL_1", "AUD/USD", "BUY", 1.5)
            book.upsert_on_accept("PARTIAL_1", "AUD/USD", "BUY", 1.5, "MT5_002")
            book.mark_partial("PARTIAL_1", 0.8, 0.7500)

            book.create_pending("FILLED_1", "NZD/USD", "SELL", 1.0)
            book.upsert_on_accept("FILLED_1", "NZD/USD", "SELL", 1.0, "MT5_003")
            book.mark_partial("FILLED_1", 1.0, 0.6800)

            book.create_pending("CANCELLED_1", "CAD/USD", "BUY", 0.8)
            book.mark_cancelled("CANCELLED_1")

            # Get active orders
            active = book.get_active_orders()
            active_coids = [order.coid for order in active]

            # Should include: PENDING_1, PENDING_2, ACCEPTED_1, PARTIAL_1
            # Should exclude: FILLED_1, CANCELLED_1
            assert len(active) == 4
            assert "PENDING_1" in active_coids
            assert "PENDING_2" in active_coids
            assert "ACCEPTED_1" in active_coids
            assert "PARTIAL_1" in active_coids
            assert "FILLED_1" not in active_coids
            assert "CANCELLED_1" not in active_coids

            # Verify status counts
            counts = book.get_order_count_by_status()
            assert counts[OrderStatus.PENDING] == 2
            assert counts[OrderStatus.ACCEPTED] == 1
            assert counts[OrderStatus.PARTIAL] == 1
            assert counts[OrderStatus.FILLED] == 1
            assert counts[OrderStatus.CANCELLED] == 1

        finally:
            os.unlink(db_path)

    def test_over_fill_protection(self):
        """Test protection against over-filling orders"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)
            coid = "OVERFILL_TEST"

            book.create_pending(coid, "EUR/USD", "BUY", 1.0)
            book.upsert_on_accept(coid, "EUR/USD", "BUY", 1.0, "MT5_123")

            # Fill 0.6
            book.mark_partial(coid, 0.6, 1.1000)

            # Try to overfill (0.6 + 0.5 = 1.1 > 1.0)
            try:
                book.mark_partial(coid, 0.5, 1.1050)
                raise AssertionError("Should have raised ValueError for over-fill")
            except ValueError as e:
                assert "Over-fill" in str(e)

            # Exact fill should work
            book.mark_partial(coid, 0.4, 1.1050)

            order = book.get_order(coid)
            assert order.status == OrderStatus.FILLED
            assert order.filled_qty == 1.0

            # Try to fill already completed order
            try:
                book.mark_partial(coid, 0.1, 1.1100)
                raise AssertionError("Should have raised ValueError for over-fill")
            except ValueError as e:
                assert "Over-fill" in str(e)

        finally:
            os.unlink(db_path)

    def test_concurrent_access(self):
        """Test thread safety with concurrent operations"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)

            def create_orders(thread_id: int, count: int):
                """Create orders in a thread"""
                for i in range(count):
                    coid = f"THREAD_{thread_id}_{i}"
                    book.create_pending(coid, "EUR/USD", "BUY", 1.0)
                    book.upsert_on_accept(
                        coid, "EUR/USD", "BUY", 1.0, f"MT5_{thread_id}_{i}"
                    )

                    # Random partial fills
                    if i % 2 == 0:
                        book.mark_partial(coid, 0.3, 1.1000 + i * 0.0001)
                        book.mark_partial(coid, 0.7, 1.1010 + i * 0.0001)
                    else:
                        book.mark_cancelled(coid)

            # Run concurrent operations
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(create_orders, thread_id, 10)
                    for thread_id in range(5)
                ]

                # Wait for all threads
                for future in futures:
                    future.result()

            # Verify results
            counts = book.get_order_count_by_status()
            total_orders = sum(counts.values())
            assert total_orders == 50  # 5 threads * 10 orders each

            # Should have 25 filled and 25 cancelled (based on i % 2)
            assert counts.get(OrderStatus.FILLED, 0) == 25
            assert counts.get(OrderStatus.CANCELLED, 0) == 25

        finally:
            os.unlink(db_path)

    def test_database_persistence(self):
        """Test that data persists across OrderBook instances"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            # Create orders with first instance
            book1 = OrderBook(db_path)
            book1.create_pending("PERSIST_1", "EUR/USD", "BUY", 1.0)
            book1.create_pending("PERSIST_2", "GBP/USD", "SELL", 0.5)
            book1.upsert_on_accept("PERSIST_2", "GBP/USD", "SELL", 0.5, "MT5_999")
            book1.mark_partial("PERSIST_2", 0.3, 1.2500)

            # Create second instance and verify data
            book2 = OrderBook(db_path)

            order1 = book2.get_order("PERSIST_1")
            assert order1 is not None
            assert order1.status == OrderStatus.PENDING

            order2 = book2.get_order("PERSIST_2")
            assert order2 is not None
            assert order2.status == OrderStatus.PARTIAL
            assert order2.filled_qty == 0.3
            assert order2.avg_fill_price == 1.2500

            # Modify with second instance
            book2.mark_cancelled("PERSIST_1")
            book2.mark_partial("PERSIST_2", 0.2, 1.2450)

            # Verify with third instance
            book3 = OrderBook(db_path)

            order1 = book3.get_order("PERSIST_1")
            assert order1.status == OrderStatus.CANCELLED

            order2 = book3.get_order("PERSIST_2")
            assert order2.status == OrderStatus.FILLED
            assert order2.filled_qty == 0.5

            # Check average price calculation
            expected_avg = (0.3 * 1.2500 + 0.2 * 1.2450) / 0.5
            assert abs(order2.avg_fill_price - expected_avg) < 1e-9

        finally:
            os.unlink(db_path)

    def test_cleanup_old_orders(self):
        """Test cleanup of old terminal orders"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)

            # Create old orders (simulate by directly updating timestamps)
            old_time = time.time() - (25 * 3600)  # 25 hours ago

            book.create_pending("OLD_FILLED", "EUR/USD", "BUY", 1.0)
            book.mark_partial("OLD_FILLED", 1.0, 1.1000)

            book.create_pending("OLD_CANCELLED", "GBP/USD", "BUY", 1.0)
            book.mark_cancelled("OLD_CANCELLED")

            book.create_pending("NEW_FILLED", "USD/JPY", "BUY", 1.0)
            book.mark_partial("NEW_FILLED", 1.0, 110.00)

            book.create_pending("ACTIVE_ORDER", "AUD/USD", "BUY", 1.0)
            book.upsert_on_accept("ACTIVE_ORDER", "AUD/USD", "BUY", 1.0, "MT5_123")

            # Manually update timestamps to simulate old orders
            with book._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE orders SET updated_ts = ? WHERE coid IN (?, ?)
                """,
                    (old_time, "OLD_FILLED", "OLD_CANCELLED"),
                )
                conn.commit()

            # Cleanup old orders (24 hour cutoff)
            deleted_count = book.cleanup_old_orders(max_age_hours=24)
            assert deleted_count == 2

            # Verify remaining orders
            remaining = book.get_active_orders()
            remaining_coids = [order.coid for order in remaining]

            # OLD_FILLED and OLD_CANCELLED should be gone
            assert "OLD_FILLED" not in [
                book.get_order(coid).coid
                for coid in ["OLD_FILLED", "OLD_CANCELLED"]
                if book.get_order(coid)
            ]

            # NEW_FILLED should be gone too if it's also terminal
            # ACTIVE_ORDER should remain
            assert "ACTIVE_ORDER" in remaining_coids

        finally:
            os.unlink(db_path)

    def test_invalid_operations(self):
        """Test error handling for invalid operations"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name

        try:
            book = OrderBook(db_path)

            # Try to fill non-existent order
            try:
                book.mark_partial("NON_EXISTENT", 1.0, 1.1000)
                raise AssertionError(
                    "Should have raised ValueError for order not found"
                )
            except ValueError as e:
                assert "Order not found" in str(e)

            # Try invalid fill quantity
            book.create_pending("INVALID_FILL", "EUR/USD", "BUY", 1.0)

            try:
                book.mark_partial("INVALID_FILL", 0, 1.1000)
                raise AssertionError(
                    "Should have raised ValueError for invalid fill quantity"
                )
            except ValueError as e:
                assert "Invalid fill quantity" in str(e)

            try:
                book.mark_partial("INVALID_FILL", -0.5, 1.1000)
                raise AssertionError(
                    "Should have raised ValueError for invalid fill quantity"
                )
            except ValueError as e:
                assert "Invalid fill quantity" in str(e)

            # Get non-existent order
            order = book.get_order("NON_EXISTENT")
            assert order is None

        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    # Run basic functionality test
    test = TestOrderBook()

    print("Running OrderBook tests...")

    try:
        test.test_basic_order_lifecycle()
        print("✅ Basic lifecycle test passed")

        test.test_order_cancellation()
        print("✅ Cancellation test passed")

        test.test_stop_updates()
        print("✅ Stop updates test passed")

        test.test_active_orders_filtering()
        print("✅ Active orders filtering test passed")

        test.test_over_fill_protection()
        print("✅ Over-fill protection test passed")

        test.test_concurrent_access()
        print("✅ Concurrent access test passed")

        test.test_database_persistence()
        print("✅ Database persistence test passed")

        test.test_cleanup_old_orders()
        print("✅ Cleanup test passed")

        test.test_invalid_operations()
        print("✅ Invalid operations test passed")

        print("\n🎉 All OrderBook tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        raise
