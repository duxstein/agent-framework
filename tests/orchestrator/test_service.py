"""
Tests for the Orchestrator Service.

This module contains comprehensive tests for the orchestrator service,
including unit tests, integration tests, and performance tests.
"""

import pytest
import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from orchestrator.service import (
    OrchestratorService,
    RunState,
    TaskState,
    TaskStatus,
    RunStatus,
    FLOW_RUNS_PROCESSED,
    TASKS_SCHEDULED,
    TASKS_COMPLETED,
    TASK_EXECUTION_TIME,
    RUN_EXECUTION_TIME,
    ACTIVE_RUNS,
    ACTIVE_TASKS,
    RETRY_ATTEMPTS,
    DEAD_LETTER_QUEUE_SIZE
)
from sdk.models import Flow, Task
from sdk.registry import FlowRegistry


class TestRunState:
    """Test cases for RunState class."""
    
    def test_run_state_creation(self):
        """Test RunState creation."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        assert run_state.run_id == run_id
        assert run_state.flow_id == "test-flow"
        assert run_state.tenant_id == "tenant-1"
        assert run_state.user_id == "user-1"
        assert run_state.correlation_id == "corr-1"
        assert run_state.status == RunStatus.PENDING
        assert len(run_state.tasks) == 0
        assert len(run_state.completed_tasks) == 0
        assert len(run_state.failed_tasks) == 0
        assert len(run_state.ready_tasks) == 0
    
    def test_run_state_to_dict(self):
        """Test RunState serialization to dictionary."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        data = run_state.to_dict()
        
        assert data["run_id"] == run_id
        assert data["flow_id"] == "test-flow"
        assert data["tenant_id"] == "tenant-1"
        assert data["user_id"] == "user-1"
        assert data["correlation_id"] == "corr-1"
        assert data["status"] == "PENDING"
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_run_state_from_dict(self):
        """Test RunState deserialization from dictionary."""
        run_id = str(uuid.uuid4())
        data = {
            "run_id": run_id,
            "flow_id": "test-flow",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "correlation_id": "corr-1",
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tasks": {},
            "completed_tasks": [],
            "failed_tasks": [],
            "ready_tasks": [],
            "input_data": {},
            "output_data": {},
            "execution_context": {},
            "task_attempts": {},
            "max_retries": 3
        }
        
        run_state = RunState.from_dict(data)
        
        assert run_state.run_id == run_id
        assert run_state.flow_id == "test-flow"
        assert run_state.tenant_id == "tenant-1"
        assert run_state.user_id == "user-1"
        assert run_state.correlation_id == "corr-1"
        assert run_state.status == RunStatus.RUNNING


