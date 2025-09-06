"""
Simple Connection Manager for Windows Job Scheduler
Provides compatibility layer for database connections
"""

import os
import pyodbc
from pathlib import Path
from typing import Dict, List, Optional, Any
from utils.logger import get_logger

class SimpleConnectionManager:
    """Simple connection manager for database operations"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.connections_cache = {}
        
        # Default system connection configuration
        self.system_config = {
            'server_name': os.getenv('DB_SERVER', 'SUMEETGILL7E47\\MSSQLSERVER01'),
            'database_name': os.getenv('DB_DATABASE', 'sreutil'),
            'trusted_connection': os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true',
            'driver': os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
            'port': int(os.getenv('DB_PORT', '1433')),
            'connection_timeout': int(os.getenv('DB_CONNECTION_TIMEOUT', '30')),
            'command_timeout': int(os.getenv('DB_COMMAND_TIMEOUT', '300')),
            'encrypt': os.getenv('DB_ENCRYPT', 'false').lower() == 'true',
            'trust_server_certificate': os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
        }
    
    def _create_new_connection(self, connection_name: str = "system") -> Optional[pyodbc.Connection]:
        """Create a new database connection"""
        try:
            config = self.system_config
            
            # Build connection string
            if config['trusted_connection']:
                # Windows Authentication
                connection_string = (
                    f"DRIVER={{{config['driver']}}};"
                    f"SERVER={config['server_name']};"
                    f"DATABASE={config['database_name']};"
                    f"Trusted_Connection=yes;"
                )
            else:
                # SQL Server Authentication
                username = os.getenv('DB_USERNAME', '')
                password = os.getenv('DB_PASSWORD', '')
                connection_string = (
                    f"DRIVER={{{config['driver']}}};"
                    f"SERVER={config['server_name']};"
                    f"DATABASE={config['database_name']};"
                    f"UID={username};"
                    f"PWD={password};"
                )
            
            # Add optional parameters
            if config['encrypt']:
                connection_string += "Encrypt=yes;"
            
            if config['trust_server_certificate']:
                connection_string += "TrustServerCertificate=yes;"
            
            # Create connection
            connection = pyodbc.connect(
                connection_string,
                timeout=config['connection_timeout']
            )
            
            # Set command timeout
            connection.timeout = config['command_timeout']
            
            self.logger.info(f"Database connection '{connection_name}' established successfully")
            return connection
            
        except Exception as e:
            self.logger.error(f"Failed to create database connection '{connection_name}': {str(e)}")
            return None
    
    def test_connection(self, connection_name: str = "system") -> Dict[str, Any]:
        """Test database connection"""
        try:
            connection = self._create_new_connection(connection_name)
            if connection:
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                cursor.close()
                connection.close()
                
                return {
                    'success': True,
                    'message': 'Database connection successful',
                    'test_result': result[0] if result else None
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to establish connection'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_connection(self, connection_name: str = "system") -> Optional[pyodbc.Connection]:
        """Get database connection"""
        return self._create_new_connection(connection_name)
    
    def execute_query(self, query: str, params: List = None, connection_name: str = "system") -> Dict[str, Any]:
        """Execute SQL query"""
        try:
            connection = self._create_new_connection(connection_name)
            if not connection:
                return {
                    'success': False,
                    'error': 'Failed to establish database connection'
                }
            
            cursor = connection.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Check if it's a SELECT query
            if query.strip().upper().startswith('SELECT'):
                columns = [column[0] for column in cursor.description] if cursor.description else []
                rows = cursor.fetchall()
                result = [dict(zip(columns, row)) for row in rows]
            else:
                result = {'rows_affected': cursor.rowcount}
                connection.commit()
            
            cursor.close()
            connection.close()
            
            return {
                'success': True,
                'result': result
            }
            
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_connections(self) -> List[Dict[str, Any]]:
        """Get all configured connections"""
        try:
            # Try to get connections from database
            result = self.execute_query("SELECT * FROM user_connections WHERE is_active = 1")
            
            if result['success']:
                connections = result['result']
                # Convert to expected format
                formatted_connections = []
                for conn in connections:
                    formatted_connections.append({
                        'name': conn.get('name', 'Unknown'),
                        'server_name': conn.get('server_name', ''),
                        'database_name': conn.get('database_name', ''),
                        'description': conn.get('description', ''),
                        'created_date': conn.get('created_date'),
                        'is_active': True
                    })
                return formatted_connections
            else:
                # Return system connection as fallback
                return [{
                    'name': 'System Connection',
                    'server_name': self.system_config['server_name'],
                    'database_name': self.system_config['database_name'],
                    'description': 'Default system database connection',
                    'created_date': None,
                    'is_active': True
                }]
                
        except Exception as e:
            self.logger.error(f"Failed to get connections: {str(e)}")
            # Return system connection as fallback
            return [{
                'name': 'System Connection',
                'server_name': self.system_config['server_name'],
                'database_name': self.system_config['database_name'],
                'description': 'Default system database connection',
                'created_date': None,
                'is_active': True
            }]

# Global instance
simple_connection_manager = SimpleConnectionManager()