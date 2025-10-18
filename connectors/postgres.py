"""
PostgreSQL connector for Enterprise AI Agent Framework.

Provides PostgreSQL database integration with insert and update actions.
Supports connection string authentication and basic error handling.
"""

import json
from typing import Dict, Any, List, Optional, Union
from .base import BaseConnector, AuthenticationError, ActionError


class PostgresConnector(BaseConnector):
    """
    PostgreSQL connector for database operations.
    
    Supports connection string authentication and provides actions for
    inserting and updating data in PostgreSQL databases.
    """
    
    CONNECTOR_NAME = "postgres"
    VERSION = "1.0.0"
    DESCRIPTION = "PostgreSQL connector for database operations"
    
    def __init__(self, tenant_id: Optional[str] = None, **kwargs):
        """
        Initialize the Postgres connector.
        
        Args:
            tenant_id (Optional[str]): Tenant identifier
            **kwargs: Additional configuration
        """
        super().__init__(
            name=self.CONNECTOR_NAME,
            version=self.VERSION,
            tenant_id=tenant_id,
            metadata={
                'service': 'postgresql',
                'driver': 'psycopg2',
                'operations': ['INSERT', 'UPDATE', 'SELECT', 'DELETE']
            }
        )
        self._connection = None
        self._connection_params = None
    
    def authenticate(self, credentials: Dict[str, Any]) -> bool:
        """
        Authenticate with PostgreSQL database.
        
        Args:
            credentials (Dict[str, Any]): Authentication credentials
                Expected keys: 'host', 'port', 'database', 'username', 'password'
                OR 'connection_string' for direct connection string
        
        Returns:
            bool: True if authentication successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Check for connection string first
            if 'connection_string' in credentials:
                connection_string = credentials['connection_string']
                if not isinstance(connection_string, str) or not connection_string.strip():
                    raise AuthenticationError("Invalid connection_string")
                
                self._connection_params = {'connection_string': connection_string}
            
            else:
                # Validate individual connection parameters
                required_fields = ['host', 'port', 'database', 'username', 'password']
                for field in required_fields:
                    if field not in credentials:
                        raise AuthenticationError(f"Missing required credential: {field}")
                
                # Validate parameter types and values
                host = credentials['host']
                if not isinstance(host, str) or not host.strip():
                    raise AuthenticationError("Invalid host")
                
                port = credentials['port']
                if not isinstance(port, int) or port <= 0 or port > 65535:
                    raise AuthenticationError("Invalid port")
                
                database = credentials['database']
                if not isinstance(database, str) or not database.strip():
                    raise AuthenticationError("Invalid database")
                
                username = credentials['username']
                if not isinstance(username, str) or not username.strip():
                    raise AuthenticationError("Invalid username")
                
                password = credentials['password']
                if not isinstance(password, str):
                    raise AuthenticationError("Invalid password")
                
                self._connection_params = {
                    'host': host,
                    'port': port,
                    'database': database,
                    'username': username,
                    'password': password
                }
            
            # In a real implementation, you would establish the database connection
            # For this example, we'll simulate the connection process
            
            # Simulate connection establishment
            # In real implementation: psycopg2.connect(**connection_params)
            self._connection = "postgres_connection_instance"
            
            # Test the connection
            # In real implementation: cursor = connection.cursor(); cursor.execute("SELECT 1"); cursor.close()
            connection_test = True
            
            if not connection_test:
                raise AuthenticationError("Database connection test failed")
            
            self.status = self.status.CONNECTED
            self.update_activity()
            
            return True
            
        except Exception as e:
            self.status = self.status.ERROR
            raise AuthenticationError(f"PostgreSQL authentication failed: {str(e)}")
    
    def execute_action(self, action_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a PostgreSQL action.
        
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
            raise AuthenticationError("Not authenticated with PostgreSQL")
        
        if not self.validate_params(action_name, params):
            raise ActionError(f"Invalid parameters for action '{action_name}'")
        
        try:
            self.update_activity()
            
            if action_name == "insert":
                return self._insert_data(params)
            elif action_name == "update":
                return self._update_data(params)
            elif action_name == "select":
                return self._select_data(params)
            elif action_name == "delete":
                return self._delete_data(params)
            else:
                raise ActionError(f"Unknown action: {action_name}")
                
        except Exception as e:
            raise ActionError(f"Failed to execute action '{action_name}': {str(e)}")
    
    def list_actions(self) -> List[Dict[str, Any]]:
        """
        List all available PostgreSQL actions.
        
        Returns:
            List[Dict[str, Any]]: List of available actions
        """
        return [
            {
                'name': 'insert',
                'description': 'Insert data into a table',
                'required_params': ['table', 'data'],
                'optional_params': ['returning'],
                'example': {
                    'table': 'users',
                    'data': {'name': 'John Doe', 'email': 'john@example.com'},
                    'returning': 'id'
                }
            },
            {
                'name': 'update',
                'description': 'Update data in a table',
                'required_params': ['table', 'data', 'where'],
                'optional_params': ['returning'],
                'example': {
                    'table': 'users',
                    'data': {'name': 'Jane Doe'},
                    'where': {'id': 1},
                    'returning': 'id'
                }
            },
            {
                'name': 'select',
                'description': 'Select data from a table',
                'required_params': ['table'],
                'optional_params': ['columns', 'where', 'limit', 'order_by'],
                'example': {
                    'table': 'users',
                    'columns': ['id', 'name', 'email'],
                    'where': {'active': True},
                    'limit': 10
                }
            },
            {
                'name': 'delete',
                'description': 'Delete data from a table',
                'required_params': ['table', 'where'],
                'optional_params': ['returning'],
                'example': {
                    'table': 'users',
                    'where': {'id': 1},
                    'returning': 'id'
                }
            }
        ]
    
    def _insert_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert data into a table.
        
        Args:
            params (Dict[str, Any]): Insert parameters
            
        Returns:
            Dict[str, Any]: Insert result
        """
        table = params['table']
        data = params['data']
        returning = params.get('returning')
        
        # Validate table name
        if not self._is_valid_table_name(table):
            raise ActionError(f"Invalid table name: {table}")
        
        # Validate data
        if not isinstance(data, dict) or not data:
            raise ActionError("Data must be a non-empty dictionary")
        
        # Validate column names
        for column in data.keys():
            if not self._is_valid_column_name(column):
                raise ActionError(f"Invalid column name: {column}")
        
        # Build SQL query
        columns = list(data.keys())
        values = list(data.values())
        placeholders = [f"${i+1}" for i in range(len(values))]
        
        sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
        
        if returning:
            sql += f" RETURNING {returning}"
        
        # In a real implementation, you would execute the SQL
        # For this example, we'll simulate the insert operation
        
        # Simulate SQL execution
        # In real implementation: cursor.execute(sql, values); result = cursor.fetchone() if returning else None
        insert_result = {
            'success': True,
            'rows_affected': 1,
            'returned_value': {'id': 123} if returning else None
        }
        
        return {
            'success': True,
            'table': table,
            'rows_inserted': insert_result['rows_affected'],
            'returned_value': insert_result['returned_value'],
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _update_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update data in a table.
        
        Args:
            params (Dict[str, Any]): Update parameters
            
        Returns:
            Dict[str, Any]: Update result
        """
        table = params['table']
        data = params['data']
        where = params['where']
        returning = params.get('returning')
        
        # Validate table name
        if not self._is_valid_table_name(table):
            raise ActionError(f"Invalid table name: {table}")
        
        # Validate data
        if not isinstance(data, dict) or not data:
            raise ActionError("Data must be a non-empty dictionary")
        
        # Validate where clause
        if not isinstance(where, dict) or not where:
            raise ActionError("Where clause must be a non-empty dictionary")
        
        # Validate column names
        for column in data.keys():
            if not self._is_valid_column_name(column):
                raise ActionError(f"Invalid column name: {column}")
        
        for column in where.keys():
            if not self._is_valid_column_name(column):
                raise ActionError(f"Invalid where column name: {column}")
        
        # Build SQL query
        set_clauses = [f"{col} = ${i+1}" for i, col in enumerate(data.keys())]
        where_clauses = [f"{col} = ${i+len(data)+1}" for i, col in enumerate(where.keys())]
        
        sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)}"
        
        if returning:
            sql += f" RETURNING {returning}"
        
        values = list(data.values()) + list(where.values())
        
        # In a real implementation, you would execute the SQL
        # For this example, we'll simulate the update operation
        
        # Simulate SQL execution
        # In real implementation: cursor.execute(sql, values); result = cursor.fetchone() if returning else None
        update_result = {
            'success': True,
            'rows_affected': 1,
            'returned_value': {'id': 123} if returning else None
        }
        
        return {
            'success': True,
            'table': table,
            'rows_updated': update_result['rows_affected'],
            'returned_value': update_result['returned_value'],
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _select_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select data from a table.
        
        Args:
            params (Dict[str, Any]): Select parameters
            
        Returns:
            Dict[str, Any]: Select result
        """
        table = params['table']
        columns = params.get('columns', ['*'])
        where = params.get('where', {})
        limit = params.get('limit')
        order_by = params.get('order_by')
        
        # Validate table name
        if not self._is_valid_table_name(table):
            raise ActionError(f"Invalid table name: {table}")
        
        # Validate columns
        if isinstance(columns, list):
            for column in columns:
                if column != '*' and not self._is_valid_column_name(column):
                    raise ActionError(f"Invalid column name: {column}")
        
        # Build SQL query
        columns_str = ', '.join(columns) if isinstance(columns, list) else columns
        sql = f"SELECT {columns_str} FROM {table}"
        
        values = []
        if where:
            where_clauses = [f"{col} = ${i+1}" for i, col in enumerate(where.keys())]
            sql += f" WHERE {' AND '.join(where_clauses)}"
            values.extend(where.values())
        
        if order_by:
            sql += f" ORDER BY {order_by}"
        
        if limit:
            sql += f" LIMIT {limit}"
        
        # In a real implementation, you would execute the SQL
        # For this example, we'll simulate the select operation
        
        # Simulate SQL execution
        # In real implementation: cursor.execute(sql, values); results = cursor.fetchall()
        select_result = {
            'success': True,
            'rows': [
                {'id': 1, 'name': 'John Doe', 'email': 'john@example.com'},
                {'id': 2, 'name': 'Jane Doe', 'email': 'jane@example.com'}
            ]
        }
        
        return {
            'success': True,
            'table': table,
            'rows': select_result['rows'],
            'row_count': len(select_result['rows']),
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _delete_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete data from a table.
        
        Args:
            params (Dict[str, Any]): Delete parameters
            
        Returns:
            Dict[str, Any]: Delete result
        """
        table = params['table']
        where = params['where']
        returning = params.get('returning')
        
        # Validate table name
        if not self._is_valid_table_name(table):
            raise ActionError(f"Invalid table name: {table}")
        
        # Validate where clause
        if not isinstance(where, dict) or not where:
            raise ActionError("Where clause must be a non-empty dictionary")
        
        # Validate where column names
        for column in where.keys():
            if not self._is_valid_column_name(column):
                raise ActionError(f"Invalid where column name: {column}")
        
        # Build SQL query
        where_clauses = [f"{col} = ${i+1}" for i, col in enumerate(where.keys())]
        sql = f"DELETE FROM {table} WHERE {' AND '.join(where_clauses)}"
        
        if returning:
            sql += f" RETURNING {returning}"
        
        values = list(where.values())
        
        # In a real implementation, you would execute the SQL
        # For this example, we'll simulate the delete operation
        
        # Simulate SQL execution
        # In real implementation: cursor.execute(sql, values); result = cursor.fetchone() if returning else None
        delete_result = {
            'success': True,
            'rows_affected': 1,
            'returned_value': {'id': 123} if returning else None
        }
        
        return {
            'success': True,
            'table': table,
            'rows_deleted': delete_result['rows_affected'],
            'returned_value': delete_result['returned_value'],
            'timestamp': self.last_activity.isoformat() if self.last_activity else None
        }
    
    def _is_valid_table_name(self, table_name: str) -> bool:
        """
        Validate PostgreSQL table name.
        
        Args:
            table_name (str): Table name to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(table_name, str) or not table_name.strip():
            return False
        
        # PostgreSQL table names can contain letters, digits, underscores, and dollar signs
        # Must start with a letter or underscore
        import re
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_$]*$'
        return re.match(pattern, table_name) is not None
    
    def _is_valid_column_name(self, column_name: str) -> bool:
        """
        Validate PostgreSQL column name.
        
        Args:
            column_name (str): Column name to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(column_name, str) or not column_name.strip():
            return False
        
        # PostgreSQL column names follow the same rules as table names
        return self._is_valid_table_name(column_name)
    
    def validate_params(self, action_name: str, params: Dict[str, Any]) -> bool:
        """
        Validate parameters for PostgreSQL actions.
        
        Args:
            action_name (str): Name of the action
            params (Dict[str, Any]): Parameters to validate
            
        Returns:
            bool: True if parameters are valid, False otherwise
        """
        if not super().validate_params(action_name, params):
            return False
        
        if action_name in ["insert", "update", "delete"]:
            # Validate table name
            if 'table' not in params or not self._is_valid_table_name(params['table']):
                return False
        
        if action_name in ["insert", "update"]:
            # Validate data
            if 'data' not in params or not isinstance(params['data'], dict):
                return False
        
        if action_name in ["update", "delete"]:
            # Validate where clause
            if 'where' not in params or not isinstance(params['where'], dict):
                return False
        
        if action_name == "select":
            # Validate table name
            if 'table' not in params or not self._is_valid_table_name(params['table']):
                return False
            
            # Validate columns if provided
            if 'columns' in params:
                columns = params['columns']
                if not isinstance(columns, (list, str)):
                    return False
        
        return True
    
    def disconnect(self) -> None:
        """Disconnect from PostgreSQL database."""
        super().disconnect()
        self._connection = None
        self._connection_params = None
