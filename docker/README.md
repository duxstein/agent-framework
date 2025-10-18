# Enterprise AI Agent Framework - Docker Compose Setup

This Docker Compose configuration provides a complete local development environment for the Enterprise AI Agent Framework, including all required services and the ingress API.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop or Docker Engine
- Docker Compose v2.0+

### Start the Services

```bash
# Start all services
docker-compose up -d

# Start with orchestrator (if implemented)
docker-compose --profile orchestrator up -d

# View logs
docker-compose logs -f ingress-api
```

### Stop the Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This will delete all data)
docker-compose down -v
```

## 📋 Services Overview

### Core Services

| Service | Port | Description |
|---------|------|-------------|
| **PostgreSQL** | 5432 | Primary database for audit logs, flow registry, and webhook configs |
| **Redis** | 6379 | Caching layer for run status and session data |
| **Kafka** | 9092 | Message broker for flow run events |
| **Zookeeper** | 2181 | Kafka coordination service |
| **Kafka UI** | 8080 | Web interface for Kafka monitoring |

### Application Services

| Service | Port | Description |
|---------|------|-------------|
| **Ingress API** | 8000 | FastAPI service for flow run management |
| **Orchestrator** | 8001 | Flow orchestration service (placeholder) |

## 🔧 Configuration

### Environment Variables

The services are configured via environment variables in `docker-compose.yml`:

```yaml
# JWT Configuration
JWT_SECRET_KEY: "your-secret-key-change-in-production"
JWT_ALGORITHM: "HS256"

# Database Configuration
DATABASE_URL: "postgresql://postgres:postgres@postgres:5432/agent_framework"

# Redis Configuration
REDIS_URL: "redis://redis:6379"

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS: "kafka:29092"
KAFKA_TOPIC_FLOW_RUNS: "flow_runs"
```

### Custom Configuration

To customize the configuration:

1. **Copy environment file:**
   ```bash
   cp docker/.env.example docker/.env
   ```

2. **Edit `docker/.env` with your settings**

3. **Update `docker-compose.yml` to use the env file:**
   ```yaml
   ingress-api:
     env_file:
       - docker/.env
   ```

## 🗄️ Database Schema

The PostgreSQL database is automatically initialized with:

- **flow_runs_audit**: Audit trail for all flow runs
- **webhook_configs**: Webhook endpoint configurations
- **flows**: Flow registry for centralized flow management
- **Indexes**: Optimized indexes for performance
- **Triggers**: Automatic timestamp updates
- **Sample Data**: Test webhook and flow configurations

### Accessing the Database

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres -d agent_framework

# View tables
\dt

# View sample data
SELECT * FROM webhook_configs;
SELECT * FROM flows;
```

## 🔍 Monitoring & Debugging

### Service Health Checks

All services include health checks. Check status:

```bash
# View service status
docker-compose ps

# Check health
docker-compose exec ingress-api curl http://localhost:8000/health
```

### Logs

```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f ingress-api
docker-compose logs -f kafka
docker-compose logs -f postgres
```

### Kafka Monitoring

Access Kafka UI at http://localhost:8080 to:
- View topics and messages
- Monitor consumer groups
- Inspect message content
- Debug message flow

## 🧪 Testing the API

### 1. Health Check

```bash
curl http://localhost:8000/health
```

### 2. Create a Flow Run (with JWT token)

```bash
# Generate a test JWT token (you'll need to implement this)
TOKEN="your-jwt-token-here"

curl -X POST http://localhost:8000/v1/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flow_id": "sample-flow-1",
    "input": {"message": "Hello World"},
    "tenant_id": "tenant-1"
  }'
```

### 3. Test Webhook Endpoint

```bash
curl -X POST http://localhost:8000/v1/webhooks/sample-webhook-1 \
  -H "Content-Type: application/json" \
  -d '{
    "webhook_id": "sample-webhook-1",
    "payload": {"message": "Webhook test"},
    "source": "test-client"
  }'
```

### 4. Check Run Status

```bash
# Replace {run_id} with actual run ID from previous response
curl http://localhost:8000/v1/runs/{run_id} \
  -H "Authorization: Bearer $TOKEN"
```

## 🔐 Security Considerations

### Production Deployment

For production deployment:

1. **Change default passwords:**
   ```yaml
   POSTGRES_PASSWORD: "strong-random-password"
   JWT_SECRET_KEY: "very-long-random-secret-key"
   ```

2. **Use secrets management:**
   ```yaml
   secrets:
     - postgres_password
     - jwt_secret_key
   ```

3. **Enable SSL/TLS:**
   - Configure PostgreSQL SSL
   - Use HTTPS for API endpoints
   - Enable Kafka SASL authentication

4. **Network security:**
   - Use custom networks
   - Restrict port exposure
   - Implement firewall rules

## 🛠️ Development

### Adding New Services

To add a new service:

1. **Add service to `docker-compose.yml`:**
   ```yaml
   new-service:
     build: ./docker/Dockerfile.new-service
     depends_on:
       - postgres
       - redis
     environment:
       DATABASE_URL: "postgresql://postgres:postgres@postgres:5432/agent_framework"
     networks:
       - agent-network
   ```

2. **Create Dockerfile:**
   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY requirements.txt .
   RUN pip install -r requirements.txt
   COPY new-service/ ./new-service/
   CMD ["python", "-m", "new-service"]
   ```

### Database Migrations

For database schema changes:

1. **Create migration script:**
   ```bash
   # Add to docker/postgres/migrations/
   touch docker/postgres/migrations/001_add_new_table.sql
   ```

2. **Update init.sql to run migrations:**
   ```sql
   -- Add to init.sql
   \i /docker-entrypoint-initdb.d/migrations/001_add_new_table.sql
   ```

## 📊 Performance Tuning

### Resource Limits

Add resource limits to services:

```yaml
services:
  ingress-api:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
```

### Scaling

Scale services horizontally:

```bash
# Scale ingress API
docker-compose up -d --scale ingress-api=3

# Scale with load balancer
docker-compose up -d nginx ingress-api
```

## 🐛 Troubleshooting

### Common Issues

1. **Port conflicts:**
   ```bash
   # Check what's using the port
   netstat -tulpn | grep :8000
   
   # Change ports in docker-compose.yml
   ports:
     - "8001:8000"  # Use different host port
   ```

2. **Database connection issues:**
   ```bash
   # Check PostgreSQL logs
   docker-compose logs postgres
   
   # Test connection
   docker-compose exec postgres pg_isready -U postgres
   ```

3. **Kafka not starting:**
   ```bash
   # Check Zookeeper
   docker-compose logs zookeeper
   
   # Restart Kafka
   docker-compose restart kafka
   ```

### Debug Mode

Enable debug logging:

```yaml
environment:
  LOG_LEVEL: "DEBUG"
  PYTHONUNBUFFERED: "1"
```

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
