"""
Base connector interface for Enterprise AI Agent Framework.

Defines the standard interface that all connectors must implement
for authentication, action execution, and discovery.
"""

import abc
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from enum import Enum


class ConnectorStatus(Enum):
    """Status of a connector."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


class ConnectorError(Exception):
    """Base exception for connector errors."""
    pass


class AuthenticationError(ConnectorError):
    """Exception raised when authentication fails."""
    pass


class ActionError(ConnectorError):
    """Exception raised when action execution fails."""
    pass


class BaseConnector(abc.ABC):
    """
    Abstract base class for all connectors.
    
    All connectors must inherit from this class and implement
    the required methods for authentication, action execution,
    and action discovery.
    
    Attributes:
        name (str): Name of the connector
        version (str): Version of the connector
        status (ConnectorStatus): Current connection status
        tenant_id (Optional[str]): Tenant identifier for multi-tenancy
        last_activity (Optional[datetime]): Last activity timestamp
        metadata (Dict[str, Any]): Additional connector metadata
    """
    
    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        tenant_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the base connector.
        
        Args:
            name (str): Name of the connector
            version (str): Version of the connector
            tenant_id (Optional[str]): Tenant identifier for multi-tenancy
            metadata (Optional[Dict[str, Any]]): Additional metadata
        """
        self.name = name
        self.version = version
        self.status = ConnectorStatus.DISCONNECTED
        self.tenant_id = tenant_id
        self.last_activity: Optional[datetime] = None
        self.metadata = metadata or {}
        self._credentials: Optional[Dict[str, Any]] = None
    
    @abc.abstractmethod
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with the external service.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
            
        Returns:
            bool: True if authentication successful, False otherwise
            
        Raises:
            AuthenticationError: If authentication fails
        """
        pass
    
    @abc.abstractmethod
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a specific action.
        
        Args:
            action_name (str): Name of the action to execute
            params (Dict[str, Any]): Parameters for the action
            
        Returns:
            Dict[str, Any]: Result of the action execution
            
        Raises:
            ActionError: If action execution fails
            AuthenticationError: If not authenticated
        """
        pass
    
    @abc.abstractmethod
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available actions for this connector.
        
        Returns:
            List[Dict[str, Any]]: List of available actions with metadata
        """
        pass
    
    def disconnect(self) -> None:
        """
        Disconnect from the external service.
        
        This method should clean up any resources and reset the
        connector to a disconnected state.
        """
        self.status = ConnectorStatus.DISCONNECTED
        self._credentials = None
        self.last_activity = None
    
    def is_connected(self) -> bool:
        """
        Check if the connector is connected.
        
        Returns:
            bool: True if connected, False otherwise
        """
        return self.status == ConnectorStatus.CONNECTED
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the connector.
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            'name': self.name,
            'version': self.version,
            'status': self.status.value,
            'tenant_id': self.tenant_id,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'is_connected': self.is_connected(),
            'metadata': self.metadata
        }
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.utcnow()
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for a specific action.
        
        This is a default implementation that can be overridden
        by subclasses for specific validation logic.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not isinstance(params, dict):
            return False
        
        # Get action definition
        actions = self.list_actions()
        action_def = next((a for a in actions if a['name'] == action_name), None)
        
        if not action_def:
            return False
        
        # Check required parameters
        required_params = action_def.get('required_params', [])
        for param in required_params:
            if param not in params:
                return False
        
        return True
    
    def get_action_info(self, action_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific action.
        
        Args:
            action_name (str): Name of the action
            
        Returns:
            Optional[Dict[str, Any]]: Action information if found, None otherwise
        """
        actions = self.list_actions()
        return next((a for a in actions if a['name'] == action_name), None)
    
    def __repr__(self) -> str:
        """String representation of the connector."""
        return f"{self.__class__.__name__}(name='{self.name}', status={self.status.value})"
    
    def __str__(self) -> str:
        """String representation of the connector."""
        return f"{self.name} v{self.version} ({self.status.value})"
