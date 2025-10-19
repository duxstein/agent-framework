### AI Agent Framework: Setup, Testing, Benchmarking, and Operations Guide

This guide walks you through local setup (Windows, macOS/Linux), running the stack, executing tests, basic benchmarking, observability, and troubleshooting for the AI Agent Framework.

---

## 1) Prerequisites

- Docker Desktop (with Docker Compose v2)
- Python 3.10+
- Git

Optional (for development):
- PowerShell (Windows) or Bash (macOS/Linux)
- curl

---

## 2) Clone and Install (local SDK/dev)

```bash
git clone <your-fork-or-repo-url>
cd agent-framework
python -m venv venv
# Windows PowerShell
./venv/Scripts/Activate.ps1
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
```

Notes:
- Local install is useful for running unit tests and the SDK; services like PostgreSQL, Redis, and Kafka are provided by Docker Compose.

---

## 3) Bring Up the Stack with Docker Compose

The repository includes a complete local environment via `docker-compose.yml`.

```bash
# From repo root
docker-compose up -d

# Check services
docker-compose ps

# Tail API logs
docker-compose logs -f ingress-api
```

Health checks and ports (defaults):
- Ingress API: http://localhost:8000 (GET /health)
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- Kafka: localhost:9092
- Kafka UI: http://localhost:8080

Tip: Use the helper script on macOS/Linux for a guided startup:
```bash
./start.sh
```

---

## 4) Configuration

Key environment variables are set in `docker-compose.yml` (see `docker/README.md` for details). To customize:
1. Copy example env and edit your values:
   ```bash
   cp docker/env.example docker/.env
   ```
2. Optionally reference `docker/.env` from `docker-compose.yml` if you want to externalize secrets.

Core variables in use:
- JWT: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`
- Database: `DATABASE_URL`
- Redis: `REDIS_URL`
- Kafka: `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC_FLOW_RUNS`

---

## 5) Quick API Smoke Test

```bash
curl http://localhost:8000/health
```

You should receive a 200 response indicating service health.

Kafka UI: open http://localhost:8080 to inspect topics and consumers.

---

## 6) Running Tests

Run the entire test suite:
```bash
pytest tests/ -v
```

Run module-specific tests:
```bash
pytest tests/sdk/test_models.py -v
pytest tests/sdk/test_policy.py -v
pytest tests/sdk/test_registry.py -v
pytest tests/ingress/test_api.py -v
pytest tests/executor/test_worker.py -v
pytest tests/orchestrator/test_service.py -v
pytest tests/observability/test_observability.py -v
```

Windows users can also run targeted curl checks via `test.sh` equivalent commands directly in PowerShell.

---

## 7) Basic Benchmarking Scenarios

These lightweight checks help validate throughput and latency characteristics locally. For rigorous results, use dedicated benchmarking tools in CI or controlled hosts.

- API health endpoint latency (baseline):
  ```bash
  for i in {1..20}; do curl -s -o /dev/null -w "%{time_total}\n" http://localhost:8000/health; done
  ```

- Ingress run creation throughput (requires JWT if enforced):
  ```bash
  TOKEN="<your-jwt-token>"
  for i in {1..50}; do \
    curl -s -o /dev/null -X POST http://localhost:8000/v1/runs \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{"flow_id":"sample-flow-1","input":{"message":"Hello"},"tenant_id":"tenant-1"}' &
  done; wait
  ```

- Observe queue behavior and worker processing via Kafka UI and logs:
  ```bash
  docker-compose logs -f orchestrator
  docker-compose logs -f executor-worker
  ```

Metrics endpoints (if enabled in services):
- Orchestrator metrics: http://localhost:9090/metrics
- Executor metrics: http://localhost:9091/metrics

---

## 8) Observability Stack

See `observability/README.md` for full instructions.

Quick start:
```bash
# Option A: helper scripts
./observability/start-observability.sh

# Option B: manual
docker-compose -f observability/docker-compose.observability.yml up -d
docker-compose -f observability/docker-compose.services.yml up -d
```

Dashboards and tools:
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090
- Jaeger: http://localhost:16686

Recommended metrics to watch:
- API: request rate, P95 latency
- Orchestrator: runs processed, task schedule/complete rates
- Executor: task durations, success/failure/retry counts
- Kafka: consumer lag
- Redis/PostgreSQL: resource and connection metrics

---

## 9) Useful Developer Commands

Logs:
```bash
docker-compose logs -f ingress-api
docker-compose logs -f orchestrator
docker-compose logs -f executor-worker
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f kafka
```

Shell into a container:
```bash
docker-compose exec -it postgres sh
docker-compose exec -it ingress-api sh
```

Reset the environment (removes volumes/data):
```bash
docker-compose down -v
```

---

## 10) Troubleshooting

- Ports already in use
  - Change exposed ports in `docker-compose.yml` (e.g., map `8001:8000`).

- Database not ready / connection failures
  - Check logs: `docker-compose logs postgres`
  - Test readiness: `docker-compose exec -T postgres pg_isready -U postgres`

- Kafka not healthy
  - Verify Zookeeper is healthy
  - Restart Kafka: `docker-compose restart kafka`

- Ingress API returns 5xx
  - Inspect `ingress-api` logs and ensure `DATABASE_URL`, `REDIS_URL`, and Kafka envs are correct.

- JWT issues when calling protected endpoints
  - Generate a valid token (see `generate_token.py`) and include `Authorization: Bearer <token>`.

---

## 11) References

- `README.md` — quick start, SDK usage, CLI examples
- `docker/README.md` — compose services, config, and ops tips
- `ingress/README.md`, `executor/README.md`, `orchestrator/README.md` — service details
- `observability/README.md` — monitoring, tracing, dashboards
- `tests/` — test suites across modules

---

## 12) Clean Up

```bash
docker-compose down
# To remove volumes and all data (irreversible):
docker-compose down -v
```


