"""
Trailing Stop and Breakeven Logic
Advanced stop management with profit-based breakeven and trailing stops.
"""

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TrailingStopManager:
    """
    Manages trailing stops and breakeven logic for open positions.

    Features:
    - Breakeven at configurable profit threshold
    - Trailing stop with minimum step and profit buffer
    - Symbol-specific point value calculations
    - Thread-safe position tracking
    """

    def __init__(self, mt5):
        """
        Initialize trailing stop manager

        Args:
            mt5: MetaTrader5 module instance
        """
        self.mt5 = mt5
        self._position_states: dict[str, dict] = {}  # Track position states

        logger.info("TrailingStopManager initialized")

    def compute_breakeven_sl(
        self, position, breakeven_threshold_pips: float = 10.0, buffer_pips: float = 2.0
    ) -> float | None:
        """
        Compute breakeven stop loss when position is profitable.

        Args:
            position: MT5 position object
            breakeven_threshold_pips: Profit threshold to trigger breakeven (pips)
            buffer_pips: Buffer above/below entry for breakeven SL (pips)

        Returns:
            New stop loss price, or None if breakeven not triggered
        """
        try:
            symbol = position.symbol
            entry_price = float(position.price_open)
            current_price = float(position.price_current)
            volume = float(position.volume)
            position_type = position.type

            # Get symbol info for point value
            symbol_info = self.mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Cannot get symbol info for {symbol}")
                return None

            point = float(symbol_info.point)

            # Calculate current profit in pips
            if position_type == 0:  # BUY position
                profit_pips = (current_price - entry_price) / point
                breakeven_sl = entry_price + (buffer_pips * point)
            else:  # SELL position
                profit_pips = (entry_price - current_price) / point
                breakeven_sl = entry_price - (buffer_pips * point)

            # Check if profit threshold reached
            if profit_pips >= breakeven_threshold_pips:
                logger.info(
                    f"Breakeven triggered for {symbol} ticket {position.ticket}: "
                    f"profit={profit_pips:.1f} pips >= {breakeven_threshold_pips} "
                    f"→ SL={breakeven_sl:.5f}"
                )
                return breakeven_sl

            return None

        except Exception as e:
            logger.error(f"Error computing breakeven SL: {e}")
            return None

    def compute_trailing_sl(
        self,
        position,
        trailing_step_pips: float = 5.0,
        trailing_buffer_pips: float = 10.0,
    ) -> float | None:
        """
        Compute trailing stop loss based on current favorable price movement.

        Args:
            position: MT5 position object
            trailing_step_pips: Minimum step to move trailing stop (pips)
            trailing_buffer_pips: Buffer distance behind current price (pips)

        Returns:
            New trailing stop loss price, or None if no update needed
        """
        try:
            symbol = position.symbol
            ticket = str(position.ticket)
            entry_price = float(position.price_open)
            current_price = float(position.price_current)
            current_sl = float(position.sl) if position.sl else None
            position_type = position.type

            # Get symbol info
            symbol_info = self.mt5.symbol_info(symbol)
            if not symbol_info:
                logger.error(f"Cannot get symbol info for {symbol}")
                return None

            point = float(symbol_info.point)

            # Calculate proposed trailing SL
            if position_type == 0:  # BUY position
                # Trail below current price
                proposed_sl = current_price - (trailing_buffer_pips * point)

                # Only update if moving SL up (more favorable)
                if current_sl is None or proposed_sl > current_sl:
                    # Check minimum step requirement
                    if current_sl is None or (proposed_sl - current_sl) >= (
                        trailing_step_pips * point - 1e-9
                    ):
                        return proposed_sl

            else:  # SELL position
                # Trail above current price
                proposed_sl = current_price + (trailing_buffer_pips * point)

                # Only update if moving SL down (more favorable)
                if current_sl is None or proposed_sl < current_sl:
                    # Check minimum step requirement
                    if current_sl is None or (current_sl - proposed_sl) >= (
                        trailing_step_pips * point - 1e-9
                    ):
                        return proposed_sl

            return None

        except Exception as e:
            logger.error(f"Error computing trailing SL: {e}")
            return None

    def update_position_stops(
        self, ticket: str, sl: float | None = None, tp: float | None = None
    ) -> bool:
        """
        Update stop loss and/or take profit for a position.

        Args:
            ticket: Position ticket number
            sl: New stop loss price
            tp: New take profit price

        Returns:
            True if update was successful
        """
        try:
            request = {
                "action": self.mt5.TRADE_ACTION_SLTP,
                "position": int(ticket),
                "sl": sl or 0.0,
                "tp": tp or 0.0,
            }

            result = self.mt5.order_send(request)

            if result and result.retcode == self.mt5.TRADE_RETCODE_DONE:
                logger.info(f"Stops updated for ticket {ticket}: SL={sl}, TP={tp}")
                return True
            else:
                error_msg = f"Failed to update stops for ticket {ticket}"
                if result:
                    error_msg += f": retcode={result.retcode}, comment={getattr(result, 'comment', 'N/A')}"
                logger.error(error_msg)
                return False

        except Exception as e:
            logger.error(f"Error updating stops for ticket {ticket}: {e}")
            return False

    def process_position_trailing(
        self,
        position,
        breakeven_threshold: float = 10.0,
        breakeven_buffer: float = 2.0,
        trailing_step: float = 5.0,
        trailing_buffer: float = 10.0,
    ) -> str | None:
        """
        Process trailing logic for a single position.

        Args:
            position: MT5 position object
            breakeven_threshold: Breakeven trigger threshold (pips)
            breakeven_buffer: Breakeven buffer (pips)
            trailing_step: Trailing stop minimum step (pips)
            trailing_buffer: Trailing stop buffer (pips)

        Returns:
            Action taken: "breakeven", "trailing", or None
        """
        ticket = str(position.ticket)
        symbol = position.symbol

        try:
            # Check position state
            position_state = self._position_states.get(ticket, {})
            breakeven_applied = position_state.get("breakeven_applied", False)

            action_taken = None

            if not breakeven_applied:
                # Try breakeven first
                breakeven_sl = self.compute_breakeven_sl(
                    position, breakeven_threshold, breakeven_buffer
                )

                if breakeven_sl is not None:
                    if self.update_position_stops(ticket, sl=breakeven_sl):
                        # Mark breakeven as applied
                        self._position_states[ticket] = {
                            **position_state,
                            "breakeven_applied": True,
                            "last_trailing_sl": breakeven_sl,
                        }
                        action_taken = "breakeven"

            if not action_taken:
                # Try trailing stop
                trailing_sl = self.compute_trailing_sl(
                    position, trailing_step, trailing_buffer
                )

                if trailing_sl is not None:
                    if self.update_position_stops(ticket, sl=trailing_sl):
                        # Update trailing state
                        self._position_states[ticket] = {
                            **position_state,
                            "last_trailing_sl": trailing_sl,
                        }
                        action_taken = "trailing"

            return action_taken

        except Exception as e:
            logger.error(f"Error processing trailing for {symbol} ticket {ticket}: {e}")
            return None

    def process_all_positions(self, **kwargs) -> dict[str, str]:
        """
        Process trailing logic for all open positions.

        Args:
            **kwargs: Parameters to pass to process_position_trailing

        Returns:
            Dictionary mapping ticket to action taken
        """
        actions = {}

        try:
            positions = self.mt5.positions_get()
            if not positions:
                return actions

            logger.debug(f"Processing trailing logic for {len(positions)} positions")

            for position in positions:
                ticket = str(position.ticket)
                action = self.process_position_trailing(position, **kwargs)

                if action:
                    actions[ticket] = action

        except Exception as e:
            logger.error(f"Error processing all positions: {e}")

        return actions

    def cleanup_closed_positions(self) -> int:
        """
        Clean up tracking state for closed positions.

        Returns:
            Number of position states cleaned up
        """
        try:
            # Get current open position tickets
            positions = self.mt5.positions_get()
            open_tickets = (
                {str(pos.ticket) for pos in positions} if positions else set()
            )

            # Remove states for closed positions
            closed_tickets = []
            for ticket in list(self._position_states.keys()):
                if ticket not in open_tickets:
                    closed_tickets.append(ticket)

            for ticket in closed_tickets:
                del self._position_states[ticket]

            if closed_tickets:
                logger.debug(f"Cleaned up {len(closed_tickets)} closed position states")

            return len(closed_tickets)

        except Exception as e:
            logger.error(f"Error cleaning up position states: {e}")
            return 0

    def get_position_state(self, ticket: str) -> dict[str, Any]:
        """
        Get tracking state for a position.

        Args:
            ticket: Position ticket number

        Returns:
            Position state dictionary
        """
        return self._position_states.get(ticket, {})

    def reset_position_state(self, ticket: str) -> None:
        """
        Reset tracking state for a position.

        Args:
            ticket: Position ticket number
        """
        if ticket in self._position_states:
            del self._position_states[ticket]
            logger.debug(f"Reset state for position {ticket}")


def create_trailing_stop_manager(mt5) -> TrailingStopManager:
    """
    Factory function to create a TrailingStopManager instance.

    Args:
        mt5: MetaTrader5 module instance

    Returns:
        TrailingStopManager instance
    """
    return TrailingStopManager(mt5)
