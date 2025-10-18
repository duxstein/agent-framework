"""
Unit tests for Enterprise AI Agent Framework SDK registry.

This module contains comprehensive tests for the FlowRegistry and FlowMetadata classes.
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from sdk.models import Task, Flow
from sdk.registry import FlowRegistry, FlowMetadata, RegistryError


class TestFlowMetadata:
    """Test cases for the FlowMetadata class."""
    
    def test_flow_metadata_creation_with_defaults(self):
        """Test flow metadata creation with default values."""
        metadata = FlowMetadata(
            flow_id="test-flow-123",
            name="Test Flow",
            version="1.0.0"
        )
        
        assert metadata.flow_id == "test-flow-123"
        assert metadata.name == "Test Flow"
        assert metadata.version == "1.0.0"
        assert metadata.tenant_id is None
        assert metadata.description == ""
        assert metadata.tags == []
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)
        assert metadata.metadata == {}
    
    def test_flow_metadata_creation_with_custom_values(self):
        """Test flow metadata creation with custom values."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)
        
        metadata = FlowMetadata(
            flow_id="test-flow-123",
            name="Test Flow",
            version="1.0.0",
            tenant_id="tenant123",
            description="A test flow",
            tags=["test", "example"],
            created_at=created_at,
            updated_at=updated_at,
            metadata={"env": "test"}
        )
        
        assert metadata.flow_id == "test-flow-123"
        assert metadata.name == "Test Flow"
        assert metadata.version == "1.0.0"
        assert metadata.tenant_id == "tenant123"
        assert metadata.description == "A test flow"
        assert metadata.tags == ["test", "example"]
        assert metadata.created_at == created_at
        assert metadata.updated_at == updated_at
        assert metadata.metadata == {"env": "test"}
    
    def test_flow_metadata_to_dict(self):
        """Test flow metadata serialization to dictionary."""
        metadata = FlowMetadata(
            flow_id="test-flow-123",
            name="Test Flow",
            version="1.0.0",
            tenant_id="tenant123",
            description="A test flow",
            tags=["test", "example"],
            metadata={"env": "test"}
        )
        
        metadata_dict = metadata.to_dict()
        
        assert metadata_dict["flow_id"] == "test-flow-123"
        assert metadata_dict["name"] == "Test Flow"
        assert metadata_dict["version"] == "1.0.0"
        assert metadata_dict["tenant_id"] == "tenant123"
        assert metadata_dict["description"] == "A test flow"
        assert metadata_dict["tags"] == ["test", "example"]
        assert metadata_dict["metadata"] == {"env": "test"}
        assert "created_at" in metadata_dict
        assert "updated_at" in metadata_dict
    
    def test_flow_metadata_from_dict(self):
        """Test flow metadata creation from dictionary."""
        data = {
            "flow_id": "test-flow-123",
            "name": "Test Flow",
            "version": "1.0.0",
            "tenant_id": "tenant123",
            "description": "A test flow",
            "tags": ["test", "example"],
            "metadata": {"env": "test"},
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-02T12:00:00"
        }
        
        metadata = FlowMetadata.from_dict(data)
        
        assert metadata.flow_id == "test-flow-123"
        assert metadata.name == "Test Flow"
        assert metadata.version == "1.0.0"
        assert metadata.tenant_id == "tenant123"
        assert metadata.description == "A test flow"
        assert metadata.tags == ["test", "example"]
        assert metadata.metadata == {"env": "test"}
        assert isinstance(metadata.created_at, datetime)
        assert isinstance(metadata.updated_at, datetime)


