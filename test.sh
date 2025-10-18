#!/bin/bash

# Enterprise AI Agent Framework - Test Script
# This script tests the Docker Compose setup

set -e

echo "🧪 Testing Enterprise AI Agent Framework..."

# Test health endpoint
echo "🔍 Testing health endpoint..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Health endpoint is working"
else
    echo "❌ Health endpoint is not responding"
    exit 1
fi

# Test API documentation
echo "🔍 Testing API documentation..."
if curl -f http://localhost:8000/docs > /dev/null 2>&1; then
    echo "✅ API documentation is accessible"
else
    echo "❌ API documentation is not accessible"
fi

# Test Kafka UI
echo "🔍 Testing Kafka UI..."
if curl -f http://localhost:8080 > /dev/null 2>&1; then
    echo "✅ Kafka UI is accessible"
else
    echo "❌ Kafka UI is not accessible"
fi

# Test database connection
echo "🔍 Testing database connection..."
if docker-compose exec -T postgres psql -U postgres -d agent_framework -c "SELECT 1;" > /dev/null 2>&1; then
    echo "✅ Database connection is working"
else
    echo "❌ Database connection failed"
fi

# Test Redis connection
echo "🔍 Testing Redis connection..."
if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis connection is working"
else
    echo "❌ Redis connection failed"
fi

# Test Kafka connection
echo "🔍 Testing Kafka connection..."
if docker-compose exec -T kafka kafka-broker-api-versions --bootstrap-server localhost:9092 > /dev/null 2>&1; then
    echo "✅ Kafka connection is working"
else
    echo "❌ Kafka connection failed"
fi

echo ""
echo "🎉 All tests completed!"
echo ""
echo "📋 Service Status:"
docker-compose ps
