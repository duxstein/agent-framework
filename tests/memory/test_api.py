"""
Test cases for Memory API.

This module contains tests for the Memory API integration layer.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from contextlib import contextmanager

from memory.api import MemoryAPI, initialize_memory_api, get_global_memory_api, set_global_memory_api


class TestMemoryAPIIntegration:
    """Integration tests for Memory API."""
    
    @pytest.fixture
    def mock_adapters(self):
        """Mock all adapters for testing."""
        redis_adapter = Mock()
        redis_adapter.connect.return_value = True
        redis_adapter.is_connected.return_value = True
        redis_adapter.health_check.return_value = {"status": "healthy"}
        
        postgres_adapter = Mock()
        postgres_adapter.connect.return_value = True
        postgres_adapter.is_connected.return_value = True
        postgres_adapter.health_check.return_value = {"status": "healthy"}
        
        vector_adapter = Mock()
        vector_adapter.connect.return_value = True
        vector_adapter.is_connected.return_value = True
        vector_adapter.health_check.return_value = {"status": "healthy"}
        
        return {
            "redis": redis_adapter,
            "postgres": postgres_adapter,
            "vector": vector_adapter
        }
    
    @patch('memory.api.RedisAdapter')
    @patch('memory.api.PostgresAdapter')
    @patch('memory.api.VectorAdapter')
    def test_memory_api_initialization(self, mock_vector, mock_postgres, mock_redis, mock_adapters):
        """Test Memory API initialization with all adapters."""
        mock_redis.return_value = mock_adapters["redis"]
        mock_postgres.return_value = mock_adapters["postgres"]
        mock_vector.return_value = mock_adapters["vector"]
        
        config = {
            "redis_config": {"host": "localhost"},
            "postgres_config": {"host": "localhost"},
            "vector_config": {"backend": "placeholder"}
        }
        
        memory_api = MemoryAPI(**config)
        
        assert memory_api.redis_adapter is not None
        assert memory_api.postgres_adapter is not None
        assert memory_api.vector_adapter is not None
    
    @patch('memory.api.RedisAdapter')
    @patch('memory.api.PostgresAdapter')
    @patch('memory.api.VectorAdapter')
    def test_memory_api_connection_success(self, mock_vector, mock_postgres, mock_redis, mock_adapters):
        """Test successful connection to all adapters."""
        mock_redis.return_value = mock_adapters["redis"]
        mock_postgres.return_value = mock_adapters["postgres"]
        mock_vector.return_value = mock_adapters["vector"]
        
        memory_api = MemoryAPI(
            redis_config={"host": "localhost"},
            postgres_config={"host": "localhost"},
            vector_config={"backend": "placeholder"}
        )
        
        result = memory_api.connect()
        
        assert result is True
        assert memory_api.is_connected() is True
        mock_adapters["redis"].connect.assert_called_once()
        mock_adapters["postgres"].connect.assert_called_once()
        mock_adapters["vector"].connect.assert_called_once()
    
    @patch('memory.api.RedisAdapter')
    @patch('memory.api.PostgresAdapter')
    @patch('memory.api.VectorAdapter')
    def test_memory_api_connection_partial_failure(self, mock_vector, mock_postgres, mock_redis, mock_adapters):
        """Test connection with partial adapter failure."""
        mock_redis.return_value = mock_adapters["redis"]
        mock_postgres.return_value = mock_adapters["postgres"]
        mock_vector.return_value = mock_adapters["vector"]
        
        # Make Redis connection fail
        mock_adapters["redis"].connect.return_value = False
        
        memory_api = MemoryAPI(
            redis_config={"host": "localhost"},
            postgres_config={"host": "localhost"},
            vector_config={"backend": "placeholder"}
        )
        
        result = memory_api.connect()
        
        assert result is False
        assert memory_api.is_connected() is False
    
    @patch('memory.api.RedisAdapter')
    @patch('memory.api.PostgresAdapter')
    @patch('memory.api.VectorAdapter')
    def test_memory_api_disconnection(self, mock_vector, mock_postgres, mock_redis, mock_adapters):
        """Test disconnection from all adapters."""
        mock_redis.return_value = mock_adapters["redis"]
        mock_postgres.return_value = mock_adapters["postgres"]
        mock_vector.return_value = mock_adapters["vector"]
        
        memory_api = MemoryAPI(
            redis_config={"host": "localhost"},
            postgres_config={"host": "localhost"},
            vector_config={"backend": "placeholder"}
        )
        
        memory_api.connect()
        memory_api.disconnect()
        
        assert memory_api.is_connected() is False
        mock_adapters["redis"].disconnect.assert_called_once()
        mock_adapters["postgres"].disconnect.assert_called_once()
        mock_adapters["vector"].disconnect.assert_called_once()


class TestMemoryAPIContextOperations:
    """Test context operations in Memory API."""
    
    @pytest.fixture
    def memory_api_with_redis(self):
        """Memory API with mocked Redis adapter."""
        redis_adapter = Mock()
        redis_adapter.connect.return_value = True
        redis_adapter.is_connected.return_value = True
        redis_adapter.get.return_value = None
        redis_adapter.set.return_value = True
        redis_adapter.delete.return_value = True
        
        memory_api = MemoryAPI(redis_config={"host": "localhost"})
        memory_api.redis_adapter = redis_adapter
        memory_api._connected = True
        
        return memory_api, redis_adapter
    
    def test_set_context(self, memory_api_with_redis):
        """Test setting context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        context_data = {"user_id": "user_1", "session_id": "session_1"}
        result = memory_api.set_context("context_1", context_data)
        
        assert result is True
        
        # Verify Redis set was called with proper data structure
        call_args = redis_adapter.set.call_args
        key = call_args[0][0]
        value_json = call_args[0][1]
        
        assert key == "context:context_1"
        
        # Parse and verify JSON structure
        value = json.loads(value_json)
        assert value["data"] == context_data
        assert "created_at" in value
        assert value["context_id"] == "context_1"
    
    def test_set_context_with_ttl(self, memory_api_with_redis):
        """Test setting context with TTL."""
        memory_api, redis_adapter = memory_api_with_redis
        
        context_data = {"user_id": "user_1"}
        result = memory_api.set_context("context_1", context_data, ttl=3600)
        
        assert result is True
        
        # Verify Redis setex was called
        call_args = redis_adapter.set.call_args
        assert len(call_args[0]) == 3  # key, value, ttl
        assert call_args[0][2] == 3600
    
    def test_get_context(self, memory_api_with_redis):
        """Test getting context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        # Mock Redis response
        context_data = {
            "data": {"user_id": "user_1"},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "context_id": "context_1"
        }
        redis_adapter.get.return_value = json.dumps(context_data)
        
        result = memory_api.get_context("context_1")
        
        assert result is not None
        assert result["data"]["user_id"] == "user_1"
        assert result["context_id"] == "context_1"
        
        # Verify Redis get was called with correct key
        redis_adapter.get.assert_called_with("context:context_1")
    
    def test_get_context_not_found(self, memory_api_with_redis):
        """Test getting non-existent context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        redis_adapter.get.return_value = None
        
        result = memory_api.get_context("nonexistent")
        
        assert result is None
    
    def test_append_event(self, memory_api_with_redis):
        """Test appending event to context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        # Mock existing context
        existing_context = {
            "data": {"user_id": "user_1"},
            "events": []
        }
        redis_adapter.get.return_value = json.dumps(existing_context)
        
        event = {"type": "user_action", "action": "login"}
        result = memory_api.append_event("context_1", event)
        
        assert result is True
        
        # Verify context was updated with event
        call_args = redis_adapter.set.call_args
        updated_context = json.loads(call_args[0][1])
        
        assert len(updated_context["events"]) == 1
        assert updated_context["events"][0]["event"] == event
        assert "timestamp" in updated_context["events"][0]
        assert "event_id" in updated_context["events"][0]
    
    def test_append_event_new_context(self, memory_api_with_redis):
        """Test appending event to new context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        # Mock no existing context
        redis_adapter.get.return_value = None
        
        event = {"type": "user_action", "action": "login"}
        result = memory_api.append_event("context_1", event)
        
        assert result is True
        
        # Verify new context was created with event
        call_args = redis_adapter.set.call_args
        new_context = json.loads(call_args[0][1])
        
        assert new_context["data"] == {}
        assert len(new_context["events"]) == 1
        assert new_context["events"][0]["event"] == event
    
    def test_clear_context(self, memory_api_with_redis):
        """Test clearing context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        result = memory_api.clear_context("context_1")
        
        assert result is True
        redis_adapter.delete.assert_called_with("context:context_1")
    
    def test_get_events(self, memory_api_with_redis):
        """Test getting events from context."""
        memory_api, redis_adapter = memory_api_with_redis
        
        # Mock context with events
        context_with_events = {
            "data": {"user_id": "user_1"},
            "events": [
                {"event": {"type": "action1"}, "timestamp": "2024-01-01T00:00:00Z", "event_id": "evt_1"},
                {"event": {"type": "action2"}, "timestamp": "2024-01-01T01:00:00Z", "event_id": "evt_2"}
            ]
        }
        redis_adapter.get.return_value = json.dumps(context_with_events)
        
        events = memory_api.get_events("context_1")
        
        assert len(events) == 2
        assert events[0]["event"]["type"] == "action1"
        assert events[1]["event"]["type"] == "action2"


class TestMemoryAPIPostgresOperations:
    """Test PostgreSQL operations in Memory API."""
    
    @pytest.fixture
    def memory_api_with_postgres(self):
        """Memory API with mocked PostgreSQL adapter."""
        postgres_adapter = Mock()
        postgres_adapter.connect.return_value = True
        postgres_adapter.is_connected.return_value = True
        postgres_adapter.write_flow_run_history.return_value = True
        postgres_adapter.read_flow_run_history.return_value = []
        postgres_adapter.write_task_output.return_value = True
        postgres_adapter.read_task_output.return_value = None
        postgres_adapter.write_audit_entry.return_value = True
        
        memory_api = MemoryAPI(postgres_config={"host": "localhost"})
        memory_api.postgres_adapter = postgres_adapter
        memory_api._connected = True
        
        return memory_api, postgres_adapter
    
    def test_write_flow_run_history(self, memory_api_with_postgres):
        """Test writing flow run history."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        data = {"status": "completed", "duration": 120}
        result = memory_api.write_flow_run_history("flow_1", "run_1", data)
        
        assert result is True
        postgres_adapter.write_flow_run_history.assert_called_with("flow_1", "run_1", data)
    
    def test_read_flow_run_history(self, memory_api_with_postgres):
        """Test reading flow run history."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        # Mock database response
        mock_history = [
            {
                "id": 1,
                "flow_id": "flow_1",
                "run_id": "run_1",
                "data": {"status": "completed"},
                "created_at": datetime.now(timezone.utc)
            }
        ]
        postgres_adapter.read_flow_run_history.return_value = mock_history
        
        result = memory_api.read_flow_run_history("flow_1")
        
        assert len(result) == 1
        assert result[0]["flow_id"] == "flow_1"
        postgres_adapter.read_flow_run_history.assert_called_with("flow_1", None, 100)
    
    def test_read_flow_run_history_with_run_id(self, memory_api_with_postgres):
        """Test reading flow run history with specific run ID."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        result = memory_api.read_flow_run_history("flow_1", "run_1", limit=50)
        
        postgres_adapter.read_flow_run_history.assert_called_with("flow_1", "run_1", 50)
    
    def test_write_task_output(self, memory_api_with_postgres):
        """Test writing task output."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        output = {"result": "success", "data": [1, 2, 3]}
        metadata = {"execution_time": 5.2}
        
        result = memory_api.write_task_output("task_1", output, metadata)
        
        assert result is True
        postgres_adapter.write_task_output.assert_called_with("task_1", output, metadata)
    
    def test_write_task_output_without_metadata(self, memory_api_with_postgres):
        """Test writing task output without metadata."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        output = {"result": "success"}
        
        result = memory_api.write_task_output("task_1", output)
        
        assert result is True
        postgres_adapter.write_task_output.assert_called_with("task_1", output, None)
    
    def test_read_task_output(self, memory_api_with_postgres):
        """Test reading task output."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        # Mock database response
        mock_output = {
            "id": 1,
            "task_id": "task_1",
            "output": {"result": "success"},
            "metadata": {"execution_time": 5.2},
            "created_at": datetime.now(timezone.utc)
        }
        postgres_adapter.read_task_output.return_value = mock_output
        
        result = memory_api.read_task_output("task_1")
        
        assert result is not None
        assert result["task_id"] == "task_1"
        assert result["output"]["result"] == "success"
        postgres_adapter.read_task_output.assert_called_with("task_1")
    
    def test_write_audit_entry(self, memory_api_with_postgres):
        """Test writing audit entry."""
        memory_api, postgres_adapter = memory_api_with_postgres
        
        data = {"user": "test_user", "ip": "127.0.0.1"}
        result = memory_api.write_audit_entry("flow", "flow_1", "create", data)
        
        assert result is True
        postgres_adapter.write_audit_entry.assert_called_with("flow", "flow_1", "create", data)


class TestMemoryAPIVectorOperations:
    """Test vector operations in Memory API."""
    
    @pytest.fixture
    def memory_api_with_vector(self):
        """Memory API with mocked Vector adapter."""
        vector_adapter = Mock()
        vector_adapter.connect.return_value = True
        vector_adapter.is_connected.return_value = True
        vector_adapter.index_embedding.return_value = True
        vector_adapter.query_embeddings.return_value = []
        vector_adapter.delete_embedding.return_value = True
        vector_adapter.get_embedding_stats.return_value = {"total_embeddings": 0}
        
        memory_api = MemoryAPI(vector_config={"backend": "placeholder"})
        memory_api.vector_adapter = vector_adapter
        memory_api._connected = True
        
        return memory_api, vector_adapter
    
    def test_index_embedding(self, memory_api_with_vector):
        """Test indexing embedding."""
        memory_api, vector_adapter = memory_api_with_vector
        
        embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        metadata = {"type": "document", "source": "pdf"}
        
        result = memory_api.index_embedding("embedding_1", embedding, metadata)
        
        assert result is True
        vector_adapter.index_embedding.assert_called_with("embedding_1", embedding, metadata)
    
    def test_index_embedding_without_metadata(self, memory_api_with_vector):
        """Test indexing embedding without metadata."""
        memory_api, vector_adapter = memory_api_with_vector
        
        embedding = [0.1, 0.2, 0.3] * 256
        
        result = memory_api.index_embedding("embedding_1", embedding)
        
        assert result is True
        vector_adapter.index_embedding.assert_called_with("embedding_1", embedding, None)
    
    def test_query_embeddings(self, memory_api_with_vector):
        """Test querying embeddings."""
        memory_api, vector_adapter = memory_api_with_vector
        
        # Mock query results
        mock_results = [
            {"id": "doc_1", "similarity": 0.95, "metadata": {"type": "document"}},
            {"id": "doc_2", "similarity": 0.87, "metadata": {"type": "document"}}
        ]
        vector_adapter.query_embeddings.return_value = mock_results
        
        query_embedding = [0.1, 0.2, 0.3] * 256
        filter_metadata = {"type": "document"}
        
        result = memory_api.query_embeddings(query_embedding, top_k=5, filter_metadata=filter_metadata)
        
        assert len(result) == 2
        assert result[0]["id"] == "doc_1"
        assert result[0]["similarity"] == 0.95
        
        vector_adapter.query_embeddings.assert_called_with(query_embedding, 5, filter_metadata)
    
    def test_query_embeddings_default_params(self, memory_api_with_vector):
        """Test querying embeddings with default parameters."""
        memory_api, vector_adapter = memory_api_with_vector
        
        query_embedding = [0.1, 0.2, 0.3] * 256
        result = memory_api.query_embeddings(query_embedding)
        
        vector_adapter.query_embeddings.assert_called_with(query_embedding, 10, None)
    
    def test_delete_embedding(self, memory_api_with_vector):
        """Test deleting embedding."""
        memory_api, vector_adapter = memory_api_with_vector
        
        result = memory_api.delete_embedding("embedding_1")
        
        assert result is True
        vector_adapter.delete_embedding.assert_called_with("embedding_1")


class TestMemoryAPILocking:
    """Test distributed locking in Memory API."""
    
    @pytest.fixture
    def memory_api_with_redis_lock(self):
        """Memory API with mocked Redis adapter for locking."""
        redis_adapter = Mock()
        redis_adapter.connect.return_value = True
        redis_adapter.is_connected.return_value = True
        
        # Mock lock context manager
        mock_lock = Mock()
        redis_adapter.lock.return_value.__enter__ = Mock(return_value=mock_lock)
        redis_adapter.lock.return_value.__exit__ = Mock(return_value=None)
        
        memory_api = MemoryAPI(redis_config={"host": "localhost"})
        memory_api.redis_adapter = redis_adapter
        memory_api._connected = True
        
        return memory_api, redis_adapter, mock_lock
    
    def test_acquire_lock_success(self, memory_api_with_redis_lock):
        """Test successful lock acquisition."""
        memory_api, redis_adapter, mock_lock = memory_api_with_redis_lock
        
        with memory_api.acquire_lock("test_lock", timeout=5, blocking_timeout=2) as lock:
            assert lock == mock_lock
        
        redis_adapter.lock.assert_called_with("test:lock:test_lock", timeout=5, blocking_timeout=2)
    
    def test_acquire_lock_default_params(self, memory_api_with_redis_lock):
        """Test lock acquisition with default parameters."""
        memory_api, redis_adapter, mock_lock = memory_api_with_redis_lock
        
        with memory_api.acquire_lock("test_lock") as lock:
            assert lock == mock_lock
        
        redis_adapter.lock.assert_called_with("test:lock:test_lock", timeout=10, blocking_timeout=5)
    
    def test_acquire_lock_no_redis(self):
        """Test lock acquisition when Redis is not available."""
        memory_api = MemoryAPI()
        memory_api._connected = True
        
        with pytest.raises(Exception, match="Redis adapter not available for distributed locking"):
            with memory_api.acquire_lock("test_lock"):
                pass


class TestMemoryAPIHealthAndStats:
    """Test health check and statistics in Memory API."""
    
    @pytest.fixture
    def memory_api_with_all_adapters(self):
        """Memory API with all adapters mocked."""
        redis_adapter = Mock()
        redis_adapter.health_check.return_value = {
            "status": "healthy",
            "used_memory": "1M",
            "connected_clients": 5
        }
        
        postgres_adapter = Mock()
        postgres_adapter.health_check.return_value = {
            "status": "healthy",
            "active_connections": 3
        }
        
        vector_adapter = Mock()
        vector_adapter.health_check.return_value = {
            "status": "healthy",
            "backend": "placeholder"
        }
        vector_adapter.get_embedding_stats.return_value = {
            "total_embeddings": 100,
            "dimension": 768
        }
        
        memory_api = MemoryAPI(
            redis_config={"host": "localhost"},
            postgres_config={"host": "localhost"},
            vector_config={"backend": "placeholder"}
        )
        memory_api.redis_adapter = redis_adapter
        memory_api.postgres_adapter = postgres_adapter
        memory_api.vector_adapter = vector_adapter
        memory_api._connected = True
        
        return memory_api, redis_adapter, postgres_adapter, vector_adapter
    
    def test_health_check_all_healthy(self, memory_api_with_all_adapters):
        """Test health check when all adapters are healthy."""
        memory_api, redis_adapter, postgres_adapter, vector_adapter = memory_api_with_all_adapters
        
        health = memory_api.health_check()
        
        assert health["overall_status"] == "healthy"
        assert "timestamp" in health
        assert "adapters" in health
        
        assert health["adapters"]["redis"]["status"] == "healthy"
        assert health["adapters"]["postgres"]["status"] == "healthy"
        assert health["adapters"]["vector"]["status"] == "healthy"
    
    def test_health_check_degraded(self, memory_api_with_all_adapters):
        """Test health check when some adapters are unhealthy."""
        memory_api, redis_adapter, postgres_adapter, vector_adapter = memory_api_with_all_adapters
        
        # Make Redis unhealthy
        redis_adapter.health_check.return_value = {"status": "error", "error": "Connection failed"}
        
        health = memory_api.health_check()
        
        assert health["overall_status"] == "degraded"
        assert health["adapters"]["redis"]["status"] == "error"
        assert health["adapters"]["postgres"]["status"] == "healthy"
        assert health["adapters"]["vector"]["status"] == "healthy"
    
    def test_get_memory_stats(self, memory_api_with_all_adapters):
        """Test getting memory statistics."""
        memory_api, redis_adapter, postgres_adapter, vector_adapter = memory_api_with_all_adapters
        
        stats = memory_api.get_memory_stats()
        
        assert "timestamp" in stats
        assert "adapters" in stats
        
        assert "redis" in stats["adapters"]
        assert "postgres" in stats["adapters"]
        assert "vector" in stats["adapters"]
        
        assert stats["adapters"]["redis"]["status"] == "healthy"
        assert stats["adapters"]["postgres"]["status"] == "healthy"
        assert stats["adapters"]["vector"]["total_embeddings"] == 100


class TestGlobalMemoryAPIFunctions:
    """Test global Memory API functions."""
    
    def test_get_global_memory_api_none(self):
        """Test getting global memory API when not set."""
        # Reset global state
        import memory.api
        memory.api._global_memory_api = None
        
        result = get_global_memory_api()
        assert result is None
    
    def test_set_and_get_global_memory_api(self):
        """Test setting and getting global memory API."""
        # Reset global state
        import memory.api
        memory.api._global_memory_api = None
        
        mock_api = Mock()
        set_global_memory_api(mock_api)
        
        result = get_global_memory_api()
        assert result == mock_api
    
    @patch('memory.api.MemoryAPI')
    def test_initialize_memory_api_success(self, mock_memory_api_class):
        """Test successful initialization of global memory API."""
        # Reset global state
        import memory.api
        memory.api._global_memory_api = None
        
        mock_api = Mock()
        mock_api.connect.return_value = True
        mock_memory_api_class.return_value = mock_api
        
        redis_config = {"host": "localhost"}
        postgres_config = {"host": "localhost"}
        vector_config = {"backend": "placeholder"}
        
        result = initialize_memory_api(redis_config, postgres_config, vector_config)
        
        assert result == mock_api
        mock_api.connect.assert_called_once()
        
        # Verify global API was set
        assert get_global_memory_api() == mock_api
    
    @patch('memory.api.MemoryAPI')
    def test_initialize_memory_api_failure(self, mock_memory_api_class):
        """Test initialization failure of global memory API."""
        # Reset global state
        import memory.api
        memory.api._global_memory_api = None
        
        mock_api = Mock()
        mock_api.connect.return_value = False
        mock_memory_api_class.return_value = mock_api
        
        result = initialize_memory_api()
        
        assert result == mock_api
        mock_api.connect.assert_called_once()
        
        # Verify global API was not set due to connection failure
        assert get_global_memory_api() is None


if __name__ == "__main__":
    pytest.main([__file__])
