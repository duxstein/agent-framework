#!/bin/bash

# Observability Stack Startup Script for Enterprise AI Agent Framework
# This script helps deploy the observability stack with proper configuration

set -e

echo "🚀 Starting Enterprise AI Agent Framework Observability Stack"
echo "=============================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose > /dev/null 2>&1; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

# Create observability network if it doesn't exist
echo "📡 Creating observability network..."
docker network create observability-network 2>/dev/null || echo "Network already exists"

# Start the observability stack
echo "📊 Starting observability stack (Prometheus, Grafana, Jaeger, etc.)..."
docker-compose -f observability/docker-compose.observability.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."
services=("prometheus" "grafana" "jaeger" "elasticsearch" "kibana" "fluentd" "alertmanager")
for service in "${services[@]}"; do
    if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
    fi
done

# Ask if user wants to start additional services
echo ""
read -p "🤔 Do you want to start Redis, PostgreSQL, and Kafka with their exporters? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗄️ Starting additional services..."
    docker-compose -f observability/docker-compose.services.yml up -d
    
    # Wait for additional services
    sleep 5
    
    # Check additional service health
    additional_services=("redis" "postgres" "kafka" "zookeeper" "redis-exporter" "postgres-exporter" "kafka-exporter")
    for service in "${additional_services[@]}"; do
        if docker ps --filter "name=$service" --filter "status=running" | grep -q "$service"; then
            echo "✅ $service is running"
        else
            echo "❌ $service is not running"
        fi
    done
fi

echo ""
echo "🎉 Observability Stack Deployment Complete!"
echo "=========================================="
echo ""
echo "📊 Access your dashboards:"
echo "  • Grafana:      http://localhost:3000 (admin/admin)"
echo "  • Prometheus:   http://localhost:9090"
echo "  • Jaeger:       http://localhost:16686"
echo "  • Kibana:       http://localhost:5601"
echo "  • Alertmanager: http://localhost:9093"
echo ""
echo "🔧 Service endpoints:"
echo "  • Elasticsearch: http://localhost:9200"
echo "  • Fluentd:       http://localhost:24224"
echo "  • Node Exporter: http://localhost:9100/metrics"
echo "  • cAdvisor:      http://localhost:8080/metrics"
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🗄️ Additional service endpoints:"
    echo "  • Redis:           redis://localhost:6379"
    echo "  • PostgreSQL:      postgresql://postgres:password@localhost:5432/agent_framework"
    echo "  • Kafka:           localhost:9092"
    echo "  • Redis Exporter:  http://localhost:9121/metrics"
    echo "  • Postgres Exporter: http://localhost:9187/metrics"
    echo "  • Kafka Exporter:  http://localhost:9308/metrics"
    echo ""
fi

echo "📋 Next steps:"
echo "  1. Import Grafana dashboard from observability/grafana_dashboard.json"
echo "  2. Configure Prometheus data source in Grafana (http://prometheus:9090)"
echo "  3. Run the demo: python examples/observability_demo.py"
echo "  4. Run tests: pytest tests/observability/test_observability.py"
echo ""
echo "🛑 To stop the stack:"
echo "  docker-compose -f observability/docker-compose.observability.yml down"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  docker-compose -f observability/docker-compose.services.yml down"
fi
echo ""
echo "✨ Happy monitoring!"
