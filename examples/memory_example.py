"""
Example usage of the Memory API.

This module demonstrates how to use the Memory API for storing and retrieving
context, events, flow run history, task outputs, and embeddings.
"""

import json
from datetime import datetime, timezone
from memory.api import MemoryAPI, initialize_memory_api


def example_basic_usage():
    """Basic usage example of Memory API."""
    print("=== Basic Memory API Usage ===")
    
    # Initialize Memory API with configurations
    redis_config = {
        "host": "localhost",
        "port": 6379,
        "db": 0,
        "key_prefix": "agent_framework:"
    }
    
    postgres_config = {
        "host": "localhost",
        "port": 5432,
        "database": "agent_framework",
        "user": "postgres",
        "password": "password"
    }
    
    vector_config = {
        "backend": "placeholder",  # Use placeholder for demo
        "dimension": 768,
        "metric": "cosine"
    }
    
    # Create Memory API instance
    memory_api = MemoryAPI(
        redis_config=redis_config,
        postgres_config=postgres_config,
        vector_config=vector_config
    )
    
    # Connect to all adapters
    if memory_api.connect():
        print("✓ Connected to all memory adapters")
    else:
        print("✗ Failed to connect to some adapters")
        return
    
    # Example 1: Context Management
    print("\n--- Context Management ---")
    
    # Set context
    context_data = {
        "user_id": "user_123",
        "session_id": "session_456",
        "preferences": {
            "language": "en",
            "theme": "dark"
        }
    }
    
    success = memory_api.set_context("user_session_123", context_data, ttl=3600)
    print(f"Set context: {'✓' if success else '✗'}")
    
    # Get context
    retrieved_context = memory_api.get_context("user_session_123")
    if retrieved_context:
        print(f"Retrieved context: {retrieved_context['data']['user_id']}")
    
    # Append events
    events = [
        {"type": "user_action", "action": "login", "timestamp": datetime.now(timezone.utc).isoformat()},
        {"type": "user_action", "action": "navigate", "page": "/dashboard"},
        {"type": "user_action", "action": "search", "query": "machine learning"}
    ]
    
    for event in events:
        success = memory_api.append_event("user_session_123", event)
        print(f"Appended event '{event['action']}': {'✓' if success else '✗'}")
    
    # Get events
    all_events = memory_api.get_events("user_session_123")
    print(f"Total events: {len(all_events)}")
    
    # Example 2: Flow Run History
    print("\n--- Flow Run History ---")
    
    flow_data = {
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "parameters": {
            "model": "gpt-4",
            "temperature": 0.7,
            "max_tokens": 1000
        },
        "metrics": {
            "input_tokens": 150,
            "estimated_cost": 0.05
        }
    }
    
    success = memory_api.write_flow_run_history("flow_001", "run_001", flow_data)
    print(f"Wrote flow run history: {'✓' if success else '✗'}")
    
    # Read flow run history
    history = memory_api.read_flow_run_history("flow_001", limit=10)
    print(f"Retrieved {len(history)} flow run history entries")
    
    # Example 3: Task Outputs
    print("\n--- Task Outputs ---")
    
    task_output = {
        "result": "success",
        "output": {
            "generated_text": "This is a sample generated response.",
            "confidence": 0.95,
            "tokens_used": 25
        },
        "execution_time": 2.5
    }
    
    task_metadata = {
        "model": "gpt-4",
        "temperature": 0.7,
        "user_id": "user_123"
    }
    
    success = memory_api.write_task_output("task_001", task_output, task_metadata)
    print(f"Wrote task output: {'✓' if success else '✗'}")
    
    # Read task output
    retrieved_output = memory_api.read_task_output("task_001")
    if retrieved_output:
        print(f"Retrieved task output: {retrieved_output['output']['result']}")
    
    # Example 4: Vector Embeddings
    print("\n--- Vector Embeddings ---")
    
    # Generate sample embeddings (768 dimensions)
    import random
    random.seed(42)  # For reproducible results
    
    documents = [
        {"id": "doc_1", "text": "Machine learning is a subset of artificial intelligence."},
        {"id": "doc_2", "text": "Deep learning uses neural networks with multiple layers."},
        {"id": "doc_3", "text": "Natural language processing helps computers understand human language."}
    ]
    
    for doc in documents:
        # Generate random embedding (in real usage, this would come from an embedding model)
        embedding = [random.uniform(-1, 1) for _ in range(768)]
        
        metadata = {
            "text": doc["text"],
            "type": "document",
            "source": "example"
        }
        
        success = memory_api.index_embedding(doc["id"], embedding, metadata)
        print(f"Indexed embedding for {doc['id']}: {'✓' if success else '✗'}")
    
    # Query similar embeddings
    query_embedding = [random.uniform(-1, 1) for _ in range(768)]
    similar_docs = memory_api.query_embeddings(query_embedding, top_k=3)
    print(f"Found {len(similar_docs)} similar documents")
    
    # Example 5: Audit Logging
    print("\n--- Audit Logging ---")
    
    audit_data = {
        "user": "user_123",
        "ip_address": "192.168.1.100",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "changes": {
            "context_updated": True,
            "events_added": 3
        }
    }
    
    success = memory_api.write_audit_entry("context", "user_session_123", "update", audit_data)
    print(f"Wrote audit entry: {'✓' if success else '✗'}")
    
    # Example 6: Distributed Locking
    print("\n--- Distributed Locking ---")
    
    try:
        with memory_api.acquire_lock("critical_section", timeout=30):
            print("✓ Acquired lock for critical section")
            # Simulate some work
            import time
            time.sleep(0.1)
            print("✓ Completed work in critical section")
    except Exception as e:
        print(f"✗ Failed to acquire lock: {e}")
    
    # Example 7: Health Check and Statistics
    print("\n--- Health Check and Statistics ---")
    
    health = memory_api.health_check()
    print(f"Overall health status: {health['overall_status']}")
    
    stats = memory_api.get_memory_stats()
    print(f"Memory statistics available for {len(stats['adapters'])} adapters")
    
    # Clean up
    memory_api.clear_context("user_session_123")
    print("\n✓ Cleaned up context")
    
    # Disconnect
    memory_api.disconnect()
    print("✓ Disconnected from all adapters")


