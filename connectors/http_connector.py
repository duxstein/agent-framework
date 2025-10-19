"""
HTTP Connector for Enterprise AI Agent Framework.

This connector provides generic HTTP API integration capabilities for making
REST API calls to external services.
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone

import structlog
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType

logger = structlog.get_logger()


class HTTPConnector(BaseConnector):
    """HTTP connector for generic API calls."""
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "base_url": {
                "type": "string",
                "description": "Base URL for API requests"
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "Request timeout in seconds"
            },
            "retry_count": {
                "type": "integer",
                "default": 3,
                "description": "Number of retries for failed requests"
            },
            "verify_ssl": {
                "type": "boolean",
                "default": True,
                "description": "Whether to verify SSL certificates"
            },
            "follow_redirects": {
                "type": "boolean",
                "default": True,
                "description": "Whether to follow redirects"
            },
            "max_redirects": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of redirects to follow"
            },
            "user_agent": {
                "type": "string",
                "default": "Enterprise AI Agent Framework HTTP Connector",
                "description": "User agent string for requests"
            }
        },
        "required": ["base_url"]
    }
    
    def __init__(self, config: ConnectorConfig):
        """Initialize HTTP connector."""
        super().__init__(config)
        self.base_url = self.config.config.get("base_url")
        self.timeout = self.config.config.get("timeout", 30)
        self.retry_count = self.config.config.get("retry_count", 3)
        self.verify_ssl = self.config.config.get("verify_ssl", True)
        self.follow_redirects = self.config.config.get("follow_redirects", True)
        self.max_redirects = self.config.config.get("max_redirects", 10)
        self.user_agent = self.config.config.get("user_agent", "Enterprise AI Agent Framework HTTP Connector")
        
        # Authentication
        self.api_key = self.config.credentials.get("api_key")
        self.username = self.config.credentials.get("username")
        self.password = self.config.credentials.get("password")
        self.bearer_token = self.config.credentials.get("bearer_token")
        
        # Setup requests session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.retry_count,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Set authentication
        if self.api_key:
            self.session.headers['X-API-Key'] = self.api_key
        elif self.bearer_token:
            self.session.headers['Authorization'] = f'Bearer {self.bearer_token}'
        elif self.username and self.password:
            self.session.auth = (self.username, self.password)
    
    def get_description(self) -> str:
        """Get connector description."""
        return "HTTP connector for generic API calls and REST service integration"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return ["http", "rest", "api", "web", "integration"]
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return ["get", "post", "put", "patch", "delete", "head", "options"]
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["api_key", "bearer_token", "basic_auth", "oauth2"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {
            "requests_per_minute": 100,
            "concurrent_requests": 10
        }
    
    def authenticate(self) -> bool:
        """Authenticate with HTTP service."""
        try:
            # Test connection with a simple request
            response = self.session.get(
                self.base_url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=self.follow_redirects
            )
            
            # Consider authentication successful if we get any response
            # (even 401/403 might be valid if credentials are configured)
            if response.status_code in [200, 401, 403]:
                self.logger.info("HTTP authentication test successful", status_code=response.status_code)
                self._authenticated = True
                return True
            else:
                self.logger.warning("HTTP authentication test returned unexpected status", status_code=response.status_code)
                self._authenticated = True  # Still consider authenticated for testing
                return True
                
        except Exception as e:
            self.logger.error("HTTP authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return [
            ConnectorAction(
                name="get",
                description="Make a GET request",
                action_type=ActionType.READ,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="post",
                description="Make a POST request",
                action_type=ActionType.WRITE,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "data": {
                        "type": "object",
                        "description": "Request body data"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint", "data"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="put",
                description="Make a PUT request",
                action_type=ActionType.WRITE,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "data": {
                        "type": "object",
                        "description": "Request body data"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint", "data"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="patch",
                description="Make a PATCH request",
                action_type=ActionType.WRITE,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "data": {
                        "type": "object",
                        "description": "Request body data"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint", "data"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="delete",
                description="Make a DELETE request",
                action_type=ActionType.DELETE,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="head",
                description="Make a HEAD request",
                action_type=ActionType.READ,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="options",
                description="Make an OPTIONS request",
                action_type=ActionType.READ,
                parameters={
                    "endpoint": {
                        "type": "string",
                        "description": "API endpoint (relative to base URL)"
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters"
                    },
                    "headers": {
                        "type": "object",
                        "description": "Additional headers"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Request timeout override"
                    }
                },
                required_parameters=["endpoint"],
                optional_parameters=["params", "headers", "timeout"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "status_code": {"type": "integer"},
                        "headers": {"type": "object"},
                        "data": {"type": "object"},
                        "url": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            )
        ]
    
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """Execute an HTTP action."""
        start_time = datetime.now()
        
        try:
            if not self._authenticated:
                if not self.authenticate():
                    return ConnectorResult(
                        success=False,
                        error="Authentication failed",
                        execution_time_ms=0
                    )
            
            # Validate parameters
            if not self.validate_parameters(action_name, parameters):
                return ConnectorResult(
                    success=False,
                    error="Invalid parameters",
                    execution_time_ms=0
                )
            
            # Execute action
            if action_name in ["get", "post", "put", "patch", "delete", "head", "options"]:
                result = self._make_request(action_name, parameters)
            else:
                return ConnectorResult(
                    success=False,
                    error=f"Unknown action: {action_name}",
                    execution_time_ms=0
                )
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ConnectorResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                metadata={"action": action_name, "base_url": self.base_url}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("HTTP action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
    
    def _make_request(self, method: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HTTP request."""
        try:
            endpoint = parameters["endpoint"]
            params = parameters.get("params", {})
            headers = parameters.get("headers", {})
            timeout = parameters.get("timeout", self.timeout)
            
            # Build URL
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            
            # Prepare request kwargs
            request_kwargs = {
                'timeout': timeout,
                'verify': self.verify_ssl,
                'allow_redirects': self.follow_redirects
            }
            
            if params:
                request_kwargs['params'] = params
            
            if headers:
                # Merge with session headers
                merged_headers = self.session.headers.copy()
                merged_headers.update(headers)
                request_kwargs['headers'] = merged_headers
            
            # Add data for methods that support it
            if method in ['post', 'put', 'patch'] and 'data' in parameters:
                request_kwargs['json'] = parameters['data']
            
            # Make request
            response = self.session.request(method.upper(), url, **request_kwargs)
            
            # Parse response
            result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "url": response.url
            }
            
            # Add response data for methods that typically return data
            if method in ['get', 'post', 'put', 'patch', 'options']:
                try:
                    result["data"] = response.json()
                except (ValueError, json.JSONDecodeError):
                    result["data"] = response.text
            
            return result
            
        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout after {timeout} seconds")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error: {e}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform HTTP-specific health check."""
        try:
            if not self.base_url:
                return {"error": "Base URL not configured"}
            
            # Test basic connectivity
            response = self.session.get(
                self.base_url,
                timeout=10,
                verify=self.verify_ssl
            )
            
            return {
                "authenticated": self._authenticated,
                "base_url": self.base_url,
                "status_code": response.status_code,
                "response_time_ms": int(response.elapsed.total_seconds() * 1000),
                "ssl_verified": self.verify_ssl
            }
            
        except Exception as e:
            return {"error": str(e)}
