# Orchestrator Service

The Orchestrator Service is the core component of the Enterprise AI Agent Framework that manages workflow execution lifecycle, including task scheduling, state management, retry handling, and metrics collection.

## Features

### 🔄 **Workflow Execution Management**
- **Kafka Consumer**: Consumes flow run events from the `flow_runs` topic
- **Flow Registry Integration**: Loads flow definitions from the SDK FlowRegistry
- **Task Scheduling**: Computes ready tasks and publishes them to the `task_queue`
- **State Management**: Maintains run state in Redis and PostgreSQL

### 📊 **State Persistence**
- **Redis**: Ephemeral state storage for active runs (key: `run:{run_id}:state`)
- **PostgreSQL**: Durable storage in `flow_run_history` and `task_execution_history` tables
- **State Recovery**: Automatic state recovery from persistent storage

### 🔁 **Retry Mechanism**
- **Exponential Backoff**: Configurable retry delays with exponential backoff
- **Max Retry Limits**: Per-task retry limits with dead letter queue fallback
- **Retry Tracking**: Comprehensive retry attempt tracking and metrics

### 📈 **Monitoring & Observability**
- **Prometheus Metrics**: Comprehensive metrics for monitoring and alerting
- **Structured Logging**: JSON-formatted logs with context-aware information
- **Health Checks**: Built-in health check endpoints for service monitoring

### 🎯 **Event Processing**
- **Task Completion**: Handles `task_done` events and progresses workflow
- **Task Failures**: Processes `task_failed` events with retry logic
- **Dead Letter Queue**: Moves failed tasks to dead letter queue after max retries

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ingress API   │───▶│   Kafka Topic   │───▶│  Orchestrator   │
│                 │    │   flow_runs     │    │    Service      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Executor      │◀───│   Kafka Topic   │◀───│  Task Scheduling│
│   Services      │    │   task_queue    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dead Letter   │◀───│   Kafka Topic   │◀───│  Retry Logic    │
│     Queue       │    │ dead_letter_q   │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Configuration

The orchestrator service can be configured using environment variables with the `ORCHESTRATOR_` prefix:

### Kafka Configuration
```bash
ORCHESTRATOR_KAFKA_BOOTSTRAP_SERVERS=["localhost:9092"]
ORCHESTRATOR_KAFKA_CONSUMER_GROUP="orchestrator-service"
ORCHESTRATOR_KAFKA_AUTO_OFFSET_RESET="latest"
```

### Redis Configuration
```bash
ORCHESTRATOR_REDIS_URL="redis://localhost:6379"
ORCHESTRATOR_REDIS_KEY_TTL=3600
```

### PostgreSQL Configuration
```bash
ORCHESTRATOR_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/agent_framework"
ORCHESTRATOR_FLOW_REGISTRY_URL="postgresql://postgres:postgres@localhost:5432/agent_framework"
```

### Retry Configuration
```bash
ORCHESTRATOR_MAX_RETRY_ATTEMPTS=3
ORCHESTRATOR_RETRY_BACKOFF_BASE=2
ORCHESTRATOR_TASK_TIMEOUT_DEFAULT=300
```

### Metrics Configuration
```bash
ORCHESTRATOR_METRICS_PORT=9090
ORCHESTRATOR_METRICS_ENABLED=true
```

## API Endpoints

### Prometheus Metrics
- **Endpoint**: `http://localhost:9090/metrics`
- **Description**: Prometheus metrics for monitoring

### Health Check
- **Endpoint**: `http://localhost:9090/health`
- **Description**: Service health status

## Database Schema

