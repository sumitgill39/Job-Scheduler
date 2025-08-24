"""
Simplified and Robust Database Connection Manager
Uses environment variables for configuration and implements proper connection pooling
"""

import os
import threading
import time
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from utils.logger import get_logger

# Import with error handling
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env file if it exists
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # dotenv not available, use os.environ directly
    pass


class DatabaseConfig:
    """Database configuration loaded from environment variables"""
    
    def __init__(self):
        from utils.logger import get_logger
        self.logger = get_logger(__name__)
        
        # Log the .env file location and existence
        env_path = Path(__file__).parent.parent / '.env'
        self.logger.info(f"[DB_CONFIG] Looking for .env file at: {env_path}")
        self.logger.info(f"[DB_CONFIG] .env file exists: {env_path.exists()}")
        
        if env_path.exists():
            self.logger.info(f"[DB_CONFIG] .env file size: {env_path.stat().st_size} bytes")
        
        # Load configuration with detailed logging
        self.logger.info("[DB_CONFIG] Loading database configuration from environment variables...")
        
        self.driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        self.server = os.getenv('DB_SERVER', 'localhost')
        self.port = int(os.getenv('DB_PORT', '1433'))
        self.database = os.getenv('DB_DATABASE', 'master')
        self.username = os.getenv('DB_USERNAME', '')
        self.password = os.getenv('DB_PASSWORD', '')
        self.trusted_connection = os.getenv('DB_TRUSTED_CONNECTION', 'false').lower() == 'true'
        self.connection_timeout = int(os.getenv('DB_CONNECTION_TIMEOUT', '30'))
        self.command_timeout = int(os.getenv('DB_COMMAND_TIMEOUT', '300'))
        self.encrypt = os.getenv('DB_ENCRYPT', 'false').lower() == 'true'
        self.trust_server_certificate = os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
        
        # Log all configuration values (mask password)
        self.logger.info("[DB_CONFIG] ===== DATABASE CONFIGURATION LOADED =====")
        self.logger.info(f"[DB_CONFIG] Config source: Environment variables (.env file)")
        self.logger.info(f"[DB_CONFIG] DB_DRIVER = '{self.driver}'")
        self.logger.info(f"[DB_CONFIG] DB_SERVER = '{self.server}'")
        self.logger.info(f"[DB_CONFIG] DB_PORT = {self.port}")
        self.logger.info(f"[DB_CONFIG] DB_DATABASE = '{self.database}'")
        self.logger.info(f"[DB_CONFIG] DB_USERNAME = '{self.username}'")
        self.logger.info(f"[DB_CONFIG] DB_PASSWORD = {'*' * len(self.password) if self.password else '(empty)'}")
        self.logger.info(f"[DB_CONFIG] DB_TRUSTED_CONNECTION = {self.trusted_connection}")
        self.logger.info(f"[DB_CONFIG] DB_ENCRYPT = {self.encrypt}")
        self.logger.info(f"[DB_CONFIG] DB_TRUST_SERVER_CERTIFICATE = {self.trust_server_certificate}")
        
        # CRITICAL AUTHENTICATION CHECKPOINT
        trusted_raw = os.getenv('DB_TRUSTED_CONNECTION', 'false')
        self.logger.critical(f"[DB_CONFIG] 🚨 RAW DB_TRUSTED_CONNECTION VALUE: '{trusted_raw}'")
        self.logger.critical(f"[DB_CONFIG] 🚨 BOOLEAN RESULT: {self.trusted_connection}")
        
        if self.trusted_connection:
            self.logger.error("[DB_CONFIG] ❌ CRITICAL ERROR: WINDOWS AUTHENTICATION DETECTED!")
            self.logger.error("[DB_CONFIG] ❌ This will use local Windows user credentials!")
            self.logger.error("[DB_CONFIG] ❌ Raw env value was: '{}'".format(trusted_raw))
            
            # Get current Windows user for comparison
            import getpass
            current_user = getpass.getuser()
            self.logger.error(f"[DB_CONFIG] ❌ Current Windows user: {current_user}")
            self.logger.error("[DB_CONFIG] ❌ CHECK YOUR .ENV FILE - DB_TRUSTED_CONNECTION SHOULD BE 'false'")
            
        else:
            self.logger.info(f"[DB_CONFIG] ✅ USING SQL SERVER AUTHENTICATION")
            self.logger.info(f"[DB_CONFIG] ✅ Username: '{self.username}'")
            if not self.username:
                self.logger.error("[DB_CONFIG] ❌ ERROR: SQL Server auth requested but no username provided!")
            if not self.password:
                self.logger.error("[DB_CONFIG] ❌ ERROR: SQL Server auth requested but no password provided!")
        
        self.logger.info("[DB_CONFIG] ===== END CONFIGURATION =====")
        
        # Log raw environment variables for debugging
        self.logger.debug("[DB_CONFIG] Raw environment variables:")
        for key in os.environ:
            if key.startswith('DB_'):
                value = os.environ[key]
                if 'PASSWORD' in key:
                    value = '*' * len(value) if value else '(empty)'
                self.logger.debug(f"[DB_CONFIG]   {key} = '{value}'")
        
        # Pool settings
        self.pool_max_connections = int(os.getenv('DB_POOL_MAX_CONNECTIONS', '10'))
        self.pool_min_connections = int(os.getenv('DB_POOL_MIN_CONNECTIONS', '2'))
        self.pool_connection_lifetime = int(os.getenv('DB_POOL_CONNECTION_LIFETIME', '3600'))
        
        # Retry settings
        self.max_retries = int(os.getenv('DB_MAX_RETRIES', '3'))
        self.retry_delay = int(os.getenv('DB_RETRY_DELAY', '5'))
        self.backoff_factor = float(os.getenv('DB_BACKOFF_FACTOR', '2'))
    
    def build_connection_string(self) -> str:
        """Build connection string from configuration"""
        self.logger.info("[CONNECTION_STRING] Building database connection string...")
        
        components = [
            f"DRIVER={{{self.driver}}}",
        ]
        
        # Handle server with optional port and named instances
        if '\\' in self.server and self.port != 1433:
            # Named instance with custom port
            server_component = f"SERVER={self.server},{self.port}"
            components.append(server_component)
            self.logger.info(f"[CONNECTION_STRING] Server: Named instance with custom port: {server_component}")
        elif '\\' in self.server:
            # Named instance with default port
            server_component = f"SERVER={self.server}"
            components.append(server_component)
            self.logger.info(f"[CONNECTION_STRING] Server: Named instance with default port: {server_component}")
        elif self.port != 1433:
            # Standard server with custom port
            server_component = f"SERVER={self.server},{self.port}"
            components.append(server_component)
            self.logger.info(f"[CONNECTION_STRING] Server: Standard server with custom port: {server_component}")
        else:
            # Standard server with default port
            server_component = f"SERVER={self.server}"
            components.append(server_component)
            self.logger.info(f"[CONNECTION_STRING] Server: Standard server with default port: {server_component}")
        
        components.append(f"DATABASE={self.database}")
        self.logger.info(f"[CONNECTION_STRING] Database: {self.database}")
        
        # Authentication - CRITICAL LOGGING
        if self.trusted_connection:
            components.append("Trusted_Connection=yes")
            self.logger.error("[CONNECTION_STRING] ❌❌❌ WINDOWS AUTHENTICATION DETECTED IN CONNECTION STRING! ❌❌❌")
            self.logger.error("[CONNECTION_STRING] ❌ Adding: Trusted_Connection=yes")
            self.logger.error("[CONNECTION_STRING] ❌ This WILL use Windows credentials!")
            
            # Get current Windows user for comparison
            import getpass
            current_user = getpass.getuser()
            self.logger.error(f"[CONNECTION_STRING] ❌ Current Windows user: {current_user}")
            self.logger.error("[CONNECTION_STRING] ❌ THIS IS THE SOURCE OF THE AUTHENTICATION ISSUE!")
            
        else:
            if self.username and self.password:
                components.append(f"UID={self.username}")
                components.append(f"PWD={self.password}")
                self.logger.info(f"[CONNECTION_STRING] ✅ AUTHENTICATION: SQL Server Authentication")
                self.logger.info(f"[CONNECTION_STRING] ✅ SQL Username: {self.username}")
                self.logger.info(f"[CONNECTION_STRING] ✅ SQL Password: {'*' * len(self.password)}")
            else:
                error_msg = "Username and password required for SQL Server authentication"
                self.logger.error(f"[CONNECTION_STRING] ❌ ERROR: {error_msg}")
                raise ValueError(error_msg)
        
        # Additional settings
        components.extend([
            f"Connection Timeout={self.connection_timeout}",
            f"Command Timeout={self.command_timeout}",
            f"Encrypt={'yes' if self.encrypt else 'no'}",
            f"TrustServerCertificate={'yes' if self.trust_server_certificate else 'no'}",
            "MARS_Connection=yes"
        ])
        
        connection_string = ";".join(components)
        
        # Log the final connection string (with password masked)
        safe_conn_str = connection_string
        if 'PWD=' in safe_conn_str:
            import re
            safe_conn_str = re.sub(r'PWD=[^;]*', 'PWD=***', safe_conn_str)
        
        self.logger.info(f"[CONNECTION_STRING] ===== FINAL CONNECTION STRING =====")
        self.logger.info(f"[CONNECTION_STRING] {safe_conn_str}")
        self.logger.info(f"[CONNECTION_STRING] ===== END CONNECTION STRING =====")
        
        return connection_string
    
    def get_safe_connection_string(self) -> str:
        """Get connection string with masked password for logging"""
        conn_str = self.build_connection_string()
        if 'PWD=' in conn_str:
            import re
            conn_str = re.sub(r'PWD=[^;]*', 'PWD=***', conn_str)
        return conn_str


