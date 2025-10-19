# Core Guidelines for Enterprise AI Agent Framework

## Project Overview
- Build an AI Agent Framework that orchestrates agentic workflows end-to-end.
- Framework must handle multi-task, multi-connector flows with ML/LLM integration.
- Must be enterprise-grade: scalable, secure, extensible, observable.

## Architecture
- Ingress (REST API / Kafka / Webhooks) → Orchestrator → Executors → Memory/State → Observability
- Use DAG or State Machine for task flows.
- Executors are stateless; scale horizontally.
- Redis for ephemeral memory/context; Postgres for durable storage and audit.

## SDK
- Define Flow and Task objects.
- Support conditional execution, retries, timeout.
- Multi-tenant support.
- Guardrails: input validation, output filtering, SLA enforcement.

## Connectors
- Pluggable, versioned connectors for external services.
- Reference connectors: Gmail, Slack, Postgres, ML tasks (LLM, OCR, re-ranker).
- Connector interface: authenticate(), execute_action(), list_actions().
- Connector registry for dynamic discovery.

## ML / AI Integration
- Support LLM, OCR, re-ranker tasks.
- Optimize models using Intel OpenVINO on DevCloud.
- Maintain versioning, benchmarking, and logging.

## Orchestrator
- Schedule tasks per DAG/state-machine.
- Evaluate conditions and guardrails.
- Push tasks to Executor via Kafka.
- Retry, timeout, dead-letter queue.

## Executor
- Execute connector or ML tasks.
- Store outputs in Redis/Postgres.
- Emit task_done/task_failed.
- Observability: metrics & logs.

## Observability
- Prometheus metrics for flows, tasks, latency, SLA.
- Grafana dashboards.
- Structured logging with run_id, task_id, timestamp, status.
- Audit logs in Postgres, append-only.

## Security & Enterprise Requirements
- Multi-tenancy.
- RBAC (Role-Based Access Control).
- Secret management for API keys/OAuth.
- Guardrails to block unsafe operations.

## Reference Agents
1. Document Intelligence Agent: PDF/Image → OCR → Summarizer → Store → Notify
2. Meeting Assistant Agent: Audio → ASR → Extract action items → Human review → Notify

## Deliverables
- Framework SDK + runtime
- Two reference agents
- Enterprise-ready deployment (Docker/K8s/Helm)
- Prometheus/Grafana dashboards
- Design document + performance benchmarks
- Unit & integration tests
- README with run instructions

## Performance Targets
- Scalable execution with retries and timeouts.
- ML/LLM tasks optimized for Intel DevCloud.
- Demonstrate framework can scale to 1000+ connectors in principle.

