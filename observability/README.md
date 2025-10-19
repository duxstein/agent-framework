# Observability Stack for Enterprise AI Agent Framework

This directory contains comprehensive observability artifacts for monitoring, logging, tracing, and alerting across the Agent Framework services.

## Overview

The observability stack provides:

- **Metrics Collection**: Prometheus for metrics scraping and storage
- **Visualization**: Grafana dashboards for metrics visualization
- **Distributed Tracing**: OpenTelemetry and Jaeger for request tracing
- **Log Aggregation**: Fluentd for log forwarding to Elasticsearch/Kibana
- **Alerting**: Alertmanager for alert routing and notification
- **Testing**: Comprehensive test suite for observability components

## Components

### 1. Prometheus Configuration (`prometheus.yml`)
- Scrapes metrics from ingress (port 8000), orchestrator (port 8001), executor (port 8002)
- Includes Redis, PostgreSQL, Kafka, and system metrics
- Configured with 15-day retention and optimized storage settings

### 2. Grafana Dashboard (`grafana_dashboard.json`)
- **Task Latency**: P50, P95, P99 percentiles
- **Task Success/Failure Rate**: Success and failure percentages
- **Kafka Consumer Lag**: Message queue lag monitoring
- **Executor CPU Usage**: CPU utilization across executor instances
- **API Request Rate**: HTTP request metrics
- **Redis Metrics**: Cache performance and memory usage
- **Service Health Status**: Overall system health

### 3. OpenTelemetry Integration (`opentelemetry_init.py`)
- Distributed tracing setup for all services
- Context propagation across service boundaries
- Automatic instrumentation for HTTP, database, and message queue operations
- Service-specific initialization functions
- Error handling and span management utilities

### 4. Fluentd Configuration (`fluentd.conf`)
- Log forwarding from all services to Elasticsearch
- Loki fallback for log storage
- Structured JSON log parsing
- Container and system log collection
- Performance monitoring and error handling

### 5. Alertmanager Rules (`alertmanager_rules.yml`)
- **Critical Alerts**: Service down, high failure rates, critical latency
- **Resource Alerts**: CPU, memory, disk usage thresholds
- **Business Alerts**: Flow execution failures, tenant isolation violations
- **Security Alerts**: Authentication failures, suspicious activity
- **Queue Alerts**: Kafka lag, task queue depth monitoring

### 6. Alertmanager Configuration (`alertmanager.yml`)
- Alert routing based on severity and service
- Email, Slack, and PagerDuty integrations
- Alert inhibition rules to reduce noise
- Time-based muting for maintenance windows

### 7. Elasticsearch Template (`elasticsearch-template.json`)
- Optimized index mapping for Agent Framework logs
- Proper field types for efficient querying
- JSONB support for flexible metadata
- Performance-optimized settings

### 8. Docker Compose (`docker-compose.observability.yml`)
- Complete observability stack deployment
- Includes Prometheus, Grafana, Jaeger, Elasticsearch, Kibana, Fluentd
- System metrics collectors (Node Exporter, cAdvisor)
- Service-specific exporters (Redis, PostgreSQL, Kafka)

### 9. Test Suite (`tests/observability/test_observability.py`)
- Prometheus metrics collection and scraping tests
- OpenTelemetry tracing functionality tests
- Structured logging validation
- Integration tests for service observability
- Performance monitoring validation

## Quick Start

### 1. Deploy Observability Stack

**Option A: Using the startup script (Recommended)**
```bash
# Linux/macOS
./observability/start-observability.sh

# Windows PowerShell
.\observability\start-observability.ps1
```

**Option B: Manual deployment**
```bash
# Start the observability stack (monitoring tools only)
docker-compose -f observability/docker-compose.observability.yml up -d

# Start the main services with their exporters (optional)
docker-compose -f observability/docker-compose.services.yml up -d

# Verify services are running
docker-compose -f observability/docker-compose.observability.yml ps
docker-compose -f observability/docker-compose.services.yml ps
```

**Note**: The observability stack is split into two files:
- `docker-compose.observability.yml`: Core monitoring tools (Prometheus, Grafana, Jaeger, etc.)
- `docker-compose.services.yml`: Main services (Redis, PostgreSQL, Kafka) with their exporters

### 2. Access Dashboards

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **Kibana**: http://localhost:5601
- **Alertmanager**: http://localhost:9093

### 3. Import Grafana Dashboard

