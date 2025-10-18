"""
Flow class for Enterprise AI Agent Framework.

Represents a complete workflow consisting of multiple tasks with support for
validation, serialization, and multi-tenancy.
"""

import json
import uuid
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from .task import Task


class Flow:
    """
    A complete workflow consisting of multiple tasks.
    
    Flows represent end-to-end processes that orchestrate multiple tasks
    in a specific order or dependency graph.
    
    Attributes:
        id (str): Unique identifier for the flow
        tasks (List[Task]): List of tasks in this flow
        tenant_id (Optional[str]): Tenant identifier for multi-tenancy
        created_at (datetime): Flow creation timestamp
        updated_at (datetime): Last update timestamp
        metadata (Dict[str, Any]): Additional metadata for the flow
    """
    
    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        tenant_id: Optional[str] = None,
        flow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a new Flow.
        
        Args:
            tasks (Optional[List[Task]]): List of tasks in this flow
            tenant_id (Optional[str]): Tenant identifier for multi-tenancy
            flow_id (Optional[str]): Custom flow ID (generated if not provided)
            metadata (Optional[Dict[str, Any]]): Additional metadata for the flow
        """
        self.id = flow_id or str(uuid.uuid4())
        self.tasks = tasks or []
        self.tenant_id = tenant_id
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.metadata = metadata or {}
    
    def add_task(self, task: Task) -> None:
        """
        Add a task to the flow.
        
        Args:
            task (Task): Task to add to the flow
            
        Raises:
            ValueError: If task is not a valid Task instance
        """
        if not isinstance(task, Task):
            raise ValueError("Task must be an instance of Task class")
        
        # Ensure tenant consistency
        if self.tenant_id and task.tenant_id and self.tenant_id != task.tenant_id:
            raise ValueError("Task tenant_id must match flow tenant_id")
        
        # Set tenant_id if not already set
        if self.tenant_id and not task.tenant_id:
            task.tenant_id = self.tenant_id
        
        self.tasks.append(task)
        self.updated_at = datetime.utcnow()
    
    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the flow by ID.
        
        Args:
            task_id (str): ID of the task to remove
            
        Returns:
            bool: True if task was removed, False if not found
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                self.updated_at = datetime.utcnow()
                return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by its ID.
        
        Args:
            task_id (str): ID of the task to retrieve
            
        Returns:
            Optional[Task]: Task if found, None otherwise
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_tasks_by_handler(self, handler: str) -> List[Task]:
        """
        Get all tasks that use a specific handler.
        
        Args:
            handler (str): Handler name to filter by
            
        Returns:
            List[Task]: List of tasks using the specified handler
        """
        return [task for task in self.tasks if task.handler == handler]
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the flow to a dictionary representation.
        
        Returns:
            Dict[str, Any]: Dictionary representation of the flow
        """
        return {
            'id': self.id,
            'tasks': [task.serialize() for task in self.tasks],
            'tenant_id': self.tenant_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
            'task_count': len(self.tasks)
        }
    
    def save(self, file_path: str) -> None:
        """
        Save the flow to a JSON file.
        
        Args:
            file_path (str): Path to save the flow JSON file
            
        Raises:
            IOError: If file cannot be written
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise IOError(f"Failed to save flow to {file_path}: {str(e)}")
    
    @classmethod
    def load(cls, file_path: str) -> 'Flow':
        """
        Load a flow from a JSON file.
        
        Args:
            file_path (str): Path to the flow JSON file
            
        Returns:
            Flow: Loaded flow instance
            
        Raises:
            IOError: If file cannot be read
            ValueError: If file contains invalid flow data
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            raise IOError(f"Failed to load flow from {file_path}: {str(e)}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Flow':
        """
        Create a flow from a dictionary.
        
        Args:
            data (Dict[str, Any]): Dictionary representation of the flow
            
        Returns:
            Flow: Flow instance created from dictionary
        """
        # Parse timestamps
        created_at = datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat()))
        updated_at = datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat()))
        
        # Deserialize tasks
        tasks = [Task.deserialize(task_data) for task_data in data.get('tasks', [])]
        
        # Create flow instance
        flow = cls(
            tasks=tasks,
            tenant_id=data.get('tenant_id'),
            flow_id=data.get('id'),
            metadata=data.get('metadata', {})
        )
        
        # Restore timestamps
        flow.created_at = created_at
        flow.updated_at = updated_at
        
        return flow
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate the flow and all its tasks.
        
        Returns:
            Dict[str, Any]: Validation results with 'valid' boolean and 'errors' list
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
            if not task.validate():
                errors.append(f"Task {i} (ID: {task.id}) is invalid")
        
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
            'valid_tasks': sum(1 for task in self.tasks if task.validate())
        }
    
    def get_execution_order(self) -> List[Task]:
        """
        Get tasks in execution order.
        
        Currently returns tasks in the order they were added.
        In a more sophisticated implementation, this could consider
        task dependencies and create a proper execution graph.
        
        Returns:
            List[Task]: Tasks in execution order
        """
        return self.tasks.copy()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get flow statistics.
        
        Returns:
            Dict[str, Any]: Statistics about the flow
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
            'tenant_id': self.tenant_id
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
            Task: Task at the specified index or with the specified ID
            
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
    
    def __repr__(self) -> str:
        """String representation of the flow."""
        return (
            f"Flow(id='{self.id}', tasks={len(self.tasks)}, "
            f"tenant_id='{self.tenant_id}')"
        )
