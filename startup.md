# Start everything
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f ingress-api

# Test the API
curl http://localhost:8000/health



🔗 Service URLs
Ingress API: http://localhost:8000
API Documentation: http://localhost:8000/docs
Kafka UI: http://localhost:8080
PostgreSQL: localhost:5432
Redis: localhost:6379
Kafka: localhost:9092


| Endpoint                   | Status       | Description |
|----------------------------|--------------|-------------|
| `/`                        | ✅ Working   | API information and endpoint list |
| `/health`                  | ✅ Working   | Health check |
| `/docs`                    | ✅ Working   | Interactive API documentation |
| `/redoc`                   | ✅ Working   | Alternative API documentation |
| `/openapi.json`            | ✅ Working   | OpenAPI specification |
| `/v1/runs`                 | ✅ Working   | Create flow runs (requires JWT) |
| `/v1/runs/{run_id}`        | ✅ Working   | Get run status (requires JWT) |
| `/v1/webhooks/{webhook_id}`| ✅ Working   | Webhook endpoint |




3