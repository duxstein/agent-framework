"""
Slack connector for Enterprise AI Agent Framework.

Provides Slack integration with post message actions.
Supports bot token authentication and basic error handling.
"""

import json
from typing import Dict, Any, List, Optional
from .base import BaseConnector, AuthenticationError, ActionError


class SlackConnector(BaseConnector):
    """
    Slack connector for posting messages to channels.
    
    Supports bot token authentication and provides actions for
    posting messages to Slack channels.
    """
    
    CONNECTOR_NAME = "slack"
    VERSION = "1.0.0"
    DESCRIPTION = "Slack connector for posting messages to channels"
    
    def __init__(self, tenant_id: Optional[str] = None, **kwargs):
        """
        Initialize the Slack connector.
        
        Args:
            tenant_id (Optional[str]): Tenant identifier
            **kwargs: Additional configuration
        """
        super().__init__(
            name=self.CONNECTOR_NAME,
            version=self.VERSION,
            tenant_id=tenant_id,
            metadata={
                'service': 'slack',
                'api_version': 'v1',
                'endpoints': ['chat.postMessage', 'conversations.list']
            }
        )
        self._client = None
        self._bot_token = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Slack API using bot token.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
                Expected keys: 'bot_token'
        
        Returns:
            bool: True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Validate required credentials
            if 'bot_token' not in credentials:
                raise AuthenticationError("Missing required credential: bot_token")
            
            bot_token = credentials['bot_token']
            if not isinstance(bot_token, str) or not bot_token.strip():
                raise AuthenticationError("Invalid bot_token")
            
            # Validate token format (Slack bot tokens start with 'xoxb-')
            if not bot_token.startswith('xoxb-'):
                raise AuthenticationError("Invalid bot token format. Bot tokens should start with 'xoxb-'")
            
            # Store credentials
            self._bot_token = bot_token
            
            # In a real implementation, you would use the Slack SDK
            # For this example, we'll simulate the authentication process
            
            # Simulate API client initialization
            self._client = "slack_client_instance"  # In real implementation: WebClient(token=bot_token)
            
            # Test authentication by making a simple API call
            # In real implementation: client.auth_test()
            auth_test_result = {
                'ok': True,
                'url': 'https://example.slack.com/',
                'team': 'Example Team',
                'user': 'bot_user',
                'team_id': 'T1234567890',
                'user_id': 'U1234567890',
                'bot_id': 'B1234567890'
            }
            
            if not auth_test_result.get('ok', False):
                raise AuthenticationError("Slack authentication test failed")
            
            self.status = self.status.CONNECTED
            self.update_activity()
            
            return True
            
        except Exception as e:
            self.status = self.status.ERROR
            raise AuthenticationError(f"Slack authentication failed: {str(e)}")
    
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Slack action.
        
        Args:
            action_name (str): Name of the action to execute
            params (Dict[str, Any]): Parameters for the action
        
        Returns:
            Dict[str, Any]: Result of the action execution
            
        Raises:
            ActionError: If action execution fails
            AuthenticationError: If not authenticated
        """
        if not self.is_connected():
            raise AuthenticationError("Not authenticated with Slack")
        
        if not self.validate_params(action_name, params):
            raise ActionError(f"Invalid parameters for action '{action_name}'")
        
        try:
            self.update_activity()
            
            if action_name == "post_message":
                return self._post_message(params)
            elif action_name == "list_channels":
                return self._list_channels(params)
            else:
                raise ActionError(f"Unknown action: {action_name}")
                
        except Exception as e:
            raise ActionError(f"Failed to execute action '{action_name}': {str(e)}")
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available Slack actions.
        
        Returns:
            List[Dict[str, Any]]: List of available actions
        """
        return [
            {
                'name': 'post_message',
                'description': 'Post a message to a Slack channel',
                'required_params': ['channel', 'text'],
                'optional_params': ['blocks', 'attachments', 'thread_ts', 'reply_broadcast'],
                'example': {
                    'channel': '#general',
                    'text': 'Hello from the AI Agent!',
                    'blocks': [
                        {
                            'type': 'section',
                            'text': {
                                'type': 'mrkdwn',
                                'text': '*Hello from the AI Agent!*'
                            }
                        }
                    ]
                }
            },
            {
                'name': 'list_channels',
                'description': 'List available channels',
                'required_params': [],
                'optional_params': ['types', 'exclude_archived'],
                'example': {
                    'types': 'public_channel,private_channel',
                    'exclude_archived': True
                }
            }
        ]
    
    def _post_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post a message to a Slack channel.
        
        Args:
            params (Dict[str, Any]): Message parameters
            
        Returns:
            Dict[str, Any]: Post result
        """
        # Extract parameters
        channel = params['channel']
        text = params['text']
        blocks = params.get('blocks')
        attachments = params.get('attachments')
        thread_ts = params.get('thread_ts')
        reply_broadcast = params.get('reply_broadcast', False)
        
        # Validate channel format
        if not self._is_valid_channel(channel):
            raise ActionError(f"Invalid channel format: {channel}")
        
        # Validate message content
        if not text and not blocks and not attachments:
            raise ActionError("Message must have text, blocks, or attachments")
        
        # Validate blocks format if provided
        if blocks and not isinstance(blocks, list):
            raise ActionError("Blocks must be a list")
        
        # Validate attachments format if provided
        if attachments and not isinstance(attachments, list):
            raise ActionError("Attachments must be a list")
        
        # Prepare message payload
        message_payload = {
            'channel': channel,
            'text': text,
            'reply_broadcast': reply_broadcast
        }
        
        if blocks:
            message_payload['blocks'] = blocks
        
        if attachments:
            message_payload['attachments'] = attachments
        
        if thread_ts:
            message_payload['thread_ts'] = thread_ts
        
        # In a real implementation, you would post the message using the Slack API
        # For this example, we'll simulate the post operation
        
        # Simulate API call
        # In real implementation: client.chat_postMessage(**message_payload)
        message_result = {
            'ok': True,
            'channel': channel,
            'ts': f"{int(self.last_activity.timestamp() * 1000)}.{hash(str(message_payload)) % 1000000}",
            'message': {
                'text': text,
                'user': 'U1234567890',  # Bot user ID
                'type': 'message',
                'subtype': None,
                'ts': f"{int(self.last_activity.timestamp() * 1000)}.{hash(str(message_payload)) % 1000000}"
            }
        }
        
        if not message_result.get('ok', False):
            raise ActionError("Failed to post message to Slack")
        
        return {
            'success': True,
            'message_ts': message_result['ts'],
            'channel': channel,
            'text': text,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _list_channels(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        List available Slack channels.
        
        Args:
            params (Dict[str, Any]): List parameters
            
        Returns:
            Dict[str, Any]: List result
        """
        # Extract parameters
        types = params.get('types', 'public_channel,private_channel')
        exclude_archived = params.get('exclude_archived', True)
        
        # In a real implementation, you would list channels using the Slack API
        # For this example, we'll simulate the list operation
        
        # Simulate API call
        # In real implementation: client.conversations_list(types=types, exclude_archived=exclude_archived)
        channels_result = {
            'ok': True,
            'channels': [
                {
                    'id': 'C1234567890',
                    'name': 'general',
                    'is_channel': True,
                    'is_group': False,
                    'is_im': False,
                    'is_private': False,
                    'is_archived': False,
                    'is_member': True,
                    'num_members': 25
                },
                {
                    'id': 'C0987654321',
                    'name': 'random',
                    'is_channel': True,
                    'is_group': False,
                    'is_im': False,
                    'is_private': False,
                    'is_archived': False,
                    'is_member': True,
                    'num_members': 15
                }
            ]
        }
        
        if not channels_result.get('ok', False):
            raise ActionError("Failed to list Slack channels")
        
        return {
            'success': True,
            'channels': channels_result['channels'],
            'count': len(channels_result['channels']),
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _is_valid_channel(self, channel: str) -> bool:
        """
        Validate Slack channel format.
        
        Args:
            channel (str): Channel identifier to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(channel, str) or not channel.strip():
            return False
        
        # Channel can be:
        # - Channel name: #general
        # - Channel ID: C1234567890
        # - User ID: U1234567890
        # - User name: @username
        
        if channel.startswith('#'):
            # Channel name
            return len(channel) > 1 and channel[1:].replace('-', '').replace('_', '').isalnum()
        elif channel.startswith('@'):
            # User name
            return len(channel) > 1 and channel[1:].replace('-', '').replace('_', '').isalnum()
        elif channel.startswith(('C', 'U', 'G')):
            # Channel/User/Group ID
            return len(channel) == 11 and channel[1:].isdigit()
        else:
            return False
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for Slack actions.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not super().validate_params(action_name, params):
            return False
        
        if action_name == "post_message":
            # Additional validation for post_message
            if 'channel' not in params or not self._is_valid_channel(params['channel']):
                return False
            
            if 'text' not in params and 'blocks' not in params and 'attachments' not in params:
                return False
            
            # Validate text if provided
            if 'text' in params and not isinstance(params['text'], str):
                return False
            
            # Validate blocks if provided
            if 'blocks' in params and not isinstance(params['blocks'], list):
                return False
            
            # Validate attachments if provided
            if 'attachments' in params and not isinstance(params['attachments'], list):
                return False
        
        elif action_name == "list_channels":
            # Additional validation for list_channels
            if 'types' in params and not isinstance(params['types'], str):
                return False
            
            if 'exclude_archived' in params and not isinstance(params['exclude_archived'], bool):
                return False
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from Slack API."""
        super().disconnect()
        self._client = None
        self._bot_token = None
