"""
Tests for Memory Adapter Layer.

This module contains comprehensive tests for the memory adapters including
RedisAdapter, PostgresAdapter, VectorAdapter, and the Memory API.
"""

import json
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from typing import Dict, Any, List

from memory.adapter import RedisAdapter, PostgresAdapter, VectorAdapter
from memory.api import MemoryAPI, initialize_memory_api, get_global_memory_api


class TestRedisAdapter:
    """Test cases for RedisAdapter."""
    
    @pytest.fixture
    def redis_config(self):
        """Redis configuration for testing."""
        return {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None,
            "connection_timeout": 5,
            "socket_timeout": 5,
            "max_connections": 50,
            "key_prefix": "test:"
        }
    
    @pytest.fixture
    def redis_adapter(self, redis_config):
        """Redis adapter instance for testing."""
        return RedisAdapter(redis_config)
    
    @patch('memory.adapter.redis.Redis')
    def test_connect_success(self, mock_redis_class, redis_adapter):
        """Test successful Redis connection."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis
        
        result = redis_adapter.connect()
        
        assert result is True
        assert redis_adapter.is_connected() is True
        mock_redis.ping.assert_called_once()
    
    @patch('memory.adapter.redis.Redis')
    def test_connect_failure(self, mock_redis_class, redis_adapter):
        """Test Redis connection failure."""
        mock_redis_class.side_effect = Exception("Connection failed")
        
        result = redis_adapter.connect()
        
        assert result is False
        assert redis_adapter.is_connected() is False
    
    @patch('memory.adapter.redis.Redis')
    def test_disconnect(self, mock_redis_class, redis_adapter):
        """Test Redis disconnection."""
        mock_redis = Mock()
        mock_redis_class.return_value = mock_redis
        redis_adapter.connect()
        
        redis_adapter.disconnect()
        
        mock_redis.close.assert_called_once()
        assert redis_adapter.is_connected() is False
    
    @patch('memory.adapter.redis.Redis')
    def test_get_set(self, mock_redis_class, redis_adapter):
        """Test Redis get/set operations."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = "test_value"
        mock_redis.set.return_value = True
        mock_redis_class.return_value = mock_redis
        redis_adapter.connect()
        
        # Test set
        result = redis_adapter.set("test_key", "test_value")
        assert result is True
        mock_redis.set.assert_called_with("test:test_key", "test_value")
        
        # Test get
        value = redis_adapter.get("test_key")
        assert value == "test_value"
        mock_redis.get.assert_called_with("test:test_key")
    
    @patch('memory.adapter.redis.Redis')
    def test_hget_hset(self, mock_redis_class, redis_adapter):
        """Test Redis hash operations."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.hget.return_value = "hash_value"
        mock_redis.hset.return_value = 1
        mock_redis_class.return_value = mock_redis
        redis_adapter.connect()
        
        # Test hset
        result = redis_adapter.hset("test_hash", "field", "hash_value")
        assert result is True
        mock_redis.hset.assert_called_with("test:test_hash", "field", "hash_value")
        
        # Test hget
        value = redis_adapter.hget("test_hash", "field")
        assert value == "hash_value"
        mock_redis.hget.assert_called_with("test:test_hash", "field")
    
    @patch('memory.adapter.redis.Redis')
    def test_lock_acquisition(self, mock_redis_class, redis_adapter):
        """Test distributed lock acquisition."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_lock = Mock()
        mock_lock.acquire.return_value = True
        mock_redis.lock.return_value = mock_lock
        mock_redis_class.return_value = mock_redis
        redis_adapter.connect()
        
        lock = redis_adapter.acquire_lock("test_lock")
        
        assert lock is not None
        mock_redis.lock.assert_called_with("test:lock:test_lock", timeout=10, blocking_timeout=5)
        mock_lock.acquire.assert_called_with(blocking=False)
    
    @patch('memory.adapter.redis.Redis')
    def test_health_check(self, mock_redis_class, redis_adapter):
        """Test Redis health check."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = "test_value"
        mock_redis.delete.return_value = 1
        mock_redis.info.return_value = {
            "redis_version": "6.2.0",
            "used_memory_human": "1M",
            "connected_clients": 5
        }
        mock_redis_class.return_value = mock_redis
        redis_adapter.connect()
        
        health = redis_adapter.health_check()
        
        assert health["status"] == "healthy"
        assert health["host"] == "localhost"
        assert health["port"] == 6379
        assert "execution_time_ms" in health


class TestPostgresAdapter:
    """Test cases for PostgresAdapter."""
    
    @pytest.fixture
    def postgres_config(self):
        """PostgreSQL configuration for testing."""
        return {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password",
            "connection_timeout": 30,
            "max_connections": 10,
            "schema": "public"
        }
    
    @pytest.fixture
    def postgres_adapter(self, postgres_config):
        """PostgreSQL adapter instance for testing."""
        return PostgresAdapter(postgres_config)
    
    @patch('memory.adapter.psycopg2.connect')
    def test_connect_success(self, mock_connect, postgres_adapter):
        """Test successful PostgreSQL connection."""
        mock_conn = Mock()
        mock_conn.close = Mock()
        mock_connect.return_value = mock_conn
        
        result = postgres_adapter.connect()
        
        assert result is True
        assert postgres_adapter.is_connected() is True
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()
    
    @patch('memory.adapter.psycopg2.connect')
    def test_connect_failure(self, mock_connect, postgres_adapter):
        """Test PostgreSQL connection failure."""
        mock_connect.side_effect = Exception("Connection failed")
        
        result = postgres_adapter.connect()
        
        assert result is False
        assert postgres_adapter.is_connected() is False
    
    @patch('memory.adapter.psycopg2.connect')
    def test_write_flow_run_history(self, mock_connect, postgres_adapter):
        """Test writing flow run history."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        postgres_adapter.connect()
        
        data = {"status": "completed", "duration": 120}
        result = postgres_adapter.write_flow_run_history("flow_1", "run_1", data)
        
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
    
    @patch('memory.adapter.psycopg2.connect')
    def test_read_flow_run_history(self, mock_connect, postgres_adapter):
        """Test reading flow run history."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        postgres_adapter.connect()
        
        # Mock database row
        mock_row = Mock()
        mock_row.__iter__ = Mock(return_value=iter([
            'id', 'flow_1', 'run_1', '{"status": "completed"}', datetime.now(timezone.utc)
        ]))
        mock_cursor.fetchall.return_value = [mock_row]
        
        result = postgres_adapter.read_flow_run_history("flow_1")
        
        assert len(result) == 1
        assert result[0]["flow_id"] == "flow_1"
        assert result[0]["run_id"] == "run_1"
        mock_cursor.close.assert_called_once()
    
    @patch('memory.adapter.psycopg2.connect')
    def test_write_task_output(self, mock_connect, postgres_adapter):
        """Test writing task output."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        postgres_adapter.connect()
        
        output = {"result": "success", "data": [1, 2, 3]}
        metadata = {"execution_time": 5.2}
        
        result = postgres_adapter.write_task_output("task_1", output, metadata)
        
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
    
    @patch('memory.adapter.psycopg2.connect')
    def test_write_audit_entry(self, mock_connect, postgres_adapter):
        """Test writing audit entry."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        postgres_adapter.connect()
        
        data = {"user": "test_user", "ip": "127.0.0.1"}
        result = postgres_adapter.write_audit_entry("flow", "flow_1", "create", data)
        
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()


class TestVectorAdapter:
    """Test cases for VectorAdapter."""
    
    @pytest.fixture
    def vector_config(self):
        """Vector adapter configuration for testing."""
        return {
            "backend": "placeholder",
            "dimension": 768,
            "metric": "cosine",
            "namespace": "test"
        }
    
    @pytest.fixture
    def vector_adapter(self, vector_config):
        """Vector adapter instance for testing."""
        return VectorAdapter(vector_config)
    
    def test_connect_placeholder(self, vector_adapter):
        """Test placeholder vector adapter connection."""
        result = vector_adapter.connect()
        
        assert result is True
        assert vector_adapter.is_connected() is True
    
    def test_connect_unsupported_backend(self, vector_adapter):
        """Test connection with unsupported backend."""
        vector_adapter.backend = "unsupported"
        
        with pytest.raises(NotImplementedError):
            vector_adapter.connect()
    
    def test_health_check(self, vector_adapter):
        """Test vector adapter health check."""
        vector_adapter.connect()
        
        health = vector_adapter.health_check()
        
        assert health["status"] == "healthy"
        assert health["backend"] == "placeholder"
        assert health["dimension"] == 768
        assert health["metric"] == "cosine"
    
    def test_index_embedding_placeholder(self, vector_adapter):
        """Test indexing embedding in placeholder mode."""
        vector_adapter.connect()
        
        embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        metadata = {"type": "document", "id": "doc_1"}
        
        result = vector_adapter.index_embedding("embedding_1", embedding, metadata)
        
        assert result is True
    
    def test_query_embeddings_placeholder(self, vector_adapter):
        """Test querying embeddings in placeholder mode."""
        vector_adapter.connect()
        
        query_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        
        result = vector_adapter.query_embeddings(query_embedding, top_k=5)
        
        assert result == []  # Placeholder returns empty list
    
    def test_delete_embedding_placeholder(self, vector_adapter):
        """Test deleting embedding in placeholder mode."""
        vector_adapter.connect()
        
        result = vector_adapter.delete_embedding("embedding_1")
        
        assert result is True
    
    def test_get_embedding_stats(self, vector_adapter):
        """Test getting embedding statistics."""
        vector_adapter.connect()
        
        stats = vector_adapter.get_embedding_stats()
        
        assert stats["backend"] == "placeholder"
        assert stats["dimension"] == 768
        assert stats["total_embeddings"] == 0


class TestMemoryAPI:
    """Test cases for MemoryAPI."""
    
    @pytest.fixture
    def memory_api_config(self):
        """Memory API configuration for testing."""
        return {
            "redis_config": {
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "key_prefix": "test:"
            },
            "postgres_config": {
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "user": "test_user",
                "password": "test_password"
            },
            "vector_config": {
                "backend": "placeholder",
                "dimension": 768
            }
        }
    
    @pytest.fixture
    def memory_api(self, memory_api_config):
        """Memory API instance for testing."""
        return MemoryAPI(
            redis_config=memory_api_config["redis_config"],
            postgres_config=memory_api_config["postgres_config"],
            vector_config=memory_api_config["vector_config"]
        )
    
    @patch('memory.api.RedisAdapter')
    @patch('memory.api.PostgresAdapter')
    @patch('memory.api.VectorAdapter')
    def test_connect_all_adapters(self, mock_vector, mock_postgres, mock_redis, memory_api):
        """Test connecting to all adapters."""
        # Mock successful connections
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = True
        mock_redis.return_value = mock_redis_instance
        
        mock_postgres_instance = Mock()
        mock_postgres_instance.connect.return_value = True
        mock_postgres.return_value = mock_postgres_instance
        
        mock_vector_instance = Mock()
        mock_vector_instance.connect.return_value = True
        mock_vector.return_value = mock_vector_instance
        
        result = memory_api.connect()
        
        assert result is True
        assert memory_api.is_connected() is True
        mock_redis_instance.connect.assert_called_once()
        mock_postgres_instance.connect.assert_called_once()
        mock_vector_instance.connect.assert_called_once()
    
    @patch('memory.api.RedisAdapter')
    def test_connect_partial_failure(self, mock_redis, memory_api):
        """Test connection with partial adapter failure."""
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = False
        mock_redis.return_value = mock_redis_instance
        
        result = memory_api.connect()
        
        assert result is False
        assert memory_api.is_connected() is False
    
    @patch('memory.api.RedisAdapter')
    def test_get_set_context(self, mock_redis, memory_api):
        """Test context get/set operations."""
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = True
        mock_redis_instance.get.return_value = json.dumps({
            "data": {"key": "value"},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "context_id": "test_context"
        })
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance
        memory_api.connect()
        
        # Test set context
        context_data = {"key": "value"}
        result = memory_api.set_context("test_context", context_data)
        assert result is True
        
        # Test get context
        retrieved_context = memory_api.get_context("test_context")
        assert retrieved_context is not None
        assert retrieved_context["data"]["key"] == "value"
    
    @patch('memory.api.RedisAdapter')
    def test_append_event(self, mock_redis, memory_api):
        """Test appending events to context."""
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = True
        mock_redis_instance.get.return_value = json.dumps({
            "data": {},
            "events": []
        })
        mock_redis_instance.set.return_value = True
        mock_redis.return_value = mock_redis_instance
        memory_api.connect()
        
        event = {"type": "task_completed", "task_id": "task_1"}
        result = memory_api.append_event("test_context", event)
        
        assert result is True
    
    @patch('memory.api.RedisAdapter')
    def test_clear_context(self, mock_redis, memory_api):
        """Test clearing context."""
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = True
        mock_redis_instance.delete.return_value = True
        mock_redis.return_value = mock_redis_instance
        memory_api.connect()
        
        result = memory_api.clear_context("test_context")
        
        assert result is True
        mock_redis_instance.delete.assert_called_with("context:test_context")
    
    @patch('memory.api.PostgresAdapter')
    def test_write_flow_run_history(self, mock_postgres, memory_api):
        """Test writing flow run history."""
        mock_postgres_instance = Mock()
        mock_postgres_instance.connect.return_value = True
        mock_postgres_instance.write_flow_run_history.return_value = True
        mock_postgres.return_value = mock_postgres_instance
        memory_api.connect()
        
        data = {"status": "completed", "duration": 120}
        result = memory_api.write_flow_run_history("flow_1", "run_1", data)
        
        assert result is True
        mock_postgres_instance.write_flow_run_history.assert_called_with("flow_1", "run_1", data)
    
    @patch('memory.api.PostgresAdapter')
    def test_write_task_output(self, mock_postgres, memory_api):
        """Test writing task output."""
        mock_postgres_instance = Mock()
        mock_postgres_instance.connect.return_value = True
        mock_postgres_instance.write_task_output.return_value = True
        mock_postgres.return_value = mock_postgres_instance
        memory_api.connect()
        
        output = {"result": "success"}
        metadata = {"execution_time": 5.2}
        result = memory_api.write_task_output("task_1", output, metadata)
        
        assert result is True
        mock_postgres_instance.write_task_output.assert_called_with("task_1", output, metadata)
    
    @patch('memory.api.VectorAdapter')
    def test_index_embedding(self, mock_vector, memory_api):
        """Test indexing embedding."""
        mock_vector_instance = Mock()
        mock_vector_instance.connect.return_value = True
        mock_vector_instance.index_embedding.return_value = True
        mock_vector.return_value = mock_vector_instance
        memory_api.connect()
        
        embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        metadata = {"type": "document"}
        result = memory_api.index_embedding("embedding_1", embedding, metadata)
        
        assert result is True
        mock_vector_instance.index_embedding.assert_called_with("embedding_1", embedding, metadata)
    
    @patch('memory.api.VectorAdapter')
    def test_query_embeddings(self, mock_vector, memory_api):
        """Test querying embeddings."""
        mock_vector_instance = Mock()
        mock_vector_instance.connect.return_value = True
        mock_vector_instance.query_embeddings.return_value = []
        mock_vector.return_value = mock_vector_instance
        memory_api.connect()
        
        query_embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
        result = memory_api.query_embeddings(query_embedding, top_k=5)
        
        assert result == []
        mock_vector_instance.query_embeddings.assert_called_with(query_embedding, 5, None)
    
    @patch('memory.api.RedisAdapter')
    def test_acquire_lock(self, mock_redis, memory_api):
        """Test distributed lock acquisition."""
        mock_redis_instance = Mock()
        mock_redis_instance.connect.return_value = True
        mock_lock = Mock()
        mock_redis_instance.lock.return_value.__enter__ = Mock(return_value=mock_lock)
        mock_redis_instance.lock.return_value.__exit__ = Mock(return_value=None)
        mock_redis.return_value = mock_redis_instance
        memory_api.connect()
        
        with memory_api.acquire_lock("test_lock") as lock:
            assert lock is not None
        
        mock_redis_instance.lock.assert_called_with("test:lock:test_lock", timeout=10, blocking_timeout=5)
    
    def test_health_check(self, memory_api):
        """Test health check."""
        health = memory_api.health_check()
        
        assert "overall_status" in health
        assert "timestamp" in health
        assert "adapters" in health
    
    def test_get_memory_stats(self, memory_api):
        """Test getting memory statistics."""
        stats = memory_api.get_memory_stats()
        
        assert "timestamp" in stats
        assert "adapters" in stats


class TestGlobalMemoryAPI:
    """Test cases for global Memory API functions."""
    
    @patch('memory.api.MemoryAPI')
    def test_initialize_memory_api(self, mock_memory_api_class):
        """Test initializing global memory API."""
        mock_memory_api = Mock()
        mock_memory_api.connect.return_value = True
        mock_memory_api_class.return_value = mock_memory_api
        
        redis_config = {"host": "localhost", "port": 6379}
        postgres_config = {"host": "localhost", "database": "test"}
        vector_config = {"backend": "placeholder"}
        
        result = initialize_memory_api(redis_config, postgres_config, vector_config)
        
        assert result == mock_memory_api
        mock_memory_api.connect.assert_called_once()
    
    @patch('memory.api._global_memory_api')
    def test_get_global_memory_api(self, mock_global_api):
        """Test getting global memory API."""
        mock_api = Mock()
        mock_global_api = mock_api
        
        result = get_global_memory_api()
        
        assert result == mock_api


class TestIntegration:
    """Integration tests for memory components."""
    
    @pytest.mark.integration
    @patch('memory.adapter.redis.Redis')
    @patch('memory.adapter.psycopg2.connect')
    def test_full_workflow(self, mock_postgres_connect, mock_redis_class):
        """Test full workflow with all adapters."""
        # Mock Redis
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis.get.return_value = None
        mock_redis.set.return_value = True
        mock_redis_class.return_value = mock_redis
        
        # Mock PostgreSQL
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_postgres_connect.return_value = mock_conn
        
        # Initialize Memory API
        memory_api = MemoryAPI(
            redis_config={"host": "localhost", "port": 6379},
            postgres_config={"host": "localhost", "database": "test"},
            vector_config={"backend": "placeholder"}
        )
        
        # Connect
        assert memory_api.connect() is True
        
        # Test context operations
        context_data = {"user_id": "user_1", "session_id": "session_1"}
        assert memory_api.set_context("context_1", context_data) is True
        
        # Test event operations
        event = {"type": "user_action", "action": "login"}
        assert memory_api.append_event("context_1", event) is True
        
        # Test flow run history
        flow_data = {"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}
        assert memory_api.write_flow_run_history("flow_1", "run_1", flow_data) is True
        
        # Test task output
        task_output = {"result": "success", "output": "Task completed"}
        assert memory_api.write_task_output("task_1", task_output) is True
        
        # Test embedding operations
        embedding = [0.1] * 768
        assert memory_api.index_embedding("embedding_1", embedding) is True
        
        # Test health check
        health = memory_api.health_check()
        assert health["overall_status"] in ["healthy", "degraded"]
        
        # Disconnect
        memory_api.disconnect()
        assert memory_api.is_connected() is False


if __name__ == "__main__":
    pytest.main([__file__])