class TestTaskState:
    """Test cases for TaskState class."""
    
    def test_task_state_creation(self):
        """Test TaskState creation."""
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"},
            max_retries=3,
            timeout=300
        )
        
        assert task_state.task_id == "task-1"
        assert task_state.handler == "test_handler"
        assert task_state.inputs == {"param1": "value1"}
        assert task_state.status == TaskStatus.PENDING
        assert task_state.max_retries == 3
        assert task_state.timeout == 300
        assert task_state.attempts == 0
    
    def test_task_state_to_dict(self):
        """Test TaskState serialization to dictionary."""
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"}
        )
        
        data = task_state.to_dict()
        
        assert data["task_id"] == "task-1"
        assert data["handler"] == "test_handler"
        assert data["inputs"] == {"param1": "value1"}
        assert data["status"] == "PENDING"
        assert data["attempts"] == 0
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_task_state_from_dict(self):
        """Test TaskState deserialization from dictionary."""
        data = {
            "task_id": "task-1",
            "handler": "test_handler",
            "inputs": {"param1": "value1"},
            "status": "COMPLETED",
            "attempts": 1,
            "max_retries": 3,
            "timeout": 300,
            "condition": None,
            "output": {"result": "success"},
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        task_state = TaskState.from_dict(data)
        
        assert task_state.task_id == "task-1"
        assert task_state.handler == "test_handler"
        assert task_state.inputs == {"param1": "value1"}
        assert task_state.status == TaskStatus.COMPLETED
        assert task_state.attempts == 1
        assert task_state.output == {"result": "success"}


class TestOrchestratorService:
    """Test cases for OrchestratorService class."""
    
    @pytest.fixture
    def orchestrator_config(self):
        """Configuration for orchestrator service."""
        return {
            "kafka_bootstrap_servers": ["localhost:9092"],
            "redis_url": "redis://localhost:6379",
            "database_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "flow_registry_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "metrics_port": 9090
        }
    
    @pytest.fixture
    def mock_orchestrator(self, orchestrator_config):
        """Create a mock orchestrator service."""
        with patch('orchestrator.service.KafkaConsumer'), \
             patch('orchestrator.service.KafkaProducer'), \
             patch('orchestrator.service.redis.from_url'), \
             patch('orchestrator.service.FlowRegistry'), \
             patch('orchestrator.service.start_http_server'):
            
            orchestrator = OrchestratorService(**orchestrator_config)
            return orchestrator
    
    @pytest.fixture
    def sample_flow(self):
        """Sample flow for testing."""
        return Flow(
            id="test-flow",
            name="Test Flow",
            description="A test flow",
            version="1.0.0",
            tenant_id="tenant-1",
            user_id="user-1",
            type="DAG",
            tasks=[
                Task(
                    id="task-1",
                    name="Task 1",
                    handler="test_handler_1",
                    inputs={"param1": "value1"},
                    retries=3,
                    timeout=300
                ),
                Task(
                    id="task-2",
                    name="Task 2",
                    handler="test_handler_2",
                    inputs={"param2": "value2"},
                    retries=2,
                    timeout=600,
                    condition="completed_tasks.contains('task-1')"
                )
            ]
        )
    
    @pytest.fixture
    def sample_flow_run_event(self):
        """Sample flow run event for testing."""
        return {
            "run_id": str(uuid.uuid4()),
            "flow_id": "test-flow",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "correlation_id": str(uuid.uuid4()),
            "input": {"message": "Hello World"},
            "execution_context": {"source": "test"}
        }
    
    def test_orchestrator_initialization(self, orchestrator_config):
        """Test orchestrator service initialization."""
        with patch('orchestrator.service.KafkaConsumer'), \
             patch('orchestrator.service.KafkaProducer'), \
             patch('orchestrator.service.redis.from_url'), \
             patch('orchestrator.service.FlowRegistry'), \
             patch('orchestrator.service.start_http_server'):
            
            orchestrator = OrchestratorService(**orchestrator_config)
            
            assert orchestrator.kafka_bootstrap_servers == ["localhost:9092"]
            assert orchestrator.redis_url == "redis://localhost:6379"
            assert orchestrator.database_url == "postgresql://postgres:postgres@localhost:5432/agent_framework"
            assert orchestrator.metrics_port == 9090
            assert len(orchestrator.active_runs) == 0
            assert len(orchestrator.dead_letter_queue) == 0
    
    @pytest.mark.asyncio
    async def test_process_flow_run_event(self, mock_orchestrator, sample_flow, sample_flow_run_event):
        """Test processing a flow run event."""
        # Mock flow registry
        mock_orchestrator.flow_registry.get_flow.return_value = sample_flow
        
        # Mock Redis client
        mock_orchestrator.redis_client.setex = Mock()
        
        # Mock PostgreSQL operations
        with patch('orchestrator.service.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Process the event
            await mock_orchestrator._process_flow_run_event(sample_flow_run_event)
            
            # Verify flow registry was called
            mock_orchestrator.flow_registry.get_flow.assert_called_once_with("test-flow")
            
            # Verify Redis state was persisted
            mock_orchestrator.redis_client.setex.assert_called_once()
            
            # Verify PostgreSQL operations
            assert mock_cursor.execute.call_count >= 2  # Flow run + task executions
    
    @pytest.mark.asyncio
    async def test_initialize_task_states(self, mock_orchestrator, sample_flow):
        """Test initializing task states."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        await mock_orchestrator._initialize_task_states(run_state, sample_flow)
        
        assert len(run_state.tasks) == 2
        assert "task-1" in run_state.tasks
        assert "task-2" in run_state.tasks
        
        task1 = run_state.tasks["task-1"]
        assert task1.handler == "test_handler_1"
        assert task1.inputs == {"param1": "value1"}
        assert task1.max_retries == 3
        assert task1.timeout == 300
        
        task2 = run_state.tasks["task-2"]
        assert task2.handler == "test_handler_2"
        assert task2.inputs == {"param2": "value2"}
        assert task2.max_retries == 2
        assert task2.timeout == 600
    
    @pytest.mark.asyncio
    async def test_compute_ready_tasks(self, mock_orchestrator, sample_flow):
        """Test computing ready tasks."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Initialize task states
        await mock_orchestrator._initialize_task_states(run_state, sample_flow)
        
        # Compute ready tasks
        await mock_orchestrator._compute_ready_tasks(run_state, sample_flow)
        
        # For DAG flows, task-1 should be ready (no dependencies)
        # task-2 should not be ready (depends on task-1)
        assert "task-1" in run_state.ready_tasks
        assert "task-2" not in run_state.ready_tasks
        
        # Mark task-1 as completed
        run_state.completed_tasks.add("task-1")
        
        # Recompute ready tasks
        await mock_orchestrator._compute_ready_tasks(run_state, sample_flow)
        
        # Now task-2 should be ready
        assert "task-2" in run_state.ready_tasks
    
    def test_evaluate_condition(self, mock_orchestrator):
        """Test condition evaluation."""
        run_state = RunState(
            run_id=str(uuid.uuid4()),
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Test truthy condition
        assert mock_orchestrator._evaluate_condition("true", run_state) == True
        
        # Test falsy condition
        assert mock_orchestrator._evaluate_condition("", run_state) == False
        
        # Test condition with completed tasks
        run_state.completed_tasks.add("task-1")
        assert mock_orchestrator._evaluate_condition("completed_tasks", run_state) == True
    
    @pytest.mark.asyncio
    async def test_schedule_ready_tasks(self, mock_orchestrator):
        """Test scheduling ready tasks."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add a task to ready tasks
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"}
        )
        run_state.tasks["task-1"] = task_state
        run_state.ready_tasks.add("task-1")
        
        # Mock Kafka producer
        mock_orchestrator.task_queue_producer.send = Mock()
        
        # Schedule ready tasks
        await mock_orchestrator._schedule_ready_tasks(run_state)
        
        # Verify task was scheduled
        mock_orchestrator.task_queue_producer.send.assert_called_once()
        
        # Verify task status was updated
        assert task_state.status == TaskStatus.RUNNING
    
    @pytest.mark.asyncio
    async def test_process_task_done_event(self, mock_orchestrator):
        """Test processing task done event."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add a running task
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"},
            status=TaskStatus.RUNNING
        )
        run_state.tasks["task-1"] = task_state
        run_state.ready_tasks.add("task-1")
        
        # Add to active runs
        mock_orchestrator.active_runs[run_id] = run_state
        
        # Mock Redis and PostgreSQL operations
        mock_orchestrator.redis_client.setex = Mock()
        with patch('orchestrator.service.psycopg2.connect'):
            # Process task done event
            event = {
                "run_id": run_id,
                "task_id": "task-1",
                "output": {"result": "success"},
                "execution_time_ms": 1000
            }
            
            await mock_orchestrator._process_task_done_event(event)
            
            # Verify task was marked as completed
            assert task_state.status == TaskStatus.COMPLETED
            assert task_state.output == {"result": "success"}
            assert "task-1" in run_state.completed_tasks
            assert "task-1" not in run_state.ready_tasks
    
    @pytest.mark.asyncio
    async def test_process_task_failed_event_with_retry(self, mock_orchestrator):
        """Test processing task failed event with retry."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add a running task
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"},
            status=TaskStatus.RUNNING,
            max_retries=3
        )
        run_state.tasks["task-1"] = task_state
        run_state.ready_tasks.add("task-1")
        run_state.task_attempts["task-1"] = 0
        
        # Add to active runs
        mock_orchestrator.active_runs[run_id] = run_state
        
        # Mock operations
        mock_orchestrator.redis_client.setex = Mock()
        mock_orchestrator.task_queue_producer.send = Mock()
        
        with patch('orchestrator.service.psycopg2.connect'), \
             patch('asyncio.create_task') as mock_create_task:
            
            # Process task failed event
            event = {
                "run_id": run_id,
                "task_id": "task-1",
                "error": "Test error",
                "execution_time_ms": 500
            }
            
            await mock_orchestrator._process_task_failed_event(event)
            
            # Verify retry was scheduled
            assert run_state.task_attempts["task-1"] == 1
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_task_failed_event_dead_letter(self, mock_orchestrator):
        """Test processing task failed event with move to dead letter queue."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add a task that has exceeded max retries
        task_state = TaskState(
            task_id="task-1",
            handler="test_handler",
            inputs={"param1": "value1"},
            status=TaskStatus.RUNNING,
            max_retries=1
        )
        run_state.tasks["task-1"] = task_state
        run_state.ready_tasks.add("task-1")
        run_state.task_attempts["task-1"] = 1  # Already at max retries
        
        # Add to active runs
        mock_orchestrator.active_runs[run_id] = run_state
        
        # Mock operations
        mock_orchestrator.redis_client.setex = Mock()
        mock_orchestrator.dead_letter_producer.send = Mock()
        
        with patch('orchestrator.service.psycopg2.connect'):
            # Process task failed event
            event = {
                "run_id": run_id,
                "task_id": "task-1",
                "error": "Test error",
                "execution_time_ms": 500
            }
            
            await mock_orchestrator._process_task_failed_event(event)
            
            # Verify task was moved to dead letter queue
            assert task_state.status == TaskStatus.DEAD_LETTER
            assert "task-1" in run_state.failed_tasks
            mock_orchestrator.dead_letter_producer.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_run_completion_success(self, mock_orchestrator):
        """Test checking run completion for successful run."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add two tasks
        task1 = TaskState(task_id="task-1", handler="handler1", inputs={})
        task2 = TaskState(task_id="task-2", handler="handler2", inputs={})
        run_state.tasks["task-1"] = task1
        run_state.tasks["task-2"] = task2
        
        # Mark both tasks as completed
        run_state.completed_tasks.add("task-1")
        run_state.completed_tasks.add("task-2")
        
        # Add to active runs
        mock_orchestrator.active_runs[run_id] = run_state
        
        # Check completion
        await mock_orchestrator._check_run_completion(run_state)
        
        # Verify run was marked as completed
        assert run_state.status == RunStatus.COMPLETED
        assert run_id not in mock_orchestrator.active_runs
    
    @pytest.mark.asyncio
    async def test_check_run_completion_failure(self, mock_orchestrator):
        """Test checking run completion for failed run."""
        run_id = str(uuid.uuid4())
        run_state = RunState(
            run_id=run_id,
            flow_id="test-flow",
            tenant_id="tenant-1",
            user_id="user-1",
            correlation_id="corr-1"
        )
        
        # Add two tasks
        task1 = TaskState(task_id="task-1", handler="handler1", inputs={})
        task2 = TaskState(task_id="task-2", handler="handler2", inputs={})
        run_state.tasks["task-1"] = task1
        run_state.tasks["task-2"] = task2
        
        # Mark one as completed, one as failed
        run_state.completed_tasks.add("task-1")
        run_state.failed_tasks.add("task-2")
        
        # Add to active runs
        mock_orchestrator.active_runs[run_id] = run_state
        
        # Check completion
        await mock_orchestrator._check_run_completion(run_state)
        
        # Verify run was marked as failed
        assert run_state.status == RunStatus.FAILED
        assert run_id not in mock_orchestrator.active_runs


class TestOrchestratorIntegration:
    """Integration tests for the orchestrator service."""
    
    @pytest.fixture
    def orchestrator_config(self):
        """Configuration for orchestrator service."""
        return {
            "kafka_bootstrap_servers": ["localhost:9092"],
            "redis_url": "redis://localhost:6379",
            "database_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "flow_registry_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "metrics_port": 9090
        }
    
    @pytest.mark.asyncio
    async def test_full_workflow_execution(self, orchestrator_config):
        """Test a complete workflow execution from start to finish."""
        with patch('orchestrator.service.KafkaConsumer') as mock_consumer_class, \
             patch('orchestrator.service.KafkaProducer') as mock_producer_class, \
             patch('orchestrator.service.redis.from_url') as mock_redis_class, \
             patch('orchestrator.service.FlowRegistry') as mock_registry_class, \
             patch('orchestrator.service.start_http_server'):
            
            # Setup mocks
            mock_redis = Mock()
            mock_redis_class.return_value = mock_redis
            
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry
            
            # Create sample flow
            sample_flow = Flow(
                id="integration-test-flow",
                name="Integration Test Flow",
                description="A flow for integration testing",
                version="1.0.0",
                tenant_id="tenant-1",
                user_id="user-1",
                type="DAG",
                tasks=[
                    Task(
                        id="task-1",
                        name="Task 1",
                        handler="test_handler_1",
                        inputs={"param1": "value1"},
                        retries=2,
                        timeout=300
                    ),
                    Task(
                        id="task-2",
                        name="Task 2",
                        handler="test_handler_2",
                        inputs={"param2": "value2"},
                        retries=1,
                        timeout=600
                    )
                ]
            )
            
            mock_registry.get_flow.return_value = sample_flow
            
            # Create orchestrator
            orchestrator = OrchestratorService(**orchestrator_config)
            
            # Mock PostgreSQL operations
            with patch('orchestrator.service.psycopg2.connect') as mock_connect:
                mock_conn = Mock()
                mock_cursor = Mock()
                mock_connect.return_value = mock_conn
                mock_conn.cursor.return_value = mock_cursor
                
                # Test flow run event processing
                run_id = str(uuid.uuid4())
                flow_run_event = {
                    "run_id": run_id,
                    "flow_id": "integration-test-flow",
                    "tenant_id": "tenant-1",
                    "user_id": "user-1",
                    "correlation_id": str(uuid.uuid4()),
                    "input": {"message": "Integration test"},
                    "execution_context": {"source": "integration_test"}
                }
                
                await orchestrator._process_flow_run_event(flow_run_event)
                
                # Verify flow was loaded
                mock_registry.get_flow.assert_called_once_with("integration-test-flow")
                
                # Verify Redis state was persisted
                mock_redis.setex.assert_called_once()
                
                # Verify PostgreSQL operations
                assert mock_cursor.execute.call_count >= 2
                
                # Verify run state was created
                assert run_id in orchestrator.active_runs
                run_state = orchestrator.active_runs[run_id]
                assert run_state.status == RunStatus.RUNNING
                assert len(run_state.tasks) == 2
                
                # Test task completion
                task_done_event = {
                    "run_id": run_id,
                    "task_id": "task-1",
                    "output": {"result": "success"},
                    "execution_time_ms": 1500
                }
                
                await orchestrator._process_task_done_event(task_done_event)
                
                # Verify task was completed
                assert "task-1" in run_state.completed_tasks
                assert run_state.tasks["task-1"].status == TaskStatus.COMPLETED
                
                # Test second task completion
                task_done_event_2 = {
                    "run_id": run_id,
                    "task_id": "task-2",
                    "output": {"result": "success"},
                    "execution_time_ms": 2000
                }
                
                await orchestrator._process_task_done_event(task_done_event_2)
                
                # Verify run completion
                assert run_state.status == RunStatus.COMPLETED
                assert run_id not in orchestrator.active_runs


class TestOrchestratorPerformance:
    """Performance tests for the orchestrator service."""
    
    @pytest.mark.asyncio
    async def test_concurrent_flow_processing(self, orchestrator_config):
        """Test processing multiple flows concurrently."""
        with patch('orchestrator.service.KafkaConsumer'), \
             patch('orchestrator.service.KafkaProducer'), \
             patch('orchestrator.service.redis.from_url'), \
             patch('orchestrator.service.FlowRegistry'), \
             patch('orchestrator.service.start_http_server'):
            
            orchestrator = OrchestratorService(**orchestrator_config)
            
            # Create sample flow
            sample_flow = Flow(
                id="perf-test-flow",
                name="Performance Test Flow",
                description="A flow for performance testing",
                version="1.0.0",
                tenant_id="tenant-1",
                user_id="user-1",
                type="DAG",
                tasks=[
                    Task(
                        id="task-1",
                        name="Task 1",
                        handler="test_handler",
                        inputs={"param1": "value1"},
                        retries=1,
                        timeout=300
                    )
                ]
            )
            
            orchestrator.flow_registry.get_flow.return_value = sample_flow
            
            # Mock operations
            orchestrator.redis_client.setex = Mock()
            
            with patch('orchestrator.service.psycopg2.connect') as mock_connect:
                mock_conn = Mock()
                mock_cursor = Mock()
                mock_connect.return_value = mock_conn
                mock_conn.cursor.return_value = mock_cursor
                
                # Process multiple flows concurrently
                num_flows = 10
                tasks = []
                
                for i in range(num_flows):
                    flow_run_event = {
                        "run_id": str(uuid.uuid4()),
                        "flow_id": "perf-test-flow",
                        "tenant_id": f"tenant-{i}",
                        "user_id": f"user-{i}",
                        "correlation_id": str(uuid.uuid4()),
                        "input": {"message": f"Performance test {i}"},
                        "execution_context": {"source": "performance_test"}
                    }
                    
                    task = orchestrator._process_flow_run_event(flow_run_event)
                    tasks.append(task)
                
                # Wait for all flows to be processed
                await asyncio.gather(*tasks)
                
                # Verify all flows were processed
                assert len(orchestrator.active_runs) == num_flows
                
                # Verify Redis operations
                assert orchestrator.redis_client.setex.call_count == num_flows


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
