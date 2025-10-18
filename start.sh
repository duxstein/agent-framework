#!/bin/bash

# Enterprise AI Agent Framework - Startup Script
# This script helps you get started with the Docker Compose setup

set -e

echo "🚀 Starting Enterprise AI Agent Framework..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose and try again."
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f docker/.env ]; then
    echo "📝 Creating environment file..."
    cp docker/env.example docker/.env
    echo "✅ Environment file created at docker/.env"
    echo "⚠️  Please review and update the environment variables as needed"
fi

# Start services
echo "🐳 Starting Docker services..."
docker-compose up -d

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check PostgreSQL
if docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; then
    echo "✅ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
fi

# Check Redis
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check Kafka
if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "✅ Kafka is ready"
else
    echo "❌ Kafka is not ready"
fi

# Check Ingress API
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Ingress API is ready"
else
    echo "❌ Ingress API is not ready"
fi

echo ""
echo "🎉 Enterprise AI Agent Framework is running!"
echo ""
echo "📋 Service URLs:"
echo "   • Ingress API:     http://localhost:8000"
echo "   • API Documentation: http://localhost:8000/docs"
echo "   • Kafka UI:        http://localhost:8080"
echo "   • PostgreSQL:      localhost:5432"
echo "   • Redis:           localhost:6379"
echo "   • Kafka:           localhost:9092"
echo ""
echo "🧪 Test the API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "📊 View logs:"
echo "   docker-compose logs -f ingress-api"
echo ""
echo "🛑 Stop services:"
echo "   docker-compose down"
echo ""
echo "📚 For more information, see docker/README.md"
