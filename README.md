# Enterprise AI Agent Framework

A comprehensive platform for building enterprise-grade AI agent workflows with support for multi-tenancy, validation, policies, PostgreSQL-backed flow registry, and a complete REST API with Docker Compose setup.

## Features

- **Pydantic Models**: Type-safe Task and Flow models with automatic validation
- **Policy System**: Extensible policy framework for pre-task, post-task, and flow-level policies
- **Flow Registry**: PostgreSQL-backed registry for managing flow metadata
- **REST API**: FastAPI-based ingress API with JWT authentication and webhook support
- **Docker Compose**: Complete local development environment with all services
- **CLI Tool**: Command-line interface (`agentctl`) for flow management
- **Multi-tenancy**: Built-in support for tenant isolation
- **Comprehensive Testing**: Full test coverage with pytest

## 🚀 Quick Start with Docker Compose

The easiest way to get started is using Docker Compose, which provides a complete local development environment:

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f ingress-api

# Test the API
curl http://localhost:8000/health

# Stop services
docker-compose down
```

### Services Included

- **Ingress API** (Port 8000): FastAPI service for flow management
- **PostgreSQL** (Port 5432): Database for audit logs and flow registry
- **Redis** (Port 6379): Caching layer for performance
- **Kafka** (Port 9092): Message broker for flow events
- **Kafka UI** (Port 8080): Web interface for Kafka monitoring

For detailed Docker setup instructions, see [docker/README.md](docker/README.md).

## Installation

```bash
pip install -r requirements.txt
```

## Quick Start

### Creating a Flow

```python
from sdk.models import Task, Flow

# Create tasks
task1 = Task(
    handler="data_processor",
    inputs={"source": "database", "table": "users"},
    retries=3,
    timeout=300,
    condition="user_count > 0"
)

task2 = Task(
    handler="ml_predictor",
    inputs={"model": "sentiment_analysis"},
    retries=2,
    timeout=600
)

# Create flow
flow = Flow(
    tasks=[task1, task2],
    version="1.0.0",
    type="DAG",
    tenant_id="tenant_123"
)

# Validate flow
validation_result = flow.validate()
if validation_result["valid"]:
    print("Flow is valid!")
else:
    print("Validation errors:", validation_result["errors"])
```

### Using Policies

```python
from sdk.policy import RetryLimitPolicy, TimeoutPolicy, TenantIsolationPolicy

# Create policies
retry_policy = RetryLimitPolicy(max_retries=5)
timeout_policy = TimeoutPolicy(max_timeout=3600)
tenant_policy = TenantIsolationPolicy()

# Apply policies
for task in flow.tasks:
    retry_result = retry_policy.evaluate(task=task, flow=flow)
    timeout_result = timeout_policy.evaluate(task=task, flow=flow)
    
    print(f"Task {task.handler}: {retry_result['result'].value}")
```

### Flow Registry

```python
from sdk.registry import FlowRegistry

# Connect to registry
registry = FlowRegistry(
    host="localhost",
    database="agent_framework",
    username="postgres",
    password="password"
)

# Register flow
metadata = registry.register_flow(
    flow=flow,
    name="Data Processing Flow",
    description="Processes user data and generates predictions",
    tags=["data-processing", "ml"]
)

# List flows
flows = registry.list_flows(tenant_id="tenant_123")
for flow_metadata in flows:
    print(f"Flow: {flow_metadata.name} (v{flow_metadata.version})")
```

### CLI Usage

```bash
# Validate a flow
python agentctl validate my_flow.json

# Publish a flow to registry
python agentctl publish my_flow.json --name "My Flow" --tags "ml,data"

# List flows
python agentctl list --tenant-id tenant_123

# Get flow details
python agentctl get flow-123-456

