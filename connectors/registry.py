"""
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
