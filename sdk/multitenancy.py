"""
Multi-tenancy support for Enterprise AI Agent Framework.

Provides tenant isolation, resource management, and tenant-specific
configurations for the AI agent framework.
"""

import uuid
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class TenantConfig:
    """
    Configuration for a specific tenant.
    
    Attributes:
        tenant_id (str): Unique tenant identifier
        name (str): Human-readable tenant name
        max_concurrent_flows (int): Maximum concurrent flows allowed
        max_tasks_per_flow (int): Maximum tasks per flow
        max_retries_per_task (int): Maximum retries per task
        max_timeout_seconds (int): Maximum timeout in seconds
        allowed_handlers (Set[str]): Set of allowed handlers
        blocked_handlers (Set[str]): Set of blocked handlers
        resource_limits (Dict[str, Any]): Resource limits for the tenant
        created_at (datetime): Tenant creation timestamp
        updated_at (datetime): Last update timestamp
        is_active (bool): Whether the tenant is active
    """
    tenant_id: str
    name: str
    max_concurrent_flows: int = 10
    max_tasks_per_flow: int = 100
    max_retries_per_task: int = 5
    max_timeout_seconds: int = 3600  # 1 hour
    allowed_handlers: Set[str] = field(default_factory=set)
    blocked_handlers: Set[str] = field(default_factory=set)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True


