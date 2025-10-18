"""
Unit tests for Enterprise AI Agent Framework SDK models.

This module contains comprehensive tests for the Task and Flow models
using Pydantic validation.
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from sdk.models import Task, Flow


class TestTask:
    """Test cases for the Task model."""
    
    def test_task_creation_with_defaults(self):
        """Test task creation with default values."""
        task = Task(handler="test_handler")
        
        assert task.handler == "test_handler"
        assert task.inputs == {}
        assert task.retries == 3
        assert task.timeout == 300
        assert task.condition is None
        assert task.metadata == {}
        assert isinstance(task.id, str)
        assert len(task.id) > 0
    
    def test_task_creation_with_custom_values(self):
        """Test task creation with custom values."""
        task = Task(
            handler="custom_handler",
            inputs={"param1": "value1", "param2": 42},
            retries=5,
            timeout=600,
            condition="some_condition",
            metadata={"env": "test"}
        )
        
        assert task.handler == "custom_handler"
        assert task.inputs == {"param1": "value1", "param2": 42}
        assert task.retries == 5
        assert task.timeout == 600
        assert task.condition == "some_condition"
        assert task.metadata == {"env": "test"}
    
    def test_task_validation_empty_handler(self):
        """Test task validation with empty handler."""
        with pytest.raises(ValueError, match="Handler cannot be empty"):
            Task(handler="")
    
    def test_task_validation_whitespace_handler(self):
        """Test task validation with whitespace-only handler."""
        with pytest.raises(ValueError, match="Handler cannot be empty"):
            Task(handler="   ")
    
    def test_task_validation_negative_retries(self):
        """Test task validation with negative retries."""
        with pytest.raises(ValueError, match="Retries must be non-negative"):
            Task(handler="test", retries=-1)
    
    def test_task_validation_zero_timeout(self):
        """Test task validation with zero timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            Task(handler="test", timeout=0)
    
    def test_task_validation_negative_timeout(self):
        """Test task validation with negative timeout."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            Task(handler="test", timeout=-100)
    
    def test_task_should_execute_no_condition(self):
        """Test task execution when no condition is set."""
        task = Task(handler="test")
        assert task.should_execute() is True
        assert task.should_execute({"some": "context"}) is True
    
    def test_task_should_execute_with_condition(self):
        """Test task execution with condition."""
        task = Task(handler="test", condition="some_condition")
        assert task.should_execute() is True
        
        task_empty_condition = Task(handler="test", condition="")
        assert task_empty_condition.should_execute() is False
        
        task_whitespace_condition = Task(handler="test", condition="   ")
        assert task_whitespace_condition.should_execute() is False
    
    def test_task_to_dict(self):
        """Test task serialization to dictionary."""
        task = Task(
            handler="test_handler",
            inputs={"param": "value"},
            retries=2,
            timeout=120,
            condition="test_condition",
            metadata={"env": "test"}
        )
        
        task_dict = task.to_dict()
        
        assert task_dict["handler"] == "test_handler"
        assert task_dict["inputs"] == {"param": "value"}
        assert task_dict["retries"] == 2
        assert task_dict["timeout"] == 120
        assert task_dict["condition"] == "test_condition"
        assert task_dict["metadata"] == {"env": "test"}
        assert "id" in task_dict
    
    def test_task_save_and_load(self):
        """Test task save and load functionality."""
        task = Task(
            handler="test_handler",
            inputs={"param": "value"},
            retries=2,
            timeout=120,
            condition="test_condition",
            metadata={"env": "test"}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save task
            task.save(temp_path)
            
            # Load task
            loaded_task = Task.load(temp_path)
            
            assert loaded_task.handler == task.handler
            assert loaded_task.inputs == task.inputs
            assert loaded_task.retries == task.retries
            assert loaded_task.timeout == task.timeout
            assert loaded_task.condition == task.condition
            assert loaded_task.metadata == task.metadata
            assert loaded_task.id == task.id
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_task_save_nonexistent_directory(self):
        """Test task save to nonexistent directory."""
        task = Task(handler="test")
        
        with pytest.raises(IOError):
            task.save("/nonexistent/path/task.json")
    
    def test_task_load_nonexistent_file(self):
        """Test task load from nonexistent file."""
        with pytest.raises(IOError):
            Task.load("/nonexistent/path/task.json")
    
    def test_task_load_invalid_json(self):
        """Test task load from invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            temp_path = f.name
        
        try:
            with pytest.raises(IOError):
                Task.load(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class TestFlow:
    """Test cases for the Flow model."""
    
    def test_flow_creation_with_defaults(self):
        """Test flow creation with default values."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        
        flow = Flow(tasks=[task1, task2])
        
        assert len(flow.tasks) == 2
        assert flow.version == "1.0.0"
        assert flow.type == "DAG"
        assert flow.tenant_id is None
        assert flow.metadata == {}
        assert isinstance(flow.id, str)
        assert len(flow.id) > 0
    
    def test_flow_creation_with_custom_values(self):
        """Test flow creation with custom values."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        
        flow = Flow(
            tasks=[task1, task2],
            version="2.0.0",
            type="STATE_MACHINE",
            tenant_id="tenant123",
            metadata={"env": "production"}
        )
        
        assert len(flow.tasks) == 2
        assert flow.version == "2.0.0"
        assert flow.type == "STATE_MACHINE"
        assert flow.tenant_id == "tenant123"
        assert flow.metadata == {"env": "production"}
    
    def test_flow_validation_empty_tasks(self):
        """Test flow validation with empty tasks list."""
        with pytest.raises(ValueError, match="Flow must contain at least one task"):
            Flow(tasks=[])
    
    def test_flow_validation_empty_version(self):
        """Test flow validation with empty version."""
        task = Task(handler="test")
        
        with pytest.raises(ValueError, match="Version cannot be empty"):
            Flow(tasks=[task], version="")
    
    def test_flow_validation_whitespace_version(self):
        """Test flow validation with whitespace-only version."""
        task = Task(handler="test")
        
        with pytest.raises(ValueError, match="Version cannot be empty"):
            Flow(tasks=[task], version="   ")
    
    def test_flow_validation_tenant_consistency(self):
        """Test flow validation with inconsistent tenant IDs."""
        task1 = Task(handler="handler1", tenant_id="tenant1")
        task2 = Task(handler="handler2", tenant_id="tenant2")
        
        with pytest.raises(ValueError, match="Task tenant_id must match flow tenant_id"):
            Flow(tasks=[task1, task2], tenant_id="tenant1")
    
    def test_flow_add_task(self):
        """Test adding a task to a flow."""
        flow = Flow(tasks=[Task(handler="handler1")])
        new_task = Task(handler="handler2")
        
        flow.add_task(new_task)
        
        assert len(flow.tasks) == 2
        assert new_task in flow.tasks
    
    def test_flow_add_task_tenant_consistency(self):
        """Test adding a task with tenant consistency check."""
        flow = Flow(tasks=[Task(handler="handler1")], tenant_id="tenant1")
        task_with_different_tenant = Task(handler="handler2", tenant_id="tenant2")
        
        with pytest.raises(ValueError, match="Task tenant_id must match flow tenant_id"):
            flow.add_task(task_with_different_tenant)
    
    def test_flow_add_task_sets_tenant_id(self):
        """Test that adding a task sets the tenant_id if not present."""
        flow = Flow(tasks=[Task(handler="handler1")], tenant_id="tenant1")
        task_without_tenant = Task(handler="handler2")
        
        flow.add_task(task_without_tenant)
        
        assert task_without_tenant.tenant_id == "tenant1"
    
    def test_flow_remove_task(self):
        """Test removing a task from a flow."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        result = flow.remove_task(task1.id)
        
        assert result is True
        assert len(flow.tasks) == 1
        assert task1 not in flow.tasks
        assert task2 in flow.tasks
    
    def test_flow_remove_task_not_found(self):
        """Test removing a non-existent task from a flow."""
        task = Task(handler="handler1")
        flow = Flow(tasks=[task])
        
        result = flow.remove_task("nonexistent_id")
        
        assert result is False
        assert len(flow.tasks) == 1
    
    def test_flow_get_task(self):
        """Test getting a task by ID."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        retrieved_task = flow.get_task(task1.id)
        
        assert retrieved_task == task1
    
    def test_flow_get_task_not_found(self):
        """Test getting a non-existent task by ID."""
        task = Task(handler="handler1")
        flow = Flow(tasks=[task])
        
        retrieved_task = flow.get_task("nonexistent_id")
        
        assert retrieved_task is None
    
    def test_flow_get_tasks_by_handler(self):
        """Test getting tasks by handler name."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        task3 = Task(handler="handler1")
        flow = Flow(tasks=[task1, task2, task3])
        
        handler1_tasks = flow.get_tasks_by_handler("handler1")
        
        assert len(handler1_tasks) == 2
        assert task1 in handler1_tasks
        assert task3 in handler1_tasks
        assert task2 not in handler1_tasks
    
    def test_flow_validate_success(self):
        """Test flow validation with valid flow."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        result = flow.validate()
        
        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["task_count"] == 2
        assert result["valid_tasks"] == 2
    
    def test_flow_validate_duplicate_task_ids(self):
        """Test flow validation with duplicate task IDs."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        task2.id = task1.id  # Force duplicate ID
        
        flow = Flow(tasks=[task1, task2])
        result = flow.validate()
        
        assert result["valid"] is False
        assert "Duplicate task IDs found in flow" in result["errors"]
    
    def test_flow_validate_inconsistent_tenant_ids(self):
        """Test flow validation with inconsistent tenant IDs."""
        task1 = Task(handler="handler1", tenant_id="tenant1")
        task2 = Task(handler="handler2", tenant_id="tenant2")
        flow = Flow(tasks=[task1, task2])
        
        result = flow.validate()
        
        assert result["valid"] is False
        assert "Tasks have inconsistent tenant IDs" in result["errors"]
    
    def test_flow_to_dict(self):
        """Test flow serialization to dictionary."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(
            tasks=[task1, task2],
            version="2.0.0",
            type="STATE_MACHINE",
            tenant_id="tenant123",
            metadata={"env": "test"}
        )
        
        flow_dict = flow.to_dict()
        
        assert flow_dict["version"] == "2.0.0"
        assert flow_dict["type"] == "STATE_MACHINE"
        assert flow_dict["tenant_id"] == "tenant123"
        assert flow_dict["metadata"] == {"env": "test"}
        assert len(flow_dict["tasks"]) == 2
        assert "id" in flow_dict
    
    def test_flow_save_and_load(self):
        """Test flow save and load functionality."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(
            tasks=[task1, task2],
            version="2.0.0",
            type="STATE_MACHINE",
            tenant_id="tenant123",
            metadata={"env": "test"}
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            # Save flow
            flow.save(temp_path)
            
            # Load flow
            loaded_flow = Flow.load(temp_path)
            
            assert loaded_flow.version == flow.version
            assert loaded_flow.type == flow.type
            assert loaded_flow.tenant_id == flow.tenant_id
            assert loaded_flow.metadata == flow.metadata
            assert len(loaded_flow.tasks) == len(flow.tasks)
            assert loaded_flow.id == flow.id
            
        finally:
            Path(temp_path).unlink(missing_ok=True)
    
    def test_flow_get_execution_order(self):
        """Test getting tasks in execution order."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        execution_order = flow.get_execution_order()
        
        assert execution_order == [task1, task2]
    
    def test_flow_get_statistics(self):
        """Test getting flow statistics."""
        task1 = Task(handler="handler1", retries=2, timeout=120)
        task2 = Task(handler="handler2", retries=3, timeout=180, condition="some_condition")
        task3 = Task(handler="handler1", retries=1, timeout=60)
        
        flow = Flow(
            tasks=[task1, task2, task3],
            tenant_id="tenant123",
            type="STATE_MACHINE",
            version="1.0.0"
        )
        
        stats = flow.get_statistics()
        
        assert stats["total_tasks"] == 3
        assert stats["unique_handlers"] == 2
        assert stats["handler_distribution"]["handler1"] == 2
        assert stats["handler_distribution"]["handler2"] == 1
        assert stats["total_retries"] == 6
        assert stats["tasks_with_timeout"] == 3
        assert stats["tasks_with_condition"] == 1
        assert stats["tenant_id"] == "tenant123"
        assert stats["flow_type"] == "STATE_MACHINE"
        assert stats["version"] == "1.0.0"
    
    def test_flow_length(self):
        """Test flow length."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        assert len(flow) == 2
    
    def test_flow_iteration(self):
        """Test flow iteration."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        tasks = list(flow)
        assert tasks == [task1, task2]
    
    def test_flow_getitem_by_index(self):
        """Test flow getitem by index."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        assert flow[0] == task1
        assert flow[1] == task2
    
    def test_flow_getitem_by_id(self):
        """Test flow getitem by task ID."""
        task1 = Task(handler="handler1")
        task2 = Task(handler="handler2")
        flow = Flow(tasks=[task1, task2])
        
        assert flow[task1.id] == task1
        assert flow[task2.id] == task2
    
    def test_flow_getitem_invalid_index(self):
        """Test flow getitem with invalid index."""
        task = Task(handler="handler1")
        flow = Flow(tasks=[task])
        
        with pytest.raises(IndexError):
            flow[10]
    
    def test_flow_getitem_nonexistent_id(self):
        """Test flow getitem with nonexistent task ID."""
        task = Task(handler="handler1")
        flow = Flow(tasks=[task])
        
        with pytest.raises(KeyError):
            flow["nonexistent_id"]
    
    def test_flow_getitem_invalid_type(self):
        """Test flow getitem with invalid index type."""
        task = Task(handler="handler1")
        flow = Flow(tasks=[task])
        
        with pytest.raises(TypeError):
            flow[1.5]
