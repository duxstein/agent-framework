# Executor Worker Service

The Executor Worker Service is a critical component of the Enterprise AI Agent Framework that processes tasks from the task queue, executes them using dynamic connector loading, and handles success/failure scenarios with comprehensive monitoring and idempotency support.

## Features

### 🔄 **Task Processing**
- **Kafka Consumer**: Consumes tasks from the `task_queue` topic
- **Idempotency**: Prevents duplicate task execution using Redis keys
- **Dynamic Connector Loading**: Loads connectors dynamically from the connector registry
- **Multiple Execution Modes**: Supports async, sync, and CPU-intensive execution paths

### 🎯 **Execution Modes**
- **Async Execution**: For I/O-bound connectors with async methods
- **Sync Execution**: For regular connectors executed in thread pools
- **CPU-Intensive Execution**: For ML/AI tasks executed in process pools

### 📊 **State Management**
- **Redis Storage**: Task outputs stored in `run:{run_id}:outputs`
- **PostgreSQL Audit**: Comprehensive task execution audit trail
- **Idempotency Keys**: `run:{run_id}:task:{task_id}:status` for duplicate prevention

### 🔁 **Retry & Error Handling**
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Dead Letter Queue**: Failed tasks moved to dead letter queue after max retries
- **Error Classification**: Different error types tracked for monitoring

### 📈 **Monitoring & Observability**
- **Prometheus Metrics**: Comprehensive metrics for monitoring and alerting
- **Structured Logging**: JSON-formatted logs with context-aware information
- **Health Checks**: Built-in health check endpoints for service monitoring

### 🎯 **Event Publishing**
- **Task Success**: Publishes `task_done` events with timing and results
- **Task Failure**: Publishes `task_failed` events for retry handling
- **Dead Letter**: Publishes to dead letter queue for failed tasks

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Orchestrator  │───▶│   Kafka Topic   │───▶│  Executor       │
│    Service      │    │   task_queue    │    │   Worker        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Connector     │◀───│  Dynamic Load   │◀───│  Task Execution │
│   Registry      │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Task Done     │◀───│   Kafka Topic   │◀───│  Success/Failure│
│   Events        │    │ task_done/failed│    │  Handling       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Configuration

The executor worker can be configured using environment variables with the `EXECUTOR_` prefix:

### Kafka Configuration
```bash
EXECUTOR_KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
EXECUTOR_KAFKA_CONSUMER_GROUP="executor-worker"
EXECUTOR_KAFKA_AUTO_OFFSET_RESET="latest"
```

### Redis Configuration
```bash
EXECUTOR_REDIS_URL="redis://localhost:6379"
EXECUTOR_IDEMPOTENCY_TTL=3600
```

### PostgreSQL Configuration
```bash
EXECUTOR_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/agent_framework"
EXECUTOR_CONNECTOR_REGISTRY_URL="postgresql://postgres:postgres@localhost:5432/agent_framework"
```

### Execution Configuration
```bash
EXECUTOR_MAX_WORKERS=10
EXECUTOR_TASK_TIMEOUT_DEFAULT=300
EXECUTOR_MAX_RETRY_ATTEMPTS=3
```

### Metrics Configuration
```bash
EXECUTOR_METRICS_PORT=9091
EXECUTOR_METRICS_ENABLED=true
```

## API Endpoints

### Prometheus Metrics
- **Endpoint**: `http://localhost:9091/metrics`
- **Description**: Prometheus metrics for monitoring

### Health Check
- **Endpoint**: `http://localhost:9091/health`
- **Description**: Service health status

## Database Schema

