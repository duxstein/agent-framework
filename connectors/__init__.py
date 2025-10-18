"""
Connectors package for Enterprise AI Agent Framework.

This package provides pluggable connectors for external services
with support for dynamic discovery, authentication, and action execution.

Main Components:
- BaseConnector: Abstract base class for all connectors
- ConnectorRegistry: Dynamic discovery and management of connectors
- Reference Connectors: Gmail, Slack, Postgres, LLM, OCR

Connector Interface:
- authenticate(credentials): Authenticate with external service
- execute_action(action_name, params): Execute specific actions
- list_actions(): List available actions for the connector
"""

from .base import BaseConnector, ConnectorStatus, ConnectorError, AuthenticationError, ActionError
from .registry import ConnectorRegistry, get_global_registry, register_connector, create_connector

# Reference connectors
from .gmail import GmailConnector
from .slack import SlackConnector
from .postgres import PostgresConnector
from .llm import LLMConnector
from .ocr import OCRConnector

__version__ = "1.0.0"
__author__ = "Enterprise AI Agent Framework Team"

__all__ = [
    # Base classes
    "BaseConnector",
    "ConnectorStatus", 
    "ConnectorError",
    "AuthenticationError",
    "ActionError",
    
    # Registry
    "ConnectorRegistry",
    "get_global_registry",
    "register_connector", 
    "create_connector",
    
    # Reference connectors
    "GmailConnector",
    "SlackConnector", 
    "PostgresConnector",
    "LLMConnector",
    "OCRConnector"
]
