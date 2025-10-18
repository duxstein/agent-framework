"""
Example usage of the Enterprise AI Agent Framework Connectors.

This file demonstrates how to use the connector interface,
registry, and reference connectors.
"""

from connectors import (
    BaseConnector, ConnectorRegistry, get_global_registry,
    GmailConnector, SlackConnector, PostgresConnector, 
    LLMConnector, OCRConnector
)


def example_connector_registry():
    """Example of using the connector registry."""
    print("=== Connector Registry Examples ===")
    
    # Get the global registry
    registry = get_global_registry()
    
    # Register connector classes
    registry.register_connector_class(GmailConnector)
    registry.register_connector_class(SlackConnector)
    registry.register_connector_class(PostgresConnector)
    registry.register_connector_class(LLMConnector)
    registry.register_connector_class(OCRConnector)
    
    # List available connectors
    available = registry.list_available_connectors()
    print(f"Available connectors: {[c['name'] for c in available]}")
    
    # Create connector instances
    gmail_instance = registry.create_connector(
        "gmail",
        tenant_id="tenant_123",
        instance_id="gmail_instance_1"
    )
    
    slack_instance = registry.create_connector(
        "slack", 
        tenant_id="tenant_123",
        instance_id="slack_instance_1"
    )
    
    print(f"Created instances: {[gmail_instance, slack_instance]}")
    
    # Get registry statistics
    stats = registry.get_registry_statistics()
    print(f"Registry statistics: {stats}")


def example_gmail_connector():
    """Example of using the Gmail connector."""
    print("\n=== Gmail Connector Example ===")
    
    # Create Gmail connector
    gmail = GmailConnector(tenant_id="tenant_123")
    
    # Authenticate
    credentials = {
        'client_id': 'your_client_id',
        'client_secret': 'your_client_secret',
        'refresh_token': 'your_refresh_token'
    }
    
    try:
        gmail.authenticate(credentials)
        print(f"Gmail authentication: {gmail.is_connected()}")
        
        # List available actions
        actions = gmail.list_actions()
        print(f"Available actions: {[a['name'] for a in actions]}")
        
        # Send email
        send_result = gmail.execute_action("send_email", {
            'to': 'recipient@example.com',
            'subject': 'Test Email from AI Agent',
            'body': 'This is a test email sent by the AI Agent Framework.',
            'cc': 'cc@example.com'
        })
        print(f"Send email result: {send_result}")
        
        # Delete email
        delete_result = gmail.execute_action("delete_email", {
            'message_id': '1234567890abcdef'
        })
        print(f"Delete email result: {delete_result}")
        
    except Exception as e:
        print(f"Gmail error: {e}")


def example_slack_connector():
    """Example of using the Slack connector."""
    print("\n=== Slack Connector Example ===")
    
    # Create Slack connector
    slack = SlackConnector(tenant_id="tenant_123")
    
    # Authenticate
    credentials = {
        'bot_token': 'xoxb-your-bot-token-here'
    }
    
    try:
        slack.authenticate(credentials)
        print(f"Slack authentication: {slack.is_connected()}")
        
        # List available actions
        actions = slack.list_actions()
        print(f"Available actions: {[a['name'] for a in actions]}")
        
        # Post message
        post_result = slack.execute_action("post_message", {
            'channel': '#general',
            'text': 'Hello from the AI Agent!',
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': '*AI Agent Notification*\nThis is a test message from the Enterprise AI Agent Framework.'
                    }
                }
            ]
        })
        print(f"Post message result: {post_result}")
        
        # List channels
        channels_result = slack.execute_action("list_channels", {
            'types': 'public_channel,private_channel',
            'exclude_archived': True
        })
        print(f"List channels result: {channels_result}")
        
    except Exception as e:
        print(f"Slack error: {e}")


def example_postgres_connector():
    """Example of using the Postgres connector."""
    print("\n=== Postgres Connector Example ===")
    
    # Create Postgres connector
    postgres = PostgresConnector(tenant_id="tenant_123")
    
    # Authenticate
    credentials = {
        'host': 'localhost',
        'port': 5432,
        'database': 'testdb',
        'username': 'testuser',
        'password': 'testpass'
    }
    
    try:
        postgres.authenticate(credentials)
        print(f"Postgres authentication: {postgres.is_connected()}")
        
        # List available actions
        actions = postgres.list_actions()
        print(f"Available actions: {[a['name'] for a in actions]}")
        
        # Insert data
        insert_result = postgres.execute_action("insert", {
            'table': 'users',
            'data': {
                'name': 'John Doe',
                'email': 'john@example.com',
                'age': 30
            },
            'returning': 'id'
        })
        print(f"Insert result: {insert_result}")
        
        # Update data
        update_result = postgres.execute_action("update", {
            'table': 'users',
            'data': {'age': 31},
            'where': {'email': 'john@example.com'},
            'returning': 'id'
        })
        print(f"Update result: {update_result}")
        
        # Select data
        select_result = postgres.execute_action("select", {
            'table': 'users',
            'columns': ['id', 'name', 'email', 'age'],
            'where': {'age': 31},
            'limit': 10
        })
        print(f"Select result: {select_result}")
        
    except Exception as e:
        print(f"Postgres error: {e}")