### Task Execution Audit Table
```sql
CREATE TABLE task_execution_audit (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    handler VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    attempts INTEGER DEFAULT 0,
    execution_mode VARCHAR(50) DEFAULT 'sync',
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    worker_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

## Prometheus Metrics

### Task Execution Metrics
- `executor_task_duration_seconds`: Task execution duration by handler, mode, and status
- `executor_task_success_count_total`: Total successful task executions by handler and mode
- `executor_task_failure_count_total`: Total failed task executions by handler, mode, and error type
- `executor_task_retry_count_total`: Total task retries by handler and attempt
- `executor_task_dead_letter_count_total`: Total tasks moved to dead letter queue by handler

### Resource Metrics
- `executor_active_tasks`: Number of currently active tasks
- `executor_connector_load_seconds`: Time taken to load connectors by handler

## Event Flow

### 1. Task Queue Message
```json
{
  "run_id": "uuid",
  "task_id": "task-id",
  "handler": "handler-name",
  "inputs": {...},
  "attempt": 0,
  "max_retries": 3,
  "timeout": 300,
  "correlation_id": "uuid",
  "tenant_id": "tenant-id",
  "user_id": "user-id",
  "execution_context": {...}
}
```

### 2. Task Done Event
```json
{
  "run_id": "uuid",
  "task_id": "task-id",
  "output": {...},
  "execution_time_ms": 1500,
  "execution_mode": "async",
  "correlation_id": "uuid",
  "tenant_id": "tenant-id",
  "user_id": "user-id",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

### 3. Task Failed Event
```json
{
  "run_id": "uuid",
  "task_id": "task-id",
  "error": "error message",
  "attempt": 1,
  "max_retries": 3,
  "execution_time_ms": 500,
  "execution_mode": "sync",
  "correlation_id": "uuid",
  "tenant_id": "tenant-id",
  "user_id": "user-id",
  "timestamp": "2025-01-01T00:00:00Z"
}
```

## Connector Integration

### Connector Interface
```python
class BaseConnector:
    def execute_action(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the connector action synchronously."""
        pass
    
    async def execute_action_async(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the connector action asynchronously."""
        pass
    
    def is_cpu_intensive(self) -> bool:
        """Return True if this connector is CPU intensive."""
        return False
```

### Execution Mode Selection
1. **Async Mode**: If connector has `execute_action_async` method
2. **CPU-Intensive Mode**: If connector has `is_cpu_intensive()` returning True
3. **Sync Mode**: Default for all other connectors

## Usage

### Starting the Service
```bash
# Direct execution
python executor/worker.py

# Docker Compose
docker-compose --profile executor up executor-worker

# With custom configuration
EXECUTOR_KAFKA_BOOTSTRAP_SERVERS="kafka:9092" python executor/worker.py
```

### Docker Deployment
```bash
docker run -d \
  --name executor-worker \
  -p 9091:9091 \
  -e EXECUTOR_KAFKA_BOOTSTRAP_SERVERS="kafka:9092" \
  -e EXECUTOR_REDIS_URL="redis://redis:6379" \
  -e EXECUTOR_DATABASE_URL="postgresql://postgres:postgres@postgres:5432/agent_framework" \
  executor-worker:latest
```

### Testing
```bash
# Run unit tests
pytest tests/executor/test_worker.py -v

# Run integration tests
pytest tests/executor/test_worker.py::TestExecutorIntegration -v

# Run performance tests
pytest tests/executor/test_worker.py::TestExecutorPerformance -v
```

## Monitoring

### Key Metrics to Monitor
1. **Task Success Rate**: `rate(executor_task_success_count_total[5m])`
2. **Task Failure Rate**: `rate(executor_task_failure_count_total[5m])`
3. **Average Execution Time**: `rate(executor_task_duration_seconds_sum[5m]) / rate(executor_task_duration_seconds_count[5m])`
4. **Active Tasks**: `executor_active_tasks`
5. **Retry Rate**: `rate(executor_task_retry_count_total[5m])`
6. **Dead Letter Queue**: `rate(executor_task_dead_letter_count_total[5m])`

### Alerting Rules
```yaml
groups:
  - name: executor
    rules:
      - alert: HighTaskFailureRate
        expr: rate(executor_task_failure_count_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate detected"
      
      - alert: TasksInDeadLetterQueue
        expr: increase(executor_task_dead_letter_count_total[5m]) > 5
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Tasks are being moved to dead letter queue"
      
      - alert: HighExecutionTime
        expr: histogram_quantile(0.95, rate(executor_task_duration_seconds_bucket[5m])) > 30
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High task execution time detected"
```

## Troubleshooting

### Common Issues

1. **Connector Loading Failures**
   - Check connector registry configuration
   - Verify connector module paths and class names
   - Check connector dependencies

2. **Task Execution Timeouts**
   - Monitor task execution times
   - Adjust timeout configurations
   - Check for resource constraints

3. **High Memory Usage**
   - Monitor connector cache size
   - Check for memory leaks in connectors
   - Adjust thread/process pool sizes

4. **Kafka Consumer Lag**
   - Monitor consumer group lag
   - Scale executor workers horizontally
   - Check for processing bottlenecks

### Debug Mode
Enable debug logging for troubleshooting:
```bash
EXECUTOR_LOG_LEVEL=DEBUG python executor/worker.py
```

## Performance Tuning

### Thread Pool Configuration
```bash
# For I/O-bound tasks
EXECUTOR_THREAD_POOL_SIZE=50

# For CPU-bound tasks
EXECUTOR_PROCESS_POOL_SIZE=8
```

### Connector Caching
```bash
# Cache size
EXECUTOR_CONNECTOR_CACHE_SIZE=200

# Cache TTL
EXECUTOR_CONNECTOR_CACHE_TTL=7200
```

### Concurrent Task Limits
```bash
# Maximum concurrent tasks
EXECUTOR_MAX_CONCURRENT_TASKS=200
```

## Contributing

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any API changes
4. Ensure all tests pass before submitting PR

## License

This project is licensed under the MIT License - see the LICENSE file for details.
