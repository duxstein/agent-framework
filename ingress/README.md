# Enterprise AI Agent Framework - Ingress API

This module provides a FastAPI-based REST API for managing AI agent flow runs with enterprise-grade features including JWT authentication, tenant scoping, audit logging, and Kafka message publishing.

## Features

- **JWT Authentication**: Secure token-based authentication with tenant scoping
- **Policy Engine Integration**: Business rules and security constraints enforcement
- **Flow Registry Integration**: Load flow definitions from centralized registry
- **Flow Validation**: Comprehensive validation using SDK Flow model + Policy Engine
- **Webhook Support**: External system integration via webhooks (n8n, Zapier, etc.)
- **Audit Logging**: Complete audit trail stored in PostgreSQL
- **Kafka Integration**: Asynchronous message publishing with orchestrator-compatible format
- **Redis Caching**: High-performance caching for run status queries
- **Structured Logging**: JSON-formatted logs for observability
- **OpenAPI Documentation**: Auto-generated API documentation
- **Health Checks**: Service health monitoring endpoints

## API Endpoints

### POST /v1/runs
Creates a new flow run.

**Request Body:**
```json
{
  "flow_id": "string",
  "flow_definition": {
    "id": "string",
    "version": "string",
    "tasks": [...],
    "type": "DAG",
    "tenant_id": "string"
  },
  "input": {},
  "tenant_id": "string",
  "request_id": "string"
}
```

**Response (202 Accepted):**
```json
{
  "run_id": "uuid",
  "correlation_id": "uuid"
}
```

### GET /v1/runs/{run_id}
Retrieves the status of a flow run.

**Response (200 OK):**
```json
{
  "run_id": "uuid",
  "status": "string",
  "created_at": "datetime",
  "updated_at": "datetime",
  "tenant_id": "string",
  "flow_id": "string",
  "input": {},
  "output": {},
  "error": "string"
}
```

### POST /v1/webhooks/{webhook_id}
Webhook endpoint for external system integrations.

**Request Body:**
```json
{
  "webhook_id": "string",
  "payload": {},
  "headers": {},
  "source": "string"
}
```

**Response (202 Accepted):**
```json
{
  "run_id": "uuid",
  "correlation_id": "uuid"
}
```

### GET /health
Health check endpoint for service monitoring.

## Configuration

The API uses environment variables for configuration:

```bash
# JWT Configuration
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/agent_framework

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_CACHE_TTL=300

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_FLOW_RUNS=flow_runs

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
```

## Database Schema

The API creates and uses the following PostgreSQL table:

```sql
CREATE TABLE flow_runs_audit (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    correlation_id VARCHAR(255) NOT NULL,
    flow_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    request_id VARCHAR(255),
    input_data JSONB NOT NULL,
    flow_definition JSONB,
    status VARCHAR(50) DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    output_data JSONB,
    error_message TEXT
);

CREATE TABLE webhook_configs (
    id SERIAL PRIMARY KEY,
    webhook_id VARCHAR(255) UNIQUE NOT NULL,
    flow_id VARCHAR(255) NOT NULL,
    tenant_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    webhook_config JSONB,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

## Running the API

### Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export JWT_SECRET_KEY="your-secret-key"
export DATABASE_URL="postgresql://user:password@localhost:5432/agent_framework"
export REDIS_URL="redis://localhost:6379"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

# Run the API
python -m ingress.api
```

### Production
```bash
# Using uvicorn directly
uvicorn ingress.api:app --host 0.0.0.0 --port 8000 --workers 4

# Using Docker (if Dockerfile is available)
docker run -p 8000:8000 --env-file .env agent-framework-ingress
```

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-mock

# Run tests
pytest tests/ingress/ -v

# Run with coverage
pytest tests/ingress/ --cov=ingress --cov-report=html
```

## Policy Engine Integration

The ingress API integrates with the framework's Policy Engine to enforce business rules and security constraints:

### Default Policies
- **Tenant Isolation Policy**: Ensures flows maintain tenant boundaries
- **Retry Limit Policy**: Enforces maximum retry limits on tasks (default: 10)
- **Timeout Policy**: Enforces maximum timeout limits (default: 2 hours)

### Policy Evaluation Flow
1. Flow definition validation using SDK Flow model
2. Policy engine evaluation with user/tenant context
3. Policy violations result in 403 Forbidden responses
4. Policy modifications are logged and can be applied

### Custom Policies
Policies can be extended by implementing the `FlowPolicy`, `PreTaskPolicy`, or `PostTaskPolicy` interfaces from the SDK.

## Flow Registry Integration

The API integrates with the Flow Registry for centralized flow management:

### Flow Loading
- **Registry First**: If no `flow_definition` provided, loads from registry
- **Override Support**: Provided `flow_definition` overrides registry
- **Validation**: All flows validated against SDK and Policy Engine

### Registry Benefits
- Centralized flow management
- Version control and metadata
- Tenant-scoped flow access
- Search and discovery capabilities

## Authentication

The API uses JWT tokens for authentication. Tokens must include:

- `sub`: User identifier
- `tenant_id`: Tenant identifier for multi-tenancy
- `exp`: Expiration timestamp

Example token payload:
```json
{
  "sub": "user123",
  "tenant_id": "tenant456",
  "exp": 1640995200
}
```

## Error Handling

The API returns structured error responses:

```json
{
  "error": "Error message",
  "detail": "Additional error details"
}
```

Common HTTP status codes:
- `202`: Flow run created successfully
- `200`: Request successful
- `400`: Bad request (validation errors)
- `401`: Unauthorized (invalid token)
- `403`: Forbidden (tenant scope violation)
- `404`: Not found (run not found)
- `500`: Internal server error
- `503`: Service unavailable (health check failed)

## Monitoring and Observability

- **Structured Logging**: All logs are in JSON format for easy parsing
- **Health Checks**: `/health` endpoint for service monitoring
- **Audit Trail**: Complete audit trail in PostgreSQL
- **Metrics**: Integration points for Prometheus/Grafana monitoring
- **Tracing**: Correlation IDs for request tracing across services

## Security Considerations

- JWT tokens should be signed with strong secrets
- Database connections should use SSL in production
- Redis should be configured with authentication
- Kafka should use SASL authentication in production
- CORS origins should be restricted in production
- Rate limiting should be implemented at the gateway level

