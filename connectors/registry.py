"""
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