class TenantManager:
    """
    Manages tenant configurations and provides tenant isolation.
    
    This class handles tenant registration, configuration management,
    and provides methods to check tenant-specific limits and permissions.
    """
    
    def __init__(self):
        """Initialize the tenant manager."""
        self._tenants: Dict[str, TenantConfig] = {}
        self._tenant_resources: Dict[str, Dict[str, Any]] = {}
    
    def register_tenant(
        self,
        name: str,
        tenant_id: Optional[str] = None,
        max_concurrent_flows: int = 10,
        max_tasks_per_flow: int = 100,
        max_retries_per_task: int = 5,
        max_timeout_seconds: int = 3600,
        allowed_handlers: Optional[List[str]] = None,
        blocked_handlers: Optional[List[str]] = None,
        resource_limits: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Register a new tenant.
        
        Args:
            name (str): Human-readable tenant name
            tenant_id (Optional[str]): Custom tenant ID (generated if not provided)
            max_concurrent_flows (int): Maximum concurrent flows allowed
            max_tasks_per_flow (int): Maximum tasks per flow
            max_retries_per_task (int): Maximum retries per task
            max_timeout_seconds (int): Maximum timeout in seconds
            allowed_handlers (Optional[List[str]]): List of allowed handlers
            blocked_handlers (Optional[List[str]]): List of blocked handlers
            resource_limits (Optional[Dict[str, Any]]): Resource limits for the tenant
            
        Returns:
            str: The tenant ID
            
        Raises:
            ValueError: If tenant name is empty or tenant_id already exists
        """
        if not name.strip():
            raise ValueError("Tenant name cannot be empty")
        
        tid = tenant_id or str(uuid.uuid4())
        
        if tid in self._tenants:
            raise ValueError(f"Tenant with ID '{tid}' already exists")
        
        config = TenantConfig(
            tenant_id=tid,
            name=name,
            max_concurrent_flows=max_concurrent_flows,
            max_tasks_per_flow=max_tasks_per_flow,
            max_retries_per_task=max_retries_per_task,
            max_timeout_seconds=max_timeout_seconds,
            allowed_handlers=set(allowed_handlers or []),
            blocked_handlers=set(blocked_handlers or []),
            resource_limits=resource_limits or {}
        )
        
        self._tenants[tid] = config
        self._tenant_resources[tid] = {
            'active_flows': 0,
            'total_tasks_executed': 0,
            'last_activity': datetime.utcnow()
        }
        
        return tid
    
    def get_tenant(self, tenant_id: str) -> Optional[TenantConfig]:
        """
        Get tenant configuration by ID.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            Optional[TenantConfig]: Tenant configuration if found, None otherwise
        """
        return self._tenants.get(tenant_id)
    
    def update_tenant(
        self,
        tenant_id: str,
        name: Optional[str] = None,
        max_concurrent_flows: Optional[int] = None,
        max_tasks_per_flow: Optional[int] = None,
        max_retries_per_task: Optional[int] = None,
        max_timeout_seconds: Optional[int] = None,
        allowed_handlers: Optional[List[str]] = None,
        blocked_handlers: Optional[List[str]] = None,
        resource_limits: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update tenant configuration.
        
        Args:
            tenant_id (str): Tenant ID
            name (Optional[str]): New tenant name
            max_concurrent_flows (Optional[int]): New max concurrent flows
            max_tasks_per_flow (Optional[int]): New max tasks per flow
            max_retries_per_task (Optional[int]): New max retries per task
            max_timeout_seconds (Optional[int]): New max timeout
            allowed_handlers (Optional[List[str]]): New allowed handlers
            blocked_handlers (Optional[List[str]]): New blocked handlers
            resource_limits (Optional[Dict[str, Any]]): New resource limits
            is_active (Optional[bool]): New active status
            
        Returns:
            bool: True if tenant was updated, False if not found
        """
        if tenant_id not in self._tenants:
            return False
        
        config = self._tenants[tenant_id]
        
        if name is not None:
            config.name = name
        if max_concurrent_flows is not None:
            config.max_concurrent_flows = max_concurrent_flows
        if max_tasks_per_flow is not None:
            config.max_tasks_per_flow = max_tasks_per_flow
        if max_retries_per_task is not None:
            config.max_retries_per_task = max_retries_per_task
        if max_timeout_seconds is not None:
            config.max_timeout_seconds = max_timeout_seconds
        if allowed_handlers is not None:
            config.allowed_handlers = set(allowed_handlers)
        if blocked_handlers is not None:
            config.blocked_handlers = set(blocked_handlers)
        if resource_limits is not None:
            config.resource_limits.update(resource_limits)
        if is_active is not None:
            config.is_active = is_active
        
        config.updated_at = datetime.utcnow()
        return True
    
    def deactivate_tenant(self, tenant_id: str) -> bool:
        """
        Deactivate a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            bool: True if tenant was deactivated, False if not found
        """
        return self.update_tenant(tenant_id, is_active=False)
    
    def activate_tenant(self, tenant_id: str) -> bool:
        """
        Activate a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            bool: True if tenant was activated, False if not found
        """
        return self.update_tenant(tenant_id, is_active=True)
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant and all its data.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            bool: True if tenant was deleted, False if not found
        """
        if tenant_id not in self._tenants:
            return False
        
        del self._tenants[tenant_id]
        self._tenant_resources.pop(tenant_id, None)
        return True
    
    def list_tenants(self, active_only: bool = True) -> List[str]:
        """
        List all tenant IDs.
        
        Args:
            active_only (bool): If True, only return active tenants
            
        Returns:
            List[str]: List of tenant IDs
        """
        if active_only:
            return [
                tid for tid, config in self._tenants.items()
                if config.is_active
            ]
        return list(self._tenants.keys())
    
    def check_tenant_limits(self, tenant_id: str) -> Dict[str, Any]:
        """
        Check if tenant is within its resource limits.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            Dict[str, Any]: Limit check results
        """
        config = self.get_tenant(tenant_id)
        if not config:
            return {'valid': False, 'error': 'Tenant not found'}
        
        if not config.is_active:
            return {'valid': False, 'error': 'Tenant is inactive'}
        
        resources = self._tenant_resources.get(tenant_id, {})
        
        checks = {
            'valid': True,
            'tenant_id': tenant_id,
            'checks': {}
        }
        
        # Check concurrent flows
        active_flows = resources.get('active_flows', 0)
        if active_flows >= config.max_concurrent_flows:
            checks['valid'] = False
            checks['checks']['concurrent_flows'] = {
                'current': active_flows,
                'limit': config.max_concurrent_flows,
                'exceeded': True
            }
        else:
            checks['checks']['concurrent_flows'] = {
                'current': active_flows,
                'limit': config.max_concurrent_flows,
                'exceeded': False
            }
        
        return checks
    
    def increment_active_flows(self, tenant_id: str) -> bool:
        """
        Increment the count of active flows for a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            bool: True if increment was successful, False if limit exceeded
        """
        config = self.get_tenant(tenant_id)
        if not config or not config.is_active:
            return False
        
        resources = self._tenant_resources.get(tenant_id, {})
        current_flows = resources.get('active_flows', 0)
        
        if current_flows >= config.max_concurrent_flows:
            return False
        
        resources['active_flows'] = current_flows + 1
        resources['last_activity'] = datetime.utcnow()
        self._tenant_resources[tenant_id] = resources
        
        return True
    
    def decrement_active_flows(self, tenant_id: str) -> None:
        """
        Decrement the count of active flows for a tenant.
        
        Args:
            tenant_id (str): Tenant ID
        """
        if tenant_id in self._tenant_resources:
            resources = self._tenant_resources[tenant_id]
            current_flows = resources.get('active_flows', 0)
            resources['active_flows'] = max(0, current_flows - 1)
            resources['last_activity'] = datetime.utcnow()
    
    def increment_task_count(self, tenant_id: str, count: int = 1) -> None:
        """
        Increment the total task count for a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            count (int): Number of tasks to add
        """
        if tenant_id in self._tenant_resources:
            resources = self._tenant_resources[tenant_id]
            resources['total_tasks_executed'] = resources.get('total_tasks_executed', 0) + count
            resources['last_activity'] = datetime.utcnow()
    
    def get_tenant_statistics(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a tenant.
        
        Args:
            tenant_id (str): Tenant ID
            
        Returns:
            Optional[Dict[str, Any]]: Tenant statistics if found, None otherwise
        """
        config = self.get_tenant(tenant_id)
        if not config:
            return None
        
        resources = self._tenant_resources.get(tenant_id, {})
        
        return {
            'tenant_id': tenant_id,
            'name': config.name,
            'is_active': config.is_active,
            'active_flows': resources.get('active_flows', 0),
            'total_tasks_executed': resources.get('total_tasks_executed', 0),
            'last_activity': resources.get('last_activity'),
            'limits': {
                'max_concurrent_flows': config.max_concurrent_flows,
                'max_tasks_per_flow': config.max_tasks_per_flow,
                'max_retries_per_task': config.max_retries_per_task,
                'max_timeout_seconds': config.max_timeout_seconds
            },
            'created_at': config.created_at,
            'updated_at': config.updated_at
        }
    
    def get_all_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for all tenants.
        
        Returns:
            Dict[str, Any]: Statistics for all tenants
        """
        stats = {
            'total_tenants': len(self._tenants),
            'active_tenants': len([t for t in self._tenants.values() if t.is_active]),
            'total_active_flows': sum(
                resources.get('active_flows', 0)
                for resources in self._tenant_resources.values()
            ),
            'total_tasks_executed': sum(
                resources.get('total_tasks_executed', 0)
                for resources in self._tenant_resources.values()
            ),
            'tenants': {}
        }
        
        for tenant_id in self._tenants.keys():
            stats['tenants'][tenant_id] = self.get_tenant_statistics(tenant_id)
        
        return stats
    
    def __repr__(self) -> str:
        """String representation of the tenant manager."""
        return f"TenantManager(tenants={len(self._tenants)}, active={len(self.list_tenants())})"