1. Open Grafana at http://localhost:3000
2. Go to Dashboards → Import
3. Upload `observability/grafana_dashboard.json`
4. Configure Prometheus as data source (http://prometheus:9090)

### 4. Configure Services

Add observability initialization to your services:

```python
# In ingress/api.py
from observability.opentelemetry_init import init_ingress_tracing
tracer = init_ingress_tracing()

# In orchestrator/service.py
from observability.opentelemetry_init import init_orchestrator_tracing
tracer = init_orchestrator_tracing()

# In executor/worker.py
from observability.opentelemetry_init import init_executor_tracing
tracer = init_executor_tracing()
```

### 5. Run Tests

```bash
# Run observability tests
pytest tests/observability/test_observability.py -v

# Run with coverage
pytest tests/observability/test_observability.py --cov=observability --cov-report=html
```

## Configuration

### Environment Variables

```bash
# OpenTelemetry Configuration
export OTEL_ENABLED=true
export OTEL_EXPORTER_TYPE=jaeger
export OTEL_SAMPLING_RATIO=1.0
export JAEGER_AGENT_HOST=jaeger
export JAEGER_AGENT_PORT=6831

# Elasticsearch Configuration
export ELASTICSEARCH_HOST=elasticsearch
export ELASTICSEARCH_PORT=9200
export ELASTICSEARCH_SCHEME=http

# Loki Configuration
export LOKI_URL=http://loki:3100

# Fluentd Configuration
export ENV=production
export CLUSTER=agent-framework
```

### Service Configuration

Each service should expose metrics on the following ports:
- **Ingress**: Port 8000 (`/metrics`)
- **Orchestrator**: Port 8001 (`/metrics`)
- **Executor**: Port 8002 (`/metrics`)

### Log Configuration

Services should output structured JSON logs to:
- `/var/log/agent-framework/{service}/*.log`

## Monitoring Key Metrics

### Critical Metrics to Monitor

1. **Service Health**
   - `up` - Service availability
   - `http_requests_total` - API request rate
   - `http_request_duration_seconds` - API response time

2. **Task Execution**
   - `task_execution_total` - Task execution rate
   - `task_execution_duration_seconds` - Task execution time
   - `task_queue_depth` - Queue depth

3. **Resource Usage**
   - `node_cpu_seconds_total` - CPU usage
   - `node_memory_MemAvailable_bytes` - Memory usage
   - `node_filesystem_free_bytes` - Disk usage

4. **Message Queue**
   - `kafka_consumer_lag_sum` - Consumer lag
   - `kafka_messages_total` - Message throughput

5. **Database**
   - `postgresql_stat_activity_count` - Connection count
   - `postgresql_query_duration_seconds` - Query performance

6. **Cache**
   - `redis_memory_used_bytes` - Memory usage
   - `redis_connected_clients` - Connection count

## Alerting

### Alert Severity Levels

- **Critical**: Immediate attention required (PagerDuty, Slack)
- **Warning**: Monitor closely (Email, Slack)
- **Info**: Log for awareness (Email only)

### Key Alert Conditions

1. **Service Down**: `up == 0`
2. **High Task Failure Rate**: `> 10% failure rate`
3. **High Latency**: `P95 > 30s`
4. **Kafka Lag**: `> 1000 messages`
5. **Resource Exhaustion**: `CPU > 95%`, `Memory > 95%`

## Troubleshooting

### Common Issues

1. **Metrics Not Appearing**
   - Check service endpoints are accessible
   - Verify Prometheus configuration
   - Check service metrics implementation

2. **Tracing Not Working**
   - Verify OpenTelemetry initialization
   - Check Jaeger connectivity
   - Validate trace context propagation

3. **Logs Not Forwarding**
   - Check Fluentd configuration
   - Verify Elasticsearch connectivity
   - Check log file permissions

4. **Alerts Not Firing**
   - Verify Alertmanager configuration
   - Check alert rule syntax
   - Validate notification channels

### Debug Commands

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Alertmanager status
curl http://localhost:9093/api/v1/status

# Check Elasticsearch health
curl http://localhost:9200/_cluster/health

# Check Jaeger services
curl http://localhost:16686/api/services

# View Fluentd logs
docker logs fluentd
```

## Performance Considerations

### Prometheus
- Adjust scrape intervals based on metric cardinality
- Use recording rules for expensive queries
- Consider federation for large deployments

### Elasticsearch
- Tune JVM heap size based on data volume
- Use index lifecycle management
- Consider shard allocation strategies

### Grafana
- Optimize dashboard queries
- Use data source caching
- Consider dashboard refresh intervals

## Security

### Access Control
- Configure authentication for all services
- Use TLS for external access
- Implement network policies

### Data Privacy
- Sanitize sensitive data in logs
- Use field-level encryption
- Implement data retention policies

## Contributing

When adding new observability features:

1. Follow existing patterns and conventions
2. Add comprehensive tests
3. Update documentation
4. Consider performance impact
5. Validate with real workloads

## License

This observability stack is part of the Enterprise AI Agent Framework and follows the same licensing terms.