### Flow Run History Table
```sql
CREATE TABLE flow_run_history (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    flow_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    input_data JSONB,
    output_data JSONB,
    execution_context JSONB,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

### Task Execution History Table
```sql
CREATE TABLE task_execution_history (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    task_id VARCHAR(255) NOT NULL,
    handler VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    attempts INTEGER DEFAULT 0,
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

## Prometheus Metrics

### Flow Metrics
- `orchestrator_flow_runs_processed_total`: Total flow runs processed
- `orchestrator_run_execution_seconds`: Run execution time histogram
- `orchestrator_active_runs`: Number of active runs

### Task Metrics
- `orchestrator_tasks_scheduled_total`: Total tasks scheduled
- `orchestrator_tasks_completed_total`: Total tasks completed by status
- `orchestrator_task_execution_seconds`: Task execution time by handler
- `orchestrator_active_tasks`: Number of active tasks

### Retry Metrics
- `orchestrator_retry_attempts_total`: Total retry attempts by task and handler
- `orchestrator_dead_letter_queue_size`: Size of dead letter queue

## Event Flow

### 1. Flow Run Event Processing
```json
{
  "event_type": "flow_run_requested",
  "run_id": "uuid",
  "correlation_id": "uuid",
  "flow_id": "flow-id",
  "tenant_id": "tenant-id",
  "user_id": "user-id",
  "input": {...},
  "flow_definition": {...},
  "execution_context": {...}
}
```

### 2. Task Queue Message
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

### 3. Task Done Event
```json
{
  "run_id": "uuid",
  "task_id": "task-id",
  "output": {...},
  "execution_time_ms": 1500
}
```

### 4. Task Failed Event
```json
{
  "run_id": "uuid",
  "task_id": "task-id",
  "error": "error message",
  "execution_time_ms": 500
}
```

## Usage

### Starting the Service
```bash
python orchestrator/service.py
```

### Docker Deployment
```bash
docker run -d \
  --name orchestrator-service \
  -p 9090:9090 \
  -e ORCHESTRATOR_KAFKA_BOOTSTRAP_SERVERS="kafka:9092" \
  -e ORCHESTRATOR_REDIS_URL="redis://redis:6379" \
  -e ORCHESTRATOR_DATABASE_URL="postgresql://postgres:postgres@postgres:5432/agent_framework" \
  orchestrator-service:latest
```

### Testing
```bash
# Run unit tests
pytest tests/orchestrator/test_service.py -v

# Run integration tests
pytest tests/orchestrator/test_service.py::TestOrchestratorIntegration -v

# Run performance tests
pytest tests/orchestrator/test_service.py::TestOrchestratorPerformance -v
```

## Monitoring

### Key Metrics to Monitor
1. **Flow Run Success Rate**: `rate(orchestrator_flow_runs_processed_total[5m])`
2. **Task Completion Rate**: `rate(orchestrator_tasks_completed_total[5m])`
3. **Active Runs**: `orchestrator_active_runs`
4. **Retry Rate**: `rate(orchestrator_retry_attempts_total[5m])`
5. **Dead Letter Queue Size**: `orchestrator_dead_letter_queue_size`

### Alerting Rules
```yaml
groups:
  - name: orchestrator
    rules:
      - alert: HighRetryRate
        expr: rate(orchestrator_retry_attempts_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High retry rate detected"
      
      - alert: DeadLetterQueueGrowing
        expr: increase(orchestrator_dead_letter_queue_size[5m]) > 10
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dead letter queue is growing rapidly"
```

## Troubleshooting

### Common Issues

1. **Kafka Connection Issues**
   - Check Kafka bootstrap servers configuration
   - Verify network connectivity to Kafka cluster
   - Check consumer group configuration

2. **Redis Connection Issues**
   - Verify Redis URL and credentials
   - Check Redis server availability
   - Monitor Redis memory usage

3. **PostgreSQL Connection Issues**
   - Verify database URL and credentials
   - Check database server availability
   - Monitor database connection pool

4. **High Memory Usage**
   - Monitor active runs count
   - Check for memory leaks in task state management
   - Adjust Redis TTL settings

### Debug Mode
Enable debug logging for troubleshooting:
```bash
ORCHESTRATOR_LOG_LEVEL=DEBUG python orchestrator/service.py
```

## Contributing

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation for any API changes
4. Ensure all tests pass before submitting PR

## License

This project is licensed under the MIT License - see the LICENSE file for details.
