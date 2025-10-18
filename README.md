# AI Agent Framework

A comprehensive framework for building and orchestrating AI agent workflows with support for DAGs, state machines, memory, guardrails, and observability.

## Project Structure

```
agent-framework/
├── sdk/                    # Framework SDK and APIs
├── orchestrator/           # Workflow orchestration engine
├── executor/              # Task execution engine
├── ingress/               # Input handling (REST, queue, files)
├── infra/                 # Infrastructure and deployment configs
├── demos/                 # Reference agent implementations
├── observability/         # Monitoring, logging, and dashboards
└── tests/                 # Unit and integration tests
```

## Features

- **Task Flows**: DAG and state machine support
- **Memory**: Redis (short-term) + Postgres/Cassandra (long-term)
- **Guardrails**: Pluggable safety and correctness policies
- **Observability**: Prometheus + Grafana + OpenTelemetry
- **ML Optimization**: Intel DevCloud + OpenVINO integration
- **Reliability**: Retries, timeouts, dead-letter queues

## Quick Start

Coming soon...

## Development

This project follows the specifications outlined in the core requirements document.

## License

TBD
