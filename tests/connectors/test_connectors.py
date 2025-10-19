"""
Tests for Connector Framework.

This module contains comprehensive tests for the connector framework,
including base connector tests and individual connector tests.
"""

import pytest
import asyncio
import json
import uuid
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from connectors.base import (
    BaseConnector,
    AsyncConnector,
    CPUIntensiveConnector,
    ConnectorConfig,
    ConnectorAction,
    ConnectorResult,
    ConnectorStatus,
    ActionType,
    ExecutionMode
)
from connectors.registry import ConnectorRegistry
from connectors.gmail_connector import GmailConnector
from connectors.slack_connector import SlackConnector
from connectors.postgres_connector import PostgreSQLConnector
from connectors.s3_connector import S3Connector
from connectors.http_connector import HTTPConnector
from connectors.llm_stub import LLMStubConnector


class TestBaseConnector:
    """Test cases for BaseConnector class."""
    
    @pytest.fixture
    def connector_config(self):
        """Configuration for connector."""
        return ConnectorConfig(
            connector_id="test-connector",
            name="test_connector",
            version="1.0.0",
            config={"timeout": 30},
            credentials={"api_key": "test-key"}
        )
    
    @pytest.fixture
    def mock_connector(self, connector_config):
        """Create a mock connector."""
        class TestConnector(BaseConnector):
            def get_description(self):
                return "Test connector"
            
            def get_author(self):
                return "Test Author"
            
            def authenticate(self):
                return True
            
            def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
                return ConnectorResult(
                    success=True,
                    data={"result": "success"},
                    execution_time_ms=100
                )
            
            def list_actions(self) -> List[ConnectorAction]:
                return [
                    ConnectorAction(
                        name="test_action",
                        description="Test action",
                        action_type=ActionType.EXECUTE,
                        parameters={
                            "param1": {
                                "type": "string",
                                "description": "Test parameter"
                            }
                        },
                        required_parameters=["param1"]
                    )
                ]
        
        return TestConnector(connector_config)
    
    def test_connector_initialization(self, connector_config):
        """Test connector initialization."""
        connector = mock_connector(connector_config)
        
        assert connector.config == connector_config
        assert connector._authenticated == False
        assert connector._health_status == ConnectorStatus.INACTIVE
        assert connector._last_health_check is None
    
    def test_connector_metadata(self, mock_connector):
        """Test connector metadata."""
        metadata = mock_connector.metadata
        
        assert metadata.name == "test_connector"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test connector"
        assert metadata.author == "Test Author"
        assert metadata.license == "MIT"
    
    def test_connector_authentication(self, mock_connector):
        """Test connector authentication."""
        result = mock_connector.authenticate()
        
        assert result == True
        assert mock_connector._authenticated == True
    
    def test_connector_action_execution(self, mock_connector):
        """Test connector action execution."""
        result = mock_connector.execute_action("test_action", {"param1": "value1"})
        
        assert result.success == True
        assert result.data == {"result": "success"}
        assert result.execution_time_ms == 100
    
    def test_connector_health_check(self, mock_connector):
        """Test connector health check."""
        health_result = mock_connector.health_check()
        
        assert health_result["status"] == "healthy"
        assert "execution_time_ms" in health_result
        assert "timestamp" in health_result
        assert mock_connector._health_status == ConnectorStatus.ACTIVE
    
    def test_connector_parameter_validation(self, mock_connector):
        """Test connector parameter validation."""
        # Valid parameters
        assert mock_connector.validate_parameters("test_action", {"param1": "value1"}) == True
        
        # Missing required parameter
        assert mock_connector.validate_parameters("test_action", {}) == False
        
        # Invalid parameter type
        assert mock_connector.validate_parameters("test_action", {"param1": 123}) == False
    
    def test_connector_status(self, mock_connector):
        """Test connector status methods."""
        assert mock_connector.get_status() == ConnectorStatus.INACTIVE
        assert mock_connector.get_last_health_check() is None
        assert mock_connector.is_authenticated() == False
        
        # After authentication
        mock_connector.authenticate()
        assert mock_connector.is_authenticated() == True
    
    def test_connector_string_representation(self, mock_connector):
        """Test connector string representation."""
        str_repr = str(mock_connector)
        repr_repr = repr(mock_connector)
        
        assert "test_connector" in str_repr
        assert "1.0.0" in str_repr
        assert "TestConnector" in repr_repr


