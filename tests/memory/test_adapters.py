"""
Test cases for Memory Adapter Layer.

This module contains unit tests for individual memory adapters.
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from memory.adapter import RedisAdapter, PostgresAdapter, VectorAdapter


class TestRedisAdapterUnit:
    """Unit tests for RedisAdapter."""
    
    def test_initialization(self):
        """Test RedisAdapter initialization."""
        config = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "key_prefix": "test:"
        }
        
        adapter = RedisAdapter(config)
        
        assert adapter.host == "localhost"
        assert adapter.port == 6379
        assert adapter.db == 0
        assert adapter.key_prefix == "test:"
        assert adapter.is_connected() is False
    
    def test_key_prefixing(self):
        """Test that keys are properly prefixed."""
        config = {"key_prefix": "agent:"}
        adapter = RedisAdapter(config)
        
        # Mock Redis client
        adapter._redis_client = Mock()
        adapter._connected = True
        
        adapter.get("test_key")
        adapter._redis_client.get.assert_called_with("agent:test_key")
        
        adapter.set("test_key", "value")
        adapter._redis_client.set.assert_called_with("agent:test_key", "value")
    
    def test_connection_pool_configuration(self):
        """Test connection pool configuration."""
        config = {
            "host": "redis.example.com",
            "port": 6380,
            "db": 5,
            "password": "secret",
            "max_connections": 100,
            "connection_timeout": 10,
            "socket_timeout": 15
        }
        
        adapter = RedisAdapter(config)
        
        assert adapter.host == "redis.example.com"
        assert adapter.port == 6380
        assert adapter.db == 5
        assert adapter.password == "secret"
        assert adapter.max_connections == 100
        assert adapter.connection_timeout == 10
        assert adapter.socket_timeout == 15
    
    @patch('memory.adapter.redis.ConnectionPool')
    @patch('memory.adapter.redis.Redis')
    def test_connection_pool_creation(self, mock_redis_class, mock_pool_class):
        """Test connection pool creation."""
        mock_pool = Mock()
        mock_pool_class.return_value = mock_pool
        
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis
        
        config = {
            "host": "localhost",
            "port": 6379,
            "max_connections": 50
        }
        
        adapter = RedisAdapter(config)
        adapter.connect()
        
        mock_pool_class.assert_called_once()
        mock_redis_class.assert_called_once_with(connection_pool=mock_pool)
    
    def test_lock_context_manager(self):
        """Test lock context manager functionality."""
        config = {}
        adapter = RedisAdapter(config)
        
        # Mock Redis client and lock
        mock_redis = Mock()
        mock_lock = Mock()
        mock_redis.lock.return_value.__enter__ = Mock(return_value=mock_lock)
        mock_redis.lock.return_value.__exit__ = Mock(return_value=None)
        
        adapter._redis_client = mock_redis
        adapter._connected = True
        
        with adapter.lock("test_lock", timeout=5, blocking_timeout=2) as lock:
            assert lock == mock_lock
        
        mock_redis.lock.assert_called_with("test:lock:test_lock", timeout=5, blocking_timeout=2)
        mock_lock.release.assert_called_once()
    
    def test_health_check_with_error(self):
        """Test health check when Redis is not available."""
        config = {}
        adapter = RedisAdapter(config)
        
        # Mock Redis client that raises exception
        adapter._redis_client = Mock()
        adapter._redis_client.ping.side_effect = Exception("Connection failed")
        
        health = adapter.health_check()
        
        assert health["status"] == "error"
        assert "Connection failed" in health["error"]


class TestPostgresAdapterUnit:
    """Unit tests for PostgresAdapter."""
    
    def test_initialization(self):
        """Test PostgresAdapter initialization."""
        config = {
            "host": "localhost",
            "port": 5432,
            "database": "test_db",
            "user": "test_user",
            "password": "test_password"
        }
        
        adapter = PostgresAdapter(config)
        
        assert adapter.host == "localhost"
        assert adapter.port == 5432
        assert adapter.database == "test_db"
        assert adapter.user == "test_user"
        assert adapter.password == "test_password"
        assert adapter.is_connected() is False
    
    def test_connection_string_building(self):
        """Test connection string building."""
        config = {
            "host": "db.example.com",
            "port": 5433,
            "database": "prod_db",
            "user": "prod_user",
            "password": "prod_password",
            "connection_timeout": 60
        }
        
        adapter = PostgresAdapter(config)
        
        # Mock connection
        with patch('memory.adapter.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_conn.close = Mock()
            mock_connect.return_value = mock_conn
            
            adapter.connect()
            
            # Verify connection string
            call_args = mock_connect.call_args[0][0]
            assert "host=db.example.com" in call_args
            assert "port=5433" in call_args
            assert "dbname=prod_db" in call_args
            assert "user=prod_user" in call_args
            assert "password=prod_password" in call_args
            assert "connect_timeout=60" in call_args
    
    def test_flow_run_history_json_serialization(self):
        """Test JSON serialization in flow run history."""
        config = {}
        adapter = PostgresAdapter(config)
        
        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        adapter._connection = mock_conn
        adapter._connection_string = "test_connection"
        
        with patch.object(adapter, '_get_connection', return_value=mock_conn):
            mock_conn.cursor.return_value = mock_cursor
            
            # Test data with complex objects
            data = {
                "status": "completed",
                "metrics": {
                    "duration": 120.5,
                    "memory_usage": [100, 200, 150],
                    "nested": {"key": "value"}
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            adapter.write_flow_run_history("flow_1", "run_1", data)
            
            # Verify JSON serialization
            call_args = mock_cursor.execute.call_args[0]
            json_data = call_args[1][2]  # Third parameter should be JSON data
            
            # Should be a string (JSON serialized)
            assert isinstance(json_data, str)
            
            # Should be valid JSON
            parsed_data = json.loads(json_data)
            assert parsed_data["status"] == "completed"
            assert parsed_data["metrics"]["duration"] == 120.5
    
    def test_task_output_with_metadata(self):
        """Test task output with metadata."""
        config = {}
        adapter = PostgresAdapter(config)
        
        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        adapter._connection = mock_conn
        adapter._connection_string = "test_connection"
        
        with patch.object(adapter, '_get_connection', return_value=mock_conn):
            mock_conn.cursor.return_value = mock_cursor
            
            output = {"result": "success", "data": [1, 2, 3]}
            metadata = {"execution_time": 5.2, "memory_peak": 1024}
            
            adapter.write_task_output("task_1", output, metadata)
            
            # Verify both output and metadata are JSON serialized
            call_args = mock_cursor.execute.call_args[0]
            output_json = call_args[1][1]
            metadata_json = call_args[1][2]
            
            assert isinstance(output_json, str)
            assert isinstance(metadata_json, str)
            
            parsed_output = json.loads(output_json)
            parsed_metadata = json.loads(metadata_json)
            
            assert parsed_output["result"] == "success"
            assert parsed_metadata["execution_time"] == 5.2
    
    def test_audit_entry_logging(self):
        """Test audit entry logging."""
        config = {}
        adapter = PostgresAdapter(config)
        
        # Mock connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        adapter._connection = mock_conn
        adapter._connection_string = "test_connection"
        
        with patch.object(adapter, '_get_connection', return_value=mock_conn):
            mock_conn.cursor.return_value = mock_cursor
            
            data = {
                "user": "test_user",
                "ip_address": "192.168.1.1",
                "user_agent": "Mozilla/5.0",
                "changes": {"field": "old_value", "new_value": "new_value"}
            }
            
            adapter.write_audit_entry("flow", "flow_1", "update", data)
            
            # Verify audit entry structure
            call_args = mock_cursor.execute.call_args[0]
            entity_type = call_args[1][0]
            entity_id = call_args[1][1]
            action = call_args[1][2]
            data_json = call_args[1][3]
            
            assert entity_type == "flow"
            assert entity_id == "flow_1"
            assert action == "update"
            assert isinstance(data_json, str)
            
            parsed_data = json.loads(data_json)
            assert parsed_data["user"] == "test_user"
            assert parsed_data["ip_address"] == "192.168.1.1"


class TestVectorAdapterUnit:
    """Unit tests for VectorAdapter."""
    
    def test_initialization(self):
        """Test VectorAdapter initialization."""
        config = {
            "backend": "pinecone",
            "dimension": 1024,
            "metric": "euclidean",
            "namespace": "production"
        }
        
        adapter = VectorAdapter(config)
        
        assert adapter.backend == "pinecone"
        assert adapter.dimension == 1024
        assert adapter.metric == "euclidean"
        assert adapter.namespace == "production"
        assert adapter.is_connected() is False
    
    def test_placeholder_backend_connection(self):
        """Test placeholder backend connection."""
        config = {"backend": "placeholder"}
        adapter = VectorAdapter(config)
        
        result = adapter.connect()
        
        assert result is True
        assert adapter.is_connected() is True
    
    def test_unsupported_backend_connection(self):
        """Test connection with unsupported backend."""
        config = {"backend": "unsupported_backend"}
        adapter = VectorAdapter(config)
        
        with pytest.raises(NotImplementedError, match="Vector backend 'unsupported_backend' not implemented yet"):
            adapter.connect()
    
    def test_embedding_dimension_validation(self):
        """Test embedding dimension validation."""
        config = {"backend": "placeholder", "dimension": 512}
        adapter = VectorAdapter(config)
        adapter.connect()
        
        # Test with correct dimension
        embedding = [0.1] * 512
        result = adapter.index_embedding("test_id", embedding)
        assert result is True
        
        # Test with incorrect dimension (should still work in placeholder mode)
        embedding_wrong = [0.1] * 256
        result = adapter.index_embedding("test_id_2", embedding_wrong)
        assert result is True  # Placeholder doesn't validate dimensions
    
    def test_metadata_handling(self):
        """Test metadata handling in vector operations."""
        config = {"backend": "placeholder"}
        adapter = VectorAdapter(config)
        adapter.connect()
        
        embedding = [0.1] * 768
        metadata = {
            "type": "document",
            "source": "pdf",
            "language": "en",
            "nested": {"key": "value", "number": 42}
        }
        
        result = adapter.index_embedding("doc_1", embedding, metadata)
        assert result is True
    
    def test_query_parameters(self):
        """Test query parameters."""
        config = {"backend": "placeholder"}
        adapter = VectorAdapter(config)
        adapter.connect()
        
        query_embedding = [0.1] * 768
        filter_metadata = {"type": "document", "language": "en"}
        
        result = adapter.query_embeddings(
            query_embedding, 
            top_k=20, 
            filter_metadata=filter_metadata
        )
        
        assert result == []  # Placeholder returns empty list
    
    def test_embedding_stats(self):
        """Test embedding statistics."""
        config = {
            "backend": "placeholder",
            "dimension": 768,
            "metric": "cosine",
            "namespace": "test"
        }
        
        adapter = VectorAdapter(config)
        adapter.connect()
        
        stats = adapter.get_embedding_stats()
        
        assert stats["backend"] == "placeholder"
        assert stats["dimension"] == 768
        assert stats["metric"] == "cosine"
        assert stats["namespace"] == "test"
        assert stats["total_embeddings"] == 0
        assert stats["status"] == "placeholder_mode"
    
    def test_error_handling_in_operations(self):
        """Test error handling in vector operations."""
        config = {"backend": "placeholder"}
        adapter = VectorAdapter(config)
        
        # Test operations when not connected
        embedding = [0.1] * 768
        
        assert adapter.index_embedding("test_id", embedding) is False
        assert adapter.query_embeddings(embedding) == []
        assert adapter.delete_embedding("test_id") is False
        
        # Test operations when connected
        adapter.connect()
        
        assert adapter.index_embedding("test_id", embedding) is True
        assert adapter.query_embeddings(embedding) == []
        assert adapter.delete_embedding("test_id") is True


class TestAdapterErrorHandling:
    """Test error handling across all adapters."""
    
    def test_redis_adapter_error_handling(self):
        """Test Redis adapter error handling."""
        config = {}
        adapter = RedisAdapter(config)
        
        # Test operations when not connected
        assert adapter.get("key") is None
        assert adapter.set("key", "value") is False
        assert adapter.hget("hash", "field") is None
        assert adapter.hset("hash", "field", "value") is False
        assert adapter.delete("key") is False
    
    def test_postgres_adapter_error_handling(self):
        """Test PostgreSQL adapter error handling."""
        config = {}
        adapter = PostgresAdapter(config)
        
        # Test operations when not connected
        assert adapter.write_flow_run_history("flow", "run", {}) is False
        assert adapter.read_flow_run_history("flow") == []
        assert adapter.write_task_output("task", {}) is False
        assert adapter.read_task_output("task") is None
        assert adapter.write_audit_entry("entity", "id", "action", {}) is False
    
    def test_vector_adapter_error_handling(self):
        """Test Vector adapter error handling."""
        config = {"backend": "placeholder"}
        adapter = VectorAdapter(config)
        
        # Test operations when not connected
        embedding = [0.1] * 768
        assert adapter.index_embedding("id", embedding) is False
        assert adapter.query_embeddings(embedding) == []
        assert adapter.delete_embedding("id") is False
        
        # Test operations when connected
        adapter.connect()
        assert adapter.index_embedding("id", embedding) is True
        assert adapter.query_embeddings(embedding) == []
        assert adapter.delete_embedding("id") is True


if __name__ == "__main__":
    pytest.main([__file__])
