"""
S3 Connector for Enterprise AI Agent Framework.

This connector provides AWS S3 integration capabilities including file upload,
download, and management operations.
"""

import os
import mimetypes
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import structlog
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType

logger = structlog.get_logger()


class S3Connector(BaseConnector):
    """S3 connector for file operations."""
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "region_name": {
                "type": "string",
                "default": "us-east-1",
                "description": "AWS region name"
            },
            "bucket_name": {
                "type": "string",
                "description": "Default S3 bucket name"
            },
            "endpoint_url": {
                "type": "string",
                "description": "Custom S3 endpoint URL (for S3-compatible services)"
            },
            "use_ssl": {
                "type": "boolean",
                "default": True,
                "description": "Whether to use SSL"
            },
            "signature_version": {
                "type": "string",
                "default": "s3v4",
                "description": "S3 signature version"
            },
            "max_pool_connections": {
                "type": "integer",
                "default": 50,
                "description": "Maximum number of connections in the pool"
            },
            "timeout": {
                "type": "integer",
                "default": 60,
                "description": "Request timeout in seconds"
            }
        },
        "required": ["bucket_name"]
    }
    
    def __init__(self, config: ConnectorConfig):
        """Initialize S3 connector."""
        super().__init__(config)
        self.region_name = self.config.config.get("region_name", "us-east-1")
        self.bucket_name = self.config.config.get("bucket_name")
        self.endpoint_url = self.config.config.get("endpoint_url")
        self.use_ssl = self.config.config.get("use_ssl", True)
        self.signature_version = self.config.config.get("signature_version", "s3v4")
        self.max_pool_connections = self.config.config.get("max_pool_connections", 50)
        self.timeout = self.config.config.get("timeout", 60)
        
        # AWS credentials
        self.aws_access_key_id = self.config.credentials.get("aws_access_key_id")
        self.aws_secret_access_key = self.config.credentials.get("aws_secret_access_key")
        self.aws_session_token = self.config.credentials.get("aws_session_token")
        
        self._s3_client = None
        self._s3_resource = None
    
    def get_description(self) -> str:
        """Get connector description."""
        return "S3 connector for file upload, download, and management operations"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return ["s3", "aws", "storage", "files", "cloud"]
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return ["upload_file", "download_file", "delete_file", "list_files", "copy_file", "presigned_url"]
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["aws_credentials", "iam_role", "aws_profile"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {
            "requests_per_second": 3500,
            "put_requests_per_second": 3500,
            "get_requests_per_second": 5500
        }
    
    def authenticate(self) -> bool:
        """Authenticate with AWS S3."""
        try:
            # Configure boto3 client
            config = Config(
                region_name=self.region_name,
                signature_version=self.signature_version,
                max_pool_connections=self.max_pool_connections,
                retries={'max_attempts': 3}
            )
            
            # Create S3 client
            session_kwargs = {}
            if self.aws_access_key_id:
                session_kwargs['aws_access_key_id'] = self.aws_access_key_id
            if self.aws_secret_access_key:
                session_kwargs['aws_secret_access_key'] = self.aws_secret_access_key
            if self.aws_session_token:
                session_kwargs['aws_session_token'] = self.aws_session_token
            
            session = boto3.Session(**session_kwargs)
            
            client_kwargs = {
                'config': config,
                'use_ssl': self.use_ssl
            }
            
            if self.endpoint_url:
                client_kwargs['endpoint_url'] = self.endpoint_url
            
            self._s3_client = session.client('s3', **client_kwargs)
            self._s3_resource = session.resource('s3', **client_kwargs)
            
            # Test connection by listing buckets
            self._s3_client.list_buckets()
            
            self.logger.info("S3 authentication successful", region=self.region_name, bucket=self.bucket_name)
            self._authenticated = True
            return True
            
        except NoCredentialsError:
            self.logger.error("AWS credentials not found")
            self._authenticated = False
            return False
        except Exception as e:
            self.logger.error("S3 authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return [
            ConnectorAction(
                name="upload_file",
                description="Upload a file to S3",
                action_type=ActionType.WRITE,
                parameters={
                    "file_path": {
                        "type": "string",
                        "description": "Local file path to upload"
                    },
                    "s3_key": {
                        "type": "string",
                        "description": "S3 object key (path in bucket)"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket name (optional, uses default if not provided)"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "MIME content type (auto-detected if not provided)"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Custom metadata for the object"
                    },
                    "acl": {
                        "type": "string",
                        "enum": ["private", "public-read", "public-read-write", "authenticated-read"],
                        "default": "private",
                        "description": "Access control list"
                    },
                    "storage_class": {
                        "type": "string",
                        "enum": ["STANDARD", "REDUCED_REDUNDANCY", "STANDARD_IA", "ONEZONE_IA", "INTELLIGENT_TIERING", "GLACIER", "DEEP_ARCHIVE"],
                        "default": "STANDARD",
                        "description": "Storage class"
                    }
                },
                required_parameters=["file_path", "s3_key"],
                optional_parameters=["bucket", "content_type", "metadata", "acl", "storage_class"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "key": {"type": "string"},
                        "etag": {"type": "string"},
                        "size": {"type": "integer"},
                        "uploaded_at": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="download_file",
                description="Download a file from S3",
                action_type=ActionType.READ,
                parameters={
                    "s3_key": {
                        "type": "string",
                        "description": "S3 object key"
                    },
                    "local_path": {
                        "type": "string",
                        "description": "Local path to save the file"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket name (optional, uses default if not provided)"
                    }
                },
                required_parameters=["s3_key", "local_path"],
                optional_parameters=["bucket"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "key": {"type": "string"},
                        "local_path": {"type": "string"},
                        "size": {"type": "integer"},
                        "downloaded_at": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="delete_file",
                description="Delete a file from S3",
                action_type=ActionType.DELETE,
                parameters={
                    "s3_key": {
                        "type": "string",
                        "description": "S3 object key to delete"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket name (optional, uses default if not provided)"
                    },
                    "version_id": {
                        "type": "string",
                        "description": "Object version ID (for versioned buckets)"
                    }
                },
                required_parameters=["s3_key"],
                optional_parameters=["bucket", "version_id"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "bucket": {"type": "string"},
                        "key": {"type": "string"},
                        "deleted": {"type": "boolean"},
                        "deleted_at": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="list_files",
                description="List files in an S3 bucket",
                action_type=ActionType.READ,
                parameters={
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket name (optional, uses default if not provided)"
                    },
                    "prefix": {
                        "type": "string",
                        "description": "Prefix to filter objects"
                    },
                    "max_keys": {
                        "type": "integer",
                        "default": 1000,
                        "description": "Maximum number of objects to return"
                    },
                    "delimiter": {
                        "type": "string",
                        "description": "Delimiter for grouping keys"
                    }
                },
                optional_parameters=["bucket", "prefix", "max_keys", "delimiter"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "objects": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "key": {"type": "string"},
                                    "size": {"type": "integer"},
                                    "last_modified": {"type": "string"},
                                    "etag": {"type": "string"},
                                    "storage_class": {"type": "string"}
                                }
                            }
                        },
                        "common_prefixes": {"type": "array"},
                        "total_count": {"type": "integer"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="copy_file",
                description="Copy a file within S3 or between buckets",
                action_type=ActionType.WRITE,
                parameters={
                    "source_bucket": {
                        "type": "string",
                        "description": "Source bucket name"
                    },
                    "source_key": {
                        "type": "string",
                        "description": "Source object key"
                    },
                    "dest_bucket": {
                        "type": "string",
                        "description": "Destination bucket name"
                    },
                    "dest_key": {
                        "type": "string",
                        "description": "Destination object key"
                    },
                    "metadata": {
                        "type": "object",
                        "description": "Custom metadata for the copied object"
                    },
                    "acl": {
                        "type": "string",
                        "enum": ["private", "public-read", "public-read-write", "authenticated-read"],
                        "default": "private",
                        "description": "Access control list"
                    }
                },
                required_parameters=["source_bucket", "source_key", "dest_bucket", "dest_key"],
                optional_parameters=["metadata", "acl"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "source_bucket": {"type": "string"},
                        "source_key": {"type": "string"},
                        "dest_bucket": {"type": "string"},
                        "dest_key": {"type": "string"},
                        "copied_at": {"type": "string"}
                    }
                },
                timeout=self.timeout,
                is_async=True
            ),
            ConnectorAction(
                name="generate_presigned_url",
                description="Generate a presigned URL for S3 operations",
                action_type=ActionType.EXECUTE,
                parameters={
                    "s3_key": {
                        "type": "string",
                        "description": "S3 object key"
                    },
                    "operation": {
                        "type": "string",
                        "enum": ["get_object", "put_object", "delete_object"],
                        "description": "S3 operation type"
                    },
                    "bucket": {
                        "type": "string",
                        "description": "S3 bucket name (optional, uses default if not provided)"
                    },
                    "expires_in": {
                        "type": "integer",
                        "default": 3600,
                        "description": "URL expiration time in seconds"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Content type for PUT operations"
                    }
                },
                required_parameters=["s3_key", "operation"],
                optional_parameters=["bucket", "expires_in", "content_type"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "expires_at": {"type": "string"},
                        "operation": {"type": "string"}
                    }
                },
                timeout=30,
                is_async=False
            )
        ]
    
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """Execute an S3 action."""
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
            if action_name == "upload_file":
                result = self._upload_file(parameters)
            elif action_name == "download_file":
                result = self._download_file(parameters)
            elif action_name == "delete_file":
                result = self._delete_file(parameters)
            elif action_name == "list_files":
                result = self._list_files(parameters)
            elif action_name == "copy_file":
                result = self._copy_file(parameters)
            elif action_name == "generate_presigned_url":
                result = self._generate_presigned_url(parameters)
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
                metadata={"action": action_name, "bucket": self.bucket_name}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("S3 action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
    
    def _upload_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to S3."""
        try:
            file_path = parameters["file_path"]
            s3_key = parameters["s3_key"]
            bucket = parameters.get("bucket", self.bucket_name)
            content_type = parameters.get("content_type")
            metadata = parameters.get("metadata", {})
            acl = parameters.get("acl", "private")
            storage_class = parameters.get("storage_class", "STANDARD")
            
            if not os.path.exists(file_path):
                raise Exception(f"File not found: {file_path}")
            
            # Auto-detect content type if not provided
            if not content_type:
                content_type, _ = mimetypes.guess_type(file_path)
                if not content_type:
                    content_type = "application/octet-stream"
            
            # Prepare extra args
            extra_args = {
                'ACL': acl,
                'StorageClass': storage_class,
                'ContentType': content_type
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            # Upload file
            self._s3_client.upload_file(
                file_path,
                bucket,
                s3_key,
                ExtraArgs=extra_args
            )
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            return {
                "bucket": bucket,
                "key": s3_key,
                "etag": f'"{hash(file_path)}"',  # Simplified ETag
                "size": file_size,
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            
        except ClientError as e:
            raise Exception(f"S3 upload failed: {e}")
        except Exception as e:
            raise Exception(f"Upload failed: {str(e)}")
    
    def _download_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from S3."""
        try:
            s3_key = parameters["s3_key"]
            local_path = parameters["local_path"]
            bucket = parameters.get("bucket", self.bucket_name)
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Download file
            self._s3_client.download_file(bucket, s3_key, local_path)
            
            # Get file size
            file_size = os.path.getsize(local_path)
            
            return {
                "bucket": bucket,
                "key": s3_key,
                "local_path": local_path,
                "size": file_size,
                "downloaded_at": datetime.now(timezone.utc).isoformat()
            }
            
        except ClientError as e:
            raise Exception(f"S3 download failed: {e}")
        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")
    
    def _delete_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file from S3."""
        try:
            s3_key = parameters["s3_key"]
            bucket = parameters.get("bucket", self.bucket_name)
            version_id = parameters.get("version_id")
            
            # Prepare delete args
            delete_kwargs = {
                'Bucket': bucket,
                'Key': s3_key
            }
            
            if version_id:
                delete_kwargs['VersionId'] = version_id
            
            # Delete file
            self._s3_client.delete_object(**delete_kwargs)
            
            return {
                "bucket": bucket,
                "key": s3_key,
                "deleted": True,
                "deleted_at": datetime.now(timezone.utc).isoformat()
            }
            
        except ClientError as e:
            raise Exception(f"S3 delete failed: {e}")
        except Exception as e:
            raise Exception(f"Delete failed: {str(e)}")
    
    def _list_files(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """List files in S3 bucket."""
        try:
            bucket = parameters.get("bucket", self.bucket_name)
            prefix = parameters.get("prefix", "")
            max_keys = parameters.get("max_keys", 1000)
            delimiter = parameters.get("delimiter")
            
            # Prepare list args
            list_kwargs = {
                'Bucket': bucket,
                'MaxKeys': max_keys
            }
            
            if prefix:
                list_kwargs['Prefix'] = prefix
            
            if delimiter:
                list_kwargs['Delimiter'] = delimiter
            
            # List objects
            response = self._s3_client.list_objects_v2(**list_kwargs)
            
            objects = []
            for obj in response.get('Contents', []):
                objects.append({
                    "key": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'].isoformat(),
                    "etag": obj['ETag'],
                    "storage_class": obj.get('StorageClass', 'STANDARD')
                })
            
            common_prefixes = response.get('CommonPrefixes', [])
            common_prefixes = [prefix['Prefix'] for prefix in common_prefixes]
            
            return {
                "objects": objects,
                "common_prefixes": common_prefixes,
                "total_count": len(objects)
            }
            
        except ClientError as e:
            raise Exception(f"S3 list failed: {e}")
        except Exception as e:
            raise Exception(f"List files failed: {str(e)}")
    
    def _copy_file(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Copy a file within S3."""
        try:
            source_bucket = parameters["source_bucket"]
            source_key = parameters["source_key"]
            dest_bucket = parameters["dest_bucket"]
            dest_key = parameters["dest_key"]
            metadata = parameters.get("metadata", {})
            acl = parameters.get("acl", "private")
            
            # Prepare copy source
            copy_source = {
                'Bucket': source_bucket,
                'Key': source_key
            }
            
            # Prepare extra args
            extra_args = {
                'ACL': acl
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
                extra_args['MetadataDirective'] = 'REPLACE'
            
            # Copy object
            self._s3_client.copy_object(
                CopySource=copy_source,
                Bucket=dest_bucket,
                Key=dest_key,
                ExtraArgs=extra_args
            )
            
            return {
                "source_bucket": source_bucket,
                "source_key": source_key,
                "dest_bucket": dest_bucket,
                "dest_key": dest_key,
                "copied_at": datetime.now(timezone.utc).isoformat()
            }
            
        except ClientError as e:
            raise Exception(f"S3 copy failed: {e}")
        except Exception as e:
            raise Exception(f"Copy file failed: {str(e)}")
    
    def _generate_presigned_url(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a presigned URL."""
        try:
            s3_key = parameters["s3_key"]
            operation = parameters["operation"]
            bucket = parameters.get("bucket", self.bucket_name)
            expires_in = parameters.get("expires_in", 3600)
            content_type = parameters.get("content_type")
            
            # Prepare parameters
            params = {
                'Bucket': bucket,
                'Key': s3_key,
                'ExpiresIn': expires_in
            }
            
            if content_type and operation == 'put_object':
                params['ContentType'] = content_type
            
            # Generate presigned URL
            url = self._s3_client.generate_presigned_url(
                operation,
                Params=params
            )
            
            expires_at = datetime.now(timezone.utc).timestamp() + expires_in
            
            return {
                "url": url,
                "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
                "operation": operation
            }
            
        except ClientError as e:
            raise Exception(f"S3 presigned URL generation failed: {e}")
        except Exception as e:
            raise Exception(f"Presigned URL generation failed: {str(e)}")
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform S3-specific health check."""
        try:
            if not self._s3_client:
                return {"error": "S3 client not initialized"}
            
            # Test by listing buckets
            response = self._s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            
            # Check if default bucket exists
            bucket_exists = self.bucket_name in buckets if self.bucket_name else False
            
            return {
                "authenticated": self._authenticated,
                "region": self.region_name,
                "bucket_name": self.bucket_name,
                "bucket_exists": bucket_exists,
                "total_buckets": len(buckets)
            }
            
        except Exception as e:
            return {"error": str(e)}
