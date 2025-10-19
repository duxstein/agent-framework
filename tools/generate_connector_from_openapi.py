#!/usr/bin/env python3
"""
OpenAPI Connector Generator for Enterprise AI Agent Framework.

This tool generates connector scaffolds from OpenAPI JSON specifications,
creating ready-to-use connectors for external APIs.
"""

import json
import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.base import ActionType


class OpenAPIConnectorGenerator:
    """Generator for creating connectors from OpenAPI specifications."""
    
    def __init__(self):
        """Initialize the generator."""
        self.template_dir = Path(__file__).parent / "templates"
        self.output_dir = Path(__file__).parent.parent / "connectors"
    
    def generate_connector(self, openapi_spec: Dict[str, Any], connector_name: str, 
                          output_path: Optional[str] = None) -> str:
        """
        Generate a connector from OpenAPI specification.
        
        Args:
            openapi_spec: OpenAPI specification dictionary
            connector_name: Name for the generated connector
            output_path: Optional output path for the connector file
            
        Returns:
            str: Path to the generated connector file
        """
        try:
            # Extract API information
            api_info = self._extract_api_info(openapi_spec)
            
            # Extract paths and operations
            operations = self._extract_operations(openapi_spec)
            
            # Generate connector code
            connector_code = self._generate_connector_code(
                connector_name, api_info, operations, openapi_spec
            )
            
            # Determine output path
            if not output_path:
                output_path = self.output_dir / f"{connector_name.lower()}_connector.py"
            
            # Write connector file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(connector_code)
            
            print(f"✅ Connector generated successfully: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"❌ Error generating connector: {e}")
            raise
    
    def _extract_api_info(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Extract API information from OpenAPI spec."""
        info = spec.get("info", {})
        servers = spec.get("servers", [])
        
        return {
            "title": info.get("title", "API"),
            "description": info.get("description", ""),
            "version": info.get("version", "1.0.0"),
            "base_url": servers[0].get("url") if servers else "https://api.example.com",
            "contact": info.get("contact", {}),
            "license": info.get("license", {})
        }
    
    def _extract_operations(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract operations from OpenAPI spec."""
        operations = []
        paths = spec.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                    operations.append({
                        "path": path,
                        "method": method.upper(),
                        "operation_id": operation.get("operationId", f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": operation.get("parameters", []),
                        "request_body": operation.get("requestBody", {}),
                        "responses": operation.get("responses", {}),
                        "tags": operation.get("tags", [])
                    })
        
        return operations
    
    def _generate_connector_code(self, connector_name: str, api_info: Dict[str, Any], 
                                operations: List[Dict[str, Any]], spec: Dict[str, Any]) -> str:
        """Generate connector Python code."""
        
        # Generate class name
        class_name = f"{connector_name.title().replace('_', '')}Connector"
        
        # Generate imports
        imports = self._generate_imports()
        
        # Generate class definition
        class_code = self._generate_class_definition(class_name, api_info, operations, spec)
        
        # Combine all parts
        connector_code = f'''"""
{api_info["title"]} Connector for Enterprise AI Agent Framework.

Generated from OpenAPI specification.
{api_info["description"]}
"""

{imports}

logger = structlog.get_logger()


class {class_name}(BaseConnector):
    """{api_info["title"]} connector for API operations."""
    
    # Configuration schema
    CONFIG_SCHEMA = {json.dumps(self._generate_config_schema(spec), indent=4)}
    
    def __init__(self, config: ConnectorConfig):
        """Initialize {api_info["title"]} connector."""
        super().__init__(config)
        self.base_url = self.config.config.get("base_url", "{api_info["base_url"]}")
        self.timeout = self.config.config.get("timeout", 30)
        self.retry_count = self.config.config.get("retry_count", 3)
        
        # Authentication
        self.api_key = self.config.credentials.get("api_key")
        self.bearer_token = self.config.credentials.get("bearer_token")
        self.username = self.config.credentials.get("username")
        self.password = self.config.credentials.get("password")
        
        # Setup requests session
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
        self.session.headers.update({{
            'User-Agent': 'Enterprise AI Agent Framework {api_info["title"]} Connector',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }})
        
        # Set authentication
        if self.api_key:
            self.session.headers['X-API-Key'] = self.api_key
        elif self.bearer_token:
            self.session.headers['Authorization'] = f'Bearer {{self.bearer_token}}'
        elif self.username and self.password:
            self.session.auth = (self.username, self.password)
    
    def get_description(self) -> str:
        """Get connector description."""
        return "{api_info["description"] or f"{api_info["title"]} connector for API operations"}"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return {self._generate_tags(operations)}
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return {self._generate_capabilities(operations)}
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return {self._generate_auth_methods(spec)}
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {{
            "requests_per_minute": 100,
            "concurrent_requests": 10
        }}
    
    def authenticate(self) -> bool:
        """Authenticate with {api_info["title"]} API."""
        try:
            # Test connection
            response = self.session.get(
                f"{{self.base_url}}/health",
                timeout=self.timeout,
                verify=True
            )
            
            if response.status_code in [200, 401, 403]:
                self.logger.info("{api_info["title"]} authentication test successful", status_code=response.status_code)
                self._authenticated = True
                return True
            else:
                self.logger.warning("{api_info["title"]} authentication test returned unexpected status", status_code=response.status_code)
                self._authenticated = True
                return True
                
        except Exception as e:
            self.logger.error("{api_info["title"]} authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return {self._generate_actions(operations)}
    
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """Execute an {api_info["title"]} action."""
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
{class_code}
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ConnectorResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                metadata={{"action": action_name, "base_url": self.base_url}}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("{api_info["title"]} action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={{"action": action_name}}
            )
    
    def _make_request(self, method: str, endpoint: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Make an HTTP request."""
        try:
            url = f"{{self.base_url.rstrip('/')}}/{{endpoint.lstrip('/')}}"
            
            request_kwargs = {{
                'timeout': self.timeout,
                'verify': True
            }}
            
            if 'params' in parameters:
                request_kwargs['params'] = parameters['params']
            
            if 'data' in parameters:
                request_kwargs['json'] = parameters['data']
            
            if 'headers' in parameters:
                merged_headers = self.session.headers.copy()
                merged_headers.update(parameters['headers'])
                request_kwargs['headers'] = merged_headers
            
            response = self.session.request(method.upper(), url, **request_kwargs)
            
            result = {{
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "url": response.url
            }}
            
            try:
                result["data"] = response.json()
            except (ValueError, json.JSONDecodeError):
                result["data"] = response.text
            
            return result
            
        except requests.exceptions.Timeout:
            raise Exception(f"Request timeout after {{self.timeout}} seconds")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"HTTP error: {{e}}")
        except Exception as e:
            raise Exception(f"Request failed: {{str(e)}}")
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform {api_info["title"]}-specific health check."""
        try:
            if not self.base_url:
                return {{"error": "Base URL not configured"}}
            
            response = self.session.get(
                f"{{self.base_url}}/health",
                timeout=10,
                verify=True
            )
            
            return {{
                "authenticated": self._authenticated,
                "base_url": self.base_url,
                "status_code": response.status_code,
                "response_time_ms": int(response.elapsed.total_seconds() * 1000)
            }}
            
        except Exception as e:
            return {{"error": str(e)}}
'''
        
        return connector_code
    
    def _generate_imports(self) -> str:
        """Generate import statements."""
        return '''import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import structlog
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType'''
    
    def _generate_class_definition(self, class_name: str, api_info: Dict[str, Any], 
                                  operations: List[Dict[str, Any]], spec: Dict[str, Any]) -> str:
        """Generate the main class definition with action handlers."""
        action_handlers = []
        
        for operation in operations:
            operation_id = operation["operation_id"]
            method = operation["method"]
            path = operation["path"]
            
            # Generate action handler
            handler = f'''            elif action_name == "{operation_id}":
                result = self._make_request("{method}", "{path}", parameters)'''
            
            action_handlers.append(handler)
        
        # Add default case
        action_handlers.append('''            else:
                return ConnectorResult(
                    success=False,
                    error=f"Unknown action: {action_name}",
                    execution_time_ms=0
                )''')
        
        return '\n'.join(action_handlers)
    
    def _generate_config_schema(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Generate configuration schema."""
        return {
            "type": "object",
            "properties": {
                "base_url": {
                    "type": "string",
                    "description": "API base URL"
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
                }
            },
            "required": ["base_url"]
        }
    
    def _generate_tags(self, operations: List[Dict[str, Any]]) -> str:
        """Generate connector tags."""
        tags = set()
        for operation in operations:
            tags.update(operation.get("tags", []))
        
        if not tags:
            tags = ["api", "rest", "http"]
        
        return str(list(tags))
    
    def _generate_capabilities(self, operations: List[Dict[str, Any]]) -> str:
        """Generate connector capabilities."""
        capabilities = []
        for operation in operations:
            capabilities.append(operation["operation_id"])
        
        return str(capabilities)
    
    def _generate_auth_methods(self, spec: Dict[str, Any]) -> str:
        """Generate authentication methods."""
        auth_methods = ["api_key", "bearer_token", "basic_auth"]
        
        # Check for OAuth in spec
        if "securitySchemes" in spec.get("components", {}):
            security_schemes = spec["components"]["securitySchemes"]
            for scheme_name, scheme in security_schemes.items():
                if scheme.get("type") == "oauth2":
                    auth_methods.append("oauth2")
                    break
        
        return str(auth_methods)
    
    def _generate_actions(self, operations: List[Dict[str, Any]]) -> str:
        """Generate ConnectorAction definitions."""
        actions = []
        
        for operation in operations:
            operation_id = operation["operation_id"]
            method = operation["method"]
            summary = operation["summary"]
            description = operation["description"]
            parameters = operation["parameters"]
            request_body = operation["request_body"]
            
            # Determine action type
            if method in ["GET", "HEAD", "OPTIONS"]:
                action_type = "ActionType.READ"
            elif method in ["POST", "PUT", "PATCH"]:
                action_type = "ActionType.WRITE"
            elif method == "DELETE":
                action_type = "ActionType.DELETE"
            else:
                action_type = "ActionType.EXECUTE"
            
            # Generate parameters schema
            params_schema = self._generate_parameters_schema(parameters, request_body)
            
            # Generate required parameters
            required_params = []
            for param in parameters:
                if param.get("required", False):
                    required_params.append(f'"{param["name"]}"')
            
            if request_body and request_body.get("required", False):
                required_params.append('"data"')
            
            # Generate optional parameters
            optional_params = []
            for param in parameters:
                if not param.get("required", False):
                    optional_params.append(f'"{param["name"]}"')
            
            if request_body and not request_body.get("required", False):
                optional_params.append('"data"')
            
            action = f'''            ConnectorAction(
                name="{operation_id}",
                description="{summary or description or f"{method} {operation["path"]}"}",
                action_type={action_type},
                parameters={json.dumps(params_schema, indent=16)},
                required_parameters=[{", ".join(required_params)}],
                optional_parameters=[{", ".join(optional_params)}],
                output_schema={{
                    "type": "object",
                    "properties": {{
                        "status_code": {{"type": "integer"}},
                        "headers": {{"type": "object"}},
                        "data": {{"type": "object"}},
                        "url": {{"type": "string"}}
                    }}
                }},
                timeout=self.timeout,
                is_async=True
            )'''
            
            actions.append(action)
        
        return f"[\n{',\n'.join(actions)}\n        ]"
    
    def _generate_parameters_schema(self, parameters: List[Dict[str, Any]], 
                                   request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Generate parameters schema."""
        schema = {}
        
        # Add path and query parameters
        for param in parameters:
            param_name = param["name"]
            param_schema = param.get("schema", {})
            
            schema[param_name] = {
                "type": param_schema.get("type", "string"),
                "description": param.get("description", "")
            }
            
            if "enum" in param_schema:
                schema[param_name]["enum"] = param_schema["enum"]
            
            if "default" in param_schema:
                schema[param_name]["default"] = param_schema["default"]
        
        # Add request body parameter
        if request_body:
            schema["data"] = {
                "type": "object",
                "description": "Request body data"
            }
        
        return schema


def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(
        description="Generate connector from OpenAPI specification"
    )
    parser.add_argument(
        "openapi_file",
        help="Path to OpenAPI JSON specification file"
    )
    parser.add_argument(
        "connector_name",
        help="Name for the generated connector"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output path for the connector file"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate OpenAPI specification before generating"
    )
    
    args = parser.parse_args()
    
    try:
        # Load OpenAPI specification
        with open(args.openapi_file, 'r', encoding='utf-8') as f:
            openapi_spec = json.load(f)
        
        # Validate if requested
        if args.validate:
            print("🔍 Validating OpenAPI specification...")
            # Basic validation
            if "openapi" not in openapi_spec and "swagger" not in openapi_spec:
                print("❌ Invalid OpenAPI specification: missing 'openapi' or 'swagger' field")
                return 1
            
            if "info" not in openapi_spec:
                print("❌ Invalid OpenAPI specification: missing 'info' field")
                return 1
            
            print("✅ OpenAPI specification is valid")
        
        # Generate connector
        print(f"🚀 Generating {args.connector_name} connector...")
        generator = OpenAPIConnectorGenerator()
        output_path = generator.generate_connector(
            openapi_spec, 
            args.connector_name, 
            args.output
        )
        
        print(f"📁 Connector saved to: {output_path}")
        print(f"📝 Next steps:")
        print(f"   1. Review and customize the generated connector")
        print(f"   2. Add any missing authentication methods")
        print(f"   3. Test the connector with your API")
        print(f"   4. Register the connector in the registry")
        
        return 0
        
    except FileNotFoundError:
        print(f"❌ Error: OpenAPI file not found: {args.openapi_file}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in OpenAPI file: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