def example_llm_connector():
    """Example of using the LLM connector."""
    print("\n=== LLM Connector Example ===")
    
    # Create LLM connector
    llm = LLMConnector(tenant_id="tenant_123")
    
    # Authenticate
    credentials = {
        'api_key': 'your-api-key',
        'provider': 'openai',
        'model': 'gpt-3.5-turbo'
    }
    
    try:
        llm.authenticate(credentials)
        print(f"LLM authentication: {llm.is_connected()}")
        
        # List available actions
        actions = llm.list_actions()
        print(f"Available actions: {[a['name'] for a in actions]}")
        
        # Summarize text
        summarize_result = llm.execute_action("summarize", {
            'text': 'This is a long article about artificial intelligence and machine learning. It covers various topics including neural networks, deep learning, natural language processing, and computer vision. The article discusses the history of AI, current applications, and future prospects.',
            'max_length': 100,
            'style': 'bullet_points',
            'focus': 'main_points'
        })
        print(f"Summarize result: {summarize_result}")
        
        # Analyze text
        analyze_result = llm.execute_action("analyze", {
            'text': 'I love this product! It works perfectly and exceeded my expectations.',
            'analysis_type': 'sentiment',
            'detailed': True
        })
        print(f"Analyze result: {analyze_result}")
        
        # Generate text
        generate_result = llm.execute_action("generate", {
            'prompt': 'Write a professional email to a client about project updates',
            'max_tokens': 200,
            'temperature': 0.7,
            'style': 'professional'
        })
        print(f"Generate result: {generate_result}")
        
    except Exception as e:
        print(f"LLM error: {e}")


def example_ocr_connector():
    """Example of using the OCR connector."""
    print("\n=== OCR Connector Example ===")
    
    # Create OCR connector
    ocr = OCRConnector(tenant_id="tenant_123")
    
    # Authenticate
    credentials = {
        'api_key': 'your-api-key',
        'engine': 'google_vision',
        'language': 'en'
    }
    
    try:
        ocr.authenticate(credentials)
        print(f"OCR authentication: {ocr.is_connected()}")
        
        # List available actions
        actions = ocr.list_actions()
        print(f"Available actions: {[a['name'] for a in actions]}")
        
        # Extract text (simulated base64 image)
        extract_result = ocr.execute_action("extract_text", {
            'image': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',  # 1x1 pixel PNG
            'confidence_threshold': 0.8,
            'preprocessing': 'enhance_contrast'
        })
        print(f"Extract text result: {extract_result}")
        
        # Extract text with layout
        layout_result = ocr.execute_action("extract_text_with_layout", {
            'image': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
            'include_coordinates': True,
            'group_by_blocks': True
        })
        print(f"Layout result: {layout_result}")
        
        # Detect document structure
        structure_result = ocr.execute_action("detect_document_structure", {
            'image': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
            'structure_types': ['header', 'paragraph', 'list'],
            'confidence_threshold': 0.7
        })
        print(f"Structure result: {structure_result}")
        
    except Exception as e:
        print(f"OCR error: {e}")


def example_custom_connector():
    """Example of creating a custom connector."""
    print("\n=== Custom Connector Example ===")
    
    class CustomConnector(BaseConnector):
        """Custom connector example."""
        
        CONNECTOR_NAME = "custom"
        VERSION = "1.0.0"
        DESCRIPTION = "Custom connector example"
        
        def authenticate(self, credentials):
            """Authenticate with custom service."""
            if 'api_key' not in credentials:
                raise AuthenticationError("Missing api_key")
            
            self._api_key = credentials['api_key']
            self.status = self.status.CONNECTED
            self.update_activity()
            return True
        
        def execute_action(self, action_name, params):
            """Execute custom action."""
            if not self.is_connected():
                raise AuthenticationError("Not authenticated")
            
            if action_name == "custom_action":
                return {
                    'success': True,
                    'result': f"Custom action executed with params: {params}",
                    'timestamp': self.last_activity.isoformat() if self.last_activity else None
                }
            else:
                raise ActionError(f"Unknown action: {action_name}")
        
        def list_actions(self):
            """List custom actions."""
            return [
                {
                    'name': 'custom_action',
                    'description': 'Execute a custom action',
                    'required_params': ['param1'],
                    'optional_params': ['param2'],
                    'example': {'param1': 'value1', 'param2': 'value2'}
                }
            ]
    
    # Use the custom connector
    custom = CustomConnector(tenant_id="tenant_123")
    
    try:
        custom.authenticate({'api_key': 'test-key'})
        print(f"Custom connector authentication: {custom.is_connected()}")
        
        result = custom.execute_action("custom_action", {
            'param1': 'test_value',
            'param2': 'optional_value'
        })
        print(f"Custom action result: {result}")
        
    except Exception as e:
        print(f"Custom connector error: {e}")


if __name__ == "__main__":
    """Run all connector examples."""
    try:
        example_connector_registry()
        example_gmail_connector()
        example_slack_connector()
        example_postgres_connector()
        example_llm_connector()
        example_ocr_connector()
        example_custom_connector()
        print("\n=== All connector examples completed successfully! ===")
    except Exception as e:
        print(f"Error running examples: {e}")
        import traceback
        traceback.print_exc()
