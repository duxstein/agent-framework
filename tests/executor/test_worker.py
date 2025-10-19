"""
Tests for the Executor Worker.

This module contains comprehensive tests for the executor worker,
including unit tests, integration tests, and performance tests.
"""

import pytest
import asyncio
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from executor.worker import (
    ExecutorWorker,
    TaskExecutionResult,
    TaskStatus,
    ExecutionMode,
    TASK_DURATION_SECONDS,
    TASK_SUCCESS_COUNT,
    TASK_FAILURE_COUNT,
    TASK_RETRY_COUNT,
    TASK_DEAD_LETTER_COUNT,
    ACTIVE_TASKS,
    CONNECTOR_LOAD_TIME
)
from connectors.registry import ConnectorRegistry


class TestTaskExecutionResult:
    """Test cases for TaskExecutionResult class."""
    
    def test_task_execution_result_creation(self):
        """Test TaskExecutionResult creation."""
        result = TaskExecutionResult(
            task_id="task-1",
            run_id="run-1",
            success=True,
            output={"result": "success"},
            execution_time_ms=1500,
            execution_mode=ExecutionMode.ASYNC
        )
        
        assert result.task_id == "task-1"
        assert result.run_id == "run-1"
        assert result.success == True
        assert result.output == {"result": "success"}
        assert result.execution_time_ms == 1500
        assert result.execution_mode == ExecutionMode.ASYNC
        assert result.error is None
    
    def test_task_execution_result_to_dict(self):
        """Test TaskExecutionResult serialization to dictionary."""
        result = TaskExecutionResult(
            task_id="task-1",
            run_id="run-1",
            success=False,
            error="Test error",
            execution_time_ms=500,
            execution_mode=ExecutionMode.SYNC
        )
        
        data = result.to_dict()
        
        assert data["task_id"] == "task-1"
        assert data["run_id"] == "run-1"
        assert data["success"] == False
        assert data["error"] == "Test error"
        assert data["execution_time_ms"] == 500
        assert data["execution_mode"] == "sync"
        assert "timestamp" in data


