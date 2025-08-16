"""
Database Connection Manager for Windows SQL Server
"""

# Import pyodbc with error handling
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None

import yaml
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, List
import time
import os
import socket
from datetime import datetime
from threading import Lock
from utils.logger import get_logger


class DatabaseConnectionManager:
    """Manages SQL Server database connections for Windows"""
    
    def __init__(self, config_file: str = "config/database_config.yaml"):
        self.config_file = config_file
        self.logger = get_logger(__name__)  # Initialize logger first
        
        if not HAS_PYODBC:
            self.logger.warning("[INIT] pyodbc not available - DatabaseConnectionManager will operate in mock mode")
            self.config = {}
            self._connection_lock = Lock()
            self._pool_lock = Lock()
            self._connection_pool = {}
            self._pool_config = {'max_connections': 50, 'connection_lifetime': 3600}
            self._current_user = os.getenv('USERNAME', os.getenv('USER', 'system'))
            self._host_name = socket.gethostname()
            return
        
        self.config = self._load_config()
        self._connection_lock = Lock()
        self._pool_lock = Lock()  # Add pool lock for cleanup operations
        self._connection_pool = {}
        
        # Initialize pool configuration
        self._pool_config = {
            'max_connections': 50,
            'connection_lifetime': 3600  # 1 hour in seconds
        }
        
        # Initialize audit trail context
        self._current_user = os.getenv('USERNAME', os.getenv('USER', 'system'))
        self._host_name = socket.gethostname()
        
        # Initialize system database tables
        self._init_system_database()
        
        self.logger.info(f"[INIT] Database Connection Manager initialized by {self._current_user}@{self._host_name}")
        self.logger.info(f"[INIT] Connection pool configured: max_connections={self._pool_config['max_connections']}, connection_lifetime={self._pool_config['connection_lifetime']}s")
    
    def _init_system_database(self):
        """Initialize system database tables for storing user connections"""
        try:
            self.logger.info("Initializing system database tables...")
            
            # Get system connection directly (avoid recursion during initialization)
            system_connection = self._create_new_connection("system")
            if not system_connection:
                self.logger.error("Could not connect to system database for initialization")
                self.logger.error("Please check your system database connection in config/database_config.yaml")
                return
            
            cursor = system_connection.cursor()
            
            # Create user connections table
            create_table_sql = """
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='user_connections' AND xtype='U')
            CREATE TABLE user_connections (
                connection_id NVARCHAR(100) PRIMARY KEY,
                name NVARCHAR(255) NOT NULL,
                server_name NVARCHAR(255) NOT NULL,
                port INT DEFAULT 1433,
                database_name NVARCHAR(255) NOT NULL,
                trusted_connection BIT DEFAULT 1,
                username NVARCHAR(255) NULL,
                password NVARCHAR(500) NULL,
                description NVARCHAR(1000) NULL,
                driver NVARCHAR(255) DEFAULT '{ODBC Driver 17 for SQL Server}',
                connection_timeout INT DEFAULT 30,
                command_timeout INT DEFAULT 300,
                encrypt BIT DEFAULT 0,
                trust_server_certificate BIT DEFAULT 1,
                created_date DATETIME DEFAULT GETDATE(),
                modified_date DATETIME DEFAULT GETDATE(),
                created_by NVARCHAR(255) DEFAULT SYSTEM_USER,
                is_active BIT DEFAULT 1,
                INDEX IX_user_connections_name (name),
                INDEX IX_user_connections_active (is_active)
            )
            """
            
            cursor.execute(create_table_sql)
            system_connection.commit()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close
            
            self.logger.info("System database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize system database: {e}")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load database configuration from YAML file"""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            if hasattr(self, 'logger'):
                self.logger.warning(f"Database config file not found: {config_path}")
            return self._get_default_config()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if config is None:
                    config = {}
                
                # Ensure databases section exists
                if 'databases' not in config or config['databases'] is None:
                    config['databases'] = {}
                
                # Ensure boolean values are properly converted
                for conn_name, conn_config in config.get('databases', {}).items():
                    if isinstance(conn_config, dict):
                        # Convert string boolean values to actual booleans
                        if 'trusted_connection' in conn_config:
                            if isinstance(conn_config['trusted_connection'], str):
                                conn_config['trusted_connection'] = conn_config['trusted_connection'].lower() == 'true'
                
                if hasattr(self, 'logger'):
                    self.logger.info(f"Loaded database configuration from {config_path}")
                return config
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"Failed to load database config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default database configuration"""
        return {
            'databases': {},  # Empty - only user-added connections
            'connection_pool': {
                'max_connections': 10,
                'min_connections': 2,
                'connection_lifetime': 3600
            },
            'retry_settings': {
                'max_retries': 3,
                'retry_delay': 5,
                'backoff_factor': 2
            }
        }
    
    def get_connection_string(self, connection_name: str = "default") -> str:
        """Build connection string for specified connection"""
        # For system connection, always use config file to avoid recursion
        if connection_name == "system":
            db_config = self.config.get('databases', {}).get(connection_name)
        else:
            # First try to get from database
            db_config = self._get_connection_from_database(connection_name)
            
            if not db_config:
                # Fall back to config file
                db_config = self.config.get('databases', {}).get(connection_name)
        
        if not db_config:
            raise ValueError(f"Database connection '{connection_name}' not found in configuration")
        
        # Build connection string components
        components = []
        
        # Driver
        driver = db_config.get('driver', '{ODBC Driver 17 for SQL Server}')
        components.append(f"DRIVER={driver}")
        
        # Server with optional port
        server = db_config.get('server', 'localhost')
        port = db_config.get('port')
        
        # Handle named instances and custom ports  
        if '\\' in server and port and port != 1433:
            # Named instance with custom port - add port after server name
            components.append(f"SERVER={server},{port}")
            pass  # Removed excessive debug logging
        elif '\\' in server:
            # Named instance - don't add port for default
            components.append(f"SERVER={server}")
        elif port and port != 1433:
            # Custom port
            components.append(f"SERVER={server},{port}")
        else:
            # Default port or no port specified
            components.append(f"SERVER={server}")
        
        # Database
        database = db_config.get('database')
        if database:
            components.append(f"DATABASE={database}")
        
        # Authentication
        if db_config.get('trusted_connection', True):
            components.append("Trusted_Connection=yes")
        else:
            username = db_config.get('username')
            password = db_config.get('password')
            if username and password:
                components.append(f"UID={username}")
                components.append(f"PWD={password}")
            else:
                raise ValueError(f"Username and password required for SQL authentication on connection '{connection_name}'")
        
        # Timeouts
        connection_timeout = db_config.get('connection_timeout', 30)
        components.append(f"Connection Timeout={connection_timeout}")
        
        command_timeout = db_config.get('command_timeout', 300)
        components.append(f"Command Timeout={command_timeout}")
        
        # Additional security options
        components.append("MARS_Connection=yes")  # Multiple Active Result Sets
        
        # Azure SQL specific settings
        if db_config.get('encrypt', False):
            components.append("Encrypt=yes")
        else:
            components.append("Encrypt=no")
            
        if db_config.get('trust_server_certificate', True):
            components.append("TrustServerCertificate=yes")
        else:
            components.append("TrustServerCertificate=no")
        
        connection_string = ";".join(components)
        
        # Log the full connection string for debugging (mask password)
        debug_string = connection_string
        if 'PWD=' in debug_string:
            import re
            debug_string = re.sub(r'PWD=[^;]*', 'PWD=***', debug_string)
        
        self.logger.debug(f"Built connection string for '{connection_name}': {debug_string}")  # Changed from info to debug
        
        return connection_string
    
    def get_connection(self, connection_name: str = "default"):
        """Get database connection from pool with proper lifecycle management"""
        if not HAS_PYODBC:
            self.logger.warning(f"[MOCK] get_connection called for '{connection_name}' - pyodbc not available, returning None")
            return None
        
        # Periodically cleanup stale connections (every 10th call)
        import random
        if random.randint(1, 10) == 1:
            self.cleanup_pool()
        
        with self._connection_lock:
            # Check if we have a valid pooled connection
            if connection_name in self._connection_pool:
                pool_entry = self._connection_pool[connection_name]
                
                if self._is_connection_valid(pool_entry):
                    # Update last used time and use count
                    pool_entry['last_used'] = datetime.now()
                    pool_entry['use_count'] += 1
                    
                    self.logger.debug(f"[POOL] Returning existing connection '{connection_name}' (uses: {pool_entry['use_count']})")
                    return pool_entry['connection']
                else:
                    # Connection is invalid, remove it and create a new one
                    self.logger.info(f"[POOL] Removing invalid connection '{connection_name}' from pool")
                    self._close_pool_entry(connection_name)
            
            # Check pool capacity
            if len(self._connection_pool) >= self._pool_config['max_connections']:
                self.logger.warning(f"[POOL] Connection pool at capacity ({len(self._connection_pool)}/{self._pool_config['max_connections']})")
                # Could implement LRU eviction here, but for now just create new connection
                return self._create_new_connection(connection_name)
            
            # Create new pooled connection
            connection = self._create_new_connection(connection_name)
            
            if connection:
                # Add to pool
                pool_entry = {
                    'connection': connection,
                    'created': datetime.now(),
                    'last_used': datetime.now(),
                    'use_count': 1
                }
                
                self._connection_pool[connection_name] = pool_entry
                self.logger.info(f"[POOL] Added new connection '{connection_name}' to pool (pool size: {len(self._connection_pool)})")
                
                return connection
            else:
                self.logger.error(f"[POOL] Failed to create connection '{connection_name}'")
                return None
    
    def _create_new_connection(self, connection_name: str):
        """Create a new database connection with retry logic"""
        retry_settings = self.config.get('retry_settings', {})
        max_retries = retry_settings.get('max_retries', 3)
        retry_delay = retry_settings.get('retry_delay', 5)
        backoff_factor = retry_settings.get('backoff_factor', 2)
        
        connection_string = self.get_connection_string(connection_name)
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"[POOL] Attempting new database connection '{connection_name}' (attempt {attempt + 1})")
                
                connection = pyodbc.connect(connection_string)
                
                # Test connection
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                # Note: Don't close connection here - it will be managed by the pool
                
                self.logger.debug(f"[POOL] Successfully created connection '{connection_name}'")
                return connection
                
            except pyodbc.Error as e:
                error_msg = f"Database connection failed (attempt {attempt + 1}): {str(e)}"
                
                if attempt < max_retries:
                    self.logger.warning(f"[POOL] {error_msg}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= backoff_factor  # Exponential backoff
                else:
                    self.logger.error(f"[POOL] {error_msg}. Max retries exceeded.")
                    
            except Exception as e:
                self.logger.error(f"[POOL] Unexpected error connecting to database: {e}")
                break
        
        return None
    
    def _is_connection_valid(self, pool_entry: Dict) -> bool:
        """Check if a pooled connection is still valid"""
        try:
            connection = pool_entry['connection']
            
            # Check if connection is already closed
            if hasattr(connection, 'closed') and connection.closed:
                self.logger.debug(f"[POOL] Connection is closed")
                return False
            
            # Check if connection is expired
            age = datetime.now() - pool_entry['created']
            if age.total_seconds() > self._pool_config['connection_lifetime']:
                self.logger.debug(f"[POOL] Connection expired (age: {age.total_seconds()}s)")
                return False
            
            # Test connection with a simple query
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return True
            
        except Exception as e:
            self.logger.debug(f"[POOL] Connection validation failed: {e}")
            return False
    
    def _close_pool_entry(self, connection_name: str):
        """Close and remove a connection from the pool safely"""
        if connection_name in self._connection_pool:
            try:
                pool_entry = self._connection_pool[connection_name]
                connection = pool_entry['connection']
                
                # Check if connection is still open before trying to close
                if hasattr(connection, 'closed') and connection.closed:
                    self.logger.debug(f"[POOL] Connection '{connection_name}' already closed")
                else:
                    # Try to close the connection safely
                    try:
                        connection.close()
                        self.logger.debug(f"[POOL] Closed connection '{connection_name}'")
                    except Exception as close_error:
                        # Connection might already be closed or in an invalid state
                        self.logger.debug(f"[POOL] Connection '{connection_name}' could not be closed gracefully: {close_error}")
                        
            except Exception as e:
                self.logger.warning(f"[POOL] Error accessing connection '{connection_name}' for closure: {e}")
            finally:
                # Always remove from pool regardless of close success
                del self._connection_pool[connection_name]
    
    def cleanup_pool(self):
        """Clean up expired connections from the pool safely"""
        try:
            with self._pool_lock:
                expired_connections = []
                current_time = datetime.now()
                
                # Only cleanup connections that are truly expired and not recently used
                for conn_name, pool_entry in self._connection_pool.items():
                    try:
                        # Skip recently used connections (within last 5 minutes)
                        time_since_use = current_time - pool_entry['last_used']
                        if time_since_use.total_seconds() < 300:  # 5 minutes
                            continue
                            
                        # Only cleanup if connection is invalid
                        if not self._is_connection_valid(pool_entry):
                            expired_connections.append(conn_name)
                    except Exception as e:
                        self.logger.debug(f"[POOL] Error checking connection '{conn_name}' during cleanup: {e}")
                        # Add to cleanup list if we can't even check it
                        expired_connections.append(conn_name)
                
                # Clean up expired connections
                cleaned_count = 0
                for conn_name in expired_connections:
                    try:
                        self.logger.debug(f"[POOL] Cleaning up expired connection '{conn_name}'")
                        self._close_pool_entry(conn_name)
                        cleaned_count += 1
                    except Exception as e:
                        self.logger.warning(f"[POOL] Error during cleanup of connection '{conn_name}': {e}")
                
                if cleaned_count > 0:
                    self.logger.info(f"[POOL] Cleaned up {cleaned_count} expired connections")
                    
        except Exception as e:
            self.logger.error(f"[POOL] Error during pool cleanup: {e}")
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics"""
        with self._pool_lock:
            active_connections = 0
            idle_connections = 0
            
            # Count active vs idle connections
            for pool_entry in self._connection_pool.values():
                idle_time = datetime.now() - pool_entry['last_used']
                if idle_time.total_seconds() < 300:  # Active if used in last 5 minutes
                    active_connections += 1
                else:
                    idle_connections += 1
            
            stats = {
                'total_connections': len(self._connection_pool),
                'active_connections': active_connections,
                'idle_connections': idle_connections,
                'max_connections': self._pool_config['max_connections'],
                'health': 'healthy' if len(self._connection_pool) < self._pool_config['max_connections'] else 'at_capacity',
                'connections': {}
            }
            
            for conn_name, pool_entry in self._connection_pool.items():
                age = datetime.now() - pool_entry['created']
                idle_time = datetime.now() - pool_entry['last_used']
                
                stats['connections'][conn_name] = {
                    'use_count': pool_entry['use_count'],
                    'age_seconds': int(age.total_seconds()),
                    'idle_seconds': int(idle_time.total_seconds()),
                    'created': pool_entry['created'].isoformat(),
                    'last_used': pool_entry['last_used'].isoformat()
                }
            
            return stats
    
    def return_connection(self, connection_name: str, connection):
        """Return a connection to the pool (for future use, currently connections auto-managed)"""
        # For now, we keep connections in pool automatically
        # In the future, could implement explicit return-to-pool mechanism
        # Parameters kept for future API compatibility
        _ = connection_name, connection  # Suppress unused parameter warnings
    
    def close_all_connections(self):
        """Close all pooled connections gracefully"""
        with self._pool_lock:
            connection_names = list(self._connection_pool.keys())
            closed_count = 0
            
            for conn_name in connection_names:
                try:
                    self._close_pool_entry(conn_name)
                    closed_count += 1
                except Exception as e:
                    self.logger.warning(f"[POOL] Error closing connection '{conn_name}' during shutdown: {e}")
            
            self.logger.info(f"[POOL] Gracefully closed {closed_count}/{len(connection_names)} pooled connections")
    
    def _test_connection_direct(self, server: str, database: str, port: int = 1433,
                              auth_type: str = "windows", username: str = None, 
                              password: str = None) -> Dict[str, Any]:
        """Test database connection directly without using saved configuration"""
        start_time = time.time()
        connection_detail = f"{server}:{port}/{database}"
        
        self.logger.info(f"[DIRECT_TEST] Starting connection test for {connection_detail} using {auth_type} authentication")
        
        try:
            # Import required modules
            import pyodbc
            
            # Build connection string components
            components = []
            components.append("DRIVER={ODBC Driver 17 for SQL Server}")
            
            # Handle server and port
            if '\\' in server and port and port != 1433:
                # Named instance with custom port - try both formats
                # Some named instances require explicit port specification
                components.append(f"SERVER={server},{port}")
                self.logger.debug(f"[DIRECT_TEST] Using named instance with explicit port: {server},{port}")
            elif '\\' in server:
                # Named instance - try without port first
                components.append(f"SERVER={server}")
                self.logger.debug(f"[DIRECT_TEST] Using named instance: {server}")
            elif port and port != 1433:
                # Standard server with custom port
                components.append(f"SERVER={server},{port}")
                self.logger.debug(f"[DIRECT_TEST] Using server with custom port: {server},{port}")
            else:
                # Default server and port
                components.append(f"SERVER={server}")
                self.logger.debug(f"[DIRECT_TEST] Using default server: {server}")
            
            components.append(f"DATABASE={database}")
            
            # Authentication
            if auth_type.lower() == 'windows':
                components.append("Trusted_Connection=yes")
                self.logger.debug(f"[DIRECT_TEST] Using Windows authentication")
            else:
                if not username or not password:
                    self.logger.error(f"[DIRECT_TEST] Username and password required for SQL authentication on {connection_detail}")
                    return {
                        'success': False,
                        'error': 'Username and password required for SQL authentication',
                        'response_time': time.time() - start_time
                    }
                components.append(f"UID={username}")
                components.append(f"PWD={password}")
                self.logger.debug(f"[DIRECT_TEST] Using SQL Server authentication with username: {username}")
                # Don't add Trusted_Connection=yes for SQL auth
            
            # Connection settings
            components.extend([
                "Connection Timeout=10",
                "Command Timeout=30",
                "Encrypt=no",
                "TrustServerCertificate=yes"
            ])
            
            connection_string = ";".join(components)
            
            # Log the full connection string for debugging (without password)
            debug_string = connection_string.replace(password, "***") if password else connection_string
            self.logger.info(f"[DIRECT_TEST] Connection string for {connection_detail}: {debug_string}")
            
            # Test the connection
            self.logger.info(f"[DIRECT_TEST] Attempting to connect to {connection_detail}...")
            
            connection = pyodbc.connect(connection_string)
            self.logger.info(f"[DIRECT_TEST] Successfully established connection to {connection_detail}")
            
            # Execute test query
            self.logger.debug(f"[DIRECT_TEST] Executing test query on {connection_detail}")
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test, @@VERSION as version")
            result = cursor.fetchone()
            cursor.close()
            connection.close()  # This is OK here as it's a direct test, not using the pool
            
            response_time = time.time() - start_time
            
            self.logger.info(f"[DIRECT_TEST] Connection test completed successfully for {connection_detail} in {response_time:.2f}s")
            
            result_data = {
                'success': True,
                'message': 'Connection successful',
                'response_time': response_time,
                'server_info': {
                    'test_result': result[0] if result else None,
                    'version': result[1][:100] if result and len(result) > 1 else 'Unknown'
                }
            }
            
            self.logger.debug(f"[DIRECT_TEST] Server info for {connection_detail}: {result_data['server_info']}")
            return result_data
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            
            # Extract more user-friendly error message
            if "Login failed" in error_msg:
                friendly_error = "Login failed - check username and password"
                self.logger.error(f"[DIRECT_TEST] Authentication failed for {connection_detail}: {error_msg}")
            elif "Server does not exist" in error_msg:
                friendly_error = "Server not found - check server name and port"
                self.logger.error(f"[DIRECT_TEST] Server not found for {connection_detail}: {error_msg}")
            elif "Database" in error_msg and "does not exist" in error_msg:
                friendly_error = "Database not found - check database name"
                self.logger.error(f"[DIRECT_TEST] Database not found for {connection_detail}: {error_msg}")
            elif "timeout" in error_msg.lower():
                friendly_error = "Connection timeout - check server accessibility"
                self.logger.error(f"[DIRECT_TEST] Connection timeout for {connection_detail}: {error_msg}")
            else:
                friendly_error = error_msg
                self.logger.error(f"[DIRECT_TEST] Connection failed for {connection_detail}: {error_msg}")
            
            self.logger.error(f"[DIRECT_TEST] Test failed for {connection_detail} after {response_time:.2f}s")
            
            return {
                'success': False,
                'error': friendly_error,
                'response_time': response_time
            }

    def test_connection(self, connection_name: str = "default") -> Dict[str, Any]:
        """Test database connection"""
        start_time = time.time()
        
        self.logger.info(f"[CONNECTION_TEST] Starting test for saved connection '{connection_name}'")
        
        # Audit log the test attempt
        self._audit_log('TEST', connection_name, {
            'test_type': 'saved_connection'
        })
        
        try:
            # Get connection info for logging
            conn_info = self.get_connection_info(connection_name)
            if conn_info:
                server_detail = f"{conn_info.get('server')}:{conn_info.get('port', 1433)}/{conn_info.get('database')}"
                auth_type = "Windows" if conn_info.get('trusted_connection') else "SQL Server"
                self.logger.debug(f"[CONNECTION_TEST] Connection '{connection_name}' details: {server_detail} using {auth_type} auth")
            
            connection = self.get_connection(connection_name)
            
            if not connection:
                self.logger.error(f"[CONNECTION_TEST] Failed to establish connection for '{connection_name}'")
                self._audit_log('TEST_FAILED', connection_name, {
                    'error': 'Failed to establish connection',
                    'response_time': time.time() - start_time
                })
                return {
                    'success': False,
                    'connection_name': connection_name,
                    'error': 'Failed to establish connection',
                    'response_time': time.time() - start_time
                }
            
            self.logger.info(f"[CONNECTION_TEST] Successfully connected to '{connection_name}'")
            
            # Get server information
            cursor = connection.cursor()
            
            # Test query with server info
            test_queries = [
                "SELECT @@VERSION as server_version"
                #"SELECT @@SERVERNAME as server_name",
                #"SELECT DB_NAME() as database_name",
                #"SELECT SYSTEM_USER as system_user",
                #"SELECT GETDATE() as current_time"
            ]
            
            self.logger.debug(f"[CONNECTION_TEST] Executing {len(test_queries)} test queries on '{connection_name}'")
            
            server_info = {}
            for query in test_queries:
                try:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    if result:
                        column_name = cursor.description[0][0].lower()
                        server_info[column_name] = str(result[0]).strip()
                        self.logger.debug(f"[CONNECTION_TEST] Query result for '{connection_name}': {column_name} = {server_info[column_name][:50]}...")
                except Exception as e:
                    self.logger.warning(f"[CONNECTION_TEST] Failed to execute test query '{query}' on '{connection_name}': {e}")
            
            cursor.close()
            # Don't close the connection here - let the pool manage it
            # connection.close() # Removed - causes "closed connection" errors
            
            response_time = time.time() - start_time
            
            self.logger.info(f"[CONNECTION_TEST] Connection test completed successfully for '{connection_name}' in {response_time:.2f}s")
            
            # Audit log the successful test
            self._audit_log('TEST_SUCCESS', connection_name, {
                'response_time': response_time,
                'server_info_keys': list(server_info.keys()),
                'queries_executed': len([q for q in test_queries if any(k in server_info for k in [q.split()[-1].lower().replace('as', '').strip()])])
            })
            
            result_data = {
                'success': True,
                'connection_name': connection_name,
                'server_info': server_info,
                'response_time': response_time,
                'message': f'Connection successful in {response_time:.2f} seconds'
            }
            
            self.logger.debug(f"[CONNECTION_TEST] Full server info for '{connection_name}': {len(server_info)} properties retrieved")
            return result_data
            
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"[CONNECTION_TEST] Connection test failed for '{connection_name}' after {response_time:.2f}s: {e}")
            
            # If connection test failed, remove it from pool to prevent reuse of bad connection
            if connection_name in self._connection_pool:
                self.logger.info(f"[CONNECTION_TEST] Removing failed connection '{connection_name}' from pool")
                self._close_pool_entry(connection_name)
            
            # Audit log the failed test
            self._audit_log('TEST_ERROR', connection_name, {
                'error': str(e),
                'exception_type': type(e).__name__,
                'response_time': response_time
            })
            
            return {
                'success': False,
                'connection_name': connection_name,
                'error': str(e),
                'response_time': response_time
            }
    
    def test_all_connections(self) -> Dict[str, Dict[str, Any]]:
        """Test all configured database connections"""
        results = {}
        
        databases = self.config.get('databases', {})
        for connection_name in databases.keys():
            self.logger.info(f"Testing connection: {connection_name}")
            results[connection_name] = self.test_connection(connection_name)
        
        return results
    
    def get_available_drivers(self) -> List[str]:
        """Get list of available ODBC drivers"""
        try:
            drivers = pyodbc.drivers()
            sql_drivers = [d for d in drivers if 'SQL Server' in d]
            self.logger.debug(f"Found {len(sql_drivers)} SQL Server drivers")
            return sql_drivers
        except Exception as e:
            self.logger.error(f"Failed to get ODBC drivers: {e}")
            return []
    
    def create_connection_config(self, connection_name: str, server: str, database: str,
                               port: int = 1433, use_windows_auth: bool = True, 
                               username: str = None, password: str = None,
                               description: str = None, **kwargs) -> Dict[str, Any]:
        """Create a new connection configuration and save to database"""
        
        # Validate parameters
        if not connection_name or not server or not database:
            raise ValueError("connection_name, server, and database are required")
        
        if not use_windows_auth and (not username or not password):
            raise ValueError("username and password are required for SQL authentication")
        
        # Build configuration
        config = {
            'connection_id': str(uuid.uuid4()),
            'name': connection_name,
            'driver': kwargs.get('driver', '{ODBC Driver 17 for SQL Server}'),
            'server': server,
            'port': port,
            'database': database,
            'trusted_connection': use_windows_auth,
            'username': username if not use_windows_auth else None,
            'password': password if not use_windows_auth else None,
            'connection_timeout': kwargs.get('connection_timeout', 30),
            'command_timeout': kwargs.get('command_timeout', 300),
            'description': description or f"Connection to {server}\\{database}",
            'encrypt': kwargs.get('encrypt', False),
            'trust_server_certificate': kwargs.get('trust_server_certificate', True)
        }
        
        # Save to database
        success = self._save_connection_to_database(config)
        if not success:
            raise Exception("Failed to save connection to database")
        
        self.logger.info(f"Created connection configuration: {connection_name}")
        
        return config
    
    def _save_connection_to_database(self, config: Dict[str, Any]) -> bool:
        """Save connection configuration to database"""
        connection_name = config.get('name', 'Unknown')
        server_detail = f"{config.get('server')}:{config.get('port', 1433)}/{config.get('database')}"
        
        self.logger.info(f"[LIFECYCLE] Saving connection '{connection_name}' to database: {server_detail}")
        
        try:
            system_connection = self._create_new_connection("system")
            if not system_connection:
                self.logger.error(f"[LIFECYCLE] Cannot save connection '{connection_name}': system database not available")
                return False
            
            cursor = system_connection.cursor()
            
            # Check if connection already exists
            cursor.execute("SELECT COUNT(*) FROM user_connections WHERE name = ?", config['name'])
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Update existing connection
                self.logger.info(f"[LIFECYCLE] Updating existing connection '{connection_name}' in database")
                cursor.execute("""
                    UPDATE user_connections 
                    SET server_name = ?, port = ?, database_name = ?, trusted_connection = ?,
                        username = ?, password = ?, description = ?, driver = ?,
                        connection_timeout = ?, command_timeout = ?, encrypt = ?, trust_server_certificate = ?,
                        modified_date = GETDATE()
                    WHERE name = ?
                """, (
                    config['server'], config['port'], config['database'], config['trusted_connection'],
                    config['username'], config['password'], config['description'], config['driver'],
                    config['connection_timeout'], config['command_timeout'], config['encrypt'], 
                    config['trust_server_certificate'], config['name']
                ))
                self.logger.debug(f"[LIFECYCLE] Updated connection '{connection_name}' with {cursor.rowcount} rows affected")
            else:
                # Insert new connection
                self.logger.info(f"[LIFECYCLE] Creating new connection '{connection_name}' in database")
                cursor.execute("""
                    INSERT INTO user_connections 
                    (connection_id, name, server_name, port, database_name, trusted_connection,
                     username, password, description, driver, connection_timeout, command_timeout,
                     encrypt, trust_server_certificate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config['connection_id'], config['name'], config['server'], config['port'], 
                    config['database'], config['trusted_connection'], config['username'], config['password'],
                    config['description'], config['driver'], config['connection_timeout'], 
                    config['command_timeout'], config['encrypt'], config['trust_server_certificate']
                ))
                self.logger.debug(f"[LIFECYCLE] Inserted new connection '{connection_name}' with ID: {config['connection_id']}")
            
            system_connection.commit()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close
            
            self.logger.info(f"[LIFECYCLE] Successfully saved connection '{connection_name}' to database")
            return True
            
        except Exception as e:
            self.logger.error(f"[LIFECYCLE] Error saving connection '{connection_name}' to database: {e}")
            try:
                system_connection.rollback()
                system_connection.close()
            except:
                pass
            return False
    
    def create_custom_connection(self, name: str, server: str, database: str, 
                               port: int = 1433, auth_type: str = "windows",
                               username: str = None, password: str = None,
                               description: str = None) -> Dict[str, Any]:
        """Create a custom database connection configuration
        
        Args:
            name: Connection name
            server: Server name/IP
            database: Database name
            port: Port number (default 1433)
            auth_type: "windows" or "sql"
            username: Username for SQL auth
            password: Password for SQL auth
            description: Connection description
            
        Returns:
            Dict: Result with success status, message, and test details
        """
        self._audit_log('CREATE', name, {
            'server': server,
            'database': database, 
            'port': port,
            'auth_type': auth_type,
            'username': username if auth_type.lower() == 'sql' else None,
            'description': description
        })
        
        try:
            use_windows_auth = auth_type.lower() == "windows"
            
            # First test the connection without saving
            test_result = self._test_connection_direct(
                server=server,
                database=database,
                port=port,
                auth_type=auth_type,
                username=username,
                password=password
            )
            
            if not test_result['success']:
                self.logger.error(f"Connection test failed for '{name}': {test_result['error']}")
                self._audit_log('CREATE_FAILED', name, {
                    'error': test_result['error'],
                    'response_time': test_result.get('response_time', 0)
                })
                return {
                    'success': False,
                    'error': f"Connection test failed: {test_result['error']}",
                    'test_details': test_result
                }
            
            # Test passed, now create and save the configuration
            config = self.create_connection_config(
                connection_name=name,
                server=server,
                database=database,
                port=port,
                use_windows_auth=use_windows_auth,
                username=username,
                password=password,
                description=description
            )
            
            self.logger.info(f"Successfully created and tested connection: {name}")
            self._audit_log('CREATE_SUCCESS', name, {
                'config_id': config.get('connection_id'),
                'test_response_time': test_result.get('response_time', 0),
                'server_info': test_result.get('server_info', {})
            })
            
            return {
                'success': True,
                'message': f"Connection '{name}' created and tested successfully",
                'test_details': test_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create custom connection '{name}': {e}")
            self._audit_log('CREATE_ERROR', name, {
                'error': str(e),
                'exception_type': type(e).__name__
            })
            return {
                'success': False,
                'error': f"Failed to create connection: {str(e)}",
                'test_details': None
            }
    
    def update_connection_config(self, connection_name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing connection configuration"""
        try:
            if connection_name not in self.config.get('databases', {}):
                self.logger.error(f"Connection '{connection_name}' not found")
                return False
            
            # Update the configuration
            current_config = self.config['databases'][connection_name]
            current_config.update(updates)
            
            # Save configuration
            self._save_config()
            
            self.logger.info(f"Updated connection configuration: {connection_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update connection '{connection_name}': {e}")
            return False
    
    def _save_config(self):
        """Save current configuration to file"""
        try:
            config_path = Path(self.config_file)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, indent=2)
            
            self.logger.info(f"Saved configuration to {config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
    
    def remove_connection(self, connection_name: str) -> bool:
        """Remove a connection configuration"""
        # Get connection info before removal for audit trail
        conn_info = self.get_connection_info(connection_name)
        self._audit_log('DELETE', connection_name, {
            'server': conn_info.get('server') if conn_info else 'unknown',
            'database': conn_info.get('database') if conn_info else 'unknown'
        })
        
        try:
            success = False
            
            # Remove from database
            db_success = self._remove_connection_from_database(connection_name)
            if db_success:
                success = True
            
            # Remove from config file (if exists there)
            if connection_name in self.config.get('databases', {}):
                del self.config['databases'][connection_name]
                self._save_config()
                success = True
            
            if success:
                self.logger.info(f"Removed connection configuration: {connection_name}")
                self._audit_log('DELETE_SUCCESS', connection_name, {})
            else:
                self.logger.warning(f"Connection '{connection_name}' not found")
                self._audit_log('DELETE_NOT_FOUND', connection_name, {})
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to remove connection '{connection_name}': {e}")
            self._audit_log('DELETE_ERROR', connection_name, {
                'error': str(e),
                'exception_type': type(e).__name__
            })
            return False
    
    def _remove_connection_from_database(self, connection_name: str) -> bool:
        """Remove connection configuration from database"""
        self.logger.info(f"[LIFECYCLE] Removing connection '{connection_name}' from database")
        
        try:
            system_connection = self._create_new_connection("system")
            if not system_connection:
                self.logger.error(f"[LIFECYCLE] Cannot remove connection '{connection_name}': system database not available")
                return False
            
            cursor = system_connection.cursor()
            
            # First check if connection exists
            cursor.execute("SELECT COUNT(*) FROM user_connections WHERE name = ? AND is_active = 1", connection_name)
            exists = cursor.fetchone()[0] > 0
            
            if not exists:
                self.logger.warning(f"[LIFECYCLE] Connection '{connection_name}' not found in database (already inactive or doesn't exist)")
                cursor.close()
                system_connection.close()
                return False
            
            # Mark as inactive instead of deleting
            cursor.execute("UPDATE user_connections SET is_active = 0, modified_date = GETDATE() WHERE name = ?", connection_name)
            rows_affected = cursor.rowcount
            
            system_connection.commit()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close
            
            if rows_affected > 0:
                self.logger.info(f"[LIFECYCLE] Successfully removed connection '{connection_name}' from database ({rows_affected} rows affected)")
            else:
                self.logger.warning(f"[LIFECYCLE] No rows affected when removing connection '{connection_name}' from database")
            
            return rows_affected > 0
            
        except Exception as e:
            self.logger.error(f"[LIFECYCLE] Error removing connection '{connection_name}' from database: {e}")
            try:
                system_connection.rollback()
                system_connection.close()
            except:
                pass
            return False
    
    def list_connections(self) -> List[str]:
        """Get list of configured connection names (excluding system connections)"""
        try:
            # First get from database
            db_connections = self._load_connections_from_database()
            
            # Then get from config (excluding system connections)
            config_connections = []
            databases = self.config.get('databases', {})
            if databases:
                for conn_name, conn_config in databases.items():
                    if not conn_config.get('is_system_connection', False):
                        config_connections.append(conn_name)
            
            # Combine and deduplicate
            all_connections = list(set(db_connections + config_connections))
            return all_connections
            
        except Exception as e:
            self.logger.error(f"Error listing connections: {e}")
            return []
    
    def _load_connections_from_database(self) -> List[str]:
        """Load connection names from database"""
        self.logger.debug(f"[LIFECYCLE] Loading connection list from database")
        
        try:
            # Use direct connection creation to avoid recursion when listing connections
            system_connection = self._create_new_connection("system")
            if not system_connection:
                self.logger.warning(f"[LIFECYCLE] Cannot load connections: system database not available")
                return []
            
            cursor = system_connection.cursor()
            cursor.execute("SELECT name, created_date FROM user_connections WHERE is_active = 1 ORDER BY name")
            rows = cursor.fetchall()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close immediately
            
            connection_names = [row[0] for row in rows]
            
            self.logger.info(f"[LIFECYCLE] Loaded {len(connection_names)} active connections from database: {', '.join(connection_names)}")
            
            if rows:
                self.logger.debug(f"[LIFECYCLE] Connection creation dates:")
                for row in rows:
                    self.logger.debug(f"[LIFECYCLE]   - {row[0]}: created {row[1]}")
            
            return connection_names
            
        except Exception as e:
            self.logger.error(f"[LIFECYCLE] Error loading connections from database: {e}")
            return []
    
    def get_connection_info(self, connection_name: str) -> Optional[Dict[str, Any]]:
        """Get connection information (without sensitive data)"""
        # For system connection, always use config file to avoid recursion
        if connection_name == "system":
            db_config = self.config.get('databases', {}).get(connection_name)
        else:
            # First try to get from database
            db_config = self._get_connection_from_database(connection_name)
            
            if not db_config:
                # Fall back to config file
                db_config = self.config.get('databases', {}).get(connection_name)
        
        if not db_config:
            return None
        
        # Return config without password
        safe_config = db_config.copy()
        if 'password' in safe_config:
            safe_config['password'] = '***'
        
        return safe_config
    
    def _get_connection_from_database(self, connection_name: str) -> Optional[Dict[str, Any]]:
        """Get connection configuration from database"""
        self.logger.debug(f"[LIFECYCLE] Loading connection '{connection_name}' configuration from database")
        
        try:
            # Use direct connection creation to avoid recursion when getting connection info
            system_connection = self._create_new_connection("system")
            if not system_connection:
                self.logger.warning(f"[LIFECYCLE] Cannot load connection '{connection_name}': system database not available")
                return None
            
            cursor = system_connection.cursor()
            cursor.execute("""
                SELECT connection_id, name, server_name, port, database_name, 
                       trusted_connection, username, password, description,
                       driver, connection_timeout, command_timeout, encrypt, trust_server_certificate,
                       created_date, modified_date
                FROM user_connections 
                WHERE name = ? AND is_active = 1
            """, connection_name)
            
            row = cursor.fetchone()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close immediately
            
            if not row:
                self.logger.warning(f"[LIFECYCLE] Connection '{connection_name}' not found in database")
                return None
            
            auth_type = "Windows" if bool(row[5]) else "SQL Server"
            server_detail = f"{row[2]}:{row[3]}/{row[4]}"
            
            self.logger.info(f"[LIFECYCLE] Successfully loaded connection '{connection_name}': {server_detail} using {auth_type} auth")
            self.logger.debug(f"[LIFECYCLE] Connection '{connection_name}' created: {row[14]}, modified: {row[15]}")
            
            return {
                'connection_id': row[0],
                'name': row[1],
                'server': row[2],
                'port': row[3],
                'database': row[4],
                'trusted_connection': bool(row[5]),
                'username': row[6],
                'password': row[7],
                'description': row[8],
                'driver': row[9],
                'connection_timeout': row[10],
                'command_timeout': row[11],
                'encrypt': bool(row[12]),
                'trust_server_certificate': bool(row[13])
            }
            
        except Exception as e:
            self.logger.error(f"[LIFECYCLE] Error getting connection '{connection_name}' from database: {e}")
            return None
    
    def _audit_log(self, action: str, connection_name: str, details: Dict[str, Any] = None):
        """Log audit trail for connection operations"""
        try:
            details = details or {}
            audit_entry = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'user': self._current_user,
                'host': self._host_name,
                'action': action,
                'connection_name': connection_name,
                'details': details
            }
            
            # Create structured audit log message
            details_str = ', '.join([f"{k}={v}" for k, v in details.items() if v is not None]) if details else 'no details'
            
            self.logger.info(
                f"[AUDIT] {audit_entry['timestamp']} | {self._current_user}@{self._host_name} | "
                f"{action} | connection='{connection_name}' | {details_str}"
            )
            
            # Also attempt to save to database audit table if possible
            self._save_audit_to_database(audit_entry)
            
        except Exception as e:
            # Don't let audit logging failures break the main operation
            self.logger.warning(f"[AUDIT] Failed to log audit entry: {e}")
    
    def _save_audit_to_database(self, audit_entry: Dict[str, Any]):
        """Save audit entry to database (if system connection is available)"""
        try:
            system_connection = self._create_new_connection("system")
            if not system_connection:
                return  # System connection not available, skip database audit
            
            cursor = system_connection.cursor()
            
            # Create audit table if it doesn't exist
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='connection_audit_log' AND xtype='U')
                CREATE TABLE connection_audit_log (
                    audit_id NVARCHAR(100) PRIMARY KEY DEFAULT NEWID(),
                    timestamp DATETIME NOT NULL,
                    user_name NVARCHAR(255) NOT NULL,
                    host_name NVARCHAR(255) NOT NULL,
                    action NVARCHAR(50) NOT NULL,
                    connection_name NVARCHAR(255) NOT NULL,
                    details NVARCHAR(MAX) NULL,
                    created_date DATETIME DEFAULT GETDATE(),
                    INDEX IX_audit_timestamp (timestamp),
                    INDEX IX_audit_connection (connection_name),
                    INDEX IX_audit_action (action)
                )
            """)
            
            # Insert audit entry
            details_json = yaml.dump(audit_entry['details']) if audit_entry['details'] else None
            
            cursor.execute("""
                INSERT INTO connection_audit_log 
                (timestamp, user_name, host_name, action, connection_name, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                audit_entry['timestamp'],
                audit_entry['user'], 
                audit_entry['host'],
                audit_entry['action'],
                audit_entry['connection_name'],
                details_json
            ))
            
            system_connection.commit()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close
            
        except Exception as e:
            # Don't let database audit failures break the main operation
            self.logger.debug(f"[AUDIT] Could not save audit to database: {e}")
    
    def get_connection_audit_trail(self, connection_name: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get audit trail for connections"""
        try:
            system_connection = self._create_new_connection("system")
            if not system_connection:
                return []
            
            cursor = system_connection.cursor()
            
            if connection_name:
                cursor.execute("""
                    SELECT TOP (?) timestamp, user_name, host_name, action, connection_name, details
                    FROM connection_audit_log 
                    WHERE connection_name = ?
                    ORDER BY timestamp DESC
                """, limit, connection_name)
            else:
                cursor.execute("""
                    SELECT TOP (?) timestamp, user_name, host_name, action, connection_name, details
                    FROM connection_audit_log 
                    ORDER BY timestamp DESC
                """, limit)
            
            rows = cursor.fetchall()
            cursor.close()
            system_connection.close()  # Direct connection, safe to close
            
            audit_trail = []
            for row in rows:
                entry = {
                    'timestamp': row[0],
                    'user': row[1],
                    'host': row[2], 
                    'action': row[3],
                    'connection_name': row[4],
                    'details': yaml.safe_load(row[5]) if row[5] else {}
                }
                audit_trail.append(entry)
            
            self.logger.debug(f"[AUDIT] Retrieved {len(audit_trail)} audit entries" + (f" for connection '{connection_name}'" if connection_name else ""))
            return audit_trail
            
        except Exception as e:
            self.logger.error(f"[AUDIT] Error retrieving audit trail: {e}")
            return []


if __name__ == "__main__":
    # Test the database connection manager
    db_manager = DatabaseConnectionManager()
    
    print("=== Available ODBC Drivers ===")
    drivers = db_manager.get_available_drivers()
    for driver in drivers:
        print(f"  {driver}")
    
    print("\n=== Configured Connections ===")
    connections = db_manager.list_connections()
    for conn in connections:
        print(f"  {conn}")
        info = db_manager.get_connection_info(conn)
        if info:
            print(f"    Server: {info.get('server')}")
            print(f"    Database: {info.get('database')}")
            print(f"    Windows Auth: {info.get('trusted_connection')}")
    
    print("\n=== Testing Connections ===")
    test_results = db_manager.test_all_connections()
    for conn_name, result in test_results.items():
        status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
        print(f"  {conn_name}: {status}")
        if result['success']:
            print(f"    Response time: {result['response_time']:.2f}s")
            if 'server_info' in result:
                for key, value in result['server_info'].items():
                    print(f"    {key}: {value}")
        else:
            print(f"    Error: {result.get('error', 'Unknown error')}")
        print()