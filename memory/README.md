# Memory Adapter Layer

The Memory Adapter Layer provides a unified interface for storing and retrieving agent context, events, flow run history, task outputs, and vector embeddings across multiple backend storage systems.

## Overview

The memory layer consists of three main components:

1. **Memory Adapters** (`memory/adapter.py`) - Backend-specific implementations
2. **Memory API** (`memory/api.py`) - Unified interface for orchestrator/executor
3. **Database Migrations** (`infra/migrations/`) - SQL schema definitions

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Orchestrator  │    │    Executor     │    │   Other Apps    │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼─────────────┐
                    │      Memory API          │
                    │   (Unified Interface)    │
                    └─────────────┬─────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
    ┌─────▼─────┐         ┌─────▼─────┐         ┌─────▼─────┐
    │   Redis   │         │PostgreSQL │         │  Vector   │
    │ Adapter   │         │ Adapter   │         │ Adapter   │
    └───────────┘         └───────────┘         └───────────┘
```

## Features

### Redis Adapter
- **Context Storage**: Fast key-value storage for agent context
- **Event Logging**: Append-only event streams
- **Distributed Locking**: Redlock algorithm for critical sections
- **TTL Support**: Automatic expiration of context data
- **Connection Pooling**: Efficient connection management

### PostgreSQL Adapter
- **Flow Run History**: Persistent storage of flow execution data
- **Task Outputs**: Structured storage of task results and metadata
- **Audit Logging**: Comprehensive audit trail for all operations
- **ACID Compliance**: Transactional integrity
- **JSON Support**: Native JSONB for flexible data structures

### Vector Adapter
- **Embedding Storage**: High-dimensional vector storage
- **Similarity Search**: Cosine, Euclidean, and dot product metrics
- **Metadata Filtering**: Query embeddings with metadata constraints
- **Scalable**: Designed for large-scale vector operations
- **Extensible**: Placeholder implementation for easy backend switching

## Quick Start

### 1. Install Dependencies

```bash
pip install redis psycopg2-binary structlog
```

### 2. Database Setup

Run the migration scripts to create the required tables:

```bash
# Apply migrations
psql -d your_database -f infra/migrations/001_create_memory_tables.sql
psql -d your_database -f infra/migrations/002_add_memory_indexes.sql
psql -d your_database -f infra/migrations/003_add_memory_partitions.sql
```

### 3. Basic Usage

```python
from memory.api import MemoryAPI

# Initialize Memory API
memory_api = MemoryAPI(
    redis_config={
        "host": "localhost",
        "port": 6379,
        "key_prefix": "agent_framework:"
    },
    postgres_config={
        "host": "localhost",
        "database": "agent_framework",
        "user": "postgres",
        "password": "password"
    },
    vector_config={
        "backend": "placeholder",  # or "pinecone", "weaviate", etc.
        "dimension": 768
    }
)

# Connect to all adapters
if memory_api.connect():
    print("Connected to all memory adapters")
    
    # Store context
    context_data = {"user_id": "user_123", "session_id": "session_456"}
    memory_api.set_context("user_session_123", context_data, ttl=3600)
    
    # Retrieve context
    retrieved_context = memory_api.get_context("user_session_123")
    print(f"User ID: {retrieved_context['data']['user_id']}")
    
    # Append events
    event = {"type": "user_action", "action": "login"}
    memory_api.append_event("user_session_123", event)
    
    # Store flow run history
    flow_data = {"status": "completed", "duration": 120}
    memory_api.write_flow_run_history("flow_001", "run_001", flow_data)
    
    # Store task output
    task_output = {"result": "success", "data": [1, 2, 3]}
    memory_api.write_task_output("task_001", task_output)
    
    # Index embeddings
    embedding = [0.1, 0.2, 0.3] * 256  # 768 dimensions
    memory_api.index_embedding("doc_001", embedding, {"type": "document"})
    
    # Query similar embeddings
    similar_docs = memory_api.query_embeddings(embedding, top_k=5)
    
    # Distributed locking
    with memory_api.acquire_lock("critical_section"):
        # Perform critical operations
        pass
    
    # Clean up
    memory_api.clear_context("user_session_123")
    memory_api.disconnect()
```

## Configuration

### Redis Configuration

```python
redis_config = {
    "host": "localhost",           # Redis host
    "port": 6379,                 # Redis port
    "db": 0,                      # Redis database number
    "password": None,             # Redis password (optional)
    "connection_timeout": 5,      # Connection timeout in seconds
    "socket_timeout": 5,          # Socket timeout in seconds
    "max_connections": 50,        # Maximum connections in pool
    "key_prefix": "agent_framework:"  # Key prefix for namespacing
}
```

### PostgreSQL Configuration

```python
postgres_config = {
    "host": "localhost",          # PostgreSQL host
    "port": 5432,                 # PostgreSQL port
    "database": "agent_framework", # Database name
    "user": "postgres",           # Database user
    "password": "password",       # Database password
    "connection_timeout": 30,     # Connection timeout in seconds
    "max_connections": 10,        # Maximum connections
    "schema": "public"            # Database schema
}
```

### Vector Configuration

```python
vector_config = {
    "backend": "placeholder",     # Backend type (placeholder, pinecone, weaviate)
    "dimension": 768,            # Embedding dimension
    "metric": "cosine",          # Similarity metric (cosine, euclidean, dotproduct)
    "namespace": "default"       # Namespace for embeddings
}
```

## API Reference

### Context Management

```python
# Set context with optional TTL
memory_api.set_context(context_id: str, context_data: dict, ttl: int = None) -> bool