class TestAsyncConnector:
    """Test cases for AsyncConnector class."""
    
    @pytest.fixture
    def async_connector_config(self):
        """Configuration for async connector."""
        return ConnectorConfig(
            connector_id="async-test",
            name="async_test",
            version="1.0.0"
        )
    
    @pytest.fixture
    def mock_async_connector(self, async_connector_config):
        """Create a mock async connector."""
        class TestAsyncConnector(AsyncConnector):
            def get_description(self):
                return "Async test connector"
            
            def get_author(self):
                return "Test Author"
            
            def authenticate(self):
                return True
            
            async def authenticate_async(self):
                return True
            
            def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
                return ConnectorResult(success=True, data={"result": "sync"})
            
            async def execute_action_async(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
                return ConnectorResult(success=True, data={"result": "async"})
            
            def list_actions(self) -> List[ConnectorAction]:
                return [
                    ConnectorAction(
                        name="async_action",
                        description="Async action",
                        action_type=ActionType.EXECUTE,
                        parameters={},
                        required_parameters=[]
                    )
                ]
        
        return TestAsyncConnector(async_connector_config)
    
    @pytest.mark.asyncio
    async def test_async_authentication(self, mock_async_connector):
        """Test async authentication."""
        result = await mock_async_connector.authenticate_async()
        
        assert result == True
        assert mock_async_connector._authenticated == True
    
    @pytest.mark.asyncio
    async def test_async_action_execution(self, mock_async_connector):
        """Test async action execution."""
        result = await mock_async_connector.execute_action_async("async_action", {})
        
        assert result.success == True
        assert result.data == {"result": "async"}
    
    @pytest.mark.asyncio
    async def test_async_health_check(self, mock_async_connector):
        """Test async health check."""
        health_result = await mock_async_connector.health_check_async()
        
        assert health_result["status"] == "healthy"
        assert "execution_time_ms" in health_result


class TestCPUIntensiveConnector:
    """Test cases for CPUIntensiveConnector class."""
    
    @pytest.fixture
    def cpu_connector_config(self):
        """Configuration for CPU-intensive connector."""
        return ConnectorConfig(
            connector_id="cpu-test",
            name="cpu_test",
            version="1.0.0"
        )
    
    @pytest.fixture
    def mock_cpu_connector(self, cpu_connector_config):
        """Create a mock CPU-intensive connector."""
        class TestCPUConnector(CPUIntensiveConnector):
            def get_description(self):
                return "CPU-intensive test connector"
            
            def get_author(self):
                return "Test Author"
            
            def authenticate(self):
                return True
            
            def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
                return ConnectorResult(success=True, data={"result": "cpu_intensive"})
            
            def list_actions(self) -> List[ConnectorAction]:
                return [
                    ConnectorAction(
                        name="cpu_action",
                        description="CPU-intensive action",
                        action_type=ActionType.EXECUTE,
                        parameters={},
                        required_parameters=[]
                    )
                ]
        
        return TestCPUConnector(cpu_connector_config)
    
    def test_cpu_intensive_flag(self, mock_cpu_connector):
        """Test CPU-intensive flag."""
        assert mock_cpu_connector.is_cpu_intensive() == True
    
    def test_cpu_intensive_capabilities(self, mock_cpu_connector):
        """Test CPU-intensive capabilities."""
        capabilities = mock_cpu_connector.get_capabilities()
        
        assert "cpu_intensive" in capabilities


class TestConnectorRegistry:
    """Test cases for ConnectorRegistry class."""
    
    @pytest.fixture
    def registry_config(self):
        """Configuration for connector registry."""
        return {
            "connection_string": "postgresql://test:test@localhost:5432/test",
            "connectors_path": "connectors"
        }
    
    @pytest.fixture
    def mock_registry(self, registry_config):
        """Create a mock connector registry."""
        with patch('connectors.registry.psycopg2.connect'):
            registry = ConnectorRegistry(**registry_config)
            return registry
    
    def test_registry_initialization(self, registry_config):
        """Test registry initialization."""
        with patch('connectors.registry.psycopg2.connect'):
            registry = ConnectorRegistry(**registry_config)
            
            assert registry.connection_string == registry_config["connection_string"]
            assert registry.connectors_path == registry_config["connectors_path"]
            assert len(registry._connector_classes) == 0
            assert len(registry._connector_instances) == 0
    
    def test_registry_database_schema_initialization(self, mock_registry):
        """Test database schema initialization."""
        with patch('connectors.registry.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            mock_registry.initialize_database_schema()
            
            mock_connect.assert_called_once()
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
    
    def test_registry_connector_discovery(self, mock_registry):
        """Test connector discovery."""
        with patch('connectors.registry.Path') as mock_path:
            mock_connectors_dir = Mock()
            mock_connectors_dir.exists.return_value = True
            mock_connectors_dir.glob.return_value = []
            mock_path.return_value = mock_connectors_dir
            
            discovered = mock_registry.discover_connectors()
            
            assert isinstance(discovered, list)
    
    def test_registry_connector_registration(self, mock_registry):
        """Test connector registration."""
        connector_info = {
            "name": "test_connector",
            "version": "1.0.0",
            "description": "Test connector",
            "author": "Test Author",
            "license": "MIT",
            "homepage": None,
            "documentation": None,
            "tags": [],
            "capabilities": [],
            "authentication_methods": [],
            "rate_limits": {},
            "module_path": "connectors.test",
            "class_name": "TestConnector",
            "config_schema": {}
        }
        
        with patch('connectors.registry.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            result = mock_registry.register_connector(connector_info)
            
            assert result == True
            mock_cursor.execute.assert_called_once()
            mock_conn.commit.assert_called_once()
    
    def test_registry_connector_retrieval(self, mock_registry):
        """Test connector retrieval."""
        with patch('connectors.registry.psycopg2.connect') as mock_connect:
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_connect.return_value = mock_conn
            mock_conn.cursor.return_value = mock_cursor
            
            # Mock cursor result
            mock_row = Mock()
            mock_row.__iter__ = Mock(return_value=iter([
                "test_connector", "1.0.0", "Test connector", "Test Author",
                "MIT", None, None, "[]", "[]", "[]", "{}",
                "connectors.test", "TestConnector", "{}", True,
                datetime.now(), datetime.now()
            ]))
            mock_cursor.fetchone.return_value = mock_row
            
            connector = mock_registry.get_connector("test_connector")
            
            assert connector is not None
            assert connector["name"] == "test_connector"


class TestGmailConnector:
    """Test cases for GmailConnector class."""
    
    @pytest.fixture
    def gmail_config(self):
        """Configuration for Gmail connector."""
        return ConnectorConfig(
            connector_id="gmail-test",
            name="gmail",
            version="1.0.0",
            config={
                "user_email": "test@example.com",
                "credentials_file": "credentials.json",
                "token_file": "token.json"
            },
            credentials={"password": "test-password"}
        )
    
    @pytest.fixture
    def mock_gmail_connector(self, gmail_config):
        """Create a mock Gmail connector."""
        with patch('connectors.gmail_connector.build'), \
             patch('connectors.gmail_connector.Credentials'), \
             patch('connectors.gmail_connector.InstalledAppFlow'), \
             patch('connectors.gmail_connector.os.path.exists'):
            
            connector = GmailConnector(gmail_config)
            return connector
    
    def test_gmail_connector_initialization(self, mock_gmail_connector):
        """Test Gmail connector initialization."""
        assert mock_gmail_connector.user_email == "test@example.com"
        assert mock_gmail_connector.credentials_file == "credentials.json"
        assert mock_gmail_connector.token_file == "token.json"
    
    def test_gmail_connector_metadata(self, mock_gmail_connector):
        """Test Gmail connector metadata."""
        metadata = mock_gmail_connector.metadata
        
        assert "gmail" in metadata.tags
        assert "email" in metadata.capabilities
        assert "oauth2" in metadata.authentication_methods
    
    def test_gmail_connector_actions(self, mock_gmail_connector):
        """Test Gmail connector actions."""
        actions = mock_gmail_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "send_email" in action_names
        assert "delete_email" in action_names
        assert "list_emails" in action_names


class TestSlackConnector:
    """Test cases for SlackConnector class."""
    
    @pytest.fixture
    def slack_config(self):
        """Configuration for Slack connector."""
        return ConnectorConfig(
            connector_id="slack-test",
            name="slack",
            version="1.0.0",
            config={"timeout": 30},
            credentials={"bot_token": "xoxb-test-token"}
        )
    
    @pytest.fixture
    def mock_slack_connector(self, slack_config):
        """Create a mock Slack connector."""
        with patch('connectors.slack_connector.requests.Session'):
            connector = SlackConnector(slack_config)
            return connector
    
    def test_slack_connector_initialization(self, mock_slack_connector):
        """Test Slack connector initialization."""
        assert mock_slack_connector.bot_token == "xoxb-test-token"
        assert mock_slack_connector.timeout == 30
    
    def test_slack_connector_metadata(self, mock_slack_connector):
        """Test Slack connector metadata."""
        metadata = mock_slack_connector.metadata
        
        assert "slack" in metadata.tags
        assert "post_message" in metadata.capabilities
        assert "bot_token" in metadata.authentication_methods
    
    def test_slack_connector_actions(self, mock_slack_connector):
        """Test Slack connector actions."""
        actions = mock_slack_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "post_message" in action_names
        assert "create_channel" in action_names
        assert "upload_file" in action_names


class TestPostgreSQLConnector:
    """Test cases for PostgreSQLConnector class."""
    
    @pytest.fixture
    def postgres_config(self):
        """Configuration for PostgreSQL connector."""
        return ConnectorConfig(
            connector_id="postgres-test",
            name="postgres",
            version="1.0.0",
            config={
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "user": "test_user"
            },
            credentials={"password": "test-password"}
        )
    
    @pytest.fixture
    def mock_postgres_connector(self, postgres_config):
        """Create a mock PostgreSQL connector."""
        with patch('connectors.postgres_connector.psycopg2.connect'):
            connector = PostgreSQLConnector(postgres_config)
            return connector
    
    def test_postgres_connector_initialization(self, mock_postgres_connector):
        """Test PostgreSQL connector initialization."""
        assert mock_postgres_connector.host == "localhost"
        assert mock_postgres_connector.port == 5432
        assert mock_postgres_connector.database == "test_db"
        assert mock_postgres_connector.user == "test_user"
    
    def test_postgres_connector_metadata(self, mock_postgres_connector):
        """Test PostgreSQL connector metadata."""
        metadata = mock_postgres_connector.metadata
        
        assert "postgresql" in metadata.tags
        assert "insert" in metadata.capabilities
        assert "password" in metadata.authentication_methods
    
    def test_postgres_connector_actions(self, mock_postgres_connector):
        """Test PostgreSQL connector actions."""
        actions = mock_postgres_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "insert" in action_names
        assert "update" in action_names
        assert "delete" in action_names
        assert "select" in action_names


class TestS3Connector:
    """Test cases for S3Connector class."""
    
    @pytest.fixture
    def s3_config(self):
        """Configuration for S3 connector."""
        return ConnectorConfig(
            connector_id="s3-test",
            name="s3",
            version="1.0.0",
            config={
                "region_name": "us-east-1",
                "bucket_name": "test-bucket"
            },
            credentials={
                "aws_access_key_id": "test-key",
                "aws_secret_access_key": "test-secret"
            }
        )
    
    @pytest.fixture
    def mock_s3_connector(self, s3_config):
        """Create a mock S3 connector."""
        with patch('connectors.s3_connector.boto3.Session'), \
             patch('connectors.s3_connector.boto3.client'):
            connector = S3Connector(s3_config)
            return connector
    
    def test_s3_connector_initialization(self, mock_s3_connector):
        """Test S3 connector initialization."""
        assert mock_s3_connector.region_name == "us-east-1"
        assert mock_s3_connector.bucket_name == "test-bucket"
        assert mock_s3_connector.aws_access_key_id == "test-key"
    
    def test_s3_connector_metadata(self, mock_s3_connector):
        """Test S3 connector metadata."""
        metadata = mock_s3_connector.metadata
        
        assert "s3" in metadata.tags
        assert "upload_file" in metadata.capabilities
        assert "aws_credentials" in metadata.authentication_methods
    
    def test_s3_connector_actions(self, mock_s3_connector):
        """Test S3 connector actions."""
        actions = mock_s3_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "upload_file" in action_names
        assert "download_file" in action_names
        assert "delete_file" in action_names


class TestHTTPConnector:
    """Test cases for HTTPConnector class."""
    
    @pytest.fixture
    def http_config(self):
        """Configuration for HTTP connector."""
        return ConnectorConfig(
            connector_id="http-test",
            name="http",
            version="1.0.0",
            config={
                "base_url": "https://api.example.com",
                "timeout": 30
            },
            credentials={"api_key": "test-api-key"}
        )
    
    @pytest.fixture
    def mock_http_connector(self, http_config):
        """Create a mock HTTP connector."""
        with patch('connectors.http_connector.requests.Session'):
            connector = HTTPConnector(http_config)
            return connector
    
    def test_http_connector_initialization(self, mock_http_connector):
        """Test HTTP connector initialization."""
        assert mock_http_connector.base_url == "https://api.example.com"
        assert mock_http_connector.timeout == 30
        assert mock_http_connector.api_key == "test-api-key"
    
    def test_http_connector_metadata(self, mock_http_connector):
        """Test HTTP connector metadata."""
        metadata = mock_http_connector.metadata
        
        assert "http" in metadata.tags
        assert "get" in metadata.capabilities
        assert "api_key" in metadata.authentication_methods
    
    def test_http_connector_actions(self, mock_http_connector):
        """Test HTTP connector actions."""
        actions = mock_http_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "get" in action_names
        assert "post" in action_names
        assert "put" in action_names
        assert "delete" in action_names


class TestLLMStubConnector:
    """Test cases for LLMStubConnector class."""
    
    @pytest.fixture
    def llm_config(self):
        """Configuration for LLM stub connector."""
        return ConnectorConfig(
            connector_id="llm-test",
            name="llm_stub",
            version="1.0.0",
            config={
                "model_name": "gpt-3.5-turbo",
                "processing_delay": 1.0,
                "error_rate": 0.0
            }
        )
    
    @pytest.fixture
    def mock_llm_connector(self, llm_config):
        """Create a mock LLM stub connector."""
        connector = LLMStubConnector(llm_config)
        return connector
    
    def test_llm_connector_initialization(self, mock_llm_connector):
        """Test LLM stub connector initialization."""
        assert mock_llm_connector.model_name == "gpt-3.5-turbo"
        assert mock_llm_connector.processing_delay == 1.0
        assert mock_llm_connector.error_rate == 0.0
    
    def test_llm_connector_cpu_intensive(self, mock_llm_connector):
        """Test LLM stub connector CPU-intensive flag."""
        assert mock_llm_connector.is_cpu_intensive() == True
    
    def test_llm_connector_metadata(self, mock_llm_connector):
        """Test LLM stub connector metadata."""
        metadata = mock_llm_connector.metadata
        
        assert "llm" in metadata.tags
        assert "summarize" in metadata.capabilities
        assert "cpu_intensive" in metadata.capabilities
    
    def test_llm_connector_actions(self, mock_llm_connector):
        """Test LLM stub connector actions."""
        actions = mock_llm_connector.list_actions()
        
        action_names = [action.name for action in actions]
        assert "summarize" in action_names
        assert "analyze_sentiment" in action_names
        assert "extract_entities" in action_names
    
    def test_llm_connector_summarize(self, mock_llm_connector):
        """Test LLM stub connector summarize action."""
        result = mock_llm_connector.execute_action("summarize", {
            "text": "This is a test text for summarization."
        })
        
        assert result.success == True
        assert "summary" in result.data
        assert "original_length" in result.data
        assert "compression_ratio" in result.data


class TestConnectorIntegration:
    """Integration tests for connector framework."""
    
    @pytest.fixture
    def integration_config(self):
        """Configuration for integration tests."""
        return ConnectorConfig(
            connector_id="integration-test",
            name="integration_test",
            version="1.0.0",
            config={"timeout": 30},
            credentials={"api_key": "test-key"}
        )
    
    @pytest.mark.asyncio
    async def test_connector_lifecycle(self, integration_config):
        """Test complete connector lifecycle."""
        # Create connector
        connector = LLMStubConnector(integration_config)
        
        # Test initialization
        assert connector.get_status() == ConnectorStatus.INACTIVE
        
        # Test authentication
        auth_result = connector.authenticate()
        assert auth_result == True
        assert connector.is_authenticated() == True
        
        # Test health check
        health_result = connector.health_check()
        assert health_result["status"] == "healthy"
        
        # Test action execution
        result = connector.execute_action("summarize", {
            "text": "Test text for summarization."
        })
        assert result.success == True
        
        # Test status after execution
        assert connector.get_status() == ConnectorStatus.ACTIVE
    
    def test_connector_error_handling(self, integration_config):
        """Test connector error handling."""
        connector = LLMStubConnector(integration_config)
        
        # Test invalid action
        result = connector.execute_action("invalid_action", {})
        assert result.success == False
        assert "Unknown action" in result.error
        
        # Test invalid parameters
        result = connector.execute_action("summarize", {})
        assert result.success == False
        assert "Invalid parameters" in result.error
    
    def test_connector_parameter_validation(self, integration_config):
        """Test connector parameter validation."""
        connector = LLMStubConnector(integration_config)
        
        # Test valid parameters
        assert connector.validate_parameters("summarize", {
            "text": "Test text",
            "max_length": 100
        }) == True
        
        # Test missing required parameter
        assert connector.validate_parameters("summarize", {
            "max_length": 100
        }) == False
        
        # Test invalid parameter type
        assert connector.validate_parameters("summarize", {
            "text": "Test text",
            "max_length": "invalid"
        }) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
