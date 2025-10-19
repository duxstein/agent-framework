"""
Policy system for Enterprise AI Agent Framework SDK.

This module provides the base Policy class and interfaces for implementing
pre-task and post-task policies that can be applied to flows and tasks.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from enum import Enum

from .models import Task, Flow


class PolicyResult(Enum):
    """Result of policy evaluation."""
    ALLOW = "allow"
    DENY = "deny"
    MODIFY = "modify"


class PolicyError(Exception):
    """Exception raised when policy evaluation fails."""
    pass


class Policy(ABC):
    """
    Base class for all policies in the framework.
    
    Policies are used to enforce business rules, security constraints,
    and operational requirements on tasks and flows.
    """
    
    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        enabled: bool = True,
        priority: int = 100,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a policy.
        
        Args:
            name: Unique name for the policy
            description: Human-readable description of the policy
            enabled: Whether the policy is enabled
            priority: Priority level (lower numbers = higher priority)
            metadata: Additional metadata for the policy
        """
        self.name = name
        self.description = description or ""
        self.enabled = enabled
        self.priority = priority
        self.metadata = metadata or {}
    
    @abstractmethod
    def evaluate(
        self,
        context: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Evaluate the policy against the given context.
        
        Args:
            context: Context information for policy evaluation
            **kwargs: Additional keyword arguments
            
        Returns:
            Dictionary containing:
            - result: PolicyResult (ALLOW, DENY, MODIFY)
            - message: Human-readable message
            - modifications: Optional modifications to apply
            - metadata: Additional policy metadata
        """
        pass
    
    def is_enabled(self) -> bool:
        """Check if the policy is enabled."""
        return self.enabled
    
    def get_priority(self) -> int:
        """Get the policy priority."""
        return self.priority
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert policy to dictionary."""
        return {
            'name': self.name,
            'description': self.description,
            'enabled': self.enabled,
            'priority': self.priority,
            'metadata': self.metadata,
            'type': self.__class__.__name__
        }
    
    def __repr__(self) -> str:
        """String representation of the policy."""
        return f"{self.__class__.__name__}(name='{self.name}', enabled={self.enabled})"


class PreTaskPolicy(Policy):
    """
    Interface for policies that are evaluated before task execution.
    
    Pre-task policies can modify task parameters, deny execution,
    or apply additional constraints before a task runs.
    """
    
    @abstractmethod
    def evaluate(
        self,
        task: Task,
        flow: Flow,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the policy before task execution.
        
        Args:
            task: Task that is about to be executed
            flow: Flow containing the task
            context: Additional context information
            
        Returns:
            Dictionary containing:
            - result: PolicyResult (ALLOW, DENY, MODIFY)
            - message: Human-readable message
            - modifications: Optional modifications to task parameters
            - metadata: Additional policy metadata
        """
        pass


class PostTaskPolicy(Policy):
    """
    Interface for policies that are evaluated after task execution.
    
    Post-task policies can validate results, apply cleanup actions,
    or trigger additional workflows based on task outcomes.
    """
    
    @abstractmethod
    def evaluate(
        self,
        task: Task,
        flow: Flow,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the policy after task execution.
        
        Args:
            task: Task that was executed
            flow: Flow containing the task
            result: Result of the task execution
            context: Additional context information
            
        Returns:
            Dictionary containing:
            - result: PolicyResult (ALLOW, DENY, MODIFY)
            - message: Human-readable message
            - modifications: Optional modifications to result
            - metadata: Additional policy metadata
        """
        pass


class FlowPolicy(Policy):
    """
    Interface for policies that are evaluated at the flow level.
    
    Flow policies can validate entire flows, apply global constraints,
    or modify flow structure before execution.
    """
    
    @abstractmethod
    def evaluate(
        self,
        flow: Flow,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate the policy against a flow.
        
        Args:
            flow: Flow to evaluate
            context: Additional context information
            
        Returns:
            Dictionary containing:
            - result: PolicyResult (ALLOW, DENY, MODIFY)
            - message: Human-readable message
            - modifications: Optional modifications to flow
            - metadata: Additional policy metadata
        """
        pass


# Example implementations

class RetryLimitPolicy(PreTaskPolicy):
    """
    Policy that enforces retry limits on tasks.
    """
    
    def __init__(
        self,
        max_retries: int = 5,
        name: str = "retry_limit",
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.max_retries = max_retries
    
    def evaluate(
        self,
        task: Task,
        flow: Flow,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate retry limit policy."""
        if task.retries > self.max_retries:
            return {
                'result': PolicyResult.DENY,
                'message': f"Task retries ({task.retries}) exceeds maximum allowed ({self.max_retries})",
                'modifications': None,
                'metadata': {'max_retries': self.max_retries, 'task_retries': task.retries}
            }
        
        return {
            'result': PolicyResult.ALLOW,
            'message': "Retry limit policy passed",
            'modifications': None,
            'metadata': {'max_retries': self.max_retries, 'task_retries': task.retries}
        }


class TimeoutPolicy(PreTaskPolicy):
    """
    Policy that enforces timeout limits on tasks.
    """
    
    def __init__(
        self,
        max_timeout: int = 3600,  # 1 hour
        name: str = "timeout_limit",
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.max_timeout = max_timeout
    
    def evaluate(
        self,
        task: Task,
        flow: Flow,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate timeout policy."""
        if task.timeout > self.max_timeout:
            return {
                'result': PolicyResult.MODIFY,
                'message': f"Task timeout ({task.timeout}s) exceeds maximum allowed ({self.max_timeout}s), reducing to maximum",
                'modifications': {'timeout': self.max_timeout},
                'metadata': {'max_timeout': self.max_timeout, 'original_timeout': task.timeout}
            }
        
        return {
            'result': PolicyResult.ALLOW,
            'message': "Timeout policy passed",
            'modifications': None,
            'metadata': {'max_timeout': self.max_timeout, 'task_timeout': task.timeout}
        }


class TenantIsolationPolicy(FlowPolicy):
    """
    Policy that enforces tenant isolation in flows.
    """
    
    def __init__(
        self,
        name: str = "tenant_isolation",
        **kwargs
    ):
        super().__init__(name, **kwargs)
    
    def evaluate(
        self,
        flow: Flow,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate tenant isolation policy."""
        if not flow.tenant_id:
            return {
                'result': PolicyResult.DENY,
                'message': "Flow must have a tenant_id for tenant isolation",
                'modifications': None,
                'metadata': {'policy': 'tenant_isolation'}
            }
        
        # Check that all tasks have the same tenant_id
        task_tenant_ids = set(task.tenant_id for task in flow.tasks if task.tenant_id)
        if len(task_tenant_ids) > 1:
            return {
                'result': PolicyResult.DENY,
                'message': "All tasks in flow must have the same tenant_id",
                'modifications': None,
                'metadata': {'policy': 'tenant_isolation', 'task_tenant_ids': list(task_tenant_ids)}
            }
        
        return {
            'result': PolicyResult.ALLOW,
            'message': "Tenant isolation policy passed",
            'modifications': None,
            'metadata': {'policy': 'tenant_isolation', 'tenant_id': flow.tenant_id}
        }


class ResultValidationPolicy(PostTaskPolicy):
    """
    Policy that validates task execution results.
    """
    
    def __init__(
        self,
        required_fields: Optional[List[str]] = None,
        name: str = "result_validation",
        **kwargs
    ):
        super().__init__(name, **kwargs)
        self.required_fields = required_fields or []
    
    def evaluate(
        self,
        task: Task,
        flow: Flow,
        result: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Evaluate result validation policy."""
        if not result:
            return {
                'result': PolicyResult.DENY,
                'message': "Task result is empty",
                'modifications': None,
                'metadata': {'policy': 'result_validation'}
            }
        
        # Check required fields
        missing_fields = []
        for field in self.required_fields:
            if field not in result:
                missing_fields.append(field)
        
        if missing_fields:
            return {
                'result': PolicyResult.DENY,
                'message': f"Task result missing required fields: {missing_fields}",
                'modifications': None,
                'metadata': {'policy': 'result_validation', 'missing_fields': missing_fields}
            }
        
        return {
            'result': PolicyResult.ALLOW,
            'message': "Result validation policy passed",
            'modifications': None,
            'metadata': {'policy': 'result_validation', 'required_fields': self.required_fields}
        }
