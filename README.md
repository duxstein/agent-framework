<!-- PROJECT LOGO -->
<p align="center">
  <a href="#">
    <img src="docs/assets/logo.png" alt="AI Agent Framework Logo" width="140" height="140">
  </a>
</p>

<h1 align="center">🤖 SynapSys</h1>

<p align="center">
  <b>End-to-End Framework for Building, Orchestrating & Observing Intelligent AI Agents</b>
  <br/>
  <br/>
  <a href="#"><img src="https://img.shields.io/badge/python-3.10+-blue.svg?logo=python&logoColor=white" alt="Python 3.10+"></a>
  <a href="#"><img src="https://img.shields.io/badge/OpenVINO-Enabled-success.svg?logo=intel&logoColor=white" alt="OpenVINO"></a>
  <a href="#"><img src="https://img.shields.io/badge/Intel-DevCloud-blue.svg?logo=intel&logoColor=white" alt="Intel DevCloud"></a>
  <a href="#"><img src="https://img.shields.io/badge/Apache-Airflow-orange.svg?logo=apacheairflow&logoColor=white" alt="Apache Airflow"></a>
  <a href="#"><img src="https://img.shields.io/badge/Apache-Kafka-black.svg?logo=apachekafka&logoColor=white" alt="Apache Kafka"></a>
  <a href="#"><img src="https://img.shields.io/badge/License-TBD-lightgrey.svg" alt="License TBD"></a>
</p>

---

## 🧭 Overview

The **SynapSys** is a modular, extensible system for building autonomous and semi-autonomous agents that can reason, act, and adapt.  
It integrates **workflow orchestration**, **observability**, **tool integrations**, and **Intel® optimizations** to deliver real-world performance and reliability for intelligent automation systems.

This repository contains an **Enterprise**-grade implementation with: multi-tenancy, Pydantic validation, a policy system, PostgreSQL-backed Flow Registry, REST ingress, Docker Compose for local dev, CLI tooling, and extensive tests.

---

## 🏗️ Project Structure

```bash
agent-framework/
├── sdk/                    # Core SDK for agent creation and workflow design
│   ├── models.py           # Pydantic Task/Flow models
│   ├── policy.py           # Policy interfaces and builtin policies
│   └── registry.py         # FlowRegistry client & helpers
├── orchestrator/           # Workflow orchestration engine (Airflow/state-machine)
│   ├── dags/               # Airflow DAG definitions generated from flows
│   └── state_machine.py    # Alternative state-machine runner
├── executor/               # Execution engine and workers
│   ├── executor_core.py
│   ├── retry_manager.py
│   └── tools/              # Tool adapters (LLM, HTTP, DB, OCR...)
├── ingress/                # REST API, webhooks, and ingress handlers
│   ├── api.py              # FastAPI application
│   └── auth.py             # JWT auth & tenant middleware
├── infra/                  # Docker, Kubernetes manifests, CI configs
│   ├── docker-compose.yml
│   └── k8s/
├── observability/          # Prometheus, Grafana, OpenTelemetry configs
├── demos/                  # Reference agents and example workflows
│   ├── doc_qna/
│   └── ticket_resolver/
├── docs/                   # Design docs, diagrams, screenshots, READMEs per module
├── tests/                  # Unit & integration tests (pytest)
└── tools/                  # CLI (agentctl) and helper scripts
```

---

## ⚙️ Features

- **Pydantic Models**: Type-safe Task and Flow models with automatic validation and helpful error messages.  
- **Policy System**: Extensible policy framework supporting pre-task, post-task, and flow-level policies (for retries, timeouts, validation, tenant rules).  
- **Flow Registry**: PostgreSQL-backed registry for versioned flow metadata, auditing, and search.  
- **REST API**: FastAPI-based ingress API with JWT authentication, multi-tenant middleware, and webhook support.  
- **Docker Compose**: Complete local development environment (Postgres, Redis, Kafka, Airflow, Grafana, Prometheus).  
- **CLI Tool**: `agentctl` for validate/publish/list/get/delete flows and view registry stats.  
- **Multi-tenancy**: Tenant isolation via request middleware, storage partitioning and policy scopes.  
- **Comprehensive Testing**: Pytest test suite covering SDK, policies, registry, and end-to-end flows.

---

## 🚀 Quick Start with Docker Compose

The easiest way to get started is using Docker Compose, which provides a complete local development environment:

```bash
# Start all services
docker-compose up -d

# View logs for the ingress API
docker-compose logs -f ingress-api

# Test the API health endpoint
curl http://localhost:8000/health

# Stop services
docker-compose down
```

### Services Included

- **Ingress API** (Port 8000): FastAPI service for flow management and ingress.  
- **PostgreSQL** (Port 5432): Database for audit logs and flow registry.  
- **Redis** (Port 6379): Caching layer and short-term memory.  
- **Kafka** (Port 9092): Message broker for flow events and inter-agent messaging.  
- **Kafka UI** (Port 8080): Web interface for Kafka monitoring.  
- **Airflow** (Port 8081): DAG orchestration UI (optional, if using Airflow orchestrator).  
- **Grafana** (Port 3000) & **Prometheus** (Port 9090): Observability stack.

For detailed Docker setup instructions, see `docker/README.md`.

---

## Installation (local dev)

```bash
git clone https://github.com/your-username/agent-framework.git
cd agent-framework
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

If you use Docker Compose, many dependencies (DB, Kafka, Redis) are provided by the compose stack so local install is mainly for development tools and SDK usage.

---

## ⚡ Quick Start Examples

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

---

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

---

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

---

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

---

## Examples

See the `examples/` directory for complete usage examples:

- `sdk_example.py`: Comprehensive example showing all SDK features

---

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

---

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

---

## Related README Files (module-specific)

> Use these links to jump to module-level documentation within this repository.

- 📦 **docker/README.md** — Docker Compose, environment, and deployment instructions.  
- ⚙️ **sdk/README.md** — SDK reference, models, and code examples.  
- 🧩 **cli/README.md** — CLI usage, flags, and examples (`agentctl`).  
- 🌐 **api/README.md** — REST API endpoints, authentication, and webhook docs.  
- 📊 **observability/README.md** — Grafana dashboards, Prometheus metrics, and tracing.  
- 🧪 **tests/README.md** — Test strategy and running CI tests.

---

## Contributing

1. Fork the repository  
2. Create a feature branch  
3. Add tests for new functionality  
4. Ensure all tests pass  
5. Submit a pull request with clear description and changelog

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

<p align="center">
  <sub>Built with ❤️ for the <b>Intel Unnati Program 2025</b><br/>
  Powered by <b>FastAPI</b>, <b>PostgreSQL</b>, and <b>Docker</b>.
  <br/>
  <b>© 2025 AI Agent Framework</b></sub>
</p>
