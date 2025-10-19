"""
PostgreSQL Connector for Enterprise AI Agent Framework.

This connector provides PostgreSQL database integration capabilities including
insert, update, delete, and query operations.
"""

import json
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone

import structlog
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from psycopg2 import sql

from connectors.base import BaseConnector, ConnectorConfig, ConnectorAction, ConnectorResult, ActionType

logger = structlog.get_logger()


class PostgreSQLConnector(BaseConnector):
    """PostgreSQL connector for database operations."""
    
    # Configuration schema
    CONFIG_SCHEMA = {
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "default": "localhost",
                "description": "Database host"
            },
            "port": {
                "type": "integer",
                "default": 5432,
                "description": "Database port"
            },
            "database": {
                "type": "string",
                "description": "Database name"
            },
            "user": {
                "type": "string",
                "description": "Database user"
            },
            "password": {
                "type": "string",
                "description": "Database password"
            },
            "connection_timeout": {
                "type": "integer",
                "default": 30,
                "description": "Connection timeout in seconds"
            },
            "max_connections": {
                "type": "integer",
                "default": 10,
                "description": "Maximum number of connections"
            },
            "ssl_mode": {
                "type": "string",
                "default": "prefer",
                "enum": ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"],
                "description": "SSL connection mode"
            }
        },
        "required": ["database", "user", "password"]
    }
    
    def __init__(self, config: ConnectorConfig):
        """Initialize PostgreSQL connector."""
        super().__init__(config)
        self.host = self.config.config.get("host", "localhost")
        self.port = self.config.config.get("port", 5432)
        self.database = self.config.config.get("database")
        self.user = self.config.config.get("user")
        self.password = self.config.credentials.get("password")
        self.connection_timeout = self.config.config.get("connection_timeout", 30)
        self.max_connections = self.config.config.get("max_connections", 10)
        self.ssl_mode = self.config.config.get("ssl_mode", "prefer")
        
        self._connection = None
        self._connection_string = None
    
    def get_description(self) -> str:
        """Get connector description."""
        return "PostgreSQL connector for database operations including insert, update, delete, and query"
    
    def get_author(self) -> str:
        """Get connector author."""
        return "Enterprise AI Agent Framework Team"
    
    def get_tags(self) -> List[str]:
        """Get connector tags."""
        return ["postgresql", "database", "sql", "postgres", "rdbms"]
    
    def get_capabilities(self) -> List[str]:
        """Get connector capabilities."""
        return ["insert", "update", "delete", "select", "transaction", "schema_management"]
    
    def get_authentication_methods(self) -> List[str]:
        """Get supported authentication methods."""
        return ["password", "certificate", "kerberos"]
    
    def get_rate_limits(self) -> Dict[str, Any]:
        """Get rate limiting information."""
        return {
            "max_connections": self.max_connections,
            "queries_per_minute": 1000,
            "concurrent_queries": 50
        }
    
    def authenticate(self) -> bool:
        """Authenticate with PostgreSQL database."""
        try:
            # Build connection string
            self._connection_string = (
                f"host={self.host} "
                f"port={self.port} "
                f"dbname={self.database} "
                f"user={self.user} "
                f"password={self.password} "
                f"connect_timeout={self.connection_timeout} "
                f"sslmode={self.ssl_mode}"
            )
            
            # Test connection
            self._connection = psycopg2.connect(self._connection_string)
            self._connection.close()
            
            self.logger.info("PostgreSQL authentication successful", host=self.host, database=self.database)
            self._authenticated = True
            return True
            
        except Exception as e:
            self.logger.error("PostgreSQL authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def list_actions(self) -> List[ConnectorAction]:
        """List all available actions."""
        return [
            ConnectorAction(
                name="insert",
                description="Insert data into a PostgreSQL table",
                action_type=ActionType.WRITE,
                parameters={
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "data": {
                        "type": "object",
                        "description": "Data to insert (column: value pairs)"
                    },
                    "returning": {
                        "type": "string",
                        "description": "Columns to return after insert"
                    },
                    "on_conflict": {
                        "type": "string",
                        "enum": ["do_nothing", "do_update"],
                        "description": "Conflict resolution strategy"
                    },
                    "conflict_target": {
                        "type": "string",
                        "description": "Column(s) for conflict detection"
                    }
                },
                required_parameters=["table", "data"],
                optional_parameters=["returning", "on_conflict", "conflict_target"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "inserted_rows": {"type": "integer"},
                        "returned_data": {"type": "array"},
                        "table": {"type": "string"}
                    }
                },
                timeout=self.connection_timeout,
                is_async=False
            ),
            ConnectorAction(
                name="update",
                description="Update data in a PostgreSQL table",
                action_type=ActionType.WRITE,
                parameters={
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "data": {
                        "type": "object",
                        "description": "Data to update (column: value pairs)"
                    },
                    "where": {
                        "type": "object",
                        "description": "WHERE clause conditions"
                    },
                    "returning": {
                        "type": "string",
                        "description": "Columns to return after update"
                    }
                },
                required_parameters=["table", "data", "where"],
                optional_parameters=["returning"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "updated_rows": {"type": "integer"},
                        "returned_data": {"type": "array"},
                        "table": {"type": "string"}
                    }
                },
                timeout=self.connection_timeout,
                is_async=False
            ),
            ConnectorAction(
                name="delete",
                description="Delete data from a PostgreSQL table",
                action_type=ActionType.DELETE,
                parameters={
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "where": {
                        "type": "object",
                        "description": "WHERE clause conditions"
                    },
                    "returning": {
                        "type": "string",
                        "description": "Columns to return after delete"
                    }
                },
                required_parameters=["table", "where"],
                optional_parameters=["returning"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "deleted_rows": {"type": "integer"},
                        "returned_data": {"type": "array"},
                        "table": {"type": "string"}
                    }
                },
                timeout=self.connection_timeout,
                is_async=False
            ),
            ConnectorAction(
                name="select",
                description="Query data from a PostgreSQL table",
                action_type=ActionType.READ,
                parameters={
                    "table": {
                        "type": "string",
                        "description": "Table name"
                    },
                    "columns": {
                        "type": "string",
                        "default": "*",
                        "description": "Columns to select (comma-separated)"
                    },
                    "where": {
                        "type": "object",
                        "description": "WHERE clause conditions"
                    },
                    "order_by": {
                        "type": "string",
                        "description": "ORDER BY clause"
                    },
                    "limit": {
                        "type": "integer",
                        "default": 1000,
                        "description": "Maximum number of rows to return"
                    },
                    "offset": {
                        "type": "integer",
                        "default": 0,
                        "description": "Number of rows to skip"
                    }
                },
                required_parameters=["table"],
                optional_parameters=["columns", "where", "order_by", "limit", "offset"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "rows": {"type": "array"},
                        "row_count": {"type": "integer"},
                        "table": {"type": "string"}
                    }
                },
                timeout=self.connection_timeout,
                is_async=False
            ),
            ConnectorAction(
                name="execute_sql",
                description="Execute raw SQL query",
                action_type=ActionType.EXECUTE,
                parameters={
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute"
                    },
                    "parameters": {
                        "type": "array",
                        "description": "Query parameters"
                    },
                    "fetch": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to fetch results"
                    }
                },
                required_parameters=["query"],
                optional_parameters=["parameters", "fetch"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "rows": {"type": "array"},
                        "row_count": {"type": "integer"},
                        "query": {"type": "string"}
                    }
                },
                timeout=self.connection_timeout,
                is_async=False
            ),
            ConnectorAction(
                name="transaction",
                description="Execute multiple operations in a transaction",
                action_type=ActionType.EXECUTE,
                parameters={
                    "operations": {
                        "type": "array",
                        "description": "List of operations to execute in transaction"
                    },
                    "isolation_level": {
                        "type": "string",
                        "enum": ["read_committed", "repeatable_read", "serializable"],
                        "default": "read_committed",
                        "description": "Transaction isolation level"
                    }
                },
                required_parameters=["operations"],
                optional_parameters=["isolation_level"],
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "results": {"type": "array"},
                        "operation_count": {"type": "integer"}
                    }
                },
                timeout=self.connection_timeout * 2,  # Longer timeout for transactions
                is_async=False
            )
        ]
    
    def execute_action(self, action_name: str, parameters: Dict[str, Any]) -> ConnectorResult:
        """Execute a PostgreSQL action."""
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
            if action_name == "insert":
                result = self._insert(parameters)
            elif action_name == "update":
                result = self._update(parameters)
            elif action_name == "delete":
                result = self._delete(parameters)
            elif action_name == "select":
                result = self._select(parameters)
            elif action_name == "execute_sql":
                result = self._execute_sql(parameters)
            elif action_name == "transaction":
                result = self._transaction(parameters)
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
                metadata={"action": action_name, "database": self.database}
            )
            
        except Exception as e:
            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            self.logger.error("PostgreSQL action execution failed", action=action_name, error=str(e))
            
            return ConnectorResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                metadata={"action": action_name}
            )
    
    def _get_connection(self):
        """Get database connection."""
        if not self._connection or self._connection.closed:
            self._connection = psycopg2.connect(self._connection_string)
        return self._connection
    
    def _insert(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Insert data into a table."""
        try:
            table = parameters["table"]
            data = parameters["data"]
            returning = parameters.get("returning")
            on_conflict = parameters.get("on_conflict")
            conflict_target = parameters.get("conflict_target")
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build INSERT query
            columns = list(data.keys())
            values = list(data.values())
            placeholders = [f"${i+1}" for i in range(len(values))]
            
            query = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
            
            # Add conflict resolution
            if on_conflict == "do_nothing":
                query += " ON CONFLICT DO NOTHING"
            elif on_conflict == "do_update" and conflict_target:
                update_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns])
                query += f" ON CONFLICT ({conflict_target}) DO UPDATE SET {update_clause}"
            
            # Add RETURNING clause
            if returning:
                query += f" RETURNING {returning}"
            
            # Execute query
            cursor.execute(query, values)
            
            if returning:
                returned_data = cursor.fetchall()
                returned_data = [dict(row) for row in returned_data]
            else:
                returned_data = []
            
            conn.commit()
            cursor.close()
            
            return {
                "inserted_rows": cursor.rowcount,
                "returned_data": returned_data,
                "table": table
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Insert failed: {str(e)}")
    
    def _update(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Update data in a table."""
        try:
            table = parameters["table"]
            data = parameters["data"]
            where = parameters["where"]
            returning = parameters.get("returning")
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build UPDATE query
            set_clause = ", ".join([f"{col} = ${i+1}" for i, col in enumerate(data.keys())])
            where_clause, where_values = self._build_where_clause(where, len(data))
            
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            
            # Add RETURNING clause
            if returning:
                query += f" RETURNING {returning}"
            
            # Execute query
            all_values = list(data.values()) + where_values
            cursor.execute(query, all_values)
            
            if returning:
                returned_data = cursor.fetchall()
                returned_data = [dict(row) for row in returned_data]
            else:
                returned_data = []
            
            conn.commit()
            cursor.close()
            
            return {
                "updated_rows": cursor.rowcount,
                "returned_data": returned_data,
                "table": table
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Update failed: {str(e)}")
    
    def _delete(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Delete data from a table."""
        try:
            table = parameters["table"]
            where = parameters["where"]
            returning = parameters.get("returning")
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build DELETE query
            where_clause, where_values = self._build_where_clause(where)
            
            query = f"DELETE FROM {table} WHERE {where_clause}"
            
            # Add RETURNING clause
            if returning:
                query += f" RETURNING {returning}"
            
            # Execute query
            cursor.execute(query, where_values)
            
            if returning:
                returned_data = cursor.fetchall()
                returned_data = [dict(row) for row in returned_data]
            else:
                returned_data = []
            
            conn.commit()
            cursor.close()
            
            return {
                "deleted_rows": cursor.rowcount,
                "returned_data": returned_data,
                "table": table
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Delete failed: {str(e)}")
    
    def _select(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Select data from a table."""
        try:
            table = parameters["table"]
            columns = parameters.get("columns", "*")
            where = parameters.get("where")
            order_by = parameters.get("order_by")
            limit = parameters.get("limit", 1000)
            offset = parameters.get("offset", 0)
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Build SELECT query
            query = f"SELECT {columns} FROM {table}"
            values = []
            
            # Add WHERE clause
            if where:
                where_clause, where_values = self._build_where_clause(where)
                query += f" WHERE {where_clause}"
                values.extend(where_values)
            
            # Add ORDER BY clause
            if order_by:
                query += f" ORDER BY {order_by}"
            
            # Add LIMIT and OFFSET
            query += f" LIMIT {limit} OFFSET {offset}"
            
            # Execute query
            cursor.execute(query, values)
            rows = cursor.fetchall()
            rows = [dict(row) for row in rows]
            
            cursor.close()
            
            return {
                "rows": rows,
                "row_count": len(rows),
                "table": table
            }
            
        except Exception as e:
            raise Exception(f"Select failed: {str(e)}")
    
    def _execute_sql(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute raw SQL query."""
        try:
            query = parameters["query"]
            query_params = parameters.get("parameters", [])
            fetch = parameters.get("fetch", True)
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Execute query
            cursor.execute(query, query_params)
            
            if fetch:
                rows = cursor.fetchall()
                rows = [dict(row) for row in rows]
            else:
                rows = []
            
            conn.commit()
            cursor.close()
            
            return {
                "rows": rows,
                "row_count": len(rows) if fetch else cursor.rowcount,
                "query": query
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"SQL execution failed: {str(e)}")
    
    def _transaction(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute operations in a transaction."""
        try:
            operations = parameters["operations"]
            isolation_level = parameters.get("isolation_level", "read_committed")
            
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Set isolation level
            isolation_map = {
                "read_committed": "READ COMMITTED",
                "repeatable_read": "REPEATABLE READ",
                "serializable": "SERIALIZABLE"
            }
            cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_map[isolation_level]}")
            
            results = []
            
            try:
                for operation in operations:
                    op_type = operation["type"]
                    op_params = operation["parameters"]
                    
                    if op_type == "insert":
                        result = self._insert(op_params)
                    elif op_type == "update":
                        result = self._update(op_params)
                    elif op_type == "delete":
                        result = self._delete(op_params)
                    elif op_type == "select":
                        result = self._select(op_params)
                    elif op_type == "execute_sql":
                        result = self._execute_sql(op_params)
                    else:
                        raise Exception(f"Unknown operation type: {op_type}")
                    
                    results.append(result)
                
                conn.commit()
                cursor.close()
                
                return {
                    "success": True,
                    "results": results,
                    "operation_count": len(operations)
                }
                
            except Exception as e:
                conn.rollback()
                cursor.close()
                raise e
            
        except Exception as e:
            raise Exception(f"Transaction failed: {str(e)}")
    
    def _build_where_clause(self, where: Dict[str, Any], param_offset: int = 0) -> tuple:
        """Build WHERE clause from conditions."""
        conditions = []
        values = []
        
        for i, (column, value) in enumerate(where.items()):
            param_num = param_offset + i + 1
            conditions.append(f"{column} = ${param_num}")
            values.append(value)
        
        return " AND ".join(conditions), values
    
    def _perform_health_check(self) -> Dict[str, Any]:
        """Perform PostgreSQL-specific health check."""
        try:
            if not self._connection_string:
                return {"error": "Connection string not configured"}
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Test basic query
            cursor.execute("SELECT version(), current_database(), current_user")
            version, db_name, user = cursor.fetchone()
            
            # Get connection info
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active'")
            active_connections = cursor.fetchone()[0]
            
            cursor.close()
            
            return {
                "authenticated": self._authenticated,
                "version": version,
                "database": db_name,
                "user": user,
                "active_connections": active_connections,
                "max_connections": self.max_connections
            }
            
        except Exception as e:
            return {"error": str(e)}
