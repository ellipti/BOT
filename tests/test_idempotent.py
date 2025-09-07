"""
Tests for IdempotentOrderExecutor - reliability and deduplication
"""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.broker import BrokerGateway, OrderRequest, OrderResult, OrderType, Side
from core.executor import IdempotentOrderExecutor, make_coid


class FakeBroker:
    """Fake broker for testing that returns predictable results"""

    def __init__(self, should_accept: bool = True):
        self.should_accept = should_accept
        self.call_count = 0
        self.last_request = None

    def connect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def place_order(self, request: OrderRequest) -> OrderResult:
        """Track calls and return configurable result"""
        self.call_count += 1
        self.last_request = request

        if self.should_accept:
            return OrderResult(
                accepted=True,
                broker_order_id=f"B{self.call_count}",
                reason=f"Executed {request.client_order_id}",
            )
        else:
            return OrderResult(
                accepted=False, broker_order_id=None, reason="Insufficient margin"
            )

    def cancel(self, broker_order_id: str) -> bool:
        return False

    def positions(self) -> list:
        return []


class TestMakeCoid:
    """Test client order ID generation"""

    def test_deterministic_generation(self):
        """Test that same inputs produce same client order ID"""
        coid1 = make_coid("XAUUSD", "BUY", "test_strategy", "20250907_1510")
        coid2 = make_coid("XAUUSD", "BUY", "test_strategy", "20250907_1510")

        assert coid1 == coid2
        assert len(coid1) == 24  # SHA256 first 24 chars
        assert isinstance(coid1, str)

    def test_different_inputs_different_ids(self):
        """Test that different inputs produce different IDs"""
        coid1 = make_coid("XAUUSD", "BUY", "strategy1", "20250907_1510")
        coid2 = make_coid(
            "XAUUSD", "SELL", "strategy1", "20250907_1510"
        )  # Different side
        coid3 = make_coid(
            "EURUSD", "BUY", "strategy1", "20250907_1510"
        )  # Different symbol
        coid4 = make_coid(
            "XAUUSD", "BUY", "strategy2", "20250907_1510"
        )  # Different strategy
        coid5 = make_coid(
            "XAUUSD", "BUY", "strategy1", "20250907_1511"
        )  # Different time

        ids = [coid1, coid2, coid3, coid4, coid5]
        assert len(set(ids)) == 5  # All unique

    def test_valid_characters(self):
        """Test that generated IDs contain only valid hex characters"""
        coid = make_coid("XAUUSD", "BUY", "test", "20250907_1510")

        # Should be valid hexadecimal string
        try:
            int(coid, 16)
        except ValueError:
            pytest.fail(f"Generated COID contains non-hex characters: {coid}")


