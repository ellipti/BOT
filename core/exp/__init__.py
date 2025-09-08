#!/usr/bin/env python3
"""
Experiment Module

A/B testing framework with assignment, guardrails, and reporting.

Components:
- assign.py: Deterministic A/B assignment
- guard.py: Guardrail monitoring and automatic rollback
- pipeline.py: Trading pipeline integration
"""

from .assign import (
    assign_arm,
    get_experiment_stats,
    is_experiment_active,
    get_assigner
)

from .guard import (
    get_guardrail_status,
    record_drawdown,
    record_order_filled,
    record_order_rejected,
    get_evaluator
)

from .pipeline import (
    get_experiment_metrics,
    handle_order_filled,
    handle_order_placed,
    handle_order_rejected,
    handle_risk_approved,
    handle_signal_detected,
    record_portfolio_drawdown,
    get_integrator
)

__all__ = [
    # Assignment functions
    "assign_arm",
    "get_experiment_stats", 
    "is_experiment_active",
    "get_assigner",
    
    # Guardrail functions
    "get_guardrail_status",
    "record_drawdown",
    "record_order_filled", 
    "record_order_rejected",
    "get_evaluator",
    
    # Pipeline integration
    "get_experiment_metrics",
    "handle_order_filled",
    "handle_order_placed",
    "handle_order_rejected", 
    "handle_risk_approved",
    "handle_signal_detected",
    "record_portfolio_drawdown",
    "get_integrator"
]
