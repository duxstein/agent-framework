"""
Memory API for Enterprise AI Agent Framework.

This module provides a unified API for memory operations that orchestrator
and executor components can use to store and retrieve context, events,
and other memory-related data.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from contextlib import contextmanager

import structlog

from .adapter import RedisAdapter, PostgresAdapter, VectorAdapter, MemoryAdapter

logger = structlog.get_logger()


class MemoryAPI:
    """Unified Memory API for orchestrator and executor components."""
    
    def __init__(self, redis_config: Optional[Dict[str, Any]] = None,
                 postgres_config: Optional[Dict[str, Any]] = None,
                 vector_config: Optional[Dict[str, Any]] = None):
        """
        Initialize Memory API with adapter configurations.
        
        Args:
            redis_config: Redis adapter configuration
            postgres_config: PostgreSQL adapter configuration  
            vector_config: Vector adapter configuration
        """
        self.logger = logger.bind(component="memory_api")
        
        # Initialize adapters
        self.redis_adapter = None
        self.postgres_adapter = None
        self.vector_adapter = None
        
        if redis_config:
            self.redis_adapter = RedisAdapter(redis_config)
        
        if postgres_config:
            self.postgres_adapter = PostgresAdapter(postgres_config)
        
        if vector_config:
            self.vector_adapter = VectorAdapter(vector_config)
        
        self._connected = False
    
    def connect(self) -> bool:
        """Connect to all configured memory adapters."""
        try:
            success = True
            
            if self.redis_adapter:
                if not self.redis_adapter.connect():
                    self.logger.error("Failed to connect to Redis")
                    success = False
            
            if self.postgres_adapter:
                if not self.postgres_adapter.connect():
                    self.logger.error("Failed to connect to PostgreSQL")
                    success = False
            
            if self.vector_adapter:
                if not self.vector_adapter.connect():
                    self.logger.error("Failed to connect to Vector database")
                    success = False
            
            self._connected = success
            self.logger.info("Memory API connection status", connected=self._connected)
            return success
            
        except Exception as e:
            self.logger.error("Memory API connection failed", error=str(e))
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from all memory adapters."""
        if self.redis_adapter:
            self.redis_adapter.disconnect()
        
        if self.postgres_adapter:
            self.postgres_adapter.disconnect()
        
        if self.vector_adapter:
            self.vector_adapter.disconnect()
        
        self._connected = False
        self.logger.info("Memory API disconnected")
    
    def is_connected(self) -> bool:
        """Check if connected to memory adapters."""
        return self._connected
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all adapters."""
        health_status = {
            "overall_status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "adapters": {}
        }
        
        if self.redis_adapter:
            redis_health = self.redis_adapter.health_check()
            health_status["adapters"]["redis"] = redis_health
            if redis_health.get("status") != "healthy":
                health_status["overall_status"] = "degraded"
        
        if self.postgres_adapter:
            postgres_health = self.postgres_adapter.health_check()
            health_status["adapters"]["postgres"] = postgres_health
            if postgres_health.get("status") != "healthy":
                health_status["overall_status"] = "degraded"
        
        if self.vector_adapter:
            vector_health = self.vector_adapter.health_check()
            health_status["adapters"]["vector"] = vector_health
            if vector_health.get("status") != "healthy":
                health_status["overall_status"] = "degraded"
        
        return health_status
    
    # Context Management Methods
    
    def get_context(self, context_id: str) -> Optional[Dict[str, Any]]:
        """
        Get context by ID.
        
        Args:
            context_id: Unique context identifier
            
        Returns:
            Context data or None if not found
        """
        try:
            if not self.redis_adapter:
                self.logger.warning("Redis adapter not available for context retrieval")
                return None
            
            context_data = self.redis_adapter.get(f"context:{context_id}")
            if context_data:
                return json.loads(context_data)
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to get context", context_id=context_id, error=str(e))
            return None
    
    def set_context(self, context_id: str, context_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Set context data.
        
        Args:
            context_id: Unique context identifier
            context_data: Context data to store
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.redis_adapter:
                self.logger.warning("Redis adapter not available for context storage")
                return False
            
            # Add metadata
            context_with_metadata = {
                "data": context_data,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "context_id": context_id
            }
            
            success = self.redis_adapter.set(
                f"context:{context_id}",
                json.dumps(context_with_metadata),
                ttl
            )
            
            if success:
                self.logger.debug("Context stored", context_id=context_id)
            
            return success
            
        except Exception as e:
            self.logger.error("Failed to set context", context_id=context_id, error=str(e))
            return False
    
    def append_event(self, context_id: str, event: Dict[str, Any]) -> bool:
        """
        Append event to context.
        
        Args:
            context_id: Context identifier
            event: Event data to append
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.redis_adapter:
                self.logger.warning("Redis adapter not available for event storage")
                return False
            
            # Get existing context
            context_data = self.get_context(context_id)
            if context_data is None:
                context_data = {"data": {}, "events": []}
            elif "events" not in context_data:
                context_data["events"] = []
            
            # Add event with metadata
            event_with_metadata = {
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_id": str(uuid.uuid4())
            }
            
            context_data["events"].append(event_with_metadata)
            
            # Store updated context
            return self.set_context(context_id, context_data["data"], ttl=None)
            
        except Exception as e:
            self.logger.error("Failed to append event", context_id=context_id, error=str(e))
            return False
    
    def clear_context(self, context_id: str) -> bool:
        """
        Clear context data.
        
        Args:
            context_id: Context identifier to clear
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.redis_adapter:
                self.logger.warning("Redis adapter not available for context clearing")
                return False
            
            success = self.redis_adapter.delete(f"context:{context_id}")
            
            if success:
                self.logger.debug("Context cleared", context_id=context_id)
            
            return success
            
        except Exception as e:
            self.logger.error("Failed to clear context", context_id=context_id, error=str(e))
            return False
    
    def get_events(self, context_id: str) -> List[Dict[str, Any]]:
        """
        Get all events for a context.
        
        Args:
            context_id: Context identifier
            
        Returns:
            List of events
        """
        try:
            context_data = self.get_context(context_id)
            if context_data and "events" in context_data:
                return context_data["events"]
            
            return []
            
        except Exception as e:
            self.logger.error("Failed to get events", context_id=context_id, error=str(e))
            return []
    
    # Flow Run History Methods
    
    def write_flow_run_history(self, flow_id: str, run_id: str, data: Dict[str, Any]) -> bool:
        """
        Write flow run history entry.
        
        Args:
            flow_id: Flow identifier
            run_id: Run identifier
            data: Flow run data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.postgres_adapter:
                self.logger.warning("PostgreSQL adapter not available for flow run history")
                return False
            
            return self.postgres_adapter.write_flow_run_history(flow_id, run_id, data)
            
        except Exception as e:
            self.logger.error("Failed to write flow run history", flow_id=flow_id, run_id=run_id, error=str(e))
            return False
    
    def read_flow_run_history(self, flow_id: str, run_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Read flow run history entries.
        
        Args:
            flow_id: Flow identifier
            run_id: Optional run identifier
            limit: Maximum number of entries to return
            
        Returns:
            List of flow run history entries
        """
        try:
            if not self.postgres_adapter:
                self.logger.warning("PostgreSQL adapter not available for flow run history")
                return []
            
            return self.postgres_adapter.read_flow_run_history(flow_id, run_id, limit)
            
        except Exception as e:
            self.logger.error("Failed to read flow run history", flow_id=flow_id, run_id=run_id, error=str(e))
            return []
    
    # Task Output Methods
    
    def write_task_output(self, task_id: str, output: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Write task output.
        
        Args:
            task_id: Task identifier
            output: Task output data
            metadata: Optional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.postgres_adapter:
                self.logger.warning("PostgreSQL adapter not available for task output")
                return False
            
            return self.postgres_adapter.write_task_output(task_id, output, metadata)
            
        except Exception as e:
            self.logger.error("Failed to write task output", task_id=task_id, error=str(e))
            return False
    
    def read_task_output(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Read task output.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task output data or None if not found
        """
        try:
            if not self.postgres_adapter:
                self.logger.warning("PostgreSQL adapter not available for task output")
                return None
            
            return self.postgres_adapter.read_task_output(task_id)
            
        except Exception as e:
            self.logger.error("Failed to read task output", task_id=task_id, error=str(e))
            return None
    
    # Audit Methods
    
    def write_audit_entry(self, entity_type: str, entity_id: str, action: str, data: Dict[str, Any]) -> bool:
        """
        Write audit entry.
        
        Args:
            entity_type: Type of entity (flow, task, etc.)
            entity_id: Entity identifier
            action: Action performed
            data: Audit data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.postgres_adapter:
                self.logger.warning("PostgreSQL adapter not available for audit logging")
                return False
            
            return self.postgres_adapter.write_audit_entry(entity_type, entity_id, action, data)
            
        except Exception as e:
            self.logger.error("Failed to write audit entry", entity_type=entity_type, entity_id=entity_id, action=action, error=str(e))
            return False
    
    # Vector/Embedding Methods
    
    def index_embedding(self, id: str, embedding: List[float], metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Index an embedding vector.
        
        Args:
            id: Unique identifier for the embedding
            embedding: Vector embedding
            metadata: Optional metadata
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.vector_adapter:
                self.logger.warning("Vector adapter not available for embedding indexing")
                return False
            
            return self.vector_adapter.index_embedding(id, embedding, metadata)
            
        except Exception as e:
            self.logger.error("Failed to index embedding", id=id, error=str(e))
            return False
    
    def query_embeddings(self, query_embedding: List[float], top_k: int = 10, 
                         filter_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Query similar embeddings.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of similar embeddings
        """
        try:
            if not self.vector_adapter:
                self.logger.warning("Vector adapter not available for embedding querying")
                return []
            
            return self.vector_adapter.query_embeddings(query_embedding, top_k, filter_metadata)
            
        except Exception as e:
            self.logger.error("Failed to query embeddings", error=str(e))
            return []
    
    def delete_embedding(self, id: str) -> bool:
        """
        Delete an embedding by ID.
        
        Args:
            id: Embedding identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.vector_adapter:
                self.logger.warning("Vector adapter not available for embedding deletion")
                return False
            
            return self.vector_adapter.delete_embedding(id)
            
        except Exception as e:
            self.logger.error("Failed to delete embedding", id=id, error=str(e))
            return False
    
    # Distributed Locking Methods
    
    @contextmanager
    def acquire_lock(self, lock_name: str, timeout: int = 10, blocking_timeout: int = 5):
        """
        Acquire a distributed lock.
        
        Args:
            lock_name: Name of the lock
            timeout: Lock timeout in seconds
            blocking_timeout: Blocking timeout in seconds
            
        Yields:
            Lock object if successful
            
        Raises:
            Exception: If lock acquisition fails
        """
        if not self.redis_adapter:
            raise Exception("Redis adapter not available for distributed locking")
        
        with self.redis_adapter.lock(lock_name, timeout, blocking_timeout) as lock:
            yield lock
    
    # Utility Methods
    
    def get_context_keys(self, pattern: str = "*") -> List[str]:
        """
        Get context keys matching pattern.
        
        Args:
            pattern: Key pattern to match
            
        Returns:
            List of matching keys
        """
        try:
            if not self.redis_adapter:
                return []
            
            # This would require implementing a keys() method in RedisAdapter
            # For now, return empty list as it's not critical functionality
            self.logger.warning("Context key listing not implemented")
            return []
            
        except Exception as e:
            self.logger.error("Failed to get context keys", pattern=pattern, error=str(e))
            return []
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory usage statistics."""
        stats = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "adapters": {}
        }
        
        if self.redis_adapter:
            redis_health = self.redis_adapter.health_check()
            stats["adapters"]["redis"] = {
                "status": redis_health.get("status"),
                "used_memory": redis_health.get("used_memory"),
                "connected_clients": redis_health.get("connected_clients")
            }
        
        if self.postgres_adapter:
            postgres_health = self.postgres_adapter.health_check()
            stats["adapters"]["postgres"] = {
                "status": postgres_health.get("status"),
                "active_connections": postgres_health.get("active_connections")
            }
        
        if self.vector_adapter:
            vector_stats = self.vector_adapter.get_embedding_stats()
            stats["adapters"]["vector"] = vector_stats
        
        return stats


# Global Memory API instance
_global_memory_api: Optional[MemoryAPI] = None


def get_global_memory_api() -> Optional[MemoryAPI]:
    """Get the global Memory API instance."""
    return _global_memory_api


def set_global_memory_api(memory_api: MemoryAPI) -> None:
    """Set the global Memory API instance."""
    global _global_memory_api
    _global_memory_api = memory_api


def initialize_memory_api(redis_config: Optional[Dict[str, Any]] = None,
                         postgres_config: Optional[Dict[str, Any]] = None,
                         vector_config: Optional[Dict[str, Any]] = None) -> MemoryAPI:
    """
    Initialize and set the global Memory API instance.
    
    Args:
        redis_config: Redis adapter configuration
        postgres_config: PostgreSQL adapter configuration
        vector_config: Vector adapter configuration
        
    Returns:
        Initialized Memory API instance
    """
    global _global_memory_api
    
    memory_api = MemoryAPI(redis_config, postgres_config, vector_config)
    
    if memory_api.connect():
        _global_memory_api = memory_api
        logger.info("Global Memory API initialized successfully")
    else:
        logger.error("Failed to initialize global Memory API")
    
    return memory_api