class TestIdempotentOrderExecutor:
    """Test idempotent order execution functionality"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
            db_path = f.name
        yield db_path
        # Cleanup - force close any remaining connections
        try:
            Path(db_path).unlink(missing_ok=True)
        except PermissionError:
            # On Windows, SQLite files may be locked
            import time

            time.sleep(0.1)  # Brief delay
            try:
                Path(db_path).unlink(missing_ok=True)
            except PermissionError:
                pass  # Ignore cleanup failures in tests

    @pytest.fixture
    def fake_broker(self):
        """Create fake broker that accepts orders"""
        return FakeBroker(should_accept=True)

    @pytest.fixture
    def executor(self, fake_broker, temp_db):
        """Create executor with fake broker and temp database"""
        return IdempotentOrderExecutor(fake_broker, temp_db)

    def test_database_initialization(self, fake_broker, temp_db):
        """Test that database is created and initialized properly"""
        # Remove existing temp file from fixture creation
        Path(temp_db).unlink(missing_ok=True)

        # Database shouldn't exist yet
        assert not Path(temp_db).exists()

        # Create executor
        executor = IdempotentOrderExecutor(fake_broker, temp_db)

        # Database should now exist
        assert Path(temp_db).exists()

        # Verify table structure
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sent'"
            )
            assert cursor.fetchone() is not None

        # Explicitly close executor's connection for cleanup
        executor.close()

    def test_first_order_accepted(self, executor, fake_broker):
        """Test that first order with new COID is accepted"""
        request = OrderRequest(
            client_order_id="test_coid_001", symbol="XAUUSD", side=Side.BUY, qty=0.1
        )

        result = executor.place(request)

        # Should be accepted
        assert result.accepted is True
        assert result.broker_order_id == "B1"
        assert "Executed" in result.reason

        # Broker should have been called once
        assert fake_broker.call_count == 1
        assert fake_broker.last_request.client_order_id == "test_coid_001"

    def test_duplicate_order_blocked(self, executor, fake_broker):
        """Test that duplicate COID is blocked without calling broker"""
        request = OrderRequest(
            client_order_id="test_coid_002", symbol="XAUUSD", side=Side.BUY, qty=0.1
        )

        # First submission - should be accepted
        result1 = executor.place(request)
        assert result1.accepted is True
        assert result1.broker_order_id == "B1"
        assert fake_broker.call_count == 1

        # Second submission - should be blocked
        result2 = executor.place(request)
        assert result2.accepted is False
        assert result2.broker_order_id is None
        assert result2.reason == "DUPLICATE_COID"

        # Broker should still have been called only once
        assert fake_broker.call_count == 1

    def test_rejected_order_not_recorded(self, temp_db):
        """Test that rejected orders are not recorded (can be retried)"""
        fake_broker = FakeBroker(should_accept=False)
        executor = IdempotentOrderExecutor(fake_broker, temp_db)

        request = OrderRequest(
            client_order_id="test_coid_003", symbol="XAUUSD", side=Side.BUY, qty=0.1
        )

        # First attempt - should be rejected
        result1 = executor.place(request)
        assert result1.accepted is False
        assert result1.reason == "Insufficient margin"

        # Should not be recorded as already sent
        assert not executor.already_sent("test_coid_003")

        # Second attempt - should still call broker (not blocked)
        result2 = executor.place(request)
        assert result2.accepted is False
        assert fake_broker.call_count == 2  # Called twice

    def test_already_sent_check(self, executor, fake_broker):
        """Test already_sent method"""
        coid = "test_coid_004"

        # Initially not sent
        assert not executor.already_sent(coid)

        # Place order
        request = OrderRequest(
            client_order_id=coid, symbol="XAUUSD", side=Side.BUY, qty=0.1
        )

        result = executor.place(request)
        assert result.accepted is True

        # Now should be marked as sent
        assert executor.already_sent(coid)

    def test_record_method(self, executor):
        """Test explicit record method"""
        coid = "test_coid_005"
        broker_id = "manual_record"

        # Initially not recorded
        assert not executor.already_sent(coid)

        # Record manually
        executor.record(coid, broker_id)

        # Should now be recorded
        assert executor.already_sent(coid)

        # Verify in database
        orders = executor.get_sent_orders()
        matching = [o for o in orders if o["client_order_id"] == coid]
        assert len(matching) == 1
        assert matching[0]["broker_order_id"] == broker_id

    def test_get_sent_orders(self, executor, fake_broker):
        """Test retrieval of sent order history"""
        # Initially no orders
        orders = executor.get_sent_orders()
        assert len(orders) == 0

        # Place a few orders
        for i in range(3):
            request = OrderRequest(
                client_order_id=f"test_coid_00{i+6}",
                symbol="XAUUSD",
                side=Side.BUY,
                qty=0.1,
            )
            executor.place(request)

        # Get orders
        orders = executor.get_sent_orders()
        assert len(orders) == 3

        # Verify structure
        for order in orders:
            assert "client_order_id" in order
            assert "broker_order_id" in order
            assert "ts" in order
            assert order["broker_order_id"].startswith("B")

    def test_purge_old_records(self, executor, fake_broker):
        """Test purging old order records"""
        # Place some orders
        for i in range(5):
            request = OrderRequest(
                client_order_id=f"test_coid_0{i+10}",
                symbol="XAUUSD",
                side=Side.BUY,
                qty=0.1,
            )
            executor.place(request)

        # Should have 5 orders
        assert len(executor.get_sent_orders()) == 5

        # Purge old records (none should be old enough with positive days)
        count = executor.purge_old_records(days_old=30)
        assert count == 0
        assert len(executor.get_sent_orders()) == 5

        # Test manual deletion by manipulating the database timestamp
        # Make records appear old by updating their timestamp
        import sqlite3
        import tempfile
        from pathlib import Path

        # Update timestamps to make records appear old (1 year ago)
        with sqlite3.connect(executor.db_path) as conn:
            conn.execute("UPDATE sent SET ts = datetime('now', '-400 days')")

        # Now purge should remove all records
        count = executor.purge_old_records(days_old=30)
        assert count == 5
        assert len(executor.get_sent_orders()) == 0

    def test_broker_exception_handling(self, temp_db):
        """Test handling of broker exceptions"""

        # Create broker that raises exceptions
        class ExceptionBroker(FakeBroker):
            def place_order(self, request):
                raise RuntimeError("Broker connection failed")

        broker = ExceptionBroker()
        executor = IdempotentOrderExecutor(broker, temp_db)

        request = OrderRequest(
            client_order_id="test_coid_exception",
            symbol="XAUUSD",
            side=Side.BUY,
            qty=0.1,
        )

        # Should handle exception gracefully
        result = executor.place(request)
        assert result.accepted is False
        assert "Execution error" in result.reason
        assert "Broker connection failed" in result.reason

        # Should not be recorded as sent
        assert not executor.already_sent("test_coid_exception")

    def test_database_error_handling(self, fake_broker):
        """Test handling of database errors"""
        # Use invalid database path that will fail during __init__
        invalid_path = "\\\\invalid\\\\server\\\\path\\\\cannot\\\\create.sqlite"

        # Should raise on initialization due to invalid path
        try:
            executor = IdempotentOrderExecutor(fake_broker, invalid_path)
            # If it doesn't raise during __init__, check if it fails on first operation
            request = OrderRequest(
                client_order_id="test_fail", symbol="XAUUSD", side=Side.BUY, qty=0.1
            )
            result = executor.place(request)
            # Should return error result rather than raising
            assert result.accepted is False
            assert "error" in result.reason.lower()
        except (sqlite3.Error, OSError, PermissionError):
            # Any database/filesystem error is expected
            pass

    def test_repr(self, executor):
        """Test string representation"""
        repr_str = repr(executor)
        assert "IdempotentOrderExecutor" in repr_str
        assert "FakeBroker" in repr_str
        # Check for temp database path pattern instead of hardcoded name
        assert ".sqlite" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