def example_global_api_usage():
    """Example using global Memory API."""
    print("\n=== Global Memory API Usage ===")
    
    # Initialize global Memory API
    redis_config = {"host": "localhost", "port": 6379}
    postgres_config = {"host": "localhost", "database": "agent_framework"}
    vector_config = {"backend": "placeholder"}
    
    memory_api = initialize_memory_api(redis_config, postgres_config, vector_config)
    
    if memory_api and memory_api.is_connected():
        print("✓ Global Memory API initialized and connected")
        
        # Use global API
        from memory.api import get_global_memory_api
        global_api = get_global_memory_api()
        
        if global_api:
            # Set some context
            context_data = {"global_context": True, "timestamp": datetime.now(timezone.utc).isoformat()}
            success = global_api.set_context("global_test", context_data)
            print(f"Set global context: {'✓' if success else '✗'}")
            
            # Retrieve context
            retrieved = global_api.get_context("global_test")
            if retrieved:
                print(f"Retrieved global context: {retrieved['data']['global_context']}")
            
            # Clean up
            global_api.clear_context("global_test")
            global_api.disconnect()
            print("✓ Global API cleaned up and disconnected")
    else:
        print("✗ Failed to initialize global Memory API")


def example_error_handling():
    """Example of error handling with Memory API."""
    print("\n=== Error Handling Example ===")
    
    # Create Memory API without any adapters
    memory_api = MemoryAPI()
    
    # Try to use operations without adapters
    print("Testing operations without adapters:")
    
    # Context operations
    result = memory_api.set_context("test", {"key": "value"})
    print(f"Set context without Redis: {'✓' if not result else '✗'} (expected False)")
    
    result = memory_api.get_context("test")
    print(f"Get context without Redis: {'✓' if result is None else '✗'} (expected None)")
    
    # PostgreSQL operations
    result = memory_api.write_flow_run_history("flow", "run", {"status": "test"})
    print(f"Write flow history without PostgreSQL: {'✓' if not result else '✗'} (expected False)")
    
    result = memory_api.write_task_output("task", {"result": "test"})
    print(f"Write task output without PostgreSQL: {'✓' if not result else '✗'} (expected False)")
    
    # Vector operations
    embedding = [0.1] * 768
    result = memory_api.index_embedding("test", embedding)
    print(f"Index embedding without Vector DB: {'✓' if not result else '✗'} (expected False)")
    
    result = memory_api.query_embeddings(embedding)
    print(f"Query embeddings without Vector DB: {'✓' if result == [] else '✗'} (expected empty list)")
    
    # Locking
    try:
        with memory_api.acquire_lock("test"):
            pass
        print("✗ Lock acquisition should have failed")
    except Exception as e:
        print(f"✓ Lock acquisition failed as expected: {type(e).__name__}")


if __name__ == "__main__":
    print("Memory API Examples")
    print("==================")
    
    # Run examples
    example_basic_usage()
    example_global_api_usage()
    example_error_handling()
    
    print("\n=== Examples Complete ===")
    print("Note: These examples use placeholder/mock configurations.")
    print("In production, configure actual Redis, PostgreSQL, and Vector database connections.")
