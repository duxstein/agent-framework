"""
Memory Adapter Layer for Enterprise AI Agent Framework.

This module provides adapters for different memory backends including Redis,
PostgreSQL, and Vector databases for storing and retrieving agent context,
events, and embeddings.
"""

import json
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union, Tuple
from contextlib import contextmanager

import structlog
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
from redis.lock import Lock

logger = structlog.get_logger()


class MemoryAdapter(ABC):
    """Abstract base class for memory adapters."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the memory adapter with configuration."""
        self.config = config
        self.logger = logger.bind(adapter=self.__class__.__name__)
        self._connected = False
    
    @abstractmethod
    def connect(self) -> bool:
        """Connect to the memory backend."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the memory backend."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to the memory backend."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on the memory backend."""
        pass


class RedisAdapter(MemoryAdapter):
    """Redis adapter for caching and distributed locking."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Redis adapter."""
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 6379)
        self.db = config.get("db", 0)
        self.password = config.get("password")
        self.connection_timeout = config.get("connection_timeout", 5)
        self.socket_timeout = config.get("socket_timeout", 5)
        self.max_connections = config.get("max_connections", 50)
        self.key_prefix = config.get("key_prefix", "agent_framework:")
        
        self._redis_client = None
        self._connection_pool = None
    
    def connect(self) -> bool:
        """Connect to Redis."""
        try:
            # Create connection pool
            self._connection_pool = redis.ConnectionPool(
                host=self.host,
                port=self.port,
                db=self.db,
                password=self.password,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.connection_timeout,
                max_connections=self.max_connections,
                decode_responses=True
            )
            
            # Create Redis client
            self._redis_client = redis.Redis(connection_pool=self._connection_pool)
            
            # Test connection
            self._redis_client.ping()
            
            self._connected = True
            self.logger.info("Redis connection established", host=self.host, port=self.port, db=self.db)
            return True
            
        except Exception as e:
            self.logger.error("Redis connection failed", error=str(e))
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._redis_client:
            self._redis_client.close()
        if self._connection_pool:
            self._connection_pool.disconnect()
        self._connected = False
        self.logger.info("Redis connection closed")
    
    def is_connected(self) -> bool:
        """Check if connected to Redis."""
        if not self._connected or not self._redis_client:
            return False
        
        try:
            self._redis_client.ping()
            return True
        except:
            self._connected = False
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform Redis health check."""
        try:
            if not self.is_connected():
                return {"status": "disconnected", "error": "Not connected to Redis"}
            
            # Test basic operations
            start_time = time.time()
            test_key = f"{self.key_prefix}health_check:{uuid.uuid4()}"
            
            # Test set/get
            self._redis_client.set(test_key, "test_value", ex=10)
            value = self._redis_client.get(test_key)
            self._redis_client.delete(test_key)
            
            # Get Redis info
            info = self._redis_client.info()
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "execution_time_ms": execution_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            if not self.is_connected():
                return None
            
            full_key = f"{self.key_prefix}{key}"
            return self._redis_client.get(full_key)
            
        except Exception as e:
            self.logger.error("Redis get failed", key=key, error=str(e))
            return None
    
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """Set key-value pair with optional TTL."""
        try:
            if not self.is_connected():
                return False
            
            full_key = f"{self.key_prefix}{key}"
            
            if ttl:
                return self._redis_client.setex(full_key, ttl, value)
            else:
                return self._redis_client.set(full_key, value)
                
        except Exception as e:
            self.logger.error("Redis set failed", key=key, error=str(e))
            return False
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        try:
            if not self.is_connected():
                return None
            
            full_name = f"{self.key_prefix}{name}"
            return self._redis_client.hget(full_name, key)
            
        except Exception as e:
            self.logger.error("Redis hget failed", name=name, key=key, error=str(e))
            return None
    
    def hset(self, name: str, key: str, value: str) -> bool:
        """Set hash field value."""
        try:
            if not self.is_connected():
                return False
            
            full_name = f"{self.key_prefix}{name}"
            return self._redis_client.hset(full_name, key, value) >= 0
            
        except Exception as e:
            self.logger.error("Redis hset failed", name=name, key=key, error=str(e))
            return False
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields and values."""
        try:
            if not self.is_connected():
                return {}
            
            full_name = f"{self.key_prefix}{name}"
            return self._redis_client.hgetall(full_name)
            
        except Exception as e:
            self.logger.error("Redis hgetall failed", name=name, error=str(e))
            return {}
    
    def delete(self, key: str) -> bool:
        """Delete key."""
        try:
            if not self.is_connected():
                return False
            
            full_key = f"{self.key_prefix}{key}"
            return self._redis_client.delete(full_key) > 0
            
        except Exception as e:
            self.logger.error("Redis delete failed", key=key, error=str(e))
            return False
    
    def acquire_lock(self, lock_name: str, timeout: int = 10, blocking_timeout: int = 5) -> Optional[Lock]:
        """Acquire a distributed lock using Redlock algorithm."""
        try:
            if not self.is_connected():
                return None
            
            full_lock_name = f"{self.key_prefix}lock:{lock_name}"
            
            # Create lock with timeout
            lock = self._redis_client.lock(
                full_lock_name,
                timeout=timeout,
                blocking_timeout=blocking_timeout
            )
            
            # Try to acquire lock
            if lock.acquire(blocking=False):
                self.logger.debug("Lock acquired", lock_name=lock_name)
                return lock
            else:
                self.logger.debug("Lock acquisition failed", lock_name=lock_name)
                return None
                
        except Exception as e:
            self.logger.error("Lock acquisition failed", lock_name=lock_name, error=str(e))
            return None
    
    @contextmanager
    def lock(self, lock_name: str, timeout: int = 10, blocking_timeout: int = 5):
        """Context manager for distributed locking."""
        lock = self.acquire_lock(lock_name, timeout, blocking_timeout)
        if lock:
            try:
                yield lock
            finally:
                lock.release()
                self.logger.debug("Lock released", lock_name=lock_name)
        else:
            raise Exception(f"Failed to acquire lock: {lock_name}")


