"""
<<<<<<< HEAD
Base Connector Framework for Enterprise AI Agent Framework.

This module provides the base connector framework that all connectors must implement,
including authentication, action execution, health checks, and registry integration.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Callable
from enum import Enum
import traceback
import logging

import structlog
from pydantic import BaseModel, Field


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


class ConnectorStatus(Enum):
    """Connector status enumeration."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"


class ActionType(Enum):
    """Action type enumeration."""
    READ = "READ"
    WRITE = "WRITE"
    DELETE = "DELETE"
    EXECUTE = "EXECUTE"


class ConnectorAction(BaseModel):
    """Represents a connector action."""
    name: str = Field(..., description="Action name")
    description: str = Field(..., description="Action description")
    action_type: ActionType = Field(..., description="Type of action")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Action parameters schema")
    required_parameters: List[str] = Field(default_factory=list, description="Required parameters")
    optional_parameters: List[str] = Field(default_factory=list, description="Optional parameters")
    output_schema: Dict[str, Any] = Field(default_factory=dict, description="Output schema")
    timeout: int = Field(default=300, description="Action timeout in seconds")
    retry_count: int = Field(default=3, description="Number of retries")
    is_async: bool = Field(default=False, description="Whether action supports async execution")
    is_cpu_intensive: bool = Field(default=False, description="Whether action is CPU intensive")


