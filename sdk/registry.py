"""
Flow Registry for Enterprise AI Agent Framework SDK.

This module provides the FlowRegistry class for managing flow metadata
with PostgreSQL backend storage.
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

from .models import Flow, Task


class RegistryError(Exception):
    """Exception raised when registry operations fail."""
    pass


class FlowMetadata:
    """
    Metadata for a flow stored in the registry.
    
    This class represents the metadata information stored in the registry
    without the full flow definition.
    """
    
    def __init__(
        self,
        flow_id: str,
        name: str,
        version: str,
        tenant_id: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize flow metadata.
        
        Args:
            flow_id: Unique identifier for the flow
            name: Human-readable name for the flow
            version: Version of the flow
            tenant_id: Tenant identifier for multi-tenancy
            description: Description of the flow
            tags: List of tags for categorization
            created_at: Creation timestamp
            updated_at: Last update timestamp
            metadata: Additional metadata
        """
        self.flow_id = flow_id
        self.name = name
        self.version = version
        self.tenant_id = tenant_id
        self.description = description or ""
        self.tags = tags or []
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary."""
        return {
            'flow_id': self.flow_id,
            'name': self.name,
            'version': self.version,
            'tenant_id': self.tenant_id,
            'description': self.description,
            'tags': self.tags,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FlowMetadata':
        """Create metadata from dictionary."""
        return cls(
            flow_id=data['flow_id'],
            name=data['name'],
            version=data['version'],
            tenant_id=data.get('tenant_id'),
            description=data.get('description'),
            tags=data.get('tags', []),
            created_at=datetime.fromisoformat(data.get('created_at', datetime.utcnow().isoformat())),
            updated_at=datetime.fromisoformat(data.get('updated_at', datetime.utcnow().isoformat())),
            metadata=data.get('metadata', {})
        )


class FlowRegistry:
    """
    Registry for managing flow metadata with PostgreSQL backend.
    
    This class provides methods for registering, retrieving, and listing
    flow metadata stored in a PostgreSQL database.
    """
    
    def __init__(
        self,
        connection_string: Optional[str] = None,
        host: str = "localhost",
        port: int = 5432,
        database: str = "agent_framework",
        username: str = "postgres",
        password: str = "password",
        schema: str = "public"
    ):
        """
        Initialize the flow registry.
        
        Args:
            connection_string: Complete PostgreSQL connection string
            host: Database host
            port: Database port
            database: Database name
            username: Database username
            password: Database password
            schema: Database schema
        """
        self.connection_string = connection_string or f"postgresql://{username}:{password}@{host}:{port}/{database}"
        self.schema = schema
        self._connection = None
        self._ensure_table_exists()
    
    def _get_connection(self):
        """Get database connection."""
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
        except ImportError:
            raise RegistryError("psycopg2 is required for PostgreSQL support. Install with: pip install psycopg2-binary")
        
        if self._connection is None or self._connection.closed:
            try:
                self._connection = psycopg2.connect(
                    self.connection_string,
                    cursor_factory=RealDictCursor
                )
            except Exception as e:
                raise RegistryError(f"Failed to connect to database: {str(e)}")
        
        return self._connection
    
    def _ensure_table_exists(self):
        """Ensure the flows table exists."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.flows (
                flow_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                tenant_id VARCHAR(255),
                description TEXT,
                tags JSONB,
                flow_data JSONB NOT NULL,
                metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_flows_tenant_id ON {self.schema}.flows(tenant_id);
            CREATE INDEX IF NOT EXISTS idx_flows_name ON {self.schema}.flows(name);
            CREATE INDEX IF NOT EXISTS idx_flows_version ON {self.schema}.flows(version);
            CREATE INDEX IF NOT EXISTS idx_flows_tags ON {self.schema}.flows USING GIN(tags);
            """
            
            cursor.execute(create_table_sql)
            conn.commit()
            cursor.close()
            
        except Exception as e:
            raise RegistryError(f"Failed to create flows table: {str(e)}")
    
    def register_flow(
        self,
        flow: Flow,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowMetadata:
        """
        Register a flow in the registry.
        
        Args:
            flow: Flow instance to register
            name: Human-readable name for the flow
            description: Description of the flow
            tags: List of tags for categorization
            metadata: Additional metadata
            
        Returns:
            FlowMetadata: Registered flow metadata
            
        Raises:
            RegistryError: If registration fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if flow already exists
            cursor.execute(
                f"SELECT flow_id FROM {self.schema}.flows WHERE flow_id = %s",
                (flow.id,)
            )
            
            if cursor.fetchone():
                raise RegistryError(f"Flow with ID {flow.id} already exists")
            
            # Create flow metadata
            flow_metadata = FlowMetadata(
                flow_id=flow.id,
                name=name,
                version=flow.version,
                tenant_id=flow.tenant_id,
                description=description,
                tags=tags,
                metadata=metadata
            )
            
            # Insert flow into database
            insert_sql = f"""
            INSERT INTO {self.schema}.flows (
                flow_id, name, version, tenant_id, description, 
                tags, flow_data, metadata, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            
            cursor.execute(insert_sql, (
                flow.id,
                name,
                flow.version,
                flow.tenant_id,
                description,
                json.dumps(tags or []),
                json.dumps(flow.to_dict()),
                json.dumps(metadata or {}),
                flow_metadata.created_at,
                flow_metadata.updated_at
            ))
            
            conn.commit()
            cursor.close()
            
            return flow_metadata
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise RegistryError(f"Failed to register flow: {str(e)}")
    
    def get_flow(self, flow_id: str) -> Optional[Flow]:
        """
        Get a flow by its ID.
        
        Args:
            flow_id: ID of the flow to retrieve
            
        Returns:
            Flow instance if found, None otherwise
            
        Raises:
            RegistryError: If retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                f"SELECT flow_data FROM {self.schema}.flows WHERE flow_id = %s",
                (flow_id,)
            )
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                flow_data = result['flow_data']
                return Flow(**flow_data)
            
            return None
            
        except Exception as e:
            raise RegistryError(f"Failed to get flow {flow_id}: {str(e)}")
    
    def get_flow_metadata(self, flow_id: str) -> Optional[FlowMetadata]:
        """
        Get flow metadata by ID.
        
        Args:
            flow_id: ID of the flow
            
        Returns:
            FlowMetadata if found, None otherwise
            
        Raises:
            RegistryError: If retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                f"""
                SELECT flow_id, name, version, tenant_id, description, 
                       tags, metadata, created_at, updated_at
                FROM {self.schema}.flows 
                WHERE flow_id = %s
                """,
                (flow_id,)
            )
            
            result = cursor.fetchone()
            cursor.close()
            
            if result:
                return FlowMetadata.from_dict(dict(result))
            
            return None
            
        except Exception as e:
            raise RegistryError(f"Failed to get flow metadata {flow_id}: {str(e)}")
    
    def list_flows(
        self,
        tenant_id: Optional[str] = None,
        name_filter: Optional[str] = None,
        tag_filter: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FlowMetadata]:
        """
        List flows with optional filtering.
        
        Args:
            tenant_id: Filter by tenant ID
            name_filter: Filter by name (partial match)
            tag_filter: Filter by tags (any match)
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of FlowMetadata objects
            
        Raises:
            RegistryError: If listing fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build query with filters
            where_conditions = []
            params = []
            
            if tenant_id:
                where_conditions.append("tenant_id = %s")
                params.append(tenant_id)
            
            if name_filter:
                where_conditions.append("name ILIKE %s")
                params.append(f"%{name_filter}%")
            
            if tag_filter:
                where_conditions.append("tags ?| %s")
                params.append(tag_filter)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            query = f"""
            SELECT flow_id, name, version, tenant_id, description, 
                   tags, metadata, created_at, updated_at
            FROM {self.schema}.flows 
            {where_clause}
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
            """
            
            params.extend([limit, offset])
            cursor.execute(query, params)
            
            results = cursor.fetchall()
            cursor.close()
            
            return [FlowMetadata.from_dict(dict(row)) for row in results]
            
        except Exception as e:
            raise RegistryError(f"Failed to list flows: {str(e)}")
    
    def update_flow(
        self,
        flow: Flow,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> FlowMetadata:
        """
        Update an existing flow in the registry.
        
        Args:
            flow: Updated flow instance
            name: Updated name (if provided)
            description: Updated description (if provided)
            tags: Updated tags (if provided)
            metadata: Updated metadata (if provided)
            
        Returns:
            Updated FlowMetadata
            
        Raises:
            RegistryError: If update fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get existing metadata
            existing_metadata = self.get_flow_metadata(flow.id)
            if not existing_metadata:
                raise RegistryError(f"Flow {flow.id} not found")
            
            # Update fields
            update_fields = []
            params = []
            
            if name is not None:
                update_fields.append("name = %s")
                params.append(name)
            
            if description is not None:
                update_fields.append("description = %s")
                params.append(description)
            
            if tags is not None:
                update_fields.append("tags = %s")
                params.append(json.dumps(tags))
            
            if metadata is not None:
                update_fields.append("metadata = %s")
                params.append(json.dumps(metadata))
            
            # Always update flow data and timestamp
            update_fields.append("flow_data = %s")
            params.append(json.dumps(flow.to_dict()))
            
            update_fields.append("updated_at = %s")
            params.append(datetime.utcnow())
            
            params.append(flow.id)
            
            update_sql = f"""
            UPDATE {self.schema}.flows 
            SET {', '.join(update_fields)}
            WHERE flow_id = %s
            """
            
            cursor.execute(update_sql, params)
            
            if cursor.rowcount == 0:
                raise RegistryError(f"Flow {flow.id} not found")
            
            conn.commit()
            cursor.close()
            
            # Return updated metadata
            return self.get_flow_metadata(flow.id)
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise RegistryError(f"Failed to update flow: {str(e)}")
    
    def delete_flow(self, flow_id: str) -> bool:
        """
        Delete a flow from the registry.
        
        Args:
            flow_id: ID of the flow to delete
            
        Returns:
            True if flow was deleted, False if not found
            
        Raises:
            RegistryError: If deletion fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                f"DELETE FROM {self.schema}.flows WHERE flow_id = %s",
                (flow_id,)
            )
            
            deleted = cursor.rowcount > 0
            conn.commit()
            cursor.close()
            
            return deleted
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise RegistryError(f"Failed to delete flow {flow_id}: {str(e)}")
    
    def search_flows(
        self,
        query: str,
        tenant_id: Optional[str] = None,
        limit: int = 100
    ) -> List[FlowMetadata]:
        """
        Search flows by name, description, or tags.
        
        Args:
            query: Search query
            tenant_id: Filter by tenant ID
            limit: Maximum number of results
            
        Returns:
            List of matching FlowMetadata objects
            
        Raises:
            RegistryError: If search fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            where_conditions = [
                "(name ILIKE %s OR description ILIKE %s OR tags::text ILIKE %s)"
            ]
            params = [f"%{query}%", f"%{query}%", f"%{query}%"]
            
            if tenant_id:
                where_conditions.append("tenant_id = %s")
                params.append(tenant_id)
            
            search_sql = f"""
            SELECT flow_id, name, version, tenant_id, description, 
                   tags, metadata, created_at, updated_at
            FROM {self.schema}.flows 
            WHERE {' AND '.join(where_conditions)}
            ORDER BY updated_at DESC
            LIMIT %s
            """
            
            params.append(limit)
            cursor.execute(search_sql, params)
            
            results = cursor.fetchall()
            cursor.close()
            
            return [FlowMetadata.from_dict(dict(row)) for row in results]
            
        except Exception as e:
            raise RegistryError(f"Failed to search flows: {str(e)}")
    
    def get_flow_statistics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about flows in the registry.
        
        Args:
            tenant_id: Filter by tenant ID
            
        Returns:
            Dictionary containing flow statistics
            
        Raises:
            RegistryError: If statistics retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            where_clause = ""
            params = []
            
            if tenant_id:
                where_clause = "WHERE tenant_id = %s"
                params.append(tenant_id)
            
            stats_sql = f"""
            SELECT 
                COUNT(*) as total_flows,
                COUNT(DISTINCT tenant_id) as unique_tenants,
                COUNT(DISTINCT name) as unique_names,
                AVG(jsonb_array_length(tags)) as avg_tags_per_flow,
                MIN(created_at) as earliest_flow,
                MAX(created_at) as latest_flow
            FROM {self.schema}.flows 
            {where_clause}
            """
            
            cursor.execute(stats_sql, params)
            result = cursor.fetchone()
            cursor.close()
            
            return dict(result)
            
        except Exception as e:
            raise RegistryError(f"Failed to get flow statistics: {str(e)}")
    
    def close(self):
        """Close the database connection."""
        if self._connection and not self._connection.closed:
            self._connection.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
