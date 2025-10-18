"""
Task class for Enterprise AI Agent Framework.

Represents a single executable task in a workflow with support for
retries, timeouts, conditions, and serialization.
"""

import json
import uuid
from typing import Any, Dict, Optional, Callable, Union
from datetime import datetime, timedelta


class Task:
    """
    A single task in an AI agent workflow.
    
    Tasks represent atomic units of work that can be executed by the framework.
    They support conditional execution, retries, timeouts, and serialization.
    
    Attributes:
        id (str): Unique identifier for the task
        handler (str): Name of the handler/connector to execute this task
        inputs (Dict[str, Any]): Input parameters for the task
        retries (int): Maximum number of retry attempts (default: 3)
        timeout (Optional[timedelta]): Maximum execution time
        condition (Optional[Callable]): Condition function for conditional execution
        tenant_id (Optional[str]): Tenant identifier for multi-tenancy
        created_at (datetime): Task creation timestamp
        updated_at (datetime): Last update timestamp
    """
    
    def __init__(
        self,
        handler: str,
        inputs: Optional[Dict[str, Any]] = None,
        retries: int = 3,
        timeout: Optional[Union[int, timedelta]] = None,
        condition: Optional[Callable] = None,
        tenant_id: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        """
        Initialize a new Task.
        
        Args:
            handler (str): Name of the handler/connector to execute this task
            inputs (Optional[Dict[str, Any]]): Input parameters for the task
            retries (int): Maximum number of retry attempts (default: 3)
            timeout (Optional[Union[int, timedelta]]): Maximum execution time in seconds or timedelta
            condition (Optional[Callable]): Condition function for conditional execution
            tenant_id (Optional[str]): Tenant identifier for multi-tenancy
            task_id (Optional[str]): Custom task ID (generated if not provided)
        """
        self.id = task_id or str(uuid.uuid4())
        self.handler = handler
        self.inputs = inputs or {}
        self.retries = max(0, retries)  # Ensure non-negative
        self.timeout = self._parse_timeout(timeout)
        self.condition = condition
        self.tenant_id = tenant_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def _parse_timeout(self, timeout: Optional[Union[int, timedelta]]) -> Optional[timedelta]:
        """
        Parse timeout value into timedelta object.
        
        Args:
            timeout: Timeout in seconds (int) or timedelta object
            
        Returns:
            Optional[timedelta]: Parsed timeout or None
        """
        if timeout is None:
            return None
        if isinstance(timeout, int):
            return timedelta(seconds=timeout)
        if isinstance(timeout, timedelta):
            return timeout
        raise ValueError("Timeout must be an integer (seconds) or timedelta object")
    
    def should_execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if this task should be executed based on its condition.
        
        Args:
            context (Optional[Dict[str, Any]]): Execution context for condition evaluation
            
        Returns:
            bool: True if task should execute, False otherwise
        """
        if self.condition is None:
            return True
        
        try:
            return bool(self.condition(context or {}))
        except Exception:
            # If condition evaluation fails, don't execute the task
            return False
    
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the task to a dictionary for storage/transmission.
        
        Returns:
            Dict[str, Any]: Serialized task data
        """
        return {
            'id': self.id,
            'handler': self.handler,
            'inputs': self.inputs,
            'retries': self.retries,
            'timeout_seconds': self.timeout.total_seconds() if self.timeout else None,
            'condition': self._serialize_condition(),
            'tenant_id': self.tenant_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def _serialize_condition(self) -> Optional[str]:
        """
        Serialize the condition function to a string representation.
        
        Note: This is a simplified serialization. In production, you might want
        to use more sophisticated serialization for functions.
        
        Returns:
            Optional[str]: String representation of the condition function
        """
        if self.condition is None:
            return None
        
        # For now, we'll store the function name and module
        # In production, you might want to use pickle or other serialization
        return f"{self.condition.__module__}.{self.condition.__name__}"
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'Task':
        """
        Deserialize a task from a dictionary.
        
        Args:
            data (Dict[str, Any]): Serialized task data
            
        Returns:
            Task: Deserialized task instance
        """
        # Parse timeout
        timeout = None
        if data.get('timeout_seconds'):
            timeout = timedelta(seconds=data['timeout_seconds'])
        
        # Parse timestamps
        created_at = datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat()))
        
        # Create task instance
        task = cls(
            handler=data['handler'],
            inputs=data.get('inputs', {}),
            retries=data.get('retries', 3),
            timeout=timeout,
            tenant_id=data.get('tenant_id'),
            task_id=data.get('id')
        )
        
        # Restore timestamps
        task.created_at = created_at
        task.updated_at = updated_at
        
        # Note: Condition deserialization is not implemented here as it requires
        # more sophisticated handling in production environments
        
        return task
    
    def to_json(self) -> str:
        """
        Convert task to JSON string.
        
        Returns:
            str: JSON representation of the task
        """
        return json.dumps(self.serialize(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Task':
        """
        Create task from JSON string.
        
        Args:
            json_str (str): JSON string representation of the task
            
        Returns:
            Task: Task instance created from JSON
        """
        data = json.loads(json_str)
        return cls.deserialize(data)
    
    def update_inputs(self, new_inputs: Dict[str, Any]) -> None:
        """
        Update task inputs.
        
        Args:
            new_inputs (Dict[str, Any]): New input parameters
        """
        self.inputs.update(new_inputs)
        self.updated_at = datetime.utcnow()
    
    def validate(self) -> bool:
        """
        Validate the task configuration.
        
        Returns:
            bool: True if task is valid, False otherwise
        """
        # Check required fields
        if not self.handler or not isinstance(self.handler, str):
            return False
        
        if not isinstance(self.inputs, dict):
            return False
        
        if self.retries < 0:
            return False
        
        if self.timeout and self.timeout.total_seconds() <= 0:
            return False
        
        return True
    
    def __repr__(self) -> str:
        """String representation of the task."""
        return (
            f"Task(id='{self.id}', handler='{self.handler}', "
            f"retries={self.retries}, tenant_id='{self.tenant_id}')"
        )
    
    def __eq__(self, other: object) -> bool:
        """Check equality with another task."""
        if not isinstance(other, Task):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash the task based on its ID."""
        return hash(self.id)