# Show registry statistics
python agentctl stats
```

## API Reference

### Models

#### Task

A single executable task in a workflow.

```python
Task(
    handler: str,                    # Handler/connector name
    inputs: Dict[str, Any] = {},    # Input parameters
    retries: int = 3,               # Maximum retry attempts
    timeout: int = 300,             # Timeout in seconds
    condition: Optional[str] = None, # Conditional execution
    metadata: Dict[str, Any] = {}   # Additional metadata
)
```

#### Flow

A complete workflow consisting of multiple tasks.

```python
Flow(
    tasks: List[Task],              # List of tasks
    version: str = "1.0.0",         # Flow version
    type: Literal["DAG", "STATE_MACHINE"] = "DAG",  # Execution type
    tenant_id: Optional[str] = None, # Tenant identifier
    metadata: Dict[str, Any] = {}   # Additional metadata
)
```

### Policy System

#### Base Policy

```python
class Policy(ABC):
    def evaluate(self, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        pass
```

#### PreTaskPolicy

Evaluated before task execution.

```python
class PreTaskPolicy(Policy):
    def evaluate(self, task: Task, flow: Flow, context: Optional[Dict] = None) -> Dict[str, Any]:
        pass
```

#### PostTaskPolicy

Evaluated after task execution.

```python
class PostTaskPolicy(Policy):
    def evaluate(self, task: Task, flow: Flow, result: Dict[str, Any], context: Optional[Dict] = None) -> Dict[str, Any]:
        pass
```

#### FlowPolicy

Evaluated at the flow level.

```python
class FlowPolicy(Policy):
    def evaluate(self, flow: Flow, context: Optional[Dict] = None) -> Dict[str, Any]:
        pass
```

### Registry

#### FlowRegistry

PostgreSQL-backed registry for flow metadata.

```python
registry = FlowRegistry(
    connection_string: Optional[str] = None,
    host: str = "localhost",
    port: int = 5432,
    database: str = "agent_framework",
    username: str = "postgres",
    password: str = "password",
    schema: str = "public"
)
```

**Methods:**
- `register_flow(flow, name, description=None, tags=None, metadata=None)`
- `get_flow(flow_id)`
- `get_flow_metadata(flow_id)`
- `list_flows(tenant_id=None, name_filter=None, tag_filter=None, limit=100, offset=0)`
- `update_flow(flow, name=None, description=None, tags=None, metadata=None)`
- `delete_flow(flow_id)`
- `search_flows(query, tenant_id=None, limit=100)`
- `get_flow_statistics(tenant_id=None)`

## Built-in Policies

### RetryLimitPolicy

Enforces maximum retry limits on tasks.

```python
policy = RetryLimitPolicy(max_retries=5)
```

### TimeoutPolicy

Enforces timeout limits on tasks.

```python
policy = TimeoutPolicy(max_timeout=3600)
```

### TenantIsolationPolicy

Enforces tenant isolation in flows.

```python
policy = TenantIsolationPolicy()
```

### ResultValidationPolicy

Validates task execution results.

```python
policy = ResultValidationPolicy(required_fields=["status", "data"])
```

## Testing

Run the test suite:

```bash
pytest tests/ -v
```

Run specific test modules:

```bash
pytest tests/sdk/test_models.py -v
pytest tests/sdk/test_policy.py -v
pytest tests/sdk/test_registry.py -v
```

## Examples

See the `examples/` directory for complete usage examples:

- `sdk_example.py`: Comprehensive example showing all SDK features

## CLI Commands

### validate

Validate a flow definition file.

```bash
python agentctl validate <flow.json> [--output results.json] [--format json|yaml|text]
```

### publish

Publish a flow to the registry.

```bash
python agentctl publish <flow.json> --name "Flow Name" [--description "Description"] [--tags "tag1,tag2"]
```

### list

List flows in the registry.

```bash
python agentctl list [--tenant-id <id>] [--name-filter <name>] [--tags "tag1,tag2"] [--format table|json|yaml]
```

### get

Retrieve a flow by ID.

```bash
python agentctl get <flow-id> [--output <file.json>]
```

### delete

Delete a flow from the registry.

```bash
python agentctl delete <flow-id> [--confirm]
```

### stats

Show registry statistics.

```bash
python agentctl stats
```

## Configuration

### Database Setup

The registry requires a PostgreSQL database. Create the database and user:

```sql
CREATE DATABASE agent_framework;
CREATE USER agent_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE agent_framework TO agent_user;
```

The registry will automatically create the required tables on first use.

### Environment Variables

You can configure the registry using environment variables:

```bash
export AGENT_DB_HOST=localhost
export AGENT_DB_PORT=5432
export AGENT_DB_NAME=agent_framework
export AGENT_DB_USER=agent_user
export AGENT_DB_PASSWORD=your_password
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