class ConnectorMetadata(BaseModel):
    """Connector metadata."""
    name: str = Field(..., description="Connector name")
    version: str = Field(..., description="Connector version")
    description: str = Field(..., description="Connector description")
    author: str = Field(..., description="Connector author")
    license: str = Field(default="MIT", description="Connector license")
    homepage: Optional[str] = Field(None, description="Connector homepage")
    documentation: Optional[str] = Field(None, description="Connector documentation")
    tags: List[str] = Field(default_factory=list, description="Connector tags")
    capabilities: List[str] = Field(default_factory=list, description="Connector capabilities")
    authentication_methods: List[str] = Field(default_factory=list, description="Supported authentication methods")
    rate_limits: Dict[str, Any] = Field(default_factory=dict, description="Rate limiting information")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorConfig(BaseModel):
    """Connector configuration."""
    connector_id: str = Field(..., description="Unique connector identifier")
    name: str = Field(..., description="Connector name")
    version: str = Field(..., description="Connector version")
    config: Dict[str, Any] = Field(default_factory=dict, description="Connector-specific configuration")
    credentials: Dict[str, Any] = Field(default_factory=dict, description="Authentication credentials")
    enabled: bool = Field(default=True, description="Whether connector is enabled")
    timeout: int = Field(default=300, description="Default timeout in seconds")
    retry_count: int = Field(default=3, description="Default retry count")
    rate_limit: Optional[int] = Field(None, description="Rate limit per minute")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConnectorResult(BaseModel):
    """Result of connector action execution."""
    success: bool = Field(..., description="Whether action was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="Action result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_time_ms: int = Field(default=0, description="Execution time in milliseconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class BaseConnector(ABC):
    """
    Abstract base class for all connectors.
    
    All connectors must inherit from this class and implement the required methods.
    """
    
    def __init__(self, config: ConnectorConfig):
        """Initialize the connector with configuration."""
        self.config = config
        self.logger = logger.bind(connector=self.config.name)
        self._authenticated = False
        self._last_health_check = None
        self._health_status = ConnectorStatus.INACTIVE
        
    @property
    def metadata(self) -> ConnectorMetadata:
        """Get connector metadata."""
        return ConnectorMetadata(
            name=self.config.name,
            version=self.config.version,
            description=self.get_description(),
            author=self.get_author(),
            license=self.get_license(),
            homepage=self.get_homepage(),
            documentation=self.get_documentation(),
            tags=self.get_tags(),
            capabilities=self.get_capabilities(),
            authentication_methods=self.get_authentication_methods(),
            rate_limits=self.get_rate_limits()
        )
    
    @abstractmethod
    def get_description(self) -> str:
        """Get connector description."""
        pass
    
    @abstractmethod
    def get_author(self) -> str:
        """Get connector author."""
        pass
    
    def get_license(self) -> str:
        """Get connector license."""
        return "MIT"
    
    def get_homepage(self) -> Optional[str]:
        """Get connector homepage URL."""
        return None
    
    def get_documentation(self) -> Optional[str]:
        """Get connector documentation URL."""
        return None
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return []
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return []
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["api_key", "oauth2", "basic_auth"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {}
    
    @abstractmethod
    def authenticate(self) -> bool:
        """
        Authenticate with the external service.
            
        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """
        Execute a connector action.
        
        Args:
            action_name: Name of the action to execute
            parameters: Action parameters
            
        Returns:
            ConnectorResult: Result of the action execution
        """
        pass
    
    async def execute_action_async(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """
        Execute a connector action asynchronously.
        
        Args:
            action_name: Name of the action to execute
            parameters: Action parameters
            
        Returns:
            ConnectorResult: Result of the action execution
        """
        # Default implementation runs sync method in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute_action, action_name, parameters)
    
    @abstractmethod
    def list_actions(self) -> List[ConnectorAction]:
=======
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
>>>>>>> 1fc482f1c958a8bf865f354544dab0fde2428422
        """
        List all available actions for this connector.
        
        Returns:
<<<<<<< HEAD
            List[ConnectorAction]: List of available actions
        """
        pass
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the connector.
        
        Returns:
            Dict[str, Any]: Health check result
        """
        try:
            start_time = time.time()
            
            # Check authentication
            if not self._authenticated:
                auth_result = self.authenticate()
                if not auth_result:
                    self._health_status = ConnectorStatus.ERROR
                    return {
                        "status": "error",
                        "message": "Authentication failed",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                self._authenticated = True
            
            # Perform connector-specific health check
            health_result = self._perform_health_check()
            
            execution_time = int((time.time() - start_time) * 1000)
            self._last_health_check = datetime.now(timezone.utc)
            self._health_status = ConnectorStatus.ACTIVE
            
            return {
                "status": "healthy",
                "message": "Connector is healthy",
                "execution_time_ms": execution_time,
                "timestamp": self._last_health_check.isoformat(),
                "details": health_result
            }
            
        except Exception as e:
            self._health_status = ConnectorStatus.ERROR
            self.logger.error("Health check failed", error=str(e), traceback=traceback.format_exc())
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """
        Perform connector-specific health check.
        
        Override this method in subclasses for custom health checks.
        
        Returns:
            Dict[str, Any]: Health check details
        """
        return {"authenticated": self._authenticated}
    
    def is_cpu_intensive(self) -> bool:
        """
        Check if this connector is CPU intensive.
        
        Returns:
            bool: True if connector is CPU intensive
        """
        return False
    
    def validate_parameters(self, action_name: str, parameters: Dict[str, Any]) -> bool:
        """
        Validate action parameters.
        
        Args:
            action_name: Name of the action
            parameters: Parameters to validate
            
        Returns:
            bool: True if parameters are valid
        """
        try:
        actions = self.list_actions()
            action = next((a for a in actions if a.name == action_name), None)
        
            if not action:
                self.logger.error("Action not found", action_name=action_name)
            return False
        
        # Check required parameters
            for param in action.required_parameters:
                if param not in parameters:
                    self.logger.error("Missing required parameter", parameter=param, action_name=action_name)
                    return False
            
            # Validate parameter types and values
            for param_name, param_value in parameters.items():
                if param_name in action.parameters:
                    param_schema = action.parameters[param_name]
                    if not self._validate_parameter_value(param_name, param_value, param_schema):
=======
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
>>>>>>> 1fc482f1c958a8bf865f354544dab0fde2428422
                return False
        
        return True
    
<<<<<<< HEAD
        except Exception as e:
            self.logger.error("Parameter validation failed", error=str(e), action_name=action_name)
            return False
    
    def _validate_parameter_value(self, param_name: str, param_value: Any, param_schema: Dict[str, Any]) -> bool:
        """
        Validate a single parameter value against its schema.
        
        Args:
            param_name: Parameter name
            param_value: Parameter value
            param_schema: Parameter schema
            
        Returns:
            bool: True if parameter is valid
        """
        try:
            param_type = param_schema.get("type", "string")
            
            if param_type == "string" and not isinstance(param_value, str):
                self.logger.error("Invalid parameter type", parameter=param_name, expected="string", actual=type(param_value).__name__)
                return False
            elif param_type == "integer" and not isinstance(param_value, int):
                self.logger.error("Invalid parameter type", parameter=param_name, expected="integer", actual=type(param_value).__name__)
                return False
            elif param_type == "boolean" and not isinstance(param_value, bool):
                self.logger.error("Invalid parameter type", parameter=param_name, expected="boolean", actual=type(param_value).__name__)
                return False
            elif param_type == "array" and not isinstance(param_value, list):
                self.logger.error("Invalid parameter type", parameter=param_name, expected="array", actual=type(param_value).__name__)
                return False
            elif param_type == "object" and not isinstance(param_value, dict):
                self.logger.error("Invalid parameter type", parameter=param_name, expected="object", actual=type(param_value).__name__)
                return False
            
            # Check enum values
            if "enum" in param_schema and param_value not in param_schema["enum"]:
                self.logger.error("Invalid parameter value", parameter=param_name, value=param_value, allowed_values=param_schema["enum"])
                return False
            
            # Check minimum/maximum values
            if "minimum" in param_schema and param_value < param_schema["minimum"]:
                self.logger.error("Parameter value too small", parameter=param_name, value=param_value, minimum=param_schema["minimum"])
                return False
            
            if "maximum" in param_schema and param_value > param_schema["maximum"]:
                self.logger.error("Parameter value too large", parameter=param_name, value=param_value, maximum=param_schema["maximum"])
                return False
            
            return True
            
        except Exception as e:
            self.logger.error("Parameter validation error", parameter=param_name, error=str(e))
            return False
    
    def get_status(self) -> ConnectorStatus:
        """Get current connector status."""
        return self._health_status
    
    def get_last_health_check(self) -> Optional[datetime]:
        """Get timestamp of last health check."""
        return self._last_health_check
    
    def is_authenticated(self) -> bool:
        """Check if connector is authenticated."""
        return self._authenticated
    
    def __str__(self) -> str:
        """String representation of the connector."""
        return f"{self.config.name} v{self.config.version}"
    
    def __repr__(self) -> str:
        """Detailed string representation of the connector."""
        return f"<{self.__class__.__name__}(name='{self.config.name}', version='{self.config.version}', status='{self._health_status.value}')>"


class AsyncConnector(BaseConnector):
    """
    Base class for connectors that support async operations.
    
    Extends BaseConnector with async-specific functionality.
    """
    
    @abstractmethod
    async def authenticate_async(self) -> bool:
        """
        Authenticate with the external service asynchronously.
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        pass
    
    async def execute_action_async(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """
        Execute a connector action asynchronously.
        
        Args:
            action_name: Name of the action to execute
            parameters: Action parameters
            
        Returns:
            ConnectorResult: Result of the action execution
        """
        # Override to provide async implementation
        return await super().execute_action_async(action_name, parameters)
    
    async def health_check_async(self) -> Dict[str, Any]:
        """
        Perform an async health check on the connector.
        
        Returns:
            Dict[str, Any]: Health check result
        """
        try:
            start_time = time.time()
            
            # Check authentication
            if not self._authenticated:
                auth_result = await self.authenticate_async()
                if not auth_result:
                    self._health_status = ConnectorStatus.ERROR
                    return {
                        "status": "error",
                        "message": "Authentication failed",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                self._authenticated = True
            
            # Perform connector-specific health check
            health_result = await self._perform_health_check_async()
            
            execution_time = int((time.time() - start_time) * 1000)
            self._last_health_check = datetime.now(timezone.utc)
            self._health_status = ConnectorStatus.ACTIVE
            
            return {
                "status": "healthy",
                "message": "Connector is healthy",
                "execution_time_ms": execution_time,
                "timestamp": self._last_health_check.isoformat(),
                "details": health_result
            }
            
        except Exception as e:
            self._health_status = ConnectorStatus.ERROR
            self.logger.error("Async health check failed", error=str(e), traceback=traceback.format_exc())
            return {
                "status": "error",
                "message": f"Health check failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _perform_health_check_async(self) -> Dict[str, Any]:
        """
        Perform connector-specific async health check.
        
        Override this method in subclasses for custom async health checks.
        
        Returns:
            Dict[str, Any]: Health check details
        """
        return {"authenticated": self._authenticated}


class CPUIntensiveConnector(BaseConnector):
    """
    Base class for CPU-intensive connectors.
    
    Extends BaseConnector with CPU-intensive specific functionality.
    """
    
    def is_cpu_intensive(self) -> bool:
        """Check if this connector is CPU intensive."""
        return True
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        capabilities = super().get_capabilities()
        capabilities.append("cpu_intensive")
        return capabilities
=======
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
>>>>>>> 1fc482f1c958a8bf865f354544dab0fde2428422
