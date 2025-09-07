"""
Fake broker implementation for unit testing without MT5 dependency.

This module provides a complete fake broker that implements the same interface
as the real MT5 broker but works entirely in memory without external dependencies.
"""

import time
import uuid
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock

from core.events.bus import EventBus
from core.events.types import Filled, OrderPlaced, Rejected


class FakeBrokerConnection:
    """
    Fake broker connection that simulates MT5 broker behavior.

    This class provides:
    - Idempotent order execution
    - Event bus integration
    - Position sizing simulation
    - Market data simulation
    - No external dependencies
    """

    def __init__(self, event_bus: EventBus | None = None):
        self.event_bus = event_bus or EventBus()
        self.connected = True
        self.orders: dict[str, dict] = {}
        self.positions: dict[str, dict] = {}
        self.deals: list[dict] = []
        self.account_balance = 10000.0
        self.account_equity = 10000.0
        self.account_margin = 0.0

        # Fake market data
        self.market_data = {
            "EURUSD": {"bid": 1.0950, "ask": 1.0952, "point": 0.00001},
            "GBPUSD": {"bid": 1.2650, "ask": 1.2653, "point": 0.00001},
            "USDJPY": {"bid": 149.50, "ask": 149.53, "point": 0.01},
            "USDCHF": {"bid": 0.8750, "ask": 0.8753, "point": 0.00001},
        }

    def is_connected(self) -> bool:
        """Check if broker is connected"""
        return self.connected

    def connect(self) -> bool:
        """Simulate connection"""
        self.connected = True
        return True

    def disconnect(self) -> None:
        """Simulate disconnection"""
        self.connected = False

    def get_account_info(self) -> dict[str, Any]:
        """Get fake account information"""
        return {
            "login": 12345678,
            "balance": self.account_balance,
            "equity": self.account_equity,
            "margin": self.account_margin,
            "margin_free": self.account_equity - self.account_margin,
            "margin_level": (
                (self.account_equity / self.account_margin * 100)
                if self.account_margin > 0
                else 0.0
            ),
            "leverage": 100,
            "currency": "USD",
            "trade_allowed": True,
            "server": "FakeBroker-Demo",
        }

    def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get fake symbol information"""
        if symbol not in self.market_data:
            return None

        data = self.market_data[symbol]
        return {
            "name": symbol,
            "digits": 5 if data["point"] == 0.00001 else 3,
            "point": data["point"],
            "trade_stops_level": 10,
            "trade_mode": 4,  # Full trading
            "volume_min": 0.01,
            "volume_max": 500.0,
            "volume_step": 0.01,
            "contract_size": 100000,
            "bid": data["bid"],
            "ask": data["ask"],
            "spread": int((data["ask"] - data["bid"]) / data["point"]),
            "visible": True,
            "select": True,
        }

    def submit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        order_type: str = "market",
        price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit an order with idempotent behavior.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            volume: Order volume
            order_type: "market", "limit", "stop"
            price: Order price for limit/stop orders
            stop_loss: Stop loss price
            take_profit: Take profit price
            client_order_id: Client-side order ID for idempotency

        Returns:
            Dict with order result
        """
        if not self.connected:
            result = {
                "success": False,
                "error": "Not connected",
                "retcode": 10031,  # Connection error
                "client_order_id": client_order_id,
            }

            if client_order_id and self.event_bus:
                self.event_bus.publish(
                    Rejected(
                        client_order_id=client_order_id,
                        symbol=symbol,
                        reason="Connection error",
                        timestamp=datetime.now(UTC),
                    )
                )
            return result

        # Generate order ID
        order_id = str(uuid.uuid4())[:8]
        if client_order_id is None:
            client_order_id = f"fake_{order_id}"

        # Check for duplicate client_order_id (idempotency)
        for existing_order in self.orders.values():
            if existing_order.get("client_order_id") == client_order_id:
                # Return existing order result
                return {
                    "success": True,
                    "order_id": existing_order["order_id"],
                    "client_order_id": client_order_id,
                    "retcode": 10009,  # Done
                    "price": existing_order["price"],
                    "volume": existing_order["volume"],
                }

        # Validate symbol
        symbol_info = self.get_symbol_info(symbol)
        if not symbol_info:
            result = {
                "success": False,
                "error": f"Unknown symbol: {symbol}",
                "retcode": 10013,  # Invalid
                "client_order_id": client_order_id,
            }

            if self.event_bus:
                self.event_bus.publish(
                    Rejected(
                        client_order_id=client_order_id,
                        symbol=symbol,
                        reason=f"Unknown symbol: {symbol}",
                        timestamp=datetime.now(UTC),
                    )
                )
            return result

        # Validate volume
        if volume < symbol_info["volume_min"] or volume > symbol_info["volume_max"]:
            result = {
                "success": False,
                "error": f"Invalid volume: {volume}",
                "retcode": 10014,  # Invalid volume
                "client_order_id": client_order_id,
            }

            if self.event_bus:
                self.event_bus.publish(
                    Rejected(
                        client_order_id=client_order_id,
                        symbol=symbol,
                        reason=f"Invalid volume: {volume}",
                        timestamp=datetime.now(UTC),
                    )
                )
            return result

        # Determine execution price
        market_data = self.market_data[symbol]
        if order_type == "market":
            execution_price = (
                market_data["ask"] if side == "buy" else market_data["bid"]
            )
        else:
            execution_price = price or (
                market_data["ask"] if side == "buy" else market_data["bid"]
            )

        # Create order record
        order_record = {
            "order_id": order_id,
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "order_type": order_type,
            "price": execution_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "status": "filled" if order_type == "market" else "pending",
            "timestamp": datetime.now(UTC),
            "filled_volume": volume if order_type == "market" else 0.0,
        }

        self.orders[order_id] = order_record

        # Publish events
        if self.event_bus:
            # Submit event
            self.event_bus.publish(
                OrderPlaced(
                    client_order_id=client_order_id,
                    symbol=symbol,
                    side=side,
                    qty=volume,
                    sl=stop_loss,
                    tp=take_profit,
                    timestamp=order_record["timestamp"],
                )
            )

            # For market orders, immediately fill
            if order_type == "market":
                self._execute_fill(order_record)

        return {
            "success": True,
            "order_id": order_id,
            "client_order_id": client_order_id,
            "retcode": 10009,  # Done
            "price": execution_price,
            "volume": volume,
        }

    def _execute_fill(self, order_record: dict) -> None:
        """Execute order fill and update positions"""
        symbol = order_record["symbol"]
        side = order_record["side"]
        volume = order_record["volume"]
        price = order_record["price"]

        # Update positions
        position_key = symbol
        if position_key not in self.positions:
            self.positions[position_key] = {
                "symbol": symbol,
                "volume": 0.0,
                "avg_price": 0.0,
                "unrealized_pnl": 0.0,
            }

        position = self.positions[position_key]

        # Calculate new position
        if side == "buy":
            new_volume = position["volume"] + volume
        else:
            new_volume = position["volume"] - volume

        if new_volume != 0:
            # Update average price
            if (position["volume"] > 0 and side == "buy") or (
                position["volume"] < 0 and side == "sell"
            ):
                # Adding to position
                total_cost = (position["volume"] * position["avg_price"]) + (
                    volume * price
                )
                position["avg_price"] = (
                    total_cost / new_volume if new_volume != 0 else price
                )
            else:
                # Opposite direction - use new price
                position["avg_price"] = price

        position["volume"] = new_volume

        # Remove position if volume is zero
        if abs(new_volume) < 0.001:
            del self.positions[position_key]

        # Create deal record
        deal_record = {
            "deal_id": str(uuid.uuid4())[:8],
            "order_id": order_record["order_id"],
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "price": price,
            "timestamp": order_record["timestamp"],
            "commission": volume * 0.01,  # Fake commission
            "profit": 0.0,  # Will be calculated later
        }

        self.deals.append(deal_record)

        # Publish fill event
        if self.event_bus:
            self.event_bus.publish(
                Filled(
                    client_order_id=order_record["client_order_id"],
                    broker_order_id=order_record["order_id"],
                    price=price,
                    qty=volume,
                    timestamp=order_record["timestamp"],
                )
            )

    def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions"""
        positions = []
        for pos in self.positions.values():
            # Calculate unrealized P&L
            symbol = pos["symbol"]
            if symbol in self.market_data:
                market_data = self.market_data[symbol]
                current_price = (
                    market_data["bid"] if pos["volume"] > 0 else market_data["ask"]
                )
                price_diff = current_price - pos["avg_price"]
                unrealized_pnl = pos["volume"] * price_diff * 100000  # Contract size

                positions.append(
                    {
                        "symbol": symbol,
                        "volume": pos["volume"],
                        "price_open": pos["avg_price"],
                        "price_current": current_price,
                        "profit": unrealized_pnl,
                        "timestamp": datetime.now(UTC),
                    }
                )

        return positions

    def get_orders(self) -> list[dict[str, Any]]:
        """Get pending orders"""
        return [order for order in self.orders.values() if order["status"] == "pending"]

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a pending order"""
        if order_id not in self.orders:
            return {
                "success": False,
                "error": f"Order not found: {order_id}",
                "retcode": 10013,
            }

        order = self.orders[order_id]
        if order["status"] != "pending":
            return {
                "success": False,
                "error": f"Order not pending: {order_id}",
                "retcode": 10013,
            }

        order["status"] = "cancelled"

        return {"success": True, "order_id": order_id, "retcode": 10009}

    def get_historical_data(
        self, symbol: str, timeframe: str = "M1", count: int = 100
    ) -> list[dict[str, Any]]:
        """Get fake historical data"""
        if symbol not in self.market_data:
            return []

        market_data = self.market_data[symbol]
        base_price = (market_data["bid"] + market_data["ask"]) / 2

        # Generate fake OHLC data
        rates = []
        current_time = int(time.time())

        for i in range(count):
            # Simple random walk
            variation = (i % 20 - 10) * 0.0001
            open_price = base_price + variation
            close_price = open_price + ((i % 7 - 3) * 0.0001)
            high_price = max(open_price, close_price) + (i % 3) * 0.0001
            low_price = min(open_price, close_price) - (i % 3) * 0.0001

            rates.append(
                {
                    "time": current_time - (count - i) * 60,  # 1 minute intervals
                    "open": round(open_price, 5),
                    "high": round(high_price, 5),
                    "low": round(low_price, 5),
                    "close": round(close_price, 5),
                    "tick_volume": 100 + (i % 50),
                    "real_volume": 0,
                }
            )

        return rates


