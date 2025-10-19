# Observability Stack Startup Script for Enterprise AI Agent Framework
# PowerShell version for Windows systems

Write-Host "🚀 Starting Enterprise AI Agent Framework Observability Stack" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green

# Check if Docker is running
try {
    docker info | Out-Null
} catch {
    Write-Host "❌ Docker is not running. Please start Docker and try again." -ForegroundColor Red
    exit 1
}

# Check if Docker Compose is available
try {
    docker-compose --version | Out-Null
} catch {
    Write-Host "❌ Docker Compose is not installed. Please install Docker Compose and try again." -ForegroundColor Red
    exit 1
}

# Create observability network if it doesn't exist
Write-Host "📡 Creating observability network..." -ForegroundColor Yellow
try {
    docker network create observability-network | Out-Null
    Write-Host "✅ Network created" -ForegroundColor Green
} catch {
    Write-Host "ℹ️ Network already exists" -ForegroundColor Blue
}

# Start the observability stack
Write-Host "📊 Starting observability stack (Prometheus, Grafana, Jaeger, etc.)..." -ForegroundColor Yellow
docker-compose -f observability/docker-compose.observability.yml up -d

# Wait for services to be ready
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service health
Write-Host "🔍 Checking service health..." -ForegroundColor Yellow
$services = @("prometheus", "grafana", "jaeger", "elasticsearch", "kibana", "fluentd", "alertmanager")
foreach ($service in $services) {
    $running = docker ps --filter "name=$service" --filter "status=running" --format "{{.Names}}" | Select-String $service
    if ($running) {
        Write-Host "✅ $service is running" -ForegroundColor Green
    } else {
        Write-Host "❌ $service is not running" -ForegroundColor Red
    }
}

# Ask if user wants to start additional services
Write-Host ""
$response = Read-Host "🤔 Do you want to start Redis, PostgreSQL, and Kafka with their exporters? (y/n)"
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host "🗄️ Starting additional services..." -ForegroundColor Yellow
    docker-compose -f observability/docker-compose.services.yml up -d
    
    # Wait for additional services
    Start-Sleep -Seconds 5
    
    # Check additional service health
    $additionalServices = @("redis", "postgres", "kafka", "zookeeper", "redis-exporter", "postgres-exporter", "kafka-exporter")
    foreach ($service in $additionalServices) {
        $running = docker ps --filter "name=$service" --filter "status=running" --format "{{.Names}}" | Select-String $service
        if ($running) {
            Write-Host "✅ $service is running" -ForegroundColor Green
        } else {
            Write-Host "❌ $service is not running" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "🎉 Observability Stack Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Access your dashboards:" -ForegroundColor Cyan
Write-Host "  • Grafana:      http://localhost:3000 (admin/admin)" -ForegroundColor White
Write-Host "  • Prometheus:   http://localhost:9090" -ForegroundColor White
Write-Host "  • Jaeger:       http://localhost:16686" -ForegroundColor White
Write-Host "  • Kibana:       http://localhost:5601" -ForegroundColor White
Write-Host "  • Alertmanager: http://localhost:9093" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Service endpoints:" -ForegroundColor Cyan
Write-Host "  • Elasticsearch: http://localhost:9200" -ForegroundColor White
Write-Host "  • Fluentd:       http://localhost:24224" -ForegroundColor White
Write-Host "  • Node Exporter: http://localhost:9100/metrics" -ForegroundColor White
Write-Host "  • cAdvisor:      http://localhost:8080/metrics" -ForegroundColor White
Write-Host ""

if ($response -eq "y" -or $response -eq "Y") {
    Write-Host "🗄️ Additional service endpoints:" -ForegroundColor Cyan
    Write-Host "  • Redis:           redis://localhost:6379" -ForegroundColor White
    Write-Host "  • PostgreSQL:      postgresql://postgres:password@localhost:5432/agent_framework" -ForegroundColor White
    Write-Host "  • Kafka:           localhost:9092" -ForegroundColor White
    Write-Host "  • Redis Exporter:  http://localhost:9121/metrics" -ForegroundColor White
    Write-Host "  • Postgres Exporter: http://localhost:9187/metrics" -ForegroundColor White
    Write-Host "  • Kafka Exporter:  http://localhost:9308/metrics" -ForegroundColor White
    Write-Host ""
}

Write-Host "📋 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Import Grafana dashboard from observability/grafana_dashboard.json" -ForegroundColor White
Write-Host "  2. Configure Prometheus data source in Grafana (http://prometheus:9090)" -ForegroundColor White
Write-Host "  3. Run the demo: python examples/observability_demo.py" -ForegroundColor White
Write-Host "  4. Run tests: pytest tests/observability/test_observability.py" -ForegroundColor White
Write-Host ""
Write-Host "🛑 To stop the stack:" -ForegroundColor Cyan
Write-Host "  docker-compose -f observability/docker-compose.observability.yml down" -ForegroundColor White
if ($response -eq "y" -or $response -eq "Y") {
    Write-Host "  docker-compose -f observability/docker-compose.services.yml down" -ForegroundColor White
}
Write-Host ""
Write-Host "✨ Happy monitoring!" -ForegroundColor Green