class PostgresAdapter(MemoryAdapter):
    """PostgreSQL adapter for persistent storage and audit trails."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize PostgreSQL adapter."""
        super().__init__(config)
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 5432)
        self.database = config.get("database")
        self.user = config.get("user")
        self.password = config.get("password")
        self.connection_timeout = config.get("connection_timeout", 30)
        self.max_connections = config.get("max_connections", 10)
        self.schema = config.get("schema", "public")
        
        self._connection = None
        self._connection_string = None
    
    def connect(self) -> bool:
        """Connect to PostgreSQL."""
        try:
            # Build connection string
            self._connection_string = (
                f"host={self.host} "
                f"port={self.port} "
                f"dbname={self.database} "
                f"user={self.user} "
                f"password={self.password} "
                f"connect_timeout={self.connection_timeout}"
            )
            
            # Test connection
            self._connection = psycopg2.connect(self._connection_string)
            self._connection.close()
            
            self._connected = True
            self.logger.info("PostgreSQL connection established", host=self.host, database=self.database)
            return True
            
        except Exception as e:
            self.logger.error("PostgreSQL connection failed", error=str(e))
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from PostgreSQL."""
        if self._connection and not self._connection.closed:
            self._connection.close()
        self._connected = False
        self.logger.info("PostgreSQL connection closed")
    
    def is_connected(self) -> bool:
        """Check if connected to PostgreSQL."""
        if not self._connected or not self._connection:
            return False
        
        try:
            if self._connection.closed:
                return False
            
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except:
            self._connected = False
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform PostgreSQL health check."""
        try:
            if not self.is_connected():
                return {"status": "disconnected", "error": "Not connected to PostgreSQL"}
            
            start_time = time.time()
            
            # Get connection
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT version(), current_database(), current_user")
            version, db_name, user = cursor.fetchone()
            
            # Get connection info
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_connections = cursor.fetchone()[0]
            
            cursor.close()
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return {
                "status": "healthy",
                "host": self.host,
                "port": self.port,
                "database": db_name,
                "user": user,
                "version": version,
                "active_connections": active_connections,
                "execution_time_ms": execution_time,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _get_connection(self):
        """Get database connection."""
        if not self._connection or self._connection.closed:
            self._connection = psycopg2.connect(self._connection_string)
        return self._connection
    
    def write_flow_run_history(self, flow_id: str, run_id: str, data: Dict[str, Any]) -> bool:
        """Write flow run history entry."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                INSERT INTO flow_run_history (
                    flow_id, run_id, data, created_at
                ) VALUES (%s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                flow_id,
                run_id,
                json.dumps(data),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            
            self.logger.debug("Flow run history written", flow_id=flow_id, run_id=run_id)
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error("Failed to write flow run history", flow_id=flow_id, run_id=run_id, error=str(e))
            return False
    
    def read_flow_run_history(self, flow_id: str, run_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Read flow run history entries."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if run_id:
                query = """
                    SELECT * FROM flow_run_history 
                    WHERE flow_id = %s AND run_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """
                cursor.execute(query, (flow_id, run_id, limit))
            else:
                query = """
                    SELECT * FROM flow_run_history 
                    WHERE flow_id = %s 
                    ORDER BY created_at DESC 
                    LIMIT %s
                """
                cursor.execute(query, (flow_id, limit))
            
            rows = cursor.fetchall()
            cursor.close()
            
            # Convert to list of dicts and parse JSON data
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict.get('data'):
                    row_dict['data'] = json.loads(row_dict['data'])
                result.append(row_dict)
            
            return result
            
        except Exception as e:
            self.logger.error("Failed to read flow run history", flow_id=flow_id, run_id=run_id, error=str(e))
            return []
    
    def write_task_output(self, task_id: str, output: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Write task output."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                INSERT INTO task_outputs (
                    task_id, output, metadata, created_at
                ) VALUES (%s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                task_id,
                json.dumps(output),
                json.dumps(metadata) if metadata else None,
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            
            self.logger.debug("Task output written", task_id=task_id)
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error("Failed to write task output", task_id=task_id, error=str(e))
            return False
    
    def read_task_output(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Read task output."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                SELECT * FROM task_outputs 
                WHERE task_id = %s 
                ORDER BY created_at DESC 
                LIMIT 1
            """
            
            cursor.execute(query, (task_id,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                result = dict(row)
                if result.get('output'):
                    result['output'] = json.loads(result['output'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                return result
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to read task output", task_id=task_id, error=str(e))
            return None
    
    def write_audit_entry(self, entity_type: str, entity_id: str, action: str, data: Dict[str, Any]) -> bool:
        """Write audit entry."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            query = """
                INSERT INTO audit_log (
                    entity_type, entity_id, action, data, created_at
                ) VALUES (%s, %s, %s, %s, %s)
            """
            
            cursor.execute(query, (
                entity_type,
                entity_id,
                action,
                json.dumps(data),
                datetime.now(timezone.utc)
            ))
            
            conn.commit()
            cursor.close()
            
            self.logger.debug("Audit entry written", entity_type=entity_type, entity_id=entity_id, action=action)
            return True
            
        except Exception as e:
            if conn:
                conn.rollback()
            self.logger.error("Failed to write audit entry", entity_type=entity_type, entity_id=entity_id, action=action, error=str(e))
            return False


class VectorAdapter(MemoryAdapter):
    """Vector database adapter for embedding storage and similarity search."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Vector adapter."""
        super().__init__(config)
        self.backend = config.get("backend", "placeholder")  # placeholder, pinecone, weaviate, etc.
        self.dimension = config.get("dimension", 768)
        self.metric = config.get("metric", "cosine")  # cosine, euclidean, dotproduct
        self.namespace = config.get("namespace", "default")
        
        self._vector_client = None
    
    def connect(self) -> bool:
        """Connect to vector database."""
        try:
            if self.backend == "placeholder":
                # Placeholder implementation - just mark as connected
                self._connected = True
                self.logger.info("Vector adapter connected (placeholder mode)", backend=self.backend)
                return True
            else:
                # TODO: Implement actual vector database connections
                # For now, raise NotImplementedError for non-placeholder backends
                raise NotImplementedError(f"Vector backend '{self.backend}' not implemented yet")
                
        except Exception as e:
            self.logger.error("Vector adapter connection failed", error=str(e))
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from vector database."""
        self._vector_client = None
        self._connected = False
        self.logger.info("Vector adapter disconnected")
    
    def is_connected(self) -> bool:
        """Check if connected to vector database."""
        return self._connected
    
    def health_check(self) -> Dict[str, Any]:
        """Perform vector database health check."""
        try:
            if not self.is_connected():
                return {"status": "disconnected", "error": "Not connected to vector database"}
            
            return {
                "status": "healthy",
                "backend": self.backend,
                "dimension": self.dimension,
                "metric": self.metric,
                "namespace": self.namespace,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def index_embedding(self, id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Index an embedding vector.
        
        Args:
            id: Unique identifier for the embedding
            embedding: Vector embedding (list of floats)
            metadata: Optional metadata associated with the embedding
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            if self.backend == "placeholder":
                # Placeholder implementation - just log the operation
                self.logger.debug("Indexing embedding (placeholder)", id=id, dimension=len(embedding))
                return True
            else:
                # TODO: Implement actual vector indexing
                raise NotImplementedError(f"Vector indexing for backend '{self.backend}' not implemented yet")
                
        except Exception as e:
            self.logger.error("Failed to index embedding", id=id, error=str(e))
            return False
    
    def query_embeddings(self, query_embedding: List[float], top_k: int = 10, 
                         filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Query similar embeddings.
        
        Args:
            query_embedding: Query vector embedding
            top_k: Number of similar embeddings to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of similar embeddings with scores and metadata
        """
        try:
            if not self.is_connected():
                return []
            
            if self.backend == "placeholder":
                # Placeholder implementation - return empty results
                self.logger.debug("Querying embeddings (placeholder)", top_k=top_k)
                return []
            else:
                # TODO: Implement actual vector querying
                raise NotImplementedError(f"Vector querying for backend '{self.backend}' not implemented yet")
                
        except Exception as e:
            self.logger.error("Failed to query embeddings", error=str(e))
            return []
    
    def delete_embedding(self, id: str) -> bool:
        """
        Delete an embedding by ID.
        
        Args:
            id: Unique identifier for the embedding
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            if self.backend == "placeholder":
                # Placeholder implementation - just log the operation
                self.logger.debug("Deleting embedding (placeholder)", id=id)
                return True
            else:
                # TODO: Implement actual vector deletion
                raise NotImplementedError(f"Vector deletion for backend '{self.backend}' not implemented yet")
                
        except Exception as e:
            self.logger.error("Failed to delete embedding", id=id, error=str(e))
            return False
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding statistics."""
        try:
            if not self.is_connected():
                return {"error": "Not connected to vector database"}
            
            if self.backend == "placeholder":
                return {
                    "backend": self.backend,
                    "dimension": self.dimension,
                    "metric": self.metric,
                    "namespace": self.namespace,
                    "total_embeddings": 0,  # Placeholder
                    "status": "placeholder_mode"
                }
            else:
                # TODO: Implement actual stats retrieval
                raise NotImplementedError(f"Stats retrieval for backend '{self.backend}' not implemented yet")
                
        except Exception as e:
            self.logger.error("Failed to get embedding stats", error=str(e))
            return {"error": str(e)}
