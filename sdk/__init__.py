"""
Enterprise AI Agent Framework SDK.

This package provides the core classes and utilities for building
enterprise-grade AI agent workflows with support for multi-tenancy,
guardrails, and comprehensive task orchestration.

Main Classes:
- Task: Represents a single executable task in a workflow
- Flow: Represents a complete workflow consisting of multiple tasks
- Guardrails: Provides validation and enforcement mechanisms
- TenantManager: Manages multi-tenant configurations and isolation
- TenantConfig: Configuration for a specific tenant
"""

from .task import Task
from .flow import Flow
from .guardrails import Guardrails, ValidationError
from .multitenancy import TenantManager, TenantConfig

__version__ = "1.0.0"
__author__ = "Enterprise AI Agent Framework Team"

__all__ = [
    "Task",
    "Flow", 
    "Guardrails",
    "ValidationError",
    "TenantManager",
    "TenantConfig"
]
