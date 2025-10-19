"""
Gmail Connector for Enterprise AI Agent Framework.

This connector provides Gmail integration capabilities including sending emails,
deleting emails, and managing email operations.
"""

import base64
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType

logger = structlog.get_logger()


class GmailConnector(BaseConnector):
    """Gmail connector for email operations."""
    
    # Gmail API scopes
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.readonly'
    ]
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "credentials_file": {
                "type": "string",
                "description": "Path to OAuth2 credentials file"
            },
            "token_file": {
                "type": "string",
                "description": "Path to store OAuth2 tokens"
            },
            "user_email": {
                "type": "string",
                "description": "Gmail user email address"
            },
            "timeout": {
                "type": "integer",
                "default": 30,
                "description": "Request timeout in seconds"
            }
        },
        "required": ["credentials_file", "user_email"]
    }
    
    def __init__(self, config: ConnectorConfig):
        """Initialize Gmail connector."""
        super().__init__(config)
        self.service = None
        self.user_email = self.config.config.get("user_email")
        self.credentials_file = self.config.config.get("credentials_file")
        self.token_file = self.config.config.get("token_file", "token.json")
        self.timeout = self.config.config.get("timeout", 30)
    
    def get_description(self) -> str:
        """Get connector description."""
        return "Gmail connector for email operations including sending and deleting emails"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return ["email", "gmail", "google", "communication"]
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return ["send_email", "delete_email", "read_email", "email_management"]
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["oauth2"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {
            "requests_per_day": 1000000000,  # Gmail API quota
            "requests_per_100_seconds": 100,
            "requests_per_100_seconds_per_user": 100
        }
    
    def authenticate(self) -> bool:
        """Authenticate with Gmail API."""
        try:
            creds = None
            
            # Load existing token
            if os.path.exists(self.token_file):
                creds = Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
            
            # If there are no valid credentials, request authorization
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, self.SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # Save credentials for next run
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            
            # Test the connection
            profile = self.service.users().getProfile(userId='me').execute()
            self.logger.info("Gmail authentication successful", email=profile.get('emailAddress'))
            
            self._authenticated = True
            return True
            
        except Exception as e:
            self.logger.error("Gmail authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return [
            ConnectorAction(
                name="send_email",
                description="Send an email via Gmail",
                action_type=ActionType.WRITE,
                parameters={
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body content"
                    },
                    "cc": {
                        "type": "string",
                        "description": "CC email addresses (comma-separated)"
                    },
                    "bcc": {
                        "type": "string",
                        "description": "BCC email addresses (comma-separated)"
                    },
                    "attachments": {
                        "type": "array",
                        "description": "List of attachment file paths"
                    },
                    "html": {
                        "type": "boolean",
                        "default": False,
                        "description": "Whether body is HTML"
                    }
                },
                required_parameters=["to", "subject", "body"],
                optional_parameters=["cc", "bcc", "attachments", "html"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "message_id": {"type": "string"},
                        "thread_id": {"type": "string"},
                        "sent_at": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="delete_email",
                description="Delete an email by message ID",
                action_type=ActionType.DELETE,
                parameters={
                    "message_id": {
                        "type": "string",
                        "description": "Gmail message ID to delete"
                    }
                },
                required_parameters=["message_id"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "deleted": {"type": "boolean"},
                        "message_id": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="list_emails",
                description="List emails with optional filters",
                action_type=ActionType.READ,
                parameters={
                    "query": {
                        "type": "string",
                        "description": "Gmail search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 10,
                        "description": "Maximum number of results"
                    },
                    "include_spam_trash": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include spam and trash"
                    }
                },
                optional_parameters=["query", "max_results", "include_spam_trash"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "thread_id": {"type": "string"},
                                    "subject": {"type": "string"},
                                    "from": {"type": "string"},
                                    "date": {"type": "string"}
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
        """Execute a Gmail action."""
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
            if action_name == "send_email":
                result = self._send_email(parameters)
            elif action_name == "delete_email":
                result = self._delete_email(parameters)
            elif action_name == "list_emails":
                result = self._list_emails(parameters)
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
                metadata={"action": action_name, "user_email": self.user_email}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("Gmail action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
    
    def _send_email(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email."""
        try:
            to = parameters["to"]
            subject = parameters["subject"]
            body = parameters["body"]
            cc = parameters.get("cc", "")
            bcc = parameters.get("bcc", "")
            attachments = parameters.get("attachments", [])
            is_html = parameters.get("html", False)
            
            # Create message
            message = self._create_message(to, subject, body, cc, bcc, attachments, is_html)
            
            # Send message
            sent_message = self.service.users().messages().send(
                userId='me', body=message
            ).execute()
            
            return {
                "message_id": sent_message['id'],
                "thread_id": sent_message['threadId'],
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "to": to,
                "subject": subject
            }
            
        except HttpError as e:
            raise Exception(f"Gmail API error: {e}")
    
    def _delete_email(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Delete an email."""
        try:
            message_id = parameters["message_id"]
            
            # Delete message
            self.service.users().messages().delete(
                userId='me', id=message_id
            ).execute()
            
            return {
                "deleted": True,
                "message_id": message_id,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }
            
        except HttpError as e:
            if e.resp.status == 404:
                raise Exception(f"Message not found: {message_id}")
            raise Exception(f"Gmail API error: {e}")
    
    def _list_emails(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """List emails."""
        try:
            query = parameters.get("query", "")
            max_results = parameters.get("max_results", 10)
            include_spam_trash = parameters.get("include_spam_trash", False)
            
            # List messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results,
                includeSpamTrash=include_spam_trash
            ).execute()
            
            messages = results.get('messages', [])
            
            # Get message details
            detailed_messages = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId='me', id=message['id']
                ).execute()
                
                # Extract headers
                headers = msg['payload'].get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
                from_addr = next((h['value'] for h in headers if h['name'] == 'From'), '')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                detailed_messages.append({
                    "id": message['id'],
                    "thread_id": message['threadId'],
                    "subject": subject,
                    "from": from_addr,
                    "date": date
                })
            
            return {
                "messages": detailed_messages,
                "total_count": len(detailed_messages),
                "query": query
            }
            
        except HttpError as e:
            raise Exception(f"Gmail API error: {e}")
    
    def _create_message(self, to: str, subject: str, body: str, cc: str = "", bcc: str = "", 
                       attachments: List[str] = None, is_html: bool = False) -> Dict[str, Any]:
        """Create a Gmail message."""
        if attachments is None:
            attachments = []
        
        # Build recipients
        recipients = [to]
        if cc:
            recipients.extend([email.strip() for email in cc.split(',')])
        if bcc:
            recipients.extend([email.strip() for email in bcc.split(',')])
        
        # Create message parts
        message_parts = []
        
        # Main body
        if is_html:
            message_parts.append({
                'mimeType': 'text/html',
                'data': base64.urlsafe_b64encode(body.encode()).decode()
            })
        else:
            message_parts.append({
                'mimeType': 'text/plain',
                'data': base64.urlsafe_b64encode(body.encode()).decode()
            })
        
        # Add attachments
        for attachment_path in attachments:
            if os.path.exists(attachment_path):
                with open(attachment_path, 'rb') as f:
                    attachment_data = f.read()
                
                message_parts.append({
                    'mimeType': 'application/octet-stream',
                    'filename': os.path.basename(attachment_path),
                    'data': base64.urlsafe_b64encode(attachment_data).decode()
                })
        
        # Create message
        if len(message_parts) == 1:
            # Simple message
            message = {
                'raw': base64.urlsafe_b64encode(
                    f"To: {', '.join(recipients)}\r\n"
                    f"Subject: {subject}\r\n"
                    f"Content-Type: {'text/html' if is_html else 'text/plain'}; charset=utf-8\r\n"
                    f"\r\n{body}"
                ).decode()
            }
        else:
            # Multipart message
            boundary = "boundary123456789"
            message_body = f"To: {', '.join(recipients)}\r\n"
            message_body += f"Subject: {subject}\r\n"
            message_body += f"Content-Type: multipart/mixed; boundary={boundary}\r\n"
            message_body += "\r\n"
            
            for part in message_parts:
                message_body += f"--{boundary}\r\n"
                message_body += f"Content-Type: {part['mimeType']}\r\n"
                if 'filename' in part:
                    message_body += f"Content-Disposition: attachment; filename=\"{part['filename']}\"\r\n"
                message_body += "Content-Transfer-Encoding: base64\r\n"
                message_body += "\r\n"
                message_body += part['data']
                message_body += "\r\n"
            
            message_body += f"--{boundary}--\r\n"
            
            message = {
                'raw': base64.urlsafe_b64encode(message_body.encode()).decode()
            }
        
        return message
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform Gmail-specific health check."""
        try:
            if not self.service:
                return {"error": "Service not initialized"}
            
            # Test API access
            profile = self.service.users().getProfile(userId='me').execute()
            
            return {
                "authenticated": self._authenticated,
                "user_email": profile.get('emailAddress'),
                "messages_total": profile.get('messagesTotal', 0),
                "threads_total": profile.get('threadsTotal', 0)
            }
            
        except Exception as e:
            return {"error": str(e)}


# Import os for file operations
import os