class FakeBrokerAdapter:
    """
    Adapter class that mimics the MT5Broker interface but uses FakeBrokerConnection.

    This can be used as a drop-in replacement for MT5Broker in unit tests.
    """

    def __init__(self, settings: Any = None, event_bus: EventBus | None = None):
        self.settings = settings or MagicMock()
        self.event_bus = event_bus or EventBus()
        self.connection = FakeBrokerConnection(self.event_bus)
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected and self.connection.is_connected()

    def connect(self) -> bool:
        """Connect to fake broker"""
        success = self.connection.connect()
        self._connected = success
        return success

    def disconnect(self) -> None:
        """Disconnect from fake broker"""
        self.connection.disconnect()
        self._connected = False

    def submit_market_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit a market order"""
        return self.connection.submit_order(
            symbol=symbol,
            side=side,
            volume=volume,
            order_type="market",
            stop_loss=stop_loss,
            take_profit=take_profit,
            client_order_id=client_order_id,
        )

    def submit_limit_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Submit a limit order"""
        return self.connection.submit_order(
            symbol=symbol,
            side=side,
            volume=volume,
            order_type="limit",
            price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            client_order_id=client_order_id,
        )

    def get_account_info(self) -> dict[str, Any]:
        """Get account information"""
        return self.connection.get_account_info()

    def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """Get symbol information"""
        return self.connection.get_symbol_info(symbol)

    def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions"""
        return self.connection.get_positions()

    def get_orders(self) -> list[dict[str, Any]]:
        """Get pending orders"""
        return self.connection.get_orders()

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an order"""
        return self.connection.cancel_order(order_id)

    def get_historical_data(
        self, symbol: str, timeframe: str = "M1", count: int = 100
    ) -> list[dict[str, Any]]:
        """Get historical data"""
        return self.connection.get_historical_data(symbol, timeframe, count)
