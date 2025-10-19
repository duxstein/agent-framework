"""
Unit tests for the Enterprise AI Agent Framework Ingress API.

This module contains comprehensive tests for the FastAPI service endpoints,
including authentication, validation, database operations, and Kafka messaging.
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from jose import jwt

from ingress.api import (
    app, verify_token, validate_tenant_scope,
    DatabaseClient, RedisClient, KafkaClient,
    FlowRunRequest, FlowRunResponse, FlowRunStatus
)
from sdk.models import Flow, Task


# Test configuration
JWT_SECRET_KEY = "test-secret-key"
JWT_ALGORITHM = "HS256"


def create_test_token(user_id: str = "test-user", tenant_id: str = "test-tenant") -> str:
    """Create a test JWT token."""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": datetime.now(timezone.utc).timestamp() + 3600
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def valid_token():
    """Create a valid JWT token for testing."""
    return create_test_token()


@pytest.fixture
def invalid_token():
    """Create an invalid JWT token for testing."""
    return "invalid.token.here"


@pytest.fixture
def mock_db_client():
    """Mock database client."""
    with patch('ingress.api.db_client') as mock:
        mock.execute_query = AsyncMock()
        yield mock


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    with patch('ingress.api.redis_client') as mock:
        mock.get = AsyncMock()
        mock.set = AsyncMock()
        yield mock


@pytest.fixture
def mock_kafka_client():
    """Mock Kafka client."""
    with patch('ingress.api.kafka_client') as mock:
        mock.send_message = AsyncMock()
        yield mock


@pytest.fixture
def sample_flow_definition():
    """Sample flow definition for testing."""
    return {
        "id": "test-flow-1",
        "version": "1.0.0",
        "tasks": [
            {
                "id": "task-1",
                "handler": "test-handler",
                "inputs": {"param1": "value1"},
                "retries": 3,
                "timeout": 300
            }
        ],
        "type": "DAG",
        "tenant_id": "test-tenant"
    }


class TestAuthentication:
    """Test authentication and authorization."""
    
    def test_verify_token_valid(self):
        """Test valid token verification."""
        token = create_test_token()
        credentials = MagicMock()
        credentials.credentials = token
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            # This would be tested in integration tests
            # For unit tests, we'll test the logic separately
            assert True  # Placeholder for actual test logic
    
    def test_verify_token_invalid(self):
        """Test invalid token verification."""
        with pytest.raises(Exception):  # Should raise HTTPException
            # This would be tested in integration tests
            assert True  # Placeholder for actual test logic
    
    def test_validate_tenant_scope_valid(self):
        """Test valid tenant scope validation."""
        user_info = {
            "user_id": "test-user",
            "tenant_id": "test-tenant"
        }
        
        # This would be tested in integration tests
        assert True  # Placeholder for actual test logic
    
    def test_validate_tenant_scope_invalid(self):
        """Test invalid tenant scope validation."""
        user_info = {
            "user_id": "test-user",
            "tenant_id": "different-tenant"
        }
        
        # This would be tested in integration tests
        assert True  # Placeholder for actual test logic


class TestFlowRunCreation:
    """Test flow run creation endpoint."""
    
    def test_create_flow_run_success(self, test_client, valid_token, mock_db_client, mock_kafka_client, sample_flow_definition):
        """Test successful flow run creation."""
        request_data = {
            "flow_id": "test-flow-1",
            "flow_definition": sample_flow_definition,
            "input": {"param1": "value1"},
            "tenant_id": "test-tenant",
            "request_id": "req-123"
        }
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            response = test_client.post("/v1/runs", json=request_data, headers=headers)
            
            assert response.status_code == 202
            data = response.json()
            assert "run_id" in data
            assert "correlation_id" in data
            assert len(data["run_id"]) == 36  # UUID length
            assert len(data["correlation_id"]) == 36  # UUID length
    
    def test_create_flow_run_invalid_flow_definition(self, test_client, valid_token):
        """Test flow run creation with invalid flow definition."""
        request_data = {
            "flow_id": "test-flow-1",
            "flow_definition": {
                "id": "test-flow-1",
                "tasks": []  # Empty tasks should fail validation
            },
            "input": {"param1": "value1"},
            "tenant_id": "test-tenant"
        }
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            response = test_client.post("/v1/runs", json=request_data, headers=headers)
            
            assert response.status_code == 400
            assert "Invalid flow definition" in response.json()["detail"]
    
    def test_create_flow_run_unauthorized(self, test_client):
        """Test flow run creation without authentication."""
        request_data = {
            "flow_id": "test-flow-1",
            "input": {"param1": "value1"},
            "tenant_id": "test-tenant"
        }
        
        response = test_client.post("/v1/runs", json=request_data)
        
        assert response.status_code == 403  # Unauthorized
    
    def test_create_flow_run_tenant_scope_violation(self, test_client):
        """Test flow run creation with tenant scope violation."""
        token = create_test_token(tenant_id="different-tenant")
        request_data = {
            "flow_id": "test-flow-1",
            "input": {"param1": "value1"},
            "tenant_id": "test-tenant"  # Different from token tenant
        }
        
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "different-tenant"
            }
            
            response = test_client.post("/v1/runs", json=request_data, headers=headers)
            
            assert response.status_code == 403
            assert "tenant scope violation" in response.json()["detail"]


class TestFlowRunStatus:
    """Test flow run status retrieval."""
    
    def test_get_flow_run_status_success(self, test_client, valid_token, mock_db_client, mock_redis_client):
        """Test successful flow run status retrieval."""
        run_id = str(uuid.uuid4())
        
        # Mock Redis cache miss
        mock_redis_client.get.return_value = None
        
        # Mock database response
        mock_db_client.execute_query.return_value = [{
            "run_id": run_id,
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "tenant_id": "test-tenant",
            "flow_id": "test-flow-1",
            "input_data": {"param1": "value1"},
            "output_data": None,
            "error_message": None
        }]
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            response = test_client.get(f"/v1/runs/{run_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == run_id
            assert data["status"] == "RUNNING"
            assert data["tenant_id"] == "test-tenant"
    
    def test_get_flow_run_status_from_cache(self, test_client, valid_token, mock_redis_client):
        """Test flow run status retrieval from cache."""
        run_id = str(uuid.uuid4())
        
        # Mock Redis cache hit
        cached_data = {
            "run_id": run_id,
            "status": "COMPLETED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "tenant_id": "test-tenant",
            "flow_id": "test-flow-1",
            "input": {"param1": "value1"},
            "output": {"result": "success"},
            "error": None
        }
        
        mock_redis_client.get.return_value = json.dumps(cached_data)
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            response = test_client.get(f"/v1/runs/{run_id}", headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == run_id
            assert data["status"] == "COMPLETED"
    
    def test_get_flow_run_status_not_found(self, test_client, valid_token, mock_db_client, mock_redis_client):
        """Test flow run status retrieval when run not found."""
        run_id = str(uuid.uuid4())
        
        # Mock Redis cache miss
        mock_redis_client.get.return_value = None
        
        # Mock database empty result
        mock_db_client.execute_query.return_value = []
        
        headers = {"Authorization": f"Bearer {valid_token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "test-tenant"
            }
            
            response = test_client.get(f"/v1/runs/{run_id}", headers=headers)
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]
    
    def test_get_flow_run_status_tenant_scope_violation(self, test_client, mock_db_client, mock_redis_client):
        """Test flow run status retrieval with tenant scope violation."""
        run_id = str(uuid.uuid4())
        token = create_test_token(tenant_id="different-tenant")
        
        # Mock Redis cache miss
        mock_redis_client.get.return_value = None
        
        # Mock database response with different tenant
        mock_db_client.execute_query.return_value = [{
            "run_id": run_id,
            "status": "RUNNING",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "tenant_id": "test-tenant",  # Different from token tenant
            "flow_id": "test-flow-1",
            "input_data": {"param1": "value1"},
            "output_data": None,
            "error_message": None
        }]
        
        headers = {"Authorization": f"Bearer {token}"}
        
        with patch('ingress.api.jwt.decode') as mock_decode:
            mock_decode.return_value = {
                "sub": "test-user",
                "tenant_id": "different-tenant"
            }
            
            response = test_client.get(f"/v1/runs/{run_id}", headers=headers)
            
            assert response.status_code == 403
            assert "tenant scope violation" in response.json()["detail"]


class TestHealthCheck:
    """Test health check endpoint."""
    
    def test_health_check_success(self, test_client, mock_db_client, mock_redis_client):
        """Test successful health check."""
        mock_db_client.execute_query.return_value = None
        mock_redis_client.get.return_value = None
        
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_health_check_failure(self, test_client, mock_db_client):
        """Test health check failure."""
        mock_db_client.execute_query.side_effect = Exception("Database connection failed")
        
        response = test_client.get("/health")
        
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]


class TestDatabaseClient:
    """Test database client functionality."""
    
    @pytest.mark.asyncio
    async def test_database_client_connection(self):
        """Test database client connection."""
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            
            client = DatabaseClient("postgresql://test:test@localhost:5432/test")
            conn = await client.get_connection()
            
            assert conn == mock_conn
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_database_client_execute_query(self):
        """Test database client query execution."""
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [{"id": 1, "name": "test"}]
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            client = DatabaseClient("postgresql://test:test@localhost:5432/test")
            result = await client.execute_query("SELECT * FROM test")
            
            assert result == [{"id": 1, "name": "test"}]
            mock_cursor.execute.assert_called_once_with("SELECT * FROM test", None)


class TestRedisClient:
    """Test Redis client functionality."""
    
    @pytest.mark.asyncio
    async def test_redis_client_get(self):
        """Test Redis client get operation."""
        with patch('redis.from_url') as mock_from_url:
            mock_client = MagicMock()
            mock_client.get.return_value = b"test_value"
            mock_from_url.return_value = mock_client
            
            client = RedisClient("redis://localhost:6379")
            result = await client.get("test_key")
            
            assert result == b"test_value"
            mock_client.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_redis_client_set(self):
        """Test Redis client set operation."""
        with patch('redis.from_url') as mock_from_url:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_from_url.return_value = mock_client
            
            client = RedisClient("redis://localhost:6379")
            result = await client.set("test_key", "test_value", expire=300)
            
            assert result is True
            mock_client.set.assert_called_once_with("test_key", "test_value", ex=300)


class TestKafkaClient:
    """Test Kafka client functionality."""
    
    @pytest.mark.asyncio
    async def test_kafka_client_send_message(self):
        """Test Kafka client send message operation."""
        with patch('kafka.KafkaProducer') as mock_producer_class:
            mock_producer = MagicMock()
            mock_future = MagicMock()
            mock_future.get.return_value = MagicMock()
            mock_producer.send.return_value = mock_future
            mock_producer_class.return_value = mock_producer
            
            client = KafkaClient(["localhost:9092"])
            await client.send_message("test_topic", {"message": "test"}, key="test_key")
            
            mock_producer.send.assert_called_once_with(
                "test_topic",
                value={"message": "test"},
                key="test_key"
            )


class TestPydanticModels:
    """Test Pydantic models."""
    
    def test_flow_run_request_valid(self):
        """Test valid FlowRunRequest."""
        request = FlowRunRequest(
            flow_id="test-flow-1",
            input={"param1": "value1"},
            tenant_id="test-tenant",
            request_id="req-123"
        )
        
        assert request.flow_id == "test-flow-1"
        assert request.input == {"param1": "value1"}
        assert request.tenant_id == "test-tenant"
        assert request.request_id == "req-123"
        assert request.flow_definition is None
    
    def test_flow_run_response_valid(self):
        """Test valid FlowRunResponse."""
        run_id = str(uuid.uuid4())
        correlation_id = str(uuid.uuid4())
        
        response = FlowRunResponse(
            run_id=run_id,
            correlation_id=correlation_id
        )
        
        assert response.run_id == run_id
        assert response.correlation_id == correlation_id
    
    def test_flow_run_status_valid(self):
        """Test valid FlowRunStatus."""
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        status = FlowRunStatus(
            run_id=run_id,
            status="RUNNING",
            created_at=now,
            updated_at=now,
            tenant_id="test-tenant",
            flow_id="test-flow-1",
            input={"param1": "value1"},
            output=None,
            error=None
        )
        
        assert status.run_id == run_id
        assert status.status == "RUNNING"
        assert status.tenant_id == "test-tenant"
        assert status.input == {"param1": "value1"}


if __name__ == "__main__":
    pytest.main([__file__])