class ConnectionPool:
    """Simple, thread-safe connection pool"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = get_logger("database.connection_pool")
        self._pool = []
        self._pool_lock = threading.Lock()
        self._created_connections = 0
        self._last_cleanup = datetime.now()
        
        self.logger.info(f"[POOL] Initialized connection pool - max: {config.pool_max_connections}, lifetime: {config.pool_connection_lifetime}s")
    
    def get_connection(self):
        """Get a connection from the pool"""
        with self._pool_lock:
            # Try to reuse existing connection
            while self._pool:
                conn_info = self._pool.pop()
                if self._is_connection_valid(conn_info):
                    conn_info['last_used'] = datetime.now()
                    self.logger.debug(f"[POOL] Reusing pooled connection (age: {(datetime.now() - conn_info['created']).seconds}s)")
                    return conn_info['connection']
                else:
                    # Connection expired or invalid
                    self._close_connection_safe(conn_info['connection'])
            
            # Create new connection if under limit
            if self._created_connections < self.config.pool_max_connections:
                connection = self._create_new_connection()
                if connection:
                    self._created_connections += 1
                    self.logger.info(f"[POOL] Created new connection ({self._created_connections}/{self.config.pool_max_connections})")
                    return connection
            
            self.logger.warning(f"[POOL] Connection pool at capacity ({self._created_connections})")
            return None
    
    def return_connection(self, connection):
        """Return a connection to the pool"""
        if not connection:
            return
        
        with self._pool_lock:
            try:
                # Test if connection is still valid
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                
                # Add back to pool
                conn_info = {
                    'connection': connection,
                    'created': datetime.now(),
                    'last_used': datetime.now()
                }
                self._pool.append(conn_info)
                self.logger.debug(f"[POOL] Returned connection to pool (pool size: {len(self._pool)})")
                
            except Exception as e:
                self.logger.debug(f"[POOL] Connection invalid when returning, closing: {e}")
                self._close_connection_safe(connection)
                self._created_connections = max(0, self._created_connections - 1)
    
    def _create_new_connection(self):
        """Create a new database connection"""
        if not HAS_PYODBC:
            self.logger.error("[POOL] pyodbc not available")
            return None
        
        connection_string = self.config.build_connection_string()
        safe_conn_str = self.config.get_safe_connection_string()
        
        self.logger.info(f"[POOL] Creating connection: {safe_conn_str}")
        
        for attempt in range(self.config.max_retries):
            try:
                connection = pyodbc.connect(connection_string)
                
                # Test the connection
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                
                self.logger.info(f"[POOL] ✅ Connection created successfully")
                return connection
                
            except Exception as e:
                self.logger.error(f"[POOL] ❌ Connection attempt {attempt + 1} failed: {e}")
                
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (self.config.backoff_factor ** attempt)
                    self.logger.info(f"[POOL] Retrying in {delay} seconds...")
                    time.sleep(delay)
        
        self.logger.error(f"[POOL] ❌ Failed to create connection after {self.config.max_retries} attempts")
        return None
    
    def _is_connection_valid(self, conn_info: Dict) -> bool:
        """Check if a pooled connection is still valid"""
        try:
            connection = conn_info['connection']
            
            # Check age
            age = datetime.now() - conn_info['created']
            if age.total_seconds() > self.config.pool_connection_lifetime:
                self.logger.debug(f"[POOL] Connection expired (age: {age.seconds}s)")
                return False
            
            # Test connection
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return True
            
        except Exception as e:
            self.logger.debug(f"[POOL] Connection validation failed: {e}")
            return False
    
    def _close_connection_safe(self, connection):
        """Safely close a connection"""
        try:
            if connection:
                connection.close()
        except Exception as e:
            self.logger.debug(f"[POOL] Error closing connection: {e}")
    
    def cleanup(self):
        """Clean up expired connections"""
        now = datetime.now()
        if (now - self._last_cleanup).total_seconds() < 300:  # Cleanup max every 5 minutes
            return
        
        with self._pool_lock:
            valid_connections = []
            closed_count = 0
            
            for conn_info in self._pool:
                if self._is_connection_valid(conn_info):
                    valid_connections.append(conn_info)
                else:
                    self._close_connection_safe(conn_info['connection'])
                    closed_count += 1
                    self._created_connections = max(0, self._created_connections - 1)
            
            self._pool = valid_connections
            self._last_cleanup = now
            
            if closed_count > 0:
                self.logger.info(f"[POOL] Cleaned up {closed_count} expired connections")
    
    def close_all(self):
        """Close all connections in the pool"""
        with self._pool_lock:
            closed_count = 0
            for conn_info in self._pool:
                self._close_connection_safe(conn_info['connection'])
                closed_count += 1
            
            self._pool.clear()
            self._created_connections = 0
            self.logger.info(f"[POOL] Closed all {closed_count} connections")


class SimpleDatabaseManager:
    """Simplified database manager using environment variables"""
    
    def __init__(self):
        self.logger = get_logger("database.manager")
        self.config = DatabaseConfig()
        self.pool = ConnectionPool(self.config)
        
        self.logger.info("[INIT] SimpleDatabaseManager initialized")
        self.logger.info(f"[INIT] Server: {self.config.server}:{self.config.port}")
        self.logger.info(f"[INIT] Database: {self.config.database}")
        self.logger.info(f"[INIT] Auth: {'Windows' if self.config.trusted_connection else 'SQL Server'}")
    
    def get_connection(self):
        """Get a database connection"""
        connection = self.pool.get_connection()
        if connection:
            self.pool.cleanup()  # Opportunistic cleanup
        return connection
    
    def return_connection(self, connection):
        """Return a connection to the pool"""
        self.pool.return_connection(connection)
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connectivity"""
        self.logger.info("[TEST] Testing database connection...")
        start_time = time.time()
        
        try:
            connection = self.get_connection()
            if not connection:
                return {
                    'success': False,
                    'error': 'Failed to get connection from pool',
                    'response_time': time.time() - start_time
                }
            
            # Execute test query
            cursor = connection.cursor()
            cursor.execute("SELECT @@VERSION as version, GETDATE() as current_time")
            result = cursor.fetchone()
            cursor.close()
            
            self.return_connection(connection)
            
            response_time = time.time() - start_time
            self.logger.info(f"[TEST] ✅ Connection test successful in {response_time:.2f}s")
            
            return {
                'success': True,
                'response_time': response_time,
                'server_version': result[0][:100] if result else 'Unknown',
                'server_time': str(result[1]) if result and len(result) > 1 else 'Unknown'
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"[TEST] ❌ Connection test failed in {response_time:.2f}s: {e}")
            
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time
            }
    
    def execute_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """Execute a query and return results"""
        connection = self.get_connection()
        if not connection:
            return {'success': False, 'error': 'No database connection available'}
        
        try:
            cursor = connection.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Fetch results if it's a SELECT query
            if query.strip().upper().startswith('SELECT'):
                results = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                cursor.close()
                self.return_connection(connection)
                
                return {
                    'success': True,
                    'data': [dict(zip(columns, row)) for row in results],
                    'row_count': len(results)
                }
            else:
                # For INSERT/UPDATE/DELETE
                row_count = cursor.rowcount
                connection.commit()
                cursor.close()
                self.return_connection(connection)
                
                return {
                    'success': True,
                    'row_count': row_count
                }
                
        except Exception as e:
            self.logger.error(f"[QUERY] Query execution failed: {e}")
            try:
                connection.rollback()
            except:
                pass
            self.return_connection(connection)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def shutdown(self):
        """Shutdown the database manager"""
        self.logger.info("[SHUTDOWN] Shutting down database manager...")
        self.pool.close_all()
        self.logger.info("[SHUTDOWN] Database manager shutdown complete")


# Global instance
_db_manager = None
_db_lock = threading.Lock()

def get_database_manager() -> SimpleDatabaseManager:
    """Get the global database manager instance"""
    global _db_manager
    if _db_manager is None:
        with _db_lock:
            if _db_manager is None:
                _db_manager = SimpleDatabaseManager()
    return _db_manager


if __name__ == "__main__":
    # Test the new database manager
    db = SimpleDatabaseManager()
    result = db.test_connection()
    print(f"Connection test: {'SUCCESS' if result['success'] else 'FAILED'}")
    if result['success']:
        print(f"Response time: {result['response_time']:.2f}s")
        print(f"Server version: {result['server_version']}")
    else:
        print(f"Error: {result['error']}")