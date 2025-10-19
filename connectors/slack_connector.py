"""
Slack Connector for Enterprise AI Agent Framework.

This connector provides Slack integration capabilities including posting messages,
managing channels, and interacting with Slack APIs.
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import structlog
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType

logger = structlog.get_logger()


class SlackConnector(BaseConnector):
    """Slack connector for messaging and channel operations."""
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "bot_token": {
                "type": "string",
                "description": "Slack bot token"
            },
            "user_token": {
                "type": "string",
                "description": "Slack user token (optional)"
            },
            "webhook_url": {
                "type": "string",
                "description": "Slack webhook URL (optional)"
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "Request timeout in seconds"
            },
            "retry_count": {
                "type": "integer",
                "default": 3,
                "description": "Number of retries for failed requests"
            }
        },
        "required": ["bot_token"]
    }
    
    def __init__(self, config: ConnectorConfig):
        """Initialize Slack connector."""
        super().__init__(config)
        self.bot_token = self.config.credentials.get("bot_token")
        self.user_token = self.config.credentials.get("user_token")
        self.webhook_url = self.config.credentials.get("webhook_url")
        self.timeout = self.config.config.get("timeout", 30)
        self.retry_count = self.config.config.get("retry_count", 3)
        
        # Setup requests session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.retry_count,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def get_description(self) -> str:
        """Get connector description."""
        return "Slack connector for messaging, channel management, and team collaboration"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return ["slack", "messaging", "collaboration", "team", "chat"]
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return ["post_message", "create_channel", "invite_users", "file_upload", "user_management"]
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["bot_token", "user_token", "webhook"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {
            "requests_per_minute": 50,
            "messages_per_minute": 20,
            "api_calls_per_minute": 100
        }
    
    def authenticate(self) -> bool:
        """Authenticate with Slack API."""
        try:
            if not self.bot_token:
                self.logger.error("Bot token not provided")
                return False
            
            # Test authentication by getting bot info
            response = self.session.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    self.logger.info("Slack authentication successful", bot_id=data.get("bot_id"))
                    self._authenticated = True
                    return True
                else:
                    self.logger.error("Slack authentication failed", error=data.get("error"))
                    return False
            else:
                self.logger.error("Slack authentication failed", status_code=response.status_code)
                return False
                
        except Exception as e:
            self.logger.error("Slack authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return [
            ConnectorAction(
                name="post_message",
                description="Post a message to a Slack channel",
                action_type=ActionType.WRITE,
                parameters={
                    "channel": {
                        "type": "string",
                        "description": "Channel name or ID (e.g., #general or C1234567890)"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message text"
                    },
                    "blocks": {
                        "type": "array",
                        "description": "Slack blocks for rich formatting"
                    },
                    "attachments": {
                        "type": "array",
                        "description": "Message attachments"
                    },
                    "thread_ts": {
                        "type": "string",
                        "description": "Timestamp of parent message for threading"
                    },
                    "reply_broadcast": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether to broadcast reply to channel"
                    }
                },
                required_parameters=["channel", "text"],
                optional_parameters=["blocks", "attachments", "thread_ts", "reply_broadcast"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string"},
                        "channel": {"type": "string"},
                        "timestamp": {"type": "string"},
                        "text": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="create_channel",
                description="Create a new Slack channel",
                action_type=ActionType.WRITE,
                parameters={
                    "name": {
                        "type": "string",
                        "description": "Channel name (without #)"
                    },
                    "is_private": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether channel is private"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Channel topic"
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Channel purpose"
                    }
                },
                required_parameters=["name"],
                optional_parameters=["is_private", "topic", "purpose"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "channel_id": {"type": "string"},
                        "channel_name": {"type": "string"},
                        "is_private": {"type": "boolean"},
                        "created": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="invite_users",
                description="Invite users to a channel",
                action_type=ActionType.WRITE,
                parameters={
                    "channel": {
                        "type": "string",
                        "description": "Channel name or ID"
                    },
                    "users": {
                        "type": "array",
                        "description": "List of user IDs or emails to invite"
                    }
                },
                required_parameters=["channel", "users"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "invited_users": {"type": "array"},
                        "failed_invites": {"type": "array"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="upload_file",
                description="Upload a file to Slack",
                action_type=ActionType.WRITE,
                parameters={
                    "file_path": {
                        "type": "string",
                        "description": "Path to file to upload"
                    },
                    "channels": {
                        "type": "string",
                        "description": "Comma-separated list of channels to share file with"
                    },
                    "title": {
                        "type": "string",
                        "description": "File title"
                    },
                    "initial_comment": {
                        "type": "string",
                        "description": "Initial comment for the file"
                    }
                },
                required_parameters=["file_path"],
                optional_parameters=["channels", "title", "initial_comment"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "file_id": {"type": "string"},
                        "file_name": {"type": "string"},
                        "file_size": {"type": "integer"},
                        "channels": {"type": "array"}
                    }
                },
                timeout=self.timeout * 2,  # Longer timeout for file uploads
                is_async=True
            ),
            ConnectorAction(
                name="list_channels",
                description="List Slack channels",
                action_type=ActionType.READ,
                parameters={
                    "exclude_archived": {
                        "type": "boolean",
                        "default": True,
                        "description": "Exclude archived channels"
                    },
                    "types": {
                        "type": "string",
                        "default": "public_channel,private_channel",
                        "description": "Channel types to include"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 100,
                        "description": "Maximum number of channels to return"
                    }
                },
                optional_parameters=["exclude_archived", "types", "limit"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "channels": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "is_private": {"type": "boolean"},
                                    "is_archived": {"type": "boolean"},
                                    "topic": {"type": "string"},
                                    "purpose": {"type": "string"},
                                    "num_members": {"type": "integer"}
                                }
                            }
                        },
                        "total_count": {"type": "integer"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            )
        ]
    
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """Execute a Slack action."""
        start_time = datetime.now()
        
        try:
            if not self._authenticated:
                if not self.authenticate():
                    return ConnectorResult(
                        success=False,
                        error="Authentication failed",
                        execution_time_ms=0
                    )
            
            # Validate parameters
            if not self.validate_parameters(action_name, parameters):
                return ConnectorResult(
                    success=False,
                    error="Invalid parameters",
                    execution_time_ms=0
                )
            
            # Execute action
            if action_name == "post_message":
                result = self._post_message(parameters)
            elif action_name == "create_channel":
                result = self._create_channel(parameters)
            elif action_name == "invite_users":
                result = self._invite_users(parameters)
            elif action_name == "upload_file":
                result = self._upload_file(parameters)
            elif action_name == "list_channels":
                result = self._list_channels(parameters)
            else:
                return ConnectorResult(
                    success=False,
                    error=f"Unknown action: {action_name}",
                    execution_time_ms=0
                )
            
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            
            return ConnectorResult(
                success=True,
                data=result,
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("Slack action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
    
    def _post_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Post a message to Slack."""
        try:
            channel = parameters["channel"]
            text = parameters["text"]
            blocks = parameters.get("blocks")
            attachments = parameters.get("attachments")
            thread_ts = parameters.get("thread_ts")
            reply_broadcast = parameters.get("reply_broadcast", False)
            
            # Prepare message data
            message_data = {
                "channel": channel,
                "text": text
            }
            
            if blocks:
                message_data["blocks"] = json.dumps(blocks)
            
            if attachments:
                message_data["attachments"] = json.dumps(attachments)
            
            if thread_ts:
                message_data["thread_ts"] = thread_ts
                if reply_broadcast:
                    message_data["reply_broadcast"] = True
            
            # Send message
            response = self.session.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                data=message_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return {
                        "message_id": data["ts"],
                        "channel": data["channel"],
                        "timestamp": data["ts"],
                        "text": data["message"]["text"]
                    }
                else:
                    raise Exception(f"Slack API error: {data.get('error')}")
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Failed to post message: {str(e)}")
    
    def _create_channel(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Slack channel."""
        try:
            name = parameters["name"]
            is_private = parameters.get("is_private", False)
            topic = parameters.get("topic", "")
            purpose = parameters.get("purpose", "")
            
            # Prepare channel data
            channel_data = {
                "name": name,
                "is_private": is_private
            }
            
            if topic:
                channel_data["topic"] = topic
            
            if purpose:
                channel_data["purpose"] = purpose
            
            # Create channel
            response = self.session.post(
                "https://slack.com/api/conversations.create",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                data=channel_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channel = data["channel"]
                    return {
                        "channel_id": channel["id"],
                        "channel_name": channel["name"],
                        "is_private": channel["is_private"],
                        "created": datetime.now(timezone.utc).isoformat()
                    }
                else:
                    raise Exception(f"Slack API error: {data.get('error')}")
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Failed to create channel: {str(e)}")
    
    def _invite_users(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Invite users to a channel."""
        try:
            channel = parameters["channel"]
            users = parameters["users"]
            
            invited_users = []
            failed_invites = []
            
            for user in users:
                try:
                    response = self.session.post(
                        "https://slack.com/api/conversations.invite",
                        headers={"Authorization": f"Bearer {self.bot_token}"},
                        data={"channel": channel, "users": user},
                        timeout=self.timeout
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("ok"):
                            invited_users.append(user)
                        else:
                            failed_invites.append({"user": user, "error": data.get("error")})
                    else:
                        failed_invites.append({"user": user, "error": f"HTTP {response.status_code}"})
                        
                except Exception as e:
                    failed_invites.append({"user": user, "error": str(e)})
            
            return {
                "channel": channel,
                "invited_users": invited_users,
                "failed_invites": failed_invites
            }
            
        except Exception as e:
            raise Exception(f"Failed to invite users: {str(e)}")
    
    def _upload_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to Slack."""
        try:
            import os
            
            file_path = parameters["file_path"]
            channels = parameters.get("channels", "")
            title = parameters.get("title", "")
            initial_comment = parameters.get("initial_comment", "")
            
            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")
            
            # Prepare file data
            files = {"file": open(file_path, "rb")}
            data = {}
            
            if channels:
                data["channels"] = channels
            
            if title:
                data["title"] = title
            
            if initial_comment:
                data["initial_comment"] = initial_comment
            
            # Upload file
            response = self.session.post(
                "https://slack.com/api/files.upload",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                files=files,
                data=data,
                timeout=self.timeout * 2
            )
            
            files["file"].close()
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    file_info = data["file"]
                    return {
                        "file_id": file_info["id"],
                        "file_name": file_info["name"],
                        "file_size": file_info["size"],
                        "channels": file_info.get("channels", [])
                    }
                else:
                    raise Exception(f"Slack API error: {data.get('error')}")
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Failed to upload file: {str(e)}")
    
    def _list_channels(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """List Slack channels."""
        try:
            exclude_archived = parameters.get("exclude_archived", True)
            types = parameters.get("types", "public_channel,private_channel")
            limit = parameters.get("limit", 100)
            
            # Prepare request data
            request_data = {
                "exclude_archived": exclude_archived,
                "types": types,
                "limit": limit
            }
            
            # Get channels
            response = self.session.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                params=request_data,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    channels = []
                    for channel in data["channels"]:
                        channels.append({
                            "id": channel["id"],
                            "name": channel["name"],
                            "is_private": channel["is_private"],
                            "is_archived": channel["is_archived"],
                            "topic": channel.get("topic", {}).get("value", ""),
                            "purpose": channel.get("purpose", {}).get("value", ""),
                            "num_members": channel.get("num_members", 0)
                        })
                    
                    return {
                        "channels": channels,
                        "total_count": len(channels)
                    }
                else:
                    raise Exception(f"Slack API error: {data.get('error')}")
            else:
                raise Exception(f"HTTP error: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"Failed to list channels: {str(e)}")
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform Slack-specific health check."""
        try:
            if not self.bot_token:
                return {"error": "Bot token not configured"}
            
            # Test API access
            response = self.session.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    return {
                        "authenticated": self._authenticated,
                        "bot_id": data.get("bot_id"),
                        "team": data.get("team"),
                        "user": data.get("user")
                    }
                else:
                    return {"error": data.get("error")}
            else:
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            return {"error": str(e)}
