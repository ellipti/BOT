"""
Position Aggregator - Handles position netting and reduction logic
Manages incoming orders against existing positions based on netting policy.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.positions.policy import NettingMode, ReduceRule

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Represents a trading position."""
    
    ticket: str
    symbol: str
    side: str  # "BUY" or "SELL"
    volume: float
    entry_price: float
    open_time: datetime
    sl: Optional[float] = None
    tp: Optional[float] = None
    
    @property
    def is_long(self) -> bool:
        """Check if position is long (BUY)."""
        return self.side == "BUY"
    
    @property
    def is_short(self) -> bool:
        """Check if position is short (SELL)."""
        return self.side == "SELL"


@dataclass
class ReduceAction:
    """Represents an action to reduce an existing position."""
    
    position_ticket: str
    reduce_volume: float
    close_price: float
    reason: str


@dataclass
class NettingResult:
    """Result of position netting operation."""
    
    reduce_actions: List[ReduceAction]
    remaining_volume: float
    average_close_price: float
    net_position_side: Optional[str]  # Final net position side if any
    summary: str


class PositionAggregator:
    """
    Handles position netting and aggregation logic.
    
    Manages incoming orders against existing positions based on configured
    netting mode and reduce rules.
    """
    
    def __init__(self, netting_mode: NettingMode = NettingMode.NETTING, 
                 reduce_rule: ReduceRule = ReduceRule.FIFO):
        """
        Initialize position aggregator.
        
        Args:
            netting_mode: NETTING or HEDGING mode
            reduce_rule: FIFO, LIFO, or PROPORTIONAL reduction rule
        """
        self.netting_mode = netting_mode
        self.reduce_rule = reduce_rule
        logger.info(f"PositionAggregator initialized: mode={netting_mode}, rule={reduce_rule}")
    
    def process_incoming_order(self, symbol: str, side: str, volume: float, 
                             price: float, existing_positions: List[Position]) -> NettingResult:
        """
        Process incoming order against existing positions.
        
        Args:
            symbol: Trading symbol
            side: Order side ("BUY" or "SELL")
            volume: Order volume
            price: Order price
            existing_positions: List of existing positions for symbol
            
        Returns:
            NettingResult with reduce actions and remaining volume
        """
        if self.netting_mode == NettingMode.HEDGING:
            # In hedging mode, no netting - all orders create new positions
            return NettingResult(
                reduce_actions=[],
                remaining_volume=volume,
                average_close_price=0.0,
                net_position_side=side,
                summary=f"HEDGING mode: New {side} {volume} position opened"
            )
        
        # NETTING mode - process against existing positions
        return self._process_netting(symbol, side, volume, price, existing_positions)
    
    def _process_netting(self, symbol: str, side: str, volume: float, 
                        price: float, existing_positions: List[Position]) -> NettingResult:
        """Process netting logic for incoming order."""
        
        # Filter opposite positions that can be reduced
        opposite_side = "SELL" if side == "BUY" else "BUY"
        opposite_positions = [p for p in existing_positions if p.side == opposite_side]
        
        if not opposite_positions:
            # No opposite positions to net against
            return NettingResult(
                reduce_actions=[],
                remaining_volume=volume,
                average_close_price=0.0,
                net_position_side=side,
                summary=f"NETTING: No opposite positions, new {side} {volume} opened"
            )
        
        # Calculate total opposite volume
        total_opposite_volume = sum(p.volume for p in opposite_positions)
        
        if volume >= total_opposite_volume:
            # Incoming order will close all opposite positions and create new net position
            reduce_actions = self._create_full_reduction(opposite_positions, price)
            remaining_volume = volume - total_opposite_volume
            avg_close_price = self._calculate_average_price(opposite_positions)
            
            if remaining_volume > 0:
                net_side = side
                summary = f"NETTING: Closed {total_opposite_volume} {opposite_side} @{avg_close_price:.5f}, opened {remaining_volume} {side}"
            else:
                net_side = None
                summary = f"NETTING: Closed {total_opposite_volume} {opposite_side} @{avg_close_price:.5f}, flat"
            
            return NettingResult(
                reduce_actions=reduce_actions,
                remaining_volume=remaining_volume,
                average_close_price=avg_close_price,
                net_position_side=net_side,
                summary=summary
            )
        
        else:
            # Incoming order will partially reduce opposite positions
            reduce_actions = self._create_partial_reduction(opposite_positions, volume, price)
            avg_close_price = self._calculate_average_price([p for p in opposite_positions if any(a.position_ticket == p.ticket for a in reduce_actions)])
            remaining_opposite = total_opposite_volume - volume
            
            return NettingResult(
                reduce_actions=reduce_actions,
                remaining_volume=0.0,
                average_close_price=avg_close_price,
                net_position_side=opposite_side,
                summary=f"NETTING: Reduced {volume} {opposite_side} @{avg_close_price:.5f}, {remaining_opposite} {opposite_side} remaining"
            )
    
    def _create_full_reduction(self, positions: List[Position], close_price: float) -> List[ReduceAction]:
        """Create reduce actions to close all positions fully."""
        actions = []
        for position in positions:
            actions.append(ReduceAction(
                position_ticket=position.ticket,
                reduce_volume=position.volume,
                close_price=close_price,
                reason=f"Full closure via netting"
            ))
        return actions
    
    def _create_partial_reduction(self, positions: List[Position], total_volume: float, 
                                close_price: float) -> List[ReduceAction]:
        """Create reduce actions for partial position reduction."""
        if self.reduce_rule == ReduceRule.FIFO:
            return self._reduce_fifo(positions, total_volume, close_price)
        elif self.reduce_rule == ReduceRule.LIFO:
            return self._reduce_lifo(positions, total_volume, close_price)
        elif self.reduce_rule == ReduceRule.PROPORTIONAL:
            return self._reduce_proportional(positions, total_volume, close_price)
        else:
            logger.warning(f"Unknown reduce rule {self.reduce_rule}, using FIFO")
            return self._reduce_fifo(positions, total_volume, close_price)
    
    def _reduce_fifo(self, positions: List[Position], total_volume: float, 
                    close_price: float) -> List[ReduceAction]:
        """Reduce positions using First In, First Out rule."""
        # Sort by open time (oldest first)
        sorted_positions = sorted(positions, key=lambda p: p.open_time)
        return self._reduce_sequential(sorted_positions, total_volume, close_price, "FIFO")
    
    def _reduce_lifo(self, positions: List[Position], total_volume: float, 
                    close_price: float) -> List[ReduceAction]:
        """Reduce positions using Last In, First Out rule."""
        # Sort by open time (newest first)
        sorted_positions = sorted(positions, key=lambda p: p.open_time, reverse=True)
        return self._reduce_sequential(sorted_positions, total_volume, close_price, "LIFO")
    
    def _reduce_sequential(self, sorted_positions: List[Position], total_volume: float,
                          close_price: float, rule_name: str) -> List[ReduceAction]:
        """Reduce positions sequentially based on sorted order."""
        actions = []
        remaining_volume = total_volume
        
        for position in sorted_positions:
            if remaining_volume <= 0:
                break
            
            if position.volume <= remaining_volume:
                # Close entire position
                actions.append(ReduceAction(
                    position_ticket=position.ticket,
                    reduce_volume=position.volume,
                    close_price=close_price,
                    reason=f"Full closure via {rule_name} netting"
                ))
                remaining_volume -= position.volume
            else:
                # Partial closure
                actions.append(ReduceAction(
                    position_ticket=position.ticket,
                    reduce_volume=remaining_volume,
                    close_price=close_price,
                    reason=f"Partial closure via {rule_name} netting"
                ))
                remaining_volume = 0
        
        return actions
    
    def _reduce_proportional(self, positions: List[Position], total_volume: float,
                           close_price: float) -> List[ReduceAction]:
        """Reduce positions proportionally across all positions."""
        actions = []
        total_position_volume = sum(p.volume for p in positions)
        
        if total_position_volume == 0:
            return actions
        
        for position in positions:
            proportion = position.volume / total_position_volume
            reduce_volume = min(total_volume * proportion, position.volume)
            
            if reduce_volume > 0:
                actions.append(ReduceAction(
                    position_ticket=position.ticket,
                    reduce_volume=reduce_volume,
                    close_price=close_price,
                    reason=f"Proportional closure ({proportion:.2%}) via netting"
                ))
        
        return actions
    
    def _calculate_average_price(self, positions: List[Position]) -> float:
        """Calculate volume-weighted average price of positions."""
        if not positions:
            return 0.0
        
        total_volume = sum(p.volume for p in positions)
        if total_volume == 0:
            return 0.0
        
        weighted_sum = sum(p.entry_price * p.volume for p in positions)
        return weighted_sum / total_volume
    
    def calculate_net_position(self, positions: List[Position]) -> Tuple[float, str]:
        """
        Calculate net position from list of positions.
        
        Returns:
            Tuple of (net_volume, net_side) where net_volume is always positive
            and net_side indicates direction. Returns (0.0, "FLAT") if flat.
        """
        long_volume = sum(p.volume for p in positions if p.is_long)
        short_volume = sum(p.volume for p in positions if p.is_short)
        
        net_volume = long_volume - short_volume
        
        if net_volume > 0:
            return abs(net_volume), "BUY"
        elif net_volume < 0:
            return abs(net_volume), "SELL"
        else:
            return 0.0, "FLAT"