class TestFlowRegistry:
    """Test cases for the FlowRegistry class."""
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_creation(self, mock_psycopg2):
        """Test flow registry creation."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        assert registry.schema == "public"
        assert registry._connection == mock_conn
        mock_psycopg2.connect.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_creation_with_connection_string(self, mock_psycopg2):
        """Test flow registry creation with connection string."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn
        
        connection_string = "postgresql://user:pass@localhost:5432/db"
        registry = FlowRegistry(connection_string=connection_string)
        
        assert registry.connection_string == connection_string
        mock_psycopg2.connect.assert_called_once_with(connection_string, cursor_factory=mock_psycopg2.extras.RealDictCursor)
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_creation_with_parameters(self, mock_psycopg2):
        """Test flow registry creation with individual parameters."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry(
            host="testhost",
            port=5433,
            database="testdb",
            username="testuser",
            password="testpass",
            schema="testschema"
        )
        
        assert registry.schema == "testschema"
        expected_connection_string = "postgresql://testuser:testpass@testhost:5433/testdb"
        assert registry.connection_string == expected_connection_string
    
    def test_flow_registry_psycopg2_not_installed(self):
        """Test flow registry when psycopg2 is not installed."""
        with patch('sdk.registry.psycopg2', side_effect=ImportError()):
            with pytest.raises(RegistryError, match="psycopg2 is required"):
                FlowRegistry()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_connection_error(self, mock_psycopg2):
        """Test flow registry connection error."""
        mock_psycopg2.connect.side_effect = Exception("Connection failed")
        
        with pytest.raises(RegistryError, match="Failed to connect to database"):
            FlowRegistry()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_register_flow_success(self, mock_psycopg2):
        """Test successful flow registration."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No existing flow
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Create test flow
        task = Task(handler="test_handler")
        flow = Flow(tasks=[task], version="1.0.0")
        
        # Register flow
        metadata = registry.register_flow(
            flow=flow,
            name="Test Flow",
            description="A test flow",
            tags=["test"],
            metadata={"env": "test"}
        )
        
        assert metadata.flow_id == flow.id
        assert metadata.name == "Test Flow"
        assert metadata.description == "A test flow"
        assert metadata.tags == ["test"]
        assert metadata.metadata == {"env": "test"}
        
        # Verify database calls
        assert mock_cursor.execute.call_count == 2  # Check existence + insert
        mock_conn.commit.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_register_flow_already_exists(self, mock_psycopg2):
        """Test flow registration when flow already exists."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {"flow_id": "existing-flow"}  # Flow exists
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Create test flow
        task = Task(handler="test_handler")
        flow = Flow(tasks=[task], version="1.0.0")
        
        # Try to register flow
        with pytest.raises(RegistryError, match="already exists"):
            registry.register_flow(flow=flow, name="Test Flow")
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_register_flow_database_error(self, mock_psycopg2):
        """Test flow registration with database error."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Create test flow
        task = Task(handler="test_handler")
        flow = Flow(tasks=[task], version="1.0.0")
        
        # Try to register flow
        with pytest.raises(RegistryError, match="Failed to register flow"):
            registry.register_flow(flow=flow, name="Test Flow")
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_get_flow_success(self, mock_psycopg2):
        """Test successful flow retrieval."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock flow data
        flow_data = {
            "id": "test-flow-123",
            "version": "1.0.0",
            "tasks": [{"id": "task-1", "handler": "test_handler", "inputs": {}, "retries": 3, "timeout": 300, "condition": None, "metadata": {}}],
            "type": "DAG",
            "tenant_id": None,
            "metadata": {}
        }
        mock_cursor.fetchone.return_value = {"flow_data": flow_data}
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Get flow
        flow = registry.get_flow("test-flow-123")
        
        assert flow is not None
        assert flow.id == "test-flow-123"
        assert flow.version == "1.0.0"
        assert len(flow.tasks) == 1
        assert flow.tasks[0].handler == "test_handler"
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_get_flow_not_found(self, mock_psycopg2):
        """Test flow retrieval when flow not found."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None  # No flow found
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Get flow
        flow = registry.get_flow("nonexistent-flow")
        
        assert flow is None
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_get_flow_metadata_success(self, mock_psycopg2):
        """Test successful flow metadata retrieval."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock metadata
        metadata_data = {
            "flow_id": "test-flow-123",
            "name": "Test Flow",
            "version": "1.0.0",
            "tenant_id": "tenant123",
            "description": "A test flow",
            "tags": ["test"],
            "metadata": {"env": "test"},
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-02T12:00:00"
        }
        mock_cursor.fetchone.return_value = metadata_data
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Get metadata
        metadata = registry.get_flow_metadata("test-flow-123")
        
        assert metadata is not None
        assert metadata.flow_id == "test-flow-123"
        assert metadata.name == "Test Flow"
        assert metadata.version == "1.0.0"
        assert metadata.tenant_id == "tenant123"
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_list_flows_success(self, mock_psycopg2):
        """Test successful flow listing."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock flow list
        flows_data = [
            {
                "flow_id": "flow-1",
                "name": "Flow 1",
                "version": "1.0.0",
                "tenant_id": "tenant1",
                "description": "First flow",
                "tags": ["test"],
                "metadata": {},
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-02T12:00:00"
            },
            {
                "flow_id": "flow-2",
                "name": "Flow 2",
                "version": "2.0.0",
                "tenant_id": "tenant2",
                "description": "Second flow",
                "tags": ["prod"],
                "metadata": {},
                "created_at": "2023-01-03T12:00:00",
                "updated_at": "2023-01-04T12:00:00"
            }
        ]
        mock_cursor.fetchall.return_value = flows_data
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # List flows
        flows = registry.list_flows(tenant_id="tenant1", limit=10)
        
        assert len(flows) == 2
        assert flows[0].flow_id == "flow-1"
        assert flows[0].name == "Flow 1"
        assert flows[1].flow_id == "flow-2"
        assert flows[1].name == "Flow 2"
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_list_flows_with_filters(self, mock_psycopg2):
        """Test flow listing with filters."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # List flows with filters
        flows = registry.list_flows(
            tenant_id="tenant1",
            name_filter="test",
            tag_filter=["test", "example"],
            limit=5,
            offset=10
        )
        
        # Verify the query was called with correct parameters
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "tenant_id = %s" in query
        assert "name ILIKE %s" in query
        assert "tags ?| %s" in query
        assert params[0] == "tenant1"  # tenant_id
        assert params[1] == "%test%"  # name_filter
        assert params[2] == ["test", "example"]  # tag_filter
        assert params[3] == 5  # limit
        assert params[4] == 10  # offset
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_update_flow_success(self, mock_psycopg2):
        """Test successful flow update."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock existing metadata
        existing_metadata = {
            "flow_id": "test-flow-123",
            "name": "Old Name",
            "version": "1.0.0",
            "tenant_id": "tenant123",
            "description": "Old description",
            "tags": ["old"],
            "metadata": {"old": "data"},
            "created_at": "2023-01-01T12:00:00",
            "updated_at": "2023-01-02T12:00:00"
        }
        
        # Mock get_flow_metadata to return existing metadata
        def mock_get_metadata(flow_id):
            return FlowMetadata.from_dict(existing_metadata)
        
        registry = FlowRegistry()
        registry.get_flow_metadata = mock_get_metadata
        
        # Create updated flow
        task = Task(handler="updated_handler")
        updated_flow = Flow(tasks=[task], version="2.0.0")
        
        # Update flow
        updated_metadata = registry.update_flow(
            flow=updated_flow,
            name="New Name",
            description="New description",
            tags=["new"],
            metadata={"new": "data"}
        )
        
        # Verify database calls
        assert mock_cursor.execute.call_count == 1
        mock_conn.commit.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_delete_flow_success(self, mock_psycopg2):
        """Test successful flow deletion."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1  # One row affected
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Delete flow
        deleted = registry.delete_flow("test-flow-123")
        
        assert deleted is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_delete_flow_not_found(self, mock_psycopg2):
        """Test flow deletion when flow not found."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0  # No rows affected
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Delete flow
        deleted = registry.delete_flow("nonexistent-flow")
        
        assert deleted is False
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_search_flows(self, mock_psycopg2):
        """Test flow search functionality."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock search results
        search_results = [
            {
                "flow_id": "flow-1",
                "name": "Test Flow",
                "version": "1.0.0",
                "tenant_id": "tenant1",
                "description": "A test flow",
                "tags": ["test"],
                "metadata": {},
                "created_at": "2023-01-01T12:00:00",
                "updated_at": "2023-01-02T12:00:00"
            }
        ]
        mock_cursor.fetchall.return_value = search_results
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Search flows
        results = registry.search_flows("test", tenant_id="tenant1", limit=10)
        
        assert len(results) == 1
        assert results[0].flow_id == "flow-1"
        assert results[0].name == "Test Flow"
        
        # Verify search query
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        
        assert "name ILIKE %s" in query
        assert "description ILIKE %s" in query
        assert "tags::text ILIKE %s" in query
        assert params[0] == "%test%"  # query
        assert params[1] == "%test%"  # query
        assert params[2] == "%test%"  # query
        assert params[3] == "tenant1"  # tenant_id
        assert params[4] == 10  # limit
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_get_statistics(self, mock_psycopg2):
        """Test flow statistics retrieval."""
        # Setup mocks
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Mock statistics
        stats_data = {
            "total_flows": 10,
            "unique_tenants": 3,
            "unique_names": 8,
            "avg_tags_per_flow": 2.5,
            "earliest_flow": datetime(2023, 1, 1),
            "latest_flow": datetime(2023, 12, 31)
        }
        mock_cursor.fetchone.return_value = stats_data
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        
        # Get statistics
        stats = registry.get_flow_statistics()
        
        assert stats["total_flows"] == 10
        assert stats["unique_tenants"] == 3
        assert stats["unique_names"] == 8
        assert stats["avg_tags_per_flow"] == 2.5
        assert isinstance(stats["earliest_flow"], datetime)
        assert isinstance(stats["latest_flow"], datetime)
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_context_manager(self, mock_psycopg2):
        """Test flow registry as context manager."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn
        
        with FlowRegistry() as registry:
            assert registry._connection == mock_conn
        
        # Connection should be closed when exiting context
        mock_conn.close.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_close(self, mock_psycopg2):
        """Test flow registry close method."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.closed = False
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        registry.close()
        
        mock_conn.close.assert_called_once()
    
    @patch('sdk.registry.psycopg2')
    def test_flow_registry_close_already_closed(self, mock_psycopg2):
        """Test flow registry close when already closed."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.closed = True
        mock_psycopg2.connect.return_value = mock_conn
        
        registry = FlowRegistry()
        registry.close()
        
        # Should not call close on already closed connection
        mock_conn.close.assert_not_called()


class TestRegistryError:
    """Test cases for the RegistryError exception."""
    
    def test_registry_error_creation(self):
        """Test RegistryError creation."""
        error = RegistryError("Test error message")
        
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)
    
    def test_registry_error_inheritance(self):
        """Test RegistryError inheritance."""
        error = RegistryError("Test error")
        
        assert isinstance(error, Exception)
        assert isinstance(error, RegistryError)
