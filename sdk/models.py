"""
Pydantic models for Enterprise AI Agent Framework SDK.

This module provides the core data models using Pydantic for validation,
serialization, and type safety.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union, Literal
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class Task(BaseModel):
    """
    A single task in an AI agent workflow.
    
    Tasks represent atomic units of work that can be executed by the framework.
    They support conditional execution, retries, timeouts, and serialization.
    
    Attributes:
        id: Unique identifier for the task
        handler: Name of the handler/connector to execute this task
        inputs: Input parameters for the task
        retries: Maximum number of retry attempts (default: 3)
        timeout: Maximum execution time in seconds
        condition: Optional condition string for conditional execution
        metadata: Additional metadata for the task
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique task identifier")
    handler: str = Field(..., description="Handler/connector name to execute this task")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input parameters for the task")
    retries: int = Field(default=3, ge=0, description="Maximum number of retry attempts")
    timeout: int = Field(default=300, gt=0, description="Maximum execution time in seconds")
    condition: Optional[str] = Field(default=None, description="Optional condition string for conditional execution")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier for multi-tenancy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")
    
    @field_validator('handler')
    @classmethod
    def validate_handler(cls, v):
        """Validate that handler is not empty."""
        if not v or not v.strip():
            raise ValueError('Handler cannot be empty')
        return v.strip()
    
    @field_validator('retries')
    @classmethod
    def validate_retries(cls, v):
        """Validate retries is non-negative."""
        if v < 0:
            raise ValueError('Retries must be non-negative')
        return v
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v):
        """Validate timeout is positive."""
        if v <= 0:
            raise ValueError('Timeout must be positive')
        return v
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        validate_assignment = True
        extra = "forbid"
    
    def should_execute(self, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if this task should be executed based on its condition.
        
        Args:
            context: Execution context for condition evaluation
            
        Returns:
            True if task should execute, False otherwise
        """
        if self.condition is None:
            return True
        
        # Simple condition evaluation - in production, you might want more sophisticated logic
        try:
            # For now, we'll do a simple string-based evaluation
            # In production, you might want to use a proper expression evaluator
            return bool(self.condition.strip())
        except Exception:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert task to dictionary.
        
        Returns:
            Dictionary representation of the task
        """
        return self.dict()
    
    def save(self, path: Union[str, Path]) -> None:
        """
        Save task to JSON file.
        
        Args:
            path: Path to save the task JSON file
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save task to {path}: {str(e)}")
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'Task':
        """
        Load task from JSON file.
        
        Args:
            path: Path to the task JSON file
            
        Returns:
            Task instance loaded from file
            
        Raises:
            IOError: If file cannot be read
            ValueError: If file contains invalid task data
        """
        try:
            path = Path(path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            raise IOError(f"Failed to load task from {path}: {str(e)}")


class Flow(BaseModel):
    """
    A complete workflow consisting of multiple tasks.
    
    Flows represent end-to-end processes that orchestrate multiple tasks
    in a specific order or dependency graph.
    
    Attributes:
        id: Unique identifier for the flow
        version: Version of the flow
        tasks: List of tasks in this flow
        type: Type of flow execution ("DAG" or "STATE_MACHINE")
        tenant_id: Tenant identifier for multi-tenancy
        metadata: Additional metadata for the flow
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique flow identifier")
    version: str = Field(default="1.0.0", description="Flow version")
    tasks: List[Task] = Field(default_factory=list, description="List of tasks in this flow")
    type: Literal["DAG", "STATE_MACHINE"] = Field(default="DAG", description="Flow execution type")
    tenant_id: Optional[str] = Field(default=None, description="Tenant identifier for multi-tenancy")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional flow metadata")
    
    @field_validator('tasks')
    @classmethod
    def validate_tasks(cls, v):
        """Validate that tasks list is not empty."""
        if not v:
            raise ValueError('Flow must contain at least one task')
        return v
    
    @field_validator('version')
    @classmethod
    def validate_version(cls, v):
        """Validate version format."""
        if not v or not v.strip():
            raise ValueError('Version cannot be empty')
        return v.strip()
    
    @model_validator(mode='after')
    def validate_tenant_consistency(self):
        """Validate tenant consistency across tasks."""
        tenant_id = self.tenant_id
        tasks = self.tasks
        
        if tenant_id and tasks:
            for task in tasks:
                if task.tenant_id and task.tenant_id != tenant_id:
                    raise ValueError('Task tenant_id must match flow tenant_id')
        
        return self
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        validate_assignment = True
        extra = "forbid"
    
    def add_task(self, task: Task) -> None:
        """
        Add a task to the flow.
        
        Args:
            task: Task to add to the flow
            
        Raises:
            ValueError: If task tenant_id doesn't match flow tenant_id
        """
        if self.tenant_id and task.tenant_id and self.tenant_id != task.tenant_id:
            raise ValueError("Task tenant_id must match flow tenant_id")
        
        # Set tenant_id if not already set
        if self.tenant_id and not task.tenant_id:
            task.tenant_id = self.tenant_id
        
        self.tasks.append(task)
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the flow by ID.
        
        Args:
            task_id: ID of the task to remove
            
        Returns:
            True if task was removed, False if not found
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by its ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Task if found, None otherwise
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_tasks_by_handler(self, handler: str) -> List[Task]:
        """
        Get all tasks that use a specific handler.
        
        Args:
            handler: Handler name to filter by
            
        Returns:
            List of tasks using the specified handler
        """
        return [task for task in self.tasks if task.handler == handler]
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the flow and all its tasks.
        
        Returns:
            Validation results with 'valid' boolean and 'errors' list
        """
        errors = []
        
        # Validate flow-level requirements
        if not self.id:
            errors.append("Flow ID is required")
        
        if not self.tasks:
            errors.append("Flow must contain at least one task")
        
        # Check for duplicate task IDs
        task_ids = [task.id for task in self.tasks]
        if len(task_ids) != len(set(task_ids)):
            errors.append("Duplicate task IDs found in flow")
        
        # Validate each task
        for i, task in enumerate(self.tasks):
            try:
                # Pydantic validation is automatic, just check if task is valid
                if not task.handler or task.retries < 0 or task.timeout <= 0:
                    errors.append(f"Task {i} (ID: {task.id}) validation failed")
            except Exception as e:
                errors.append(f"Task {i} (ID: {task.id}) validation failed: {str(e)}")
        
        # Check tenant consistency
        tenant_ids = set(task.tenant_id for task in self.tasks if task.tenant_id)
        if len(tenant_ids) > 1:
            errors.append("Tasks have inconsistent tenant IDs")
        
        if self.tenant_id and tenant_ids and self.tenant_id not in tenant_ids:
            errors.append("Flow tenant_id doesn't match task tenant_ids")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'task_count': len(self.tasks),
            'valid_tasks': len([task for task in self.tasks if task.handler and task.retries >= 0 and task.timeout > 0])
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert flow to dictionary.
        
        Returns:
            Dictionary representation of the flow
        """
        return self.dict()
    
    def save(self, path: Union[str, Path]) -> None:
        """
        Save flow to JSON file.
        
        Args:
            path: Path to save the flow JSON file
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save flow to {path}: {str(e)}")
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> 'Flow':
        """
        Load flow from JSON file.
        
        Args:
            path: Path to the flow JSON file
            
        Returns:
            Flow instance loaded from file
            
        Raises:
            IOError: If file cannot be read
            ValueError: If file contains invalid flow data
        """
        try:
            path = Path(path)
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(**data)
        except Exception as e:
            raise IOError(f"Failed to load flow from {path}: {str(e)}")
    
    def get_execution_order(self) -> List[Task]:
        """
        Get tasks in execution order.
        
        Currently returns tasks in the order they were added.
        In a more sophisticated implementation, this could consider
        task dependencies and create a proper execution graph.
        
        Returns:
            Tasks in execution order
        """
        return self.tasks.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get flow statistics.
        
        Returns:
            Statistics about the flow
        """
        handlers = {}
        total_retries = 0
        tasks_with_timeout = 0
        tasks_with_condition = 0
        
        for task in self.tasks:
            # Count handlers
            handlers[task.handler] = handlers.get(task.handler, 0) + 1
            
            # Count retries
            total_retries += task.retries
            
            # Count timeouts
            if task.timeout:
                tasks_with_timeout += 1
            
            # Count conditions
            if task.condition:
                tasks_with_condition += 1
        
        return {
            'total_tasks': len(self.tasks),
            'unique_handlers': len(handlers),
            'handler_distribution': handlers,
            'total_retries': total_retries,
            'tasks_with_timeout': tasks_with_timeout,
            'tasks_with_condition': tasks_with_condition,
            'tenant_id': self.tenant_id,
            'flow_type': self.type,
            'version': self.version
        }
    
    def __len__(self) -> int:
        """Return the number of tasks in the flow."""
        return len(self.tasks)
    
    def __iter__(self):
        """Allow iteration over tasks."""
        return iter(self.tasks)
    
    def __getitem__(self, index: Union[int, str]) -> Task:
        """
        Get task by index or ID.
        
        Args:
            index: Task index (int) or task ID (str)
            
        Returns:
            Task at the specified index or with the specified ID
            
        Raises:
            IndexError: If index is out of range
            KeyError: If task ID is not found
        """
        if isinstance(index, int):
            return self.tasks[index]
        elif isinstance(index, str):
            task = self.get_task(index)
            if task is None:
                raise KeyError(f"Task with ID '{index}' not found")
            return task
        else:
            raise TypeError("Index must be int or str")
