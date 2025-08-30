"""
Simple Connection Manager for SQLAlchemy integration
Works with the existing routes that expect db_manager
"""

from database.sqlalchemy_models import get_db_session
from sqlalchemy import text
from utils.logger import get_logger

class SimpleConnectionManager:
    """Simple connection manager that uses SQLAlchemy to access user_connections table"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("[CONNECTION_MANAGER] Simple connection manager initialized")
    
    def _create_new_connection(self, connection_name):
        """Create a database session (mimics old connection pool interface)"""
        return get_db_session()
    
    def list_connections(self):
        """List all available connections from user_connections table"""
        try:
            with get_db_session() as session:
                result = session.execute(text("""
                    SELECT connection_id, name, server_name, database_name, 
                           trusted_connection, is_active
                    FROM user_connections 
                    WHERE is_active = 1
                    ORDER BY name
                """))
                
                connections = []
                for row in result:
                    connections.append({
                        'connection_id': row.connection_id,
                        'name': row.name,
                        'server_name': row.server_name,
                        'database_name': row.database_name,
                        'trusted_connection': bool(row.trusted_connection),
                        'is_active': bool(row.is_active)
                    })
                
                self.logger.info(f"[CONNECTION_MANAGER] Listed {len(connections)} connections")
                return connections
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error listing connections: {e}")
            return []
    
    def get_connection_info(self, connection_id):
        """Get detailed connection information"""
        try:
            with get_db_session() as session:
                result = session.execute(text("""
                    SELECT * FROM user_connections 
                    WHERE connection_id = :connection_id AND is_active = 1
                """), {'connection_id': connection_id})
                
                row = result.fetchone()
                if row:
                    return {
                        'connection_id': row.connection_id,
                        'name': row.name,
                        'server_name': row.server_name,
                        'port': row.port,
                        'database_name': row.database_name,
                        'trusted_connection': bool(row.trusted_connection),
                        'username': row.username,
                        'description': row.description,
                        'driver': row.driver,
                        'connection_timeout': row.connection_timeout,
                        'command_timeout': row.command_timeout,
                        'encrypt': bool(row.encrypt),
                        'trust_server_certificate': bool(row.trust_server_certificate),
                        'is_active': bool(row.is_active)
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error getting connection info: {e}")
            return None
    
    def create_custom_connection(self, connection_data=None, validate=True, **kwargs):
        """Create a new custom connection with validation"""
        try:
            # Handle both dict parameter and keyword arguments
            if connection_data is None:
                connection_data = kwargs
            else:
                # If both provided, merge them (kwargs take precedence)
                connection_data = {**connection_data, **kwargs}
            
            # Map route parameter names to database column names
            if 'server' in connection_data and 'server_name' not in connection_data:
                connection_data['server_name'] = connection_data['server']
            if 'database' in connection_data and 'database_name' not in connection_data:
                connection_data['database_name'] = connection_data['database']
            
            # Standard validation before saving (can be disabled for testing)
            if validate:
                self.logger.info(f"[CONNECTION_MANAGER] Validating connection before saving: {connection_data.get('name')}")
                validation_result = self.validate_connection_data(connection_data)
                
                if not validation_result['success']:
                    self.logger.error(f"[CONNECTION_MANAGER] Connection validation failed: {validation_result['error']}")
                    return {
                        'success': False,
                        'error': f"Connection validation failed: {validation_result['error']}",
                        'validation_details': validation_result
                    }
                else:
                    self.logger.info(f"[CONNECTION_MANAGER] Connection validation successful: {connection_data.get('name')} ({validation_result.get('response_time', 0)}ms)")
            
            # Generate connection_id if not provided
            if 'connection_id' not in connection_data:
                import uuid
                connection_data['connection_id'] = str(uuid.uuid4())
            
            with get_db_session() as session:
                session.execute(text("""
                    INSERT INTO user_connections (
                        connection_id, name, server_name, port, database_name,
                        trusted_connection, username, password, description,
                        driver, connection_timeout, command_timeout,
                        encrypt, trust_server_certificate, created_by
                    ) VALUES (:connection_id, :name, :server_name, :port, :database_name,
                             :trusted_connection, :username, :password, :description,
                             :driver, :connection_timeout, :command_timeout,
                             :encrypt, :trust_server_certificate, :created_by)
                """), {
                    'connection_id': connection_data.get('connection_id'),
                    'name': connection_data.get('name'),
                    'server_name': connection_data.get('server_name'),
                    'port': connection_data.get('port', 1433),
                    'database_name': connection_data.get('database_name'),
                    'trusted_connection': connection_data.get('trusted_connection', True),
                    'username': connection_data.get('username'),
                    'password': connection_data.get('password'),
                    'description': connection_data.get('description', ''),
                    'driver': connection_data.get('driver', 'ODBC Driver 17 for SQL Server'),
                    'connection_timeout': connection_data.get('connection_timeout', 30),
                    'command_timeout': connection_data.get('command_timeout', 300),
                    'encrypt': connection_data.get('encrypt', False),
                    'trust_server_certificate': connection_data.get('trust_server_certificate', True),
                    'created_by': 'web_ui'
                })
                session.commit()
                
                self.logger.info(f"[CONNECTION_MANAGER] Created connection: {connection_data.get('name')}")
                return {
                    'success': True,
                    'message': f"Connection '{connection_data.get('name')}' created successfully"
                }
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error creating connection: {e}")
            return {
                'success': False,
                'error': f'Error creating connection: {str(e)}'
            }
    
    def remove_connection(self, connection_id):
        """Remove a connection (mark as inactive)"""
        try:
            with get_db_session() as session:
                session.execute(text("""
                    UPDATE user_connections 
                    SET is_active = 0, modified_date = GETDATE()
                    WHERE connection_id = :connection_id
                """), {'connection_id': connection_id})
                session.commit()
                
                self.logger.info(f"[CONNECTION_MANAGER] Removed connection: {connection_id}")
                return {
                    'success': True,
                    'message': f"Connection {connection_id} removed successfully"
                }
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error removing connection: {e}")
            return {
                'success': False,
                'error': f'Error removing connection: {str(e)}'
            }
    
    def test_connection(self, connection_id):
        """Test a database connection by attempting to connect"""
        try:
            conn_info = self.get_connection_info(connection_id)
            if not conn_info:
                return {'success': False, 'error': 'Connection not found'}
            
            # Build connection string and test actual database connection
            return self._validate_connection_string(conn_info)
            
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error testing connection {connection_id}: {e}")
            return {'success': False, 'error': str(e)}
    
    def validate_connection_for_sql_job(self, connection_id):
        """Standard validation function for connections before SQL job execution"""
        try:
            self.logger.info(f"[CONNECTION_MANAGER] Validating connection for SQL job execution: {connection_id}")
            
            # Get connection info
            conn_info = self.get_connection_info(connection_id)
            if not conn_info:
                return {
                    'success': False,
                    'error': f'Connection {connection_id} not found or inactive',
                    'connection_id': connection_id
                }
            
            # Perform actual connection test
            validation_result = self._validate_connection_string(conn_info)
            
            # Add connection metadata to result
            validation_result['connection_id'] = connection_id
            validation_result['connection_name'] = conn_info.get('name')
            
            if validation_result['success']:
                self.logger.info(f"[CONNECTION_MANAGER] SQL job connection validation successful: {conn_info.get('name')} ({validation_result.get('response_time', 0)}ms)")
            else:
                self.logger.error(f"[CONNECTION_MANAGER] SQL job connection validation failed: {conn_info.get('name')} - {validation_result.get('error')}")
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error validating connection for SQL job: {e}")
            return {
                'success': False,
                'error': f'Connection validation error: {str(e)}',
                'connection_id': connection_id
            }
    
    def validate_connection_data(self, connection_data):
        """Validate connection data by testing the connection before saving"""
        try:
            # Create temporary connection info for validation
            temp_conn_info = {
                'server_name': connection_data.get('server_name') or connection_data.get('server'),
                'database_name': connection_data.get('database_name') or connection_data.get('database'),
                'port': connection_data.get('port', 1433),
                'driver': connection_data.get('driver', 'ODBC Driver 17 for SQL Server'),
                'trusted_connection': connection_data.get('trusted_connection', True),
                'username': connection_data.get('username'),
                'password': connection_data.get('password'),
                'connection_timeout': connection_data.get('connection_timeout', 30),
                'name': connection_data.get('name', 'Test Connection')
            }
            
            self.logger.info(f"[CONNECTION_MANAGER] Validating connection data for: {temp_conn_info.get('name')}")
            return self._validate_connection_string(temp_conn_info)
            
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error validating connection data: {e}")
            return {
                'success': False,
                'error': f'Validation error: {str(e)}'
            }
    
    def get_validated_connection_string(self, connection_id):
        """Get a validated connection string for SQL job execution"""
        try:
            # First validate the connection
            validation_result = self.validate_connection_for_sql_job(connection_id)
            
            if not validation_result['success']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'connection_id': connection_id
                }
            
            # Get connection info and build connection string
            conn_info = self.get_connection_info(connection_id)
            if not conn_info:
                return {
                    'success': False,
                    'error': f'Connection {connection_id} not found',
                    'connection_id': connection_id
                }
            
            connection_string = self._build_connection_string(conn_info)
            
            return {
                'success': True,
                'connection_string': connection_string,
                'connection_id': connection_id,
                'connection_name': conn_info.get('name'),
                'server': conn_info.get('server_name'),
                'database': conn_info.get('database_name'),
                'validation_time': validation_result.get('response_time', 0)
            }
            
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error getting validated connection string: {e}")
            return {
                'success': False,
                'error': f'Error getting connection string: {str(e)}',
                'connection_id': connection_id
            }
    
    def _build_connection_string(self, conn_info):
        """Build SQL Server connection string from connection info"""
        try:
            server = conn_info.get('server_name', '')
            database = conn_info.get('database_name', '')
            port = conn_info.get('port', 1433)
            driver = conn_info.get('driver', 'ODBC Driver 17 for SQL Server')
            trusted_connection = conn_info.get('trusted_connection', True)
            username = conn_info.get('username', '')
            password = conn_info.get('password', '')
            connection_timeout = conn_info.get('connection_timeout', 30)
            
            # Build connection string
            conn_str_parts = [
                f"DRIVER={{{driver}}}",
                f"SERVER={server}"
            ]
            
            # Add port if not default and not already in server string
            if port != 1433 and ',' not in server:
                conn_str_parts.append(f"PORT={port}")
            
            conn_str_parts.append(f"DATABASE={database}")
            
            if trusted_connection:
                conn_str_parts.append("Trusted_Connection=yes")
            else:
                if username:
                    conn_str_parts.append(f"UID={username}")
                if password:
                    conn_str_parts.append(f"PWD={password}")
            
            conn_str_parts.extend([
                f"Connection Timeout={connection_timeout}",
                "Encrypt=no",
                "TrustServerCertificate=yes"
            ])
            
            return ";".join(conn_str_parts)
            
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error building connection string: {e}")
            raise
    
    def _validate_connection_string(self, conn_info):
        """Validate connection by attempting to connect to the database"""
        import time
        start_time = time.time()
        
        try:
            import pyodbc
            
            conn_string = self._build_connection_string(conn_info)
            self.logger.info(f"[CONNECTION_MANAGER] Testing connection: {conn_info.get('name')}")
            
            # Attempt to connect to database
            with pyodbc.connect(conn_string) as conn:
                cursor = conn.cursor()
                # Simple test query
                cursor.execute("SELECT 1 as test_value")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    response_time = round((time.time() - start_time) * 1000, 2)  # milliseconds
                    self.logger.info(f"[CONNECTION_MANAGER] Connection test successful: {conn_info.get('name')} ({response_time}ms)")
                    return {
                        'success': True,
                        'message': f"Connection '{conn_info['name']}' is working properly",
                        'response_time': response_time,
                        'server': conn_info.get('server_name'),
                        'database': conn_info.get('database_name')
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Connection test query failed'
                    }
                    
        except Exception as e:
            response_time = round((time.time() - start_time) * 1000, 2)
            error_msg = str(e)
            self.logger.error(f"[CONNECTION_MANAGER] Connection test failed for {conn_info.get('name')}: {error_msg}")
            
            return {
                'success': False,
                'error': error_msg,
                'response_time': response_time,
                'server': conn_info.get('server_name'),
                'database': conn_info.get('database_name')
            }

# Create global instance
simple_connection_manager = SimpleConnectionManager()
