#!/usr/bin/env python3
"""
Experiment Pipeline Integration

Enhances the trading pipeline with A/B experiment tracking.
Injects experiment arm assignment and monitors experiment metrics.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from core.events.types import Filled, OrderPlaced, Rejected, RiskApproved, SignalDetected
from core.exp.assign import assign_arm, is_experiment_active
from core.exp.guard import record_drawdown, record_order_filled, record_order_rejected
from observability.metrics import get_metrics

logger = logging.getLogger(__name__)


class ExperimentPipelineIntegrator:
    """Integrates A/B experiments into the trading pipeline"""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.order_times = {}  # Track order placement times for fill latency
        
    def handle_signal_detected(self, event: SignalDetected) -> SignalDetected:
        """
        Handle SignalDetected event - assign experiment arm and modify strategy_id
        
        Args:
            event: Original signal event
            
        Returns:
            Modified event with experiment arm assignment
        """
        if not is_experiment_active():
            # No experiment active, return original event
            return event
        
        try:
            # Assign experiment arm
            arm_name, arm_config = assign_arm(event.symbol)
            experiment_strategy_id = arm_config.get("strategy_id", event.strategy_id)
            
            # Create modified event with experiment strategy
            modified_event = SignalDetected(
                ts=event.ts,
                symbol=event.symbol,
                side=event.side,
                strength=event.strength,
                strategy_id=experiment_strategy_id
            )
            
            # Add experiment metadata (if events support extra fields)
            if hasattr(modified_event, '__dict__'):
                modified_event.__dict__['exp_arm'] = arm_name
                modified_event.__dict__['exp_original_strategy'] = event.strategy_id
            
            # Record assignment metric
            self.metrics.inc("experiment_signal_assigned",
                           symbol=event.symbol,
                           arm=arm_name, 
                           strategy=experiment_strategy_id,
                           side=event.side)
            
            logger.debug(f"Assigned {event.symbol} signal to experiment arm {arm_name} (strategy: {experiment_strategy_id})")
            
            return modified_event
            
        except Exception as e:
            logger.error(f"Failed to assign experiment arm: {e}")
            return event
    
    def handle_risk_approved(self, event: RiskApproved) -> None:
        """
        Handle RiskApproved event - record experiment metrics
        
        Args:
            event: Risk approval event
        """
        if not is_experiment_active():
            return
        
        try:
            # Get arm assignment (if available)
            arm_name = getattr(event, 'exp_arm', None)
            if not arm_name:
                # Try to assign based on current strategy
                arm_name, _ = assign_arm(event.symbol)
            
            # Record risk approval metric
            self.metrics.inc("experiment_risk_approved",
                           symbol=event.symbol,
                           arm=arm_name,
                           strategy=event.strategy_id,
                           side=event.side)
            
            # Record position size metric
            self.metrics.observe("experiment_position_size", event.qty,
                               symbol=event.symbol,
                               arm=arm_name,
                               strategy=event.strategy_id)
            
            logger.debug(f"Recorded risk approval for arm {arm_name}: {event.qty} lots")
            
        except Exception as e:
            logger.error(f"Failed to record risk approval metrics: {e}")
    
    def handle_order_placed(self, event: OrderPlaced) -> None:
        """
        Handle OrderPlaced event - record placement time and metrics
        
        Args:
            event: Order placement event
        """
        if not is_experiment_active():
            return
        
        try:
            # Get arm assignment
            arm_name = getattr(event, 'exp_arm', None)
            if not arm_name:
                arm_name, _ = assign_arm(event.symbol)
            
            # Record placement time for fill latency calculation
            self.order_times[event.client_order_id] = {
                'placement_time': event.ts,
                'arm': arm_name,
                'symbol': event.symbol
            }
            
            # Record order placement metric
            self.metrics.inc("experiment_order_placed",
                           symbol=event.symbol,
                           arm=arm_name,
                           side=event.side)
            
            logger.debug(f"Recorded order placement for arm {arm_name}: {event.client_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to record order placement metrics: {e}")
    
    def handle_order_filled(self, event: Filled) -> None:
        """
        Handle Filled event - record fill metrics and guardrail data
        
        Args:
            event: Order fill event
        """
        if not is_experiment_active():
            return
        
        try:
            # Get order placement info
            order_info = self.order_times.pop(event.client_order_id, None)
            
            if order_info:
                arm_name = order_info['arm']
                symbol = order_info['symbol']
                
                # Calculate fill latency
                fill_latency_ms = (event.ts - order_info['placement_time']).total_seconds() * 1000
                
                # Record fill metrics
                self.metrics.inc("experiment_order_filled",
                               symbol=symbol,
                               arm=arm_name)
                
                self.metrics.observe("experiment_fill_latency_ms", fill_latency_ms,
                                   symbol=symbol,
                                   arm=arm_name)
                
                # Record for guardrail monitoring
                record_order_filled(arm_name, symbol, fill_latency_ms)
                
                logger.debug(f"Recorded fill for arm {arm_name}: {fill_latency_ms:.1f}ms latency")
            else:
                logger.warning(f"No placement info found for filled order: {event.client_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to record fill metrics: {e}")
    
    def handle_order_rejected(self, event: Rejected) -> None:
        """
        Handle Rejected event - record rejection metrics and guardrail data
        
        Args:
            event: Order rejection event
        """
        if not is_experiment_active():
            return
        
        try:
            # Get order placement info
            order_info = self.order_times.pop(event.client_order_id, None)
            
            if order_info:
                arm_name = order_info['arm']
                symbol = order_info['symbol']
                
                # Record rejection metrics
                self.metrics.inc("experiment_order_rejected",
                               symbol=symbol,
                               arm=arm_name,
                               reason=event.reason)
                
                # Record for guardrail monitoring
                record_order_rejected(arm_name, symbol)
                
                logger.debug(f"Recorded rejection for arm {arm_name}: {event.reason}")
            else:
                logger.warning(f"No placement info found for rejected order: {event.client_order_id}")
            
        except Exception as e:
            logger.error(f"Failed to record rejection metrics: {e}")
    
    def record_portfolio_drawdown(self, symbol: str, drawdown_pct: float) -> None:
        """
        Record portfolio drawdown for experiment monitoring
        
        Args:
            symbol: Trading symbol
            drawdown_pct: Drawdown percentage (0.0-1.0)
        """
        if not is_experiment_active():
            return
        
        try:
            # Get current arm assignment for symbol
            arm_name, _ = assign_arm(symbol)
            
            # Record drawdown metric
            self.metrics.observe("experiment_drawdown_pct", drawdown_pct * 100,
                               symbol=symbol,
                               arm=arm_name)
            
            # Record for guardrail monitoring
            record_drawdown(arm_name, drawdown_pct)
            
            logger.debug(f"Recorded drawdown for arm {arm_name}: {drawdown_pct:.3f}%")
            
        except Exception as e:
            logger.error(f"Failed to record drawdown metrics: {e}")
    
    def get_experiment_metrics(self) -> Dict:
        """Get current experiment metrics summary"""
        try:
            from core.exp.assign import get_experiment_stats
            from core.exp.guard import get_guardrail_status
            
            return {
                "assignment": get_experiment_stats(),
                "guardrails": get_guardrail_status(),
                "active_orders": len(self.order_times),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get experiment metrics: {e}")
            return {"error": str(e)}


# Global integrator instance
_integrator: Optional[ExperimentPipelineIntegrator] = None


def get_integrator() -> ExperimentPipelineIntegrator:
    """Get global experiment pipeline integrator"""
    global _integrator
    if _integrator is None:
        _integrator = ExperimentPipelineIntegrator()
    return _integrator


# Event handler functions for easy integration
def handle_signal_detected(event: SignalDetected) -> SignalDetected:
    """Handle signal detected event with experiment assignment"""
    return get_integrator().handle_signal_detected(event)


def handle_risk_approved(event: RiskApproved) -> None:
    """Handle risk approved event with experiment tracking"""
    get_integrator().handle_risk_approved(event)


def handle_order_placed(event: OrderPlaced) -> None:
    """Handle order placed event with experiment tracking"""
    get_integrator().handle_order_placed(event)


def handle_order_filled(event: Filled) -> None:
    """Handle order filled event with experiment tracking"""
    get_integrator().handle_order_filled(event)


def handle_order_rejected(event: Rejected) -> None:
    """Handle order rejected event with experiment tracking"""
    get_integrator().handle_order_rejected(event)


def record_portfolio_drawdown(symbol: str, drawdown_pct: float) -> None:
    """Record portfolio drawdown for experiment monitoring"""
    get_integrator().record_portfolio_drawdown(symbol, drawdown_pct)


def get_experiment_metrics() -> Dict:
    """Get current experiment metrics"""
    return get_integrator().get_experiment_metrics()


if __name__ == "__main__":
    # Test the pipeline integration
    import json
    from datetime import datetime, timezone
    
    integrator = ExperimentPipelineIntegrator()
    
    # Test signal assignment
    signal = SignalDetected(
        symbol="XAUUSD",
        side="BUY",
        strength=0.85,
        strategy_id="baseline_ma"
    )
    
    modified_signal = integrator.handle_signal_detected(signal)
    print(f"Original strategy: {signal.strategy_id}")
    print(f"Assigned strategy: {modified_signal.strategy_id}")
    print(f"Assigned arm: {getattr(modified_signal, 'exp_arm', 'none')}")
    
    # Test metrics
    metrics = integrator.get_experiment_metrics()
    print(f"\nExperiment metrics:")
    print(json.dumps(metrics, indent=2, default=str))
