"""
Gmail connector for Enterprise AI Agent Framework.

Provides Gmail integration with send and delete email actions.
Supports OAuth2 authentication and basic error handling.
"""

import json
import base64
from typing import Dict, Any, List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import mimetypes
import os

from .base import BaseConnector, AuthenticationError, ActionError


class GmailConnector(BaseConnector):
    """
    Gmail connector for sending and deleting emails.
    
    Supports OAuth2 authentication and provides actions for
    sending emails and deleting messages.
    """
    
    CONNECTOR_NAME = "gmail"
    VERSION = "1.0.0"
    DESCRIPTION = "Gmail connector for sending and deleting emails"
    
    def __init__(self, tenant_id: Optional[str] = None, **kwargs):
        """
        Initialize the Gmail connector.
        
        Args:
            tenant_id (Optional[str]): Tenant identifier
            **kwargs: Additional configuration
        """
        super().__init__(
            name=self.CONNECTOR_NAME,
            version=self.VERSION,
            tenant_id=tenant_id,
            metadata={
                'service': 'gmail',
                'api_version': 'v1',
                'scopes': ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.modify']
            }
        )
        self._service = None
        self._credentials = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with Gmail API using OAuth2.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
                Expected keys: 'client_id', 'client_secret', 'refresh_token', 'access_token'
        
        Returns:
            bool: True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # In a real implementation, you would use the Google API client library
            # For this example, we'll simulate the authentication process
            
            required_fields = ['client_id', 'client_secret']
            for field in required_fields:
                if field not in credentials:
                    raise AuthenticationError(f"Missing required credential: {field}")
            
            # Validate credentials format
            if not isinstance(credentials['client_id'], str) or not credentials['client_id']:
                raise AuthenticationError("Invalid client_id")
            
            if not isinstance(credentials['client_secret'], str) or not credentials['client_secret']:
                raise AuthenticationError("Invalid client_secret")
            
            # Store credentials
            self._credentials = credentials.copy()
            
            # Simulate service initialization
            self._service = "gmail_service_instance"  # In real implementation: build('gmail', 'v1', credentials=creds)
            
            self.status = self.status.CONNECTED
            self.update_activity()
            
            return True
            
        except Exception as e:
            self.status = self.status.ERROR
            raise AuthenticationError(f"Gmail authentication failed: {str(e)}")
    
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a Gmail action.
        
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
            raise AuthenticationError("Not authenticated with Gmail")
        
        if not self.validate_params(action_name, params):
            raise ActionError(f"Invalid parameters for action '{action_name}'")
        
        try:
            self.update_activity()
            
            if action_name == "send_email":
                return self._send_email(params)
            elif action_name == "delete_email":
                return self._delete_email(params)
            else:
                raise ActionError(f"Unknown action: {action_name}")
                
        except Exception as e:
            raise ActionError(f"Failed to execute action '{action_name}': {str(e)}")
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available Gmail actions.
        
        Returns:
            List[Dict[str, Any]]: List of available actions
        """
        return [
            {
                'name': 'send_email',
                'description': 'Send an email message',
                'required_params': ['to', 'subject', 'body'],
                'optional_params': ['cc', 'bcc', 'attachments', 'html_body'],
                'example': {
                    'to': 'recipient@example.com',
                    'subject': 'Test Email',
                    'body': 'This is a test email',
                    'cc': 'cc@example.com',
                    'bcc': 'bcc@example.com'
                }
            },
            {
                'name': 'delete_email',
                'description': 'Delete an email message',
                'required_params': ['message_id'],
                'optional_params': [],
                'example': {
                    'message_id': '1234567890abcdef'
                }
            }
        ]
    
    def _send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send an email message.
        
        Args:
            params (Dict[str, Any]): Email parameters
            
        Returns:
            Dict[str, Any]: Send result
        """
        # Extract parameters
        to = params['to']
        subject = params['subject']
        body = params.get('body', '')
        html_body = params.get('html_body')
        cc = params.get('cc')
        bcc = params.get('bcc')
        attachments = params.get('attachments', [])
        
        # Validate email addresses
        if not self._is_valid_email(to):
            raise ActionError(f"Invalid 'to' email address: {to}")
        
        if cc and not self._is_valid_email(cc):
            raise ActionError(f"Invalid 'cc' email address: {cc}")
        
        if bcc and not self._is_valid_email(bcc):
            raise ActionError(f"Invalid 'bcc' email address: {bcc}")
        
        # Create email message
        if html_body:
            message = MIMEMultipart('alternative')
            text_part = MIMEText(body, 'plain')
            html_part = MIMEText(html_body, 'html')
            message.attach(text_part)
            message.attach(html_part)
        else:
            message = MIMEText(body, 'plain')
        
        message['To'] = to
        message['Subject'] = subject
        
        if cc:
            message['Cc'] = cc
        if bcc:
            message['Bcc'] = bcc
        
        # Add attachments if provided
        for attachment_path in attachments:
            if os.path.exists(attachment_path):
                self._add_attachment(message, attachment_path)
            else:
                raise ActionError(f"Attachment file not found: {attachment_path}")
        
        # In a real implementation, you would send the email using the Gmail API
        # For this example, we'll simulate the send operation
        
        # Simulate API call
        message_id = f"msg_{hash(str(message))}"
        
        return {
            'success': True,
            'message_id': message_id,
            'to': to,
            'subject': subject,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _delete_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete an email message.
        
        Args:
            params (Dict[str, Any]): Delete parameters
            
        Returns:
            Dict[str, Any]: Delete result
        """
        message_id = params['message_id']
        
        if not message_id or not isinstance(message_id, str):
            raise ActionError("Invalid message_id")
        
        # In a real implementation, you would delete the email using the Gmail API
        # For this example, we'll simulate the delete operation
        
        # Simulate API call
        success = True  # In real implementation: service.users().messages().delete(userId='me', id=message_id).execute()
        
        return {
            'success': success,
            'message_id': message_id,
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _add_attachment(self, message: MIMEMultipart, file_path: str) -> None:
        """
        Add an attachment to the email message.
        
        Args:
            message (MIMEMultipart): Email message
            file_path (str): Path to the attachment file
        """
        try:
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            
            filename = os.path.basename(file_path)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {filename}'
            )
            
            message.attach(part)
            
        except Exception as e:
            raise ActionError(f"Failed to add attachment {file_path}: {str(e)}")
    
    def _is_valid_email(self, email: str) -> bool:
        """
        Validate email address format.
        
        Args:
            email (str): Email address to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for Gmail actions.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not super().validate_params(action_name, params):
            return False
        
        if action_name == "send_email":
            # Additional validation for send_email
            if 'to' not in params or not self._is_valid_email(params['to']):
                return False
            
            if 'subject' not in params or not isinstance(params['subject'], str):
                return False
            
            if 'body' not in params and 'html_body' not in params:
                return False
            
            # Validate attachments if provided
            if 'attachments' in params:
                attachments = params['attachments']
                if not isinstance(attachments, list):
                    return False
                for attachment in attachments:
                    if not isinstance(attachment, str):
                        return False
        
        elif action_name == "delete_email":
            # Additional validation for delete_email
            if 'message_id' not in params:
                return False
            
            message_id = params['message_id']
            if not isinstance(message_id, str) or not message_id.strip():
                return False
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from Gmail API."""
        super().disconnect()
        self._service = None
        self._credentials = None