class TestExecutorWorker:
    """Test cases for ExecutorWorker class."""
    
    @pytest.fixture
    def executor_config(self):
        """Configuration for executor worker."""
        return {
            "kafka_bootstrap_servers": "localhost:9092",
            "redis_url": "redis://localhost:6379",
            "database_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "connector_registry_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "metrics_port": 9091,
            "max_workers": 5
        }
    
    @pytest.fixture
    def mock_executor(self, executor_config):
        """Create a mock executor worker."""
        with patch('executor.worker.KafkaConsumer'), \
             patch('executor.worker.KafkaProducer'), \
             patch('executor.worker.redis.from_url'), \
             patch('executor.worker.ConnectorRegistry'), \
             patch('executor.worker.start_http_server'), \
             patch('executor.worker.ThreadPoolExecutor'), \
             patch('executor.worker.ProcessPoolExecutor'):
            
            executor = ExecutorWorker(**executor_config)
            return executor
    
    @pytest.fixture
    def sample_task_message(self):
        """Sample task message for testing."""
        return {
            "run_id": str(uuid.uuid4()),
            "task_id": "task-1",
            "handler": "test_handler",
            "inputs": {"param1": "value1"},
            "attempt": 0,
            "max_retries": 3,
            "timeout": 300,
            "correlation_id": str(uuid.uuid4()),
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "execution_context": {"source": "test"}
        }
    
    def test_executor_initialization(self, executor_config):
        """Test executor worker initialization."""
        with patch('executor.worker.KafkaConsumer'), \
             patch('executor.worker.KafkaProducer'), \
             patch('executor.worker.redis.from_url'), \
             patch('executor.worker.ConnectorRegistry'), \
             patch('executor.worker.start_http_server'), \
             patch('executor.worker.ThreadPoolExecutor'), \
             patch('executor.worker.ProcessPoolExecutor'):
            
            executor = ExecutorWorker(**executor_config)
            
            assert executor.kafka_bootstrap_servers == ["localhost:9092"]
            assert executor.redis_url == "redis://localhost:6379"
            assert executor.database_url == "postgresql://postgres:postgres@localhost:5432/agent_framework"
            assert executor.metrics_port == 9091
            assert executor.max_workers == 5
            assert len(executor.connector_cache) == 0
    
    @pytest.mark.asyncio
    async def test_process_task_success(self, mock_executor, sample_task_message):
        """Test successful task processing."""
        # Mock Redis client
        mock_executor.redis_client.get.return_value = None  # No existing status
        mock_executor.redis_client.setex = Mock()
        mock_executor.redis_client.hset = Mock()
        mock_executor.redis_client.expire = Mock()
        
        # Mock connector
        mock_connector = Mock()
        mock_connector.execute_action.return_value = {"result": "success"}
        
        # Mock connector loading
        mock_executor._load_connector = AsyncMock(return_value=mock_connector)
        mock_executor._determine_execution_mode = Mock(return_value=ExecutionMode.SYNC)
        mock_executor._execute_sync = AsyncMock(return_value={"result": "success"})
        
        # Mock database operations
        with patch('executor.worker.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock Kafka producers
            mock_executor.task_done_producer.send = Mock()
            
            # Process the task
            await mock_executor._process_task(sample_task_message)
            
            # Verify connector was loaded
            mock_executor._load_connector.assert_called_once_with("test_handler")
            
            # Verify task was executed
            mock_executor._execute_sync.assert_called_once()
            
            # Verify success handling
            mock_executor.task_done_producer.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_process_task_idempotency_check(self, mock_executor, sample_task_message):
        """Test idempotency check prevents duplicate processing."""
        # Mock Redis client to return existing completed status
        mock_executor.redis_client.get.return_value = b'COMPLETED'
        
        # Mock connector loading
        mock_executor._load_connector = AsyncMock()
        
        # Process the task
        await mock_executor._process_task(sample_task_message)
        
        # Verify connector was not loaded (task skipped)
        mock_executor._load_connector.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_check_idempotency_new_task(self, mock_executor):
        """Test idempotency check for new task."""
        run_id = str(uuid.uuid4())
        task_id = "task-1"
        
        # Mock Redis client
        mock_executor.redis_client.get.return_value = None
        mock_executor.redis_client.setex = Mock()
        
        # Check idempotency
        result = await mock_executor._check_idempotency(run_id, task_id)
        
        # Verify task is allowed to run
        assert result == True
        
        # Verify Redis operations
        mock_executor.redis_client.get.assert_called_once()
        mock_executor.redis_client.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_idempotency_existing_task(self, mock_executor):
        """Test idempotency check for existing completed task."""
        run_id = str(uuid.uuid4())
        task_id = "task-1"
        
        # Mock Redis client to return completed status
        mock_executor.redis_client.get.return_value = b'COMPLETED'
        
        # Check idempotency
        result = await mock_executor._check_idempotency(run_id, task_id)
        
        # Verify task is not allowed to run
        assert result == False
    
    @pytest.mark.asyncio
    async def test_load_connector_success(self, mock_executor):
        """Test successful connector loading."""
        handler = "test_handler"
        
        # Mock connector registry
        mock_executor.connector_registry.get_connector.return_value = {
            "module_path": "connectors.test",
            "class_name": "TestConnector"
        }
        
        # Mock connector class
        mock_connector_class = Mock()
        mock_connector_instance = Mock()
        mock_connector_class.return_value = mock_connector_instance
        
        with patch('executor.worker.importlib.import_module') as mock_import:
            mock_module = Mock()
            mock_module.TestConnector = mock_connector_class
            mock_import.return_value = mock_module
            
            # Load connector
            result = await mock_executor._load_connector(handler)
            
            # Verify connector was loaded
            assert result == mock_connector_instance
            assert handler in mock_executor.connector_cache
            
            # Verify registry was called
            mock_executor.connector_registry.get_connector.assert_called_once_with(handler)
    
    @pytest.mark.asyncio
    async def test_load_connector_not_found(self, mock_executor):
        """Test connector loading when connector not found."""
        handler = "unknown_handler"
        
        # Mock connector registry to return None
        mock_executor.connector_registry.get_connector.return_value = None
        
        # Load connector
        result = await mock_executor._load_connector(handler)
        
        # Verify connector was not loaded
        assert result is None
    
    def test_determine_execution_mode_async(self, mock_executor):
        """Test execution mode determination for async connector."""
        # Mock connector with async method
        mock_connector = Mock()
        mock_connector.execute_action_async = Mock()
        
        # Determine execution mode
        mode = mock_executor._determine_execution_mode(mock_connector, {}, {})
        
        # Verify async mode was selected
        assert mode == ExecutionMode.ASYNC
    
    def test_determine_execution_mode_cpu_intensive(self, mock_executor):
        """Test execution mode determination for CPU-intensive connector."""
        # Mock connector that is CPU intensive
        mock_connector = Mock()
        mock_connector.is_cpu_intensive.return_value = True
        
        # Determine execution mode
        mode = mock_executor._determine_execution_mode(mock_connector, {}, {})
        
        # Verify CPU intensive mode was selected
        assert mode == ExecutionMode.CPU_INTENSIVE
    
    def test_determine_execution_mode_sync(self, mock_executor):
        """Test execution mode determination for sync connector."""
        # Mock regular connector
        mock_connector = Mock()
        
        # Determine execution mode
        mode = mock_executor._determine_execution_mode(mock_connector, {}, {})
        
        # Verify sync mode was selected
        assert mode == ExecutionMode.SYNC
    
    @pytest.mark.asyncio
    async def test_execute_async_success(self, mock_executor):
        """Test successful async execution."""
        # Mock connector
        mock_connector = Mock()
        mock_connector.execute_action_async = AsyncMock(return_value={"result": "success"})
        
        # Execute async
        result = await mock_executor._execute_async(mock_connector, {"param": "value"}, 300)
        
        # Verify result
        assert result == {"result": "success"}
        mock_connector.execute_action_async.assert_called_once_with({"param": "value"})
    
    @pytest.mark.asyncio
    async def test_execute_async_timeout(self, mock_executor):
        """Test async execution timeout."""
        # Mock connector that takes too long
        mock_connector = Mock()
        mock_connector.execute_action_async = AsyncMock(side_effect=asyncio.sleep(1))
        
        # Execute async with short timeout
        with pytest.raises(TimeoutError):
            await mock_executor._execute_async(mock_connector, {"param": "value"}, 0.1)
    
    @pytest.mark.asyncio
    async def test_execute_sync_success(self, mock_executor):
        """Test successful sync execution."""
        # Mock connector
        mock_connector = Mock()
        mock_connector.execute_action.return_value = {"result": "success"}
        
        # Mock thread pool executor
        mock_executor.thread_pool.submit = Mock()
        mock_future = Mock()
        mock_future.result.return_value = {"result": "success"}
        mock_executor.thread_pool.submit.return_value = mock_future
        
        # Execute sync
        result = await mock_executor._execute_sync(mock_connector, {"param": "value"}, 300)
        
        # Verify result
        assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_handle_task_success(self, mock_executor):
        """Test handling successful task execution."""
        # Create successful result
        result = TaskExecutionResult(
            task_id="task-1",
            run_id="run-1",
            success=True,
            output={"result": "success"},
            execution_time_ms=1500,
            execution_mode=ExecutionMode.ASYNC
        )
        
        # Mock Redis operations
        mock_executor.redis_client.setex = Mock()
        mock_executor.redis_client.hset = Mock()
        mock_executor.redis_client.expire = Mock()
        
        # Mock Kafka producer
        mock_executor.task_done_producer.send = Mock()
        
        # Mock database update
        mock_executor._update_task_audit = AsyncMock()
        
        # Handle success
        await mock_executor._handle_task_success(result, "corr-1", "tenant-1", "user-1")
        
        # Verify Redis operations
        mock_executor.redis_client.setex.assert_called_once()
        mock_executor.redis_client.hset.assert_called_once()
        mock_executor.redis_client.expire.assert_called_once()
        
        # Verify Kafka message was sent
        mock_executor.task_done_producer.send.assert_called_once()
        
        # Verify database was updated
        mock_executor._update_task_audit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_task_failure_retry(self, mock_executor):
        """Test handling failed task execution with retry."""
        # Create failed result
        result = TaskExecutionResult(
            task_id="task-1",
            run_id="run-1",
            success=False,
            error="Test error",
            execution_time_ms=500,
            execution_mode=ExecutionMode.SYNC
        )
        
        # Mock Redis operations
        mock_executor.redis_client.setex = Mock()
        
        # Mock Kafka producer
        mock_executor.task_failed_producer.send = Mock()
        
        # Mock database update
        mock_executor._update_task_audit = AsyncMock()
        
        # Handle failure (attempt < max_retries)
        await mock_executor._handle_task_failure(result, 1, 3, "corr-1", "tenant-1", "user-1")
        
        # Verify task failed message was sent
        mock_executor.task_failed_producer.send.assert_called_once()
        
        # Verify database was updated
        mock_executor._update_task_audit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_task_failure_dead_letter(self, mock_executor):
        """Test handling failed task execution moved to dead letter queue."""
        # Create failed result
        result = TaskExecutionResult(
            task_id="task-1",
            run_id="run-1",
            success=False,
            error="Test error",
            execution_time_ms=500,
            execution_mode=ExecutionMode.SYNC
        )
        
        # Mock Redis operations
        mock_executor.redis_client.setex = Mock()
        
        # Mock Kafka producer
        mock_executor.dead_letter_producer.send = Mock()
        
        # Mock database update
        mock_executor._update_task_audit = AsyncMock()
        
        # Handle failure (attempt >= max_retries)
        await mock_executor._handle_task_failure(result, 3, 3, "corr-1", "tenant-1", "user-1")
        
        # Verify dead letter message was sent
        mock_executor.dead_letter_producer.send.assert_called_once()
        
        # Verify database was updated
        mock_executor._update_task_audit.assert_called_once()


class TestExecutorIntegration:
    """Integration tests for the executor worker."""
    
    @pytest.fixture
    def executor_config(self):
        """Configuration for executor worker."""
        return {
            "kafka_bootstrap_servers": "localhost:9092",
            "redis_url": "redis://localhost:6379",
            "database_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "connector_registry_url": "postgresql://postgres:postgres@localhost:5432/agent_framework",
            "metrics_port": 9091,
            "max_workers": 5
        }
    
    @pytest.mark.asyncio
    async def test_full_task_execution_flow(self, executor_config):
        """Test complete task execution flow from start to finish."""
        with patch('executor.worker.KafkaConsumer') as mock_consumer_class, \
             patch('executor.worker.KafkaProducer') as mock_producer_class, \
             patch('executor.worker.redis.from_url') as mock_redis_class, \
             patch('executor.worker.ConnectorRegistry') as mock_registry_class, \
             patch('executor.worker.start_http_server'), \
             patch('executor.worker.ThreadPoolExecutor'), \
             patch('executor.worker.ProcessPoolExecutor'):
            
            # Setup mocks
            mock_redis = Mock()
            mock_redis_class.return_value = mock_redis
            
            mock_registry = Mock()
            mock_registry_class.return_value = mock_registry
            
            # Create sample task message
            run_id = str(uuid.uuid4())
            task_message = {
                "run_id": run_id,
                "task_id": "integration-test-task",
                "handler": "test_handler",
                "inputs": {"param1": "value1"},
                "attempt": 0,
                "max_retries": 3,
                "timeout": 300,
                "correlation_id": str(uuid.uuid4()),
                "tenant_id": "tenant-1",
                "user_id": "user-1",
                "execution_context": {"source": "integration_test"}
            }
            
            # Mock connector registry
            mock_registry.get_connector.return_value = {
                "module_path": "connectors.test",
                "class_name": "TestConnector"
            }
            
            # Mock connector
            mock_connector = Mock()
            mock_connector.execute_action.return_value = {"result": "integration success"}
            
            # Create executor
            executor = ExecutorWorker(**executor_config)
            
            # Mock connector loading
            executor._load_connector = AsyncMock(return_value=mock_connector)
            executor._determine_execution_mode = Mock(return_value=ExecutionMode.SYNC)
            executor._execute_sync = AsyncMock(return_value={"result": "integration success"})
            
            # Mock Redis operations
            mock_redis.get.return_value = None  # No existing status
            mock_redis.setex = Mock()
            mock_redis.hset = Mock()
            mock_redis.expire = Mock()
            
            # Mock Kafka producers
            executor.task_done_producer.send = Mock()
            
            # Mock database operations
            with patch('executor.worker.psycopg2.connect') as mock_connect:
                mock_conn = Mock()
                mock_cursor = Mock()
                mock_connect.return_value = mock_conn
                mock_conn.cursor.return_value = mock_cursor
                
                # Process the task
                await executor._process_task(task_message)
                
                # Verify connector was loaded
                executor._load_connector.assert_called_once_with("test_handler")
                
                # Verify task was executed
                executor._execute_sync.assert_called_once()
                
                # Verify success handling
                executor.task_done_producer.send.assert_called_once()
                
                # Verify Redis operations
                mock_redis.setex.assert_called()
                mock_redis.hset.assert_called_once()
                mock_redis.expire.assert_called_once()


class TestExecutorPerformance:
    """Performance tests for the executor worker."""
    
    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self, executor_config):
        """Test processing multiple tasks concurrently."""
        with patch('executor.worker.KafkaConsumer'), \
             patch('executor.worker.KafkaProducer'), \
             patch('executor.worker.redis.from_url'), \
             patch('executor.worker.ConnectorRegistry'), \
             patch('executor.worker.start_http_server'), \
             patch('executor.worker.ThreadPoolExecutor'), \
             patch('executor.worker.ProcessPoolExecutor'):
            
            executor = ExecutorWorker(**executor_config)
            
            # Mock connector
            mock_connector = Mock()
            mock_connector.execute_action.return_value = {"result": "success"}
            
            # Mock operations
            executor._load_connector = AsyncMock(return_value=mock_connector)
            executor._determine_execution_mode = Mock(return_value=ExecutionMode.SYNC)
            executor._execute_sync = AsyncMock(return_value={"result": "success"})
            executor.redis_client.get.return_value = None
            executor.redis_client.setex = Mock()
            executor.redis_client.hset = Mock()
            executor.redis_client.expire = Mock()
            executor.task_done_producer.send = Mock()
            executor._update_task_audit = AsyncMock()
            
            # Process multiple tasks concurrently
            num_tasks = 10
            tasks = []
            
            for i in range(num_tasks):
                task_message = {
                    "run_id": str(uuid.uuid4()),
                    "task_id": f"perf-task-{i}",
                    "handler": f"handler_{i}",
                    "inputs": {"param": f"value_{i}"},
                    "attempt": 0,
                    "max_retries": 3,
                    "timeout": 300,
                    "correlation_id": str(uuid.uuid4()),
                    "tenant_id": f"tenant-{i}",
                    "user_id": f"user-{i}",
                    "execution_context": {"source": "performance_test"}
                }
                
                task = executor._process_task(task_message)
                tasks.append(task)
            
            # Wait for all tasks to be processed
            await asyncio.gather(*tasks)
            
            # Verify all tasks were processed
            assert executor._load_connector.call_count == num_tasks
            assert executor._execute_sync.call_count == num_tasks
            assert executor.task_done_producer.send.call_count == num_tasks


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