# Get context
memory_api.get_context(context_id: str) -> dict | None

# Append event to context
memory_api.append_event(context_id: str, event: dict) -> bool

# Get all events for context
memory_api.get_events(context_id: str) -> list

# Clear context
memory_api.clear_context(context_id: str) -> bool
```

### Flow Run History

```python
# Write flow run history
memory_api.write_flow_run_history(flow_id: str, run_id: str, data: dict) -> bool

# Read flow run history
memory_api.read_flow_run_history(flow_id: str, run_id: str = None, limit: int = 100) -> list
```

### Task Outputs

```python
# Write task output
memory_api.write_task_output(task_id: str, output: dict, metadata: dict = None) -> bool

# Read task output
memory_api.read_task_output(task_id: str) -> dict | None
```

### Vector Operations

```python
# Index embedding
memory_api.index_embedding(id: str, embedding: list, metadata: dict = None) -> bool

# Query similar embeddings
memory_api.query_embeddings(query_embedding: list, top_k: int = 10, filter_metadata: dict = None) -> list

# Delete embedding
memory_api.delete_embedding(id: str) -> bool
```

### Distributed Locking

```python
# Acquire distributed lock
with memory_api.acquire_lock(lock_name: str, timeout: int = 10, blocking_timeout: int = 5):
    # Critical section
    pass
```

### Health and Statistics

```python
# Health check
health = memory_api.health_check() -> dict

# Memory statistics
stats = memory_api.get_memory_stats() -> dict
```

## Database Schema

### Core Tables

- **flow_run_history**: Flow execution history and metadata
- **task_outputs**: Task execution results and outputs
- **audit_log**: Comprehensive audit trail
- **memory_context**: Context data storage (alternative to Redis)
- **memory_events**: Event streams for contexts
- **vector_embeddings**: Vector embeddings and metadata

### Key Features

- **JSONB Support**: Native JSON storage with indexing
- **Partitioning**: Automatic partitioning for large tables
- **Indexing**: Optimized indexes for common query patterns
- **TTL Support**: Automatic cleanup of expired data
- **Audit Trail**: Complete operation history

## Testing

Run the test suite:

```bash
# Run all memory tests
pytest tests/memory/

# Run specific test files
pytest tests/memory/test_adapters.py
pytest tests/memory/test_api.py

# Run with coverage
pytest tests/memory/ --cov=memory --cov-report=html
```

## Examples

See `examples/memory_example.py` for comprehensive usage examples including:

- Basic context management
- Flow run history tracking
- Task output storage
- Vector embedding operations
- Distributed locking
- Error handling
- Global API usage

## Performance Considerations

### Redis
- Use connection pooling for high concurrency
- Set appropriate TTL values to prevent memory bloat
- Consider Redis clustering for horizontal scaling

### PostgreSQL
- Enable partitioning for large datasets
- Use appropriate indexes for query patterns
- Consider read replicas for read-heavy workloads

### Vector Database
- Choose appropriate similarity metrics for your use case
- Consider dimensionality reduction for large embeddings
- Use metadata filtering to improve query performance

## Monitoring

The Memory API provides health checks and statistics for monitoring:

```python
# Health check
health = memory_api.health_check()
if health["overall_status"] != "healthy":
    # Handle degraded state
    pass

# Statistics
stats = memory_api.get_memory_stats()
print(f"Redis memory usage: {stats['adapters']['redis']['used_memory']}")
print(f"PostgreSQL connections: {stats['adapters']['postgres']['active_connections']}")
print(f"Vector embeddings: {stats['adapters']['vector']['total_embeddings']}")
```

## Troubleshooting

### Common Issues

1. **Connection Failures**: Check network connectivity and credentials
2. **Memory Issues**: Monitor Redis memory usage and set appropriate TTLs
3. **Performance**: Review database indexes and query patterns
4. **Lock Timeouts**: Adjust timeout values based on operation duration

### Debugging

Enable debug logging:

```python
import structlog
structlog.configure(
    processors=[
        structlog.dev.ConsoleRenderer()
    ]
)
```

## Contributing

When adding new adapters or features:

1. Follow the existing adapter pattern
2. Add comprehensive tests
3. Update documentation
4. Consider backward compatibility
5. Add appropriate error handling

## License

This memory adapter layer is part of the Enterprise AI Agent Framework and follows the same licensing terms.
