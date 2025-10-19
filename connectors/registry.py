"""
<<<<<<< HEAD
Connector Registry for Enterprise AI Agent Framework.

This module provides the connector registry that dynamically discovers and manages connectors,
including registration, discovery, and lifecycle management.
"""

import os
import json
import importlib
import inspect
from pathlib import Path
from typing import Dict, Any, List, Optional, Type, Union
from datetime import datetime, timezone
import traceback

import structlog
import psycopg2
from psycopg2.extras import RealDictCursor

from connectors.base import BaseConnector, ConnectorConfig, ConnectorMetadata, ConnectorStatus

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


class ConnectorRegistry:
    """Registry for managing connectors."""
    
    def __init__(self, connection_string: str, connectors_path: Optional[str] = None):
        """Initialize the connector registry."""
        self.connection_string = connection_string
        self.connectors_path = connectors_path or "connectors"
        self.logger = logger.bind(component="connector_registry")
        self._connector_classes: Dict[str, Type[BaseConnector]] = {}
        self._connector_instances: Dict[str, BaseConnector] = {}
        
    def initialize_database_schema(self):
        """Initialize the database schema for connector registry."""
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS connectors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                version VARCHAR(50) NOT NULL,
                description TEXT,
                author VARCHAR(255),
                license VARCHAR(100),
                homepage VARCHAR(500),
                documentation VARCHAR(500),
                tags JSONB,
                capabilities JSONB,
                authentication_methods JSONB,
                rate_limits JSONB,
                module_path VARCHAR(500),
                class_name VARCHAR(255),
                config_schema JSONB,
                enabled BOOLEAN DEFAULT true,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE TABLE IF NOT EXISTS connector_configs (
                id SERIAL PRIMARY KEY,
                connector_id VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                config JSONB,
                credentials JSONB,
                enabled BOOLEAN DEFAULT true,
                timeout INTEGER DEFAULT 300,
                retry_count INTEGER DEFAULT 3,
                rate_limit INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                UNIQUE(connector_id, name)
            );
            
            CREATE INDEX IF NOT EXISTS idx_connectors_name ON connectors(name);
            CREATE INDEX IF NOT EXISTS idx_connectors_enabled ON connectors(enabled);
            CREATE INDEX IF NOT EXISTS idx_connector_configs_connector_id ON connector_configs(connector_id);
            CREATE INDEX IF NOT EXISTS idx_connector_configs_enabled ON connector_configs(enabled);
            """
            
            cursor.execute(create_table_query)
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("Database schema initialized successfully")
            
        except Exception as e:
            self.logger.error("Failed to initialize database schema", error=str(e))
            raise
    
    def discover_connectors(self) -> List[Dict[str, Any]]:
        """
        Discover connectors from the connectors directory and entry points.
        
        Returns:
            List[Dict[str, Any]]: List of discovered connector metadata
        """
        discovered_connectors = []
        
        try:
            # Discover from connectors directory
            connectors_dir = Path(self.connectors_path)
            if connectors_dir.exists():
                discovered_connectors.extend(self._discover_from_directory(connectors_dir))
            
            # Discover from entry points
            discovered_connectors.extend(self._discover_from_entry_points())
            
            self.logger.info("Connector discovery completed", count=len(discovered_connectors))
            
        except Exception as e:
            self.logger.error("Connector discovery failed", error=str(e), traceback=traceback.format_exc())
        
        return discovered_connectors
    
    def _discover_from_directory(self, connectors_dir: Path) -> List[Dict[str, Any]]:
        """Discover connectors from a directory."""
        discovered = []
        
        for py_file in connectors_dir.glob("*_connector.py"):
            try:
                module_name = f"connectors.{py_file.stem}"
                module = importlib.import_module(module_name)
                
                # Find connector classes
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and 
                        issubclass(obj, BaseConnector) and 
                        obj != BaseConnector and
                        not name.startswith('_')):
                        
                        connector_info = self._extract_connector_info(obj, module_name)
                        if connector_info:
                            discovered.append(connector_info)
                            
            except Exception as e:
                self.logger.warning("Failed to discover connector from file", file=str(py_file), error=str(e))
        
        return discovered
    
    def _discover_from_entry_points(self) -> List[Dict[str, Any]]:
        """Discover connectors from entry points."""
        discovered = []
        
        try:
            import pkg_resources
            
            for entry_point in pkg_resources.iter_entry_points('agent_framework.connectors'):
                try:
                    connector_class = entry_point.load()
                    if issubclass(connector_class, BaseConnector):
                        connector_info = self._extract_connector_info(connector_class, entry_point.module_name)
                        if connector_info:
                            discovered.append(connector_info)
                            
                except Exception as e:
                    self.logger.warning("Failed to load entry point", entry_point=str(entry_point), error=str(e))
                    
        except ImportError:
            # pkg_resources not available, skip entry point discovery
            pass
        
        return discovered
    
    def _extract_connector_info(self, connector_class: Type[BaseConnector], module_name: str) -> Optional[Dict[str, Any]]:
        """Extract connector information from a connector class."""
        try:
            # Create a temporary instance to get metadata
            temp_config = ConnectorConfig(
                connector_id="temp",
                name=connector_class.__name__.lower().replace('connector', ''),
                version="1.0.0"
            )
            temp_instance = connector_class(temp_config)
            metadata = temp_instance.metadata
            
            return {
                "name": metadata.name,
                "version": metadata.version,
                "description": metadata.description,
                "author": metadata.author,
                "license": metadata.license,
                "homepage": metadata.homepage,
                "documentation": metadata.documentation,
                "tags": metadata.tags,
                "capabilities": metadata.capabilities,
                "authentication_methods": metadata.authentication_methods,
                "rate_limits": metadata.rate_limits,
                "module_path": module_name,
                "class_name": connector_class.__name__,
                "config_schema": self._extract_config_schema(connector_class)
            }
            
        except Exception as e:
            self.logger.warning("Failed to extract connector info", class_name=connector_class.__name__, error=str(e))
            return None
    
    def _extract_config_schema(self, connector_class: Type[BaseConnector]) -> Dict[str, Any]:
        """Extract configuration schema from connector class."""
        try:
            # Look for CONFIG_SCHEMA class attribute
            if hasattr(connector_class, 'CONFIG_SCHEMA'):
                return connector_class.CONFIG_SCHEMA
            
            # Default schema
            return {
                "type": "object",
                "properties": {
                    "timeout": {"type": "integer", "default": 300},
                    "retry_count": {"type": "integer", "default": 3}
                }
            }
            
        except Exception as e:
            self.logger.warning("Failed to extract config schema", class_name=connector_class.__name__, error=str(e))
            return {}
    
    def register_connector(self, connector_info: Dict[str, Any]) -> bool:
        """
        Register a connector in the database.
        
        Args:
            connector_info: Connector information
            
        Returns:
            bool: True if registration successful
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            upsert_query = """
            INSERT INTO connectors 
            (name, version, description, author, license, homepage, documentation, 
             tags, capabilities, authentication_methods, rate_limits, module_path, 
             class_name, config_schema, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) 
            DO UPDATE SET 
                version = EXCLUDED.version,
                description = EXCLUDED.description,
                author = EXCLUDED.author,
                license = EXCLUDED.license,
                homepage = EXCLUDED.homepage,
                documentation = EXCLUDED.documentation,
                tags = EXCLUDED.tags,
                capabilities = EXCLUDED.capabilities,
                authentication_methods = EXCLUDED.authentication_methods,
                rate_limits = EXCLUDED.rate_limits,
                module_path = EXCLUDED.module_path,
                class_name = EXCLUDED.class_name,
                config_schema = EXCLUDED.config_schema,
                updated_at = EXCLUDED.updated_at
            """
            
            cursor.execute(upsert_query, (
                connector_info["name"],
                connector_info["version"],
                connector_info["description"],
                connector_info["author"],
                connector_info["license"],
                connector_info["homepage"],
                connector_info["documentation"],
                json.dumps(connector_info["tags"]),
                json.dumps(connector_info["capabilities"]),
                json.dumps(connector_info["authentication_methods"]),
                json.dumps(connector_info["rate_limits"]),
                connector_info["module_path"],
                connector_info["class_name"],
                json.dumps(connector_info["config_schema"]),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("Connector registered successfully", name=connector_info["name"])
            return True
            
        except Exception as e:
            self.logger.error("Failed to register connector", name=connector_info.get("name"), error=str(e))
            return False
    
    def get_connector(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get connector information by name.
        
        Args:
            name: Connector name
            
        Returns:
            Optional[Dict[str, Any]]: Connector information
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = "SELECT * FROM connectors WHERE name = %s AND enabled = true"
            cursor.execute(query, (name,))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result:
                # Convert RealDictRow to regular dict
                connector_info = dict(result)
                
                # Parse JSON fields
                for field in ['tags', 'capabilities', 'authentication_methods', 'rate_limits', 'config_schema']:
                    if connector_info.get(field):
                        connector_info[field] = json.loads(connector_info[field])
                
                return connector_info
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get connector", name=name, error=str(e))
            return None
    
    def list_connectors(self, enabled_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all connectors.
        
        Args:
            enabled_only: Whether to return only enabled connectors
            
        Returns:
            List[Dict[str, Any]]: List of connector information
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if enabled_only:
                query = "SELECT * FROM connectors WHERE enabled = true ORDER BY name"
            else:
                query = "SELECT * FROM connectors ORDER BY name"
            
            cursor.execute(query)
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            connectors = []
            for result in results:
                connector_info = dict(result)
                
                # Parse JSON fields
                for field in ['tags', 'capabilities', 'authentication_methods', 'rate_limits', 'config_schema']:
                    if connector_info.get(field):
                        connector_info[field] = json.loads(connector_info[field])
                
                connectors.append(connector_info)
            
            return connectors
            
        except Exception as e:
            self.logger.error("Failed to list connectors", error=str(e))
            return []
    
    def create_connector_instance(self, name: str, config: ConnectorConfig) -> Optional[BaseConnector]:
        """
        Create a connector instance.
        
        Args:
            name: Connector name
            config: Connector configuration
            
        Returns:
            Optional[BaseConnector]: Connector instance
        """
        try:
            # Get connector information
            connector_info = self.get_connector(name)
            if not connector_info:
                self.logger.error("Connector not found", name=name)
                return None
            
            # Load connector class
            module_path = connector_info["module_path"]
            class_name = connector_info["class_name"]
            
            module = importlib.import_module(module_path)
            connector_class = getattr(module, class_name)
            
            # Create instance
            instance = connector_class(config)
            
            # Cache instance
            instance_key = f"{name}:{config.name}"
            self._connector_instances[instance_key] = instance
            
            self.logger.info("Connector instance created", name=name, instance_key=instance_key)
            return instance
            
        except Exception as e:
            self.logger.error("Failed to create connector instance", name=name, error=str(e), traceback=traceback.format_exc())
            return None
    
    def get_connector_instance(self, name: str, config_name: str) -> Optional[BaseConnector]:
        """
        Get a cached connector instance.
        
        Args:
            name: Connector name
            config_name: Configuration name
            
        Returns:
            Optional[BaseConnector]: Cached connector instance
        """
        instance_key = f"{name}:{config_name}"
        return self._connector_instances.get(instance_key)
    
    def register_connector_config(self, config: ConnectorConfig) -> bool:
        """
        Register a connector configuration.
        
        Args:
            config: Connector configuration
            
        Returns:
            bool: True if registration successful
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor()
            
            upsert_query = """
            INSERT INTO connector_configs 
            (connector_id, name, version, config, credentials, enabled, timeout, retry_count, rate_limit, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (connector_id, name) 
            DO UPDATE SET 
                version = EXCLUDED.version,
                config = EXCLUDED.config,
                credentials = EXCLUDED.credentials,
                enabled = EXCLUDED.enabled,
                timeout = EXCLUDED.timeout,
                retry_count = EXCLUDED.retry_count,
                rate_limit = EXCLUDED.rate_limit,
                updated_at = EXCLUDED.updated_at
            """
            
            cursor.execute(upsert_query, (
                config.connector_id,
                config.name,
                config.version,
                json.dumps(config.config),
                json.dumps(config.credentials),
                config.enabled,
                config.timeout,
                config.retry_count,
                config.rate_limit,
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            self.logger.info("Connector config registered successfully", connector_id=config.connector_id, name=config.name)
            return True
            
        except Exception as e:
            self.logger.error("Failed to register connector config", connector_id=config.connector_id, name=config.name, error=str(e))
            return False
    
    def get_connector_config(self, connector_id: str, config_name: str) -> Optional[ConnectorConfig]:
        """
        Get a connector configuration.
        
        Args:
            connector_id: Connector ID
            config_name: Configuration name
            
        Returns:
            Optional[ConnectorConfig]: Connector configuration
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = "SELECT * FROM connector_configs WHERE connector_id = %s AND name = %s"
            cursor.execute(query, (connector_id, config_name))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            if result:
                config_data = dict(result)
                
                # Parse JSON fields
                config_data["config"] = json.loads(config_data["config"]) if config_data["config"] else {}
                config_data["credentials"] = json.loads(config_data["credentials"]) if config_data["credentials"] else {}
                
                return ConnectorConfig(**config_data)
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get connector config", connector_id=connector_id, config_name=config_name, error=str(e))
            return None
    
    def list_connector_configs(self, connector_id: Optional[str] = None) -> List[ConnectorConfig]:
        """
        List connector configurations.
        
        Args:
            connector_id: Optional connector ID filter
            
        Returns:
            List[ConnectorConfig]: List of connector configurations
        """
        try:
            conn = psycopg2.connect(self.connection_string)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if connector_id:
                query = "SELECT * FROM connector_configs WHERE connector_id = %s ORDER BY name"
                cursor.execute(query, (connector_id,))
            else:
                query = "SELECT * FROM connector_configs ORDER BY connector_id, name"
                cursor.execute(query)
            
            results = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            configs = []
            for result in results:
                config_data = dict(result)
                
                # Parse JSON fields
                config_data["config"] = json.loads(config_data["config"]) if config_data["config"] else {}
                config_data["credentials"] = json.loads(config_data["credentials"]) if config_data["credentials"] else {}
                
                configs.append(ConnectorConfig(**config_data))
            
            return configs
            
        except Exception as e:
            self.logger.error("Failed to list connector configs", error=str(e))
            return []
    
    def sync_connectors(self) -> int:
        """
        Synchronize discovered connectors with the database.
        
        Returns:
            int: Number of connectors synchronized
        """
        try:
            # Discover connectors
            discovered_connectors = self.discover_connectors()
            
            # Register each connector
            registered_count = 0
            for connector_info in discovered_connectors:
                if self.register_connector(connector_info):
                    registered_count += 1
            
            self.logger.info("Connector synchronization completed", registered=registered_count, discovered=len(discovered_connectors))
            return registered_count
            
        except Exception as e:
            self.logger.error("Connector synchronization failed", error=str(e))
            return 0
=======
Connector registry for Enterprise AI Agent Framework.

Provides dynamic discovery and management of connectors
with support for registration, instantiation, and lifecycle management.
"""

import importlib
import inspect
from typing import Dict, Any, List, Optional, Type, Set
from datetime import datetime
from .base import BaseConnector, ConnectorError


class ConnectorRegistry:
    """
    Registry for managing connector classes and instances.
    
    Provides dynamic discovery of connectors, instantiation,
    and lifecycle management with support for multi-tenancy.
    
    Attributes:
        _connector_classes (Dict[str, Type[BaseConnector]]): Registered connector classes
        _connector_instances (Dict[str, BaseConnector]): Active connector instances
        _tenant_connectors (Dict[str, Set[str]]): Tenant-specific connector mappings
    """
    
    def __init__(self):
        """Initialize the connector registry."""
        self._connector_classes: Dict[str, Type[BaseConnector]] = {}
        self._connector_instances: Dict[str, BaseConnector] = {}
        self._tenant_connectors: Dict[str, Set[str]] = {}
    
    def register_connector_class(self, connector_class: Type[BaseConnector]) -> None:
        """
        Register a connector class.
        
        Args:
            connector_class (Type[BaseConnector]): Connector class to register
            
        Raises:
            ValueError: If connector class is invalid
        """
        if not inspect.isclass(connector_class):
            raise ValueError("connector_class must be a class")
        
        if not issubclass(connector_class, BaseConnector):
            raise ValueError("connector_class must inherit from BaseConnector")
        
        # Get connector name from class
        connector_name = getattr(connector_class, 'CONNECTOR_NAME', connector_class.__name__)
        
        self._connector_classes[connector_name] = connector_class
        print(f"Registered connector class: {connector_name}")
    
    def register_connector_from_module(self, module_name: str, connector_name: str) -> None:
        """
        Register a connector class from a module.
        
        Args:
            module_name (str): Name of the module containing the connector
            connector_name (str): Name of the connector class
        """
        try:
            module = importlib.import_module(module_name)
            connector_class = getattr(module, connector_name)
            self.register_connector_class(connector_class)
        except (ImportError, AttributeError) as e:
            raise ConnectorError(f"Failed to register connector from module: {e}")
    
    def create_connector(
        self,
        connector_name: str,
        tenant_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        **kwargs
    ) -> BaseConnector:
        """
        Create a new connector instance.
        
        Args:
            connector_name (str): Name of the connector class
            tenant_id (Optional[str]): Tenant identifier
            instance_id (Optional[str]): Custom instance ID
            **kwargs: Additional arguments for connector initialization
            
        Returns:
            BaseConnector: New connector instance
            
        Raises:
            ConnectorError: If connector class not found or creation fails
        """
        if connector_name not in self._connector_classes:
            raise ConnectorError(f"Connector class '{connector_name}' not found")
        
        try:
            connector_class = self._connector_classes[connector_name]
            
            # Create instance with tenant_id
            if tenant_id:
                kwargs['tenant_id'] = tenant_id
            
            instance = connector_class(**kwargs)
            
            # Generate instance ID if not provided
            if not instance_id:
                instance_id = f"{connector_name}_{tenant_id or 'default'}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
            # Store instance
            self._connector_instances[instance_id] = instance
            
            # Track tenant mapping
            if tenant_id:
                if tenant_id not in self._tenant_connectors:
                    self._tenant_connectors[tenant_id] = set()
                self._tenant_connectors[tenant_id].add(instance_id)
            
            return instance
            
        except Exception as e:
            raise ConnectorError(f"Failed to create connector instance: {e}")
    
    def get_connector(self, instance_id: str) -> Optional[BaseConnector]:
        """
        Get a connector instance by ID.
        
        Args:
            instance_id (str): Instance ID
            
        Returns:
            Optional[BaseConnector]: Connector instance if found, None otherwise
        """
        return self._connector_instances.get(instance_id)
    
    def get_connectors_by_tenant(self, tenant_id: str) -> List[BaseConnector]:
        """
        Get all connector instances for a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            List[BaseConnector]: List of connector instances
        """
        instance_ids = self._tenant_connectors.get(tenant_id, set())
        return [self._connector_instances[instance_id] for instance_id in instance_ids if instance_id in self._connector_instances]
    
    def get_connectors_by_type(self, connector_name: str) -> List[BaseConnector]:
        """
        Get all instances of a specific connector type.
        
        Args:
            connector_name (str): Name of the connector class
            
        Returns:
            List[BaseConnector]: List of connector instances
        """
        return [
            instance for instance in self._connector_instances.values()
            if instance.__class__.__name__ == connector_name or getattr(instance.__class__, 'CONNECTOR_NAME', instance.__class__.__name__) == connector_name
        ]
    
    def remove_connector(self, instance_id: str) -> bool:
        """
        Remove a connector instance.
        
        Args:
            instance_id (str): Instance ID
            
        Returns:
            bool: True if removed, False if not found
        """
        if instance_id not in self._connector_instances:
            return False
        
        instance = self._connector_instances[instance_id]
        
        # Disconnect if connected
        if instance.is_connected():
            instance.disconnect()
        
        # Remove from tenant mapping
        for tenant_id, instance_ids in self._tenant_connectors.items():
            instance_ids.discard(instance_id)
        
        # Remove instance
        del self._connector_instances[instance_id]
        
        return True
    
    def list_available_connectors(self) -> List[Dict[str, Any]]:
        """
        List all available connector classes.
        
        Returns:
            List[Dict[str, Any]]: List of connector class information
        """
        connectors = []
        
        for name, connector_class in self._connector_classes.items():
            # Get connector metadata
            metadata = {
                'name': name,
                'class_name': connector_class.__name__,
                'module': connector_class.__module__,
                'version': getattr(connector_class, 'VERSION', '1.0.0'),
                'description': getattr(connector_class, 'DESCRIPTION', ''),
                'actions': []
            }
            
            # Try to get actions from a sample instance
            try:
                sample_instance = connector_class()
                metadata['actions'] = sample_instance.list_actions()
            except Exception:
                # If we can't create a sample instance, leave actions empty
                pass
            
            connectors.append(metadata)
        
        return connectors
    
    def list_active_instances(self) -> List[Dict[str, Any]]:
        """
        List all active connector instances.
        
        Returns:
            List[Dict[str, Any]]: List of instance information
        """
        instances = []
        
        for instance_id, instance in self._connector_instances.items():
            instances.append({
                'instance_id': instance_id,
                'connector_name': instance.name,
                'status': instance.get_status(),
                'is_connected': instance.is_connected()
            })
        
        return instances
    
    def discover_connectors_in_module(self, module_name: str) -> List[str]:
        """
        Discover connector classes in a module.
        
        Args:
            module_name (str): Name of the module to search
            
        Returns:
            List[str]: List of discovered connector class names
        """
        try:
            module = importlib.import_module(module_name)
            discovered = []
            
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, BaseConnector) and 
                    obj != BaseConnector):
                    discovered.append(name)
                    self.register_connector_class(obj)
            
            return discovered
            
        except ImportError as e:
            raise ConnectorError(f"Failed to discover connectors in module '{module_name}': {e}")
    
    def get_registry_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dict[str, Any]: Registry statistics
        """
        total_instances = len(self._connector_instances)
        connected_instances = sum(1 for instance in self._connector_instances.values() if instance.is_connected())
        
        tenant_stats = {}
        for tenant_id, instance_ids in self._tenant_connectors.items():
            tenant_stats[tenant_id] = {
                'total_instances': len(instance_ids),
                'connected_instances': sum(
                    1 for instance_id in instance_ids
                    if instance_id in self._connector_instances and self._connector_instances[instance_id].is_connected()
                )
            }
        
        return {
            'total_connector_classes': len(self._connector_classes),
            'total_instances': total_instances,
            'connected_instances': connected_instances,
            'disconnected_instances': total_instances - connected_instances,
            'tenant_count': len(self._tenant_connectors),
            'tenant_statistics': tenant_stats,
            'available_connectors': list(self._connector_classes.keys())
        }
    
    def cleanup_disconnected_instances(self) -> int:
        """
        Remove all disconnected connector instances.
        
        Returns:
            int: Number of instances removed
        """
        disconnected_ids = [
            instance_id for instance_id, instance in self._connector_instances.items()
            if not instance.is_connected()
        ]
        
        for instance_id in disconnected_ids:
            self.remove_connector(instance_id)
        
        return len(disconnected_ids)
    
    def __repr__(self) -> str:
        """String representation of the registry."""
        return f"ConnectorRegistry(classes={len(self._connector_classes)}, instances={len(self._connector_instances)})"


# Global registry instance
_global_registry = ConnectorRegistry()


def get_global_registry() -> ConnectorRegistry:
    """
    Get the global connector registry instance.
    
    Returns:
        ConnectorRegistry: Global registry instance
    """
    return _global_registry


def register_connector(connector_class: Type[BaseConnector]) -> None:
    """
    Register a connector class in the global registry.
    
    Args:
        connector_class (Type[BaseConnector]): Connector class to register
    """
    _global_registry.register_connector_class(connector_class)


def create_connector(connector_name: str, tenant_id: Optional[str] = None, **kwargs) -> BaseConnector:
    """
    Create a connector instance using the global registry.
    
    Args:
        connector_name (str): Name of the connector class
        tenant_id (Optional[str]): Tenant identifier
        **kwargs: Additional arguments for connector initialization
        
    Returns:
        BaseConnector: New connector instance
    """
    return _global_registry.create_connector(connector_name, tenant_id, **kwargs)
>>>>>>> 1fc482f1c958a8bf865f354544dab0fde2428422
