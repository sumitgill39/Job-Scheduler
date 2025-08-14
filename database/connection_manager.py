"""
Database Connection Manager for Windows SQL Server
"""

import pyodbc
import yaml
import uuid
from pathlib import Path
from typing import Dict, Optional, Any, List
import time
from threading import Lock
from utils.logger import get_logger


class DatabaseConnectionManager:
    """Manages SQL Server database connections for Windows"""
    
    def __init__(self, config_file: str = "config/database_config.yaml"):
        self.config_file = config_file
        self.logger = get_logger(__name__)  # Initialize logger first
        self.config = self._load_config()
        self._connection_lock = Lock()
        self._connection_pool = {}
        
        # Initialize system database tables
        self._init_system_database()
        
        self.logger.info("Database Connection Manager initialized")
    
    def _init_system_database(self):
        """Initialize system database tables for storing user connections"""
        try:
            self.logger.info("Initializing system database tables...")
            
            # Get system connection
            system_connection = self.get_connection("system")
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
            system_connection.close()
            
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
            self.logger.debug(f"Using named instance with explicit port: {server},{port}")
        elif '\\' in server:
            # Named instance - don't add port for default
            components.append(f"SERVER={server}")
            self.logger.debug(f"Using named instance: {server}")
        elif port and port != 1433:
            # Custom port
            components.append(f"SERVER={server},{port}")
            self.logger.debug(f"Using server with custom port: {server},{port}")
        else:
            # Default port or no port specified
            components.append(f"SERVER={server}")
            self.logger.debug(f"Using default server: {server}")
        
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
        
        self.logger.info(f"Built connection string for '{connection_name}': {debug_string}")
        print(f"[DEBUG] Connection string for '{connection_name}': {debug_string}")  # Also print to console
        
        return connection_string
    
    def get_connection(self, connection_name: str = "default") -> Optional[pyodbc.Connection]:
        """Get database connection with retry logic"""
        retry_settings = self.config.get('retry_settings', {})
        max_retries = retry_settings.get('max_retries', 3)
        retry_delay = retry_settings.get('retry_delay', 5)
        backoff_factor = retry_settings.get('backoff_factor', 2)
        
        connection_string = self.get_connection_string(connection_name)
        
        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(f"Attempting database connection '{connection_name}' (attempt {attempt + 1})")
                
                connection = pyodbc.connect(connection_string)
                
                # Test connection
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                
                self.logger.info(f"Successfully connected to database '{connection_name}'")
                return connection
                
            except pyodbc.Error as e:
                error_msg = f"Database connection failed (attempt {attempt + 1}): {str(e)}"
                
                if attempt < max_retries:
                    self.logger.warning(f"{error_msg}. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= backoff_factor  # Exponential backoff
                else:
                    self.logger.error(f"{error_msg}. Max retries exceeded.")
                    
            except Exception as e:
                self.logger.error(f"Unexpected error connecting to database: {e}")
                break
        
        return None
    
    def _test_connection_direct(self, server: str, database: str, port: int = 1433,
                              auth_type: str = "windows", username: str = None, 
                              password: str = None) -> Dict[str, Any]:
        """Test database connection directly without using saved configuration"""
        start_time = time.time()
        
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
                self.logger.debug(f"Using named instance with explicit port: {server},{port}")
            elif '\\' in server:
                # Named instance - try without port first
                components.append(f"SERVER={server}")
                self.logger.debug(f"Using named instance: {server}")
            elif port and port != 1433:
                # Standard server with custom port
                components.append(f"SERVER={server},{port}")
                self.logger.debug(f"Using server with custom port: {server},{port}")
            else:
                # Default server and port
                components.append(f"SERVER={server}")
                self.logger.debug(f"Using default server: {server}")
            
            components.append(f"DATABASE={database}")
            
            # Authentication
            if auth_type.lower() == 'windows':
                components.append("Trusted_Connection=yes")
            else:
                if not username or not password:
                    return {
                        'success': False,
                        'error': 'Username and password required for SQL authentication',
                        'response_time': time.time() - start_time
                    }
                components.append(f"UID={username}")
                components.append(f"PWD={password}")
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
            self.logger.info(f"Testing connection with string: {debug_string}")
            
            # Test the connection
            self.logger.info(f"Testing connection to {server}\\{database}")
            
            connection = pyodbc.connect(connection_string)
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test, @@VERSION as version")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            
            response_time = time.time() - start_time
            
            return {
                'success': True,
                'message': 'Connection successful',
                'response_time': response_time,
                'server_info': {
                    'test_result': result[0] if result else None,
                    'version': result[1][:100] if result and len(result) > 1 else 'Unknown'
                }
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            
            # Extract more user-friendly error message
            if "Login failed" in error_msg:
                error_msg = "Login failed - check username and password"
            elif "Server does not exist" in error_msg:
                error_msg = "Server not found - check server name and port"
            elif "Database" in error_msg and "does not exist" in error_msg:
                error_msg = "Database not found - check database name"
            elif "timeout" in error_msg.lower():
                error_msg = "Connection timeout - check server accessibility"
            
            self.logger.error(f"Connection test failed: {e}")
            
            return {
                'success': False,
                'error': error_msg,
                'response_time': response_time
            }

    def test_connection(self, connection_name: str = "default") -> Dict[str, Any]:
        """Test database connection"""
        start_time = time.time()
        
        try:
            connection = self.get_connection(connection_name)
            
            if not connection:
                return {
                    'success': False,
                    'connection_name': connection_name,
                    'error': 'Failed to establish connection',
                    'response_time': time.time() - start_time
                }
            
            # Get server information
            cursor = connection.cursor()
            
            # Test query with server info
            test_queries = [
                "SELECT @@VERSION as server_version",
                "SELECT @@SERVERNAME as server_name",
                "SELECT DB_NAME() as database_name",
                "SELECT SYSTEM_USER as current_user",
                "SELECT GETDATE() as current_time"
            ]
            
            server_info = {}
            for query in test_queries:
                try:
                    cursor.execute(query)
                    result = cursor.fetchone()
                    if result:
                        column_name = cursor.description[0][0].lower()
                        server_info[column_name] = str(result[0]).strip()
                except Exception as e:
                    self.logger.debug(f"Failed to execute test query '{query}': {e}")
            
            cursor.close()
            connection.close()
            
            response_time = time.time() - start_time
            
            return {
                'success': True,
                'connection_name': connection_name,
                'server_info': server_info,
                'response_time': response_time,
                'message': f'Connection successful in {response_time:.2f} seconds'
            }
            
        except Exception as e:
            return {
                'success': False,
                'connection_name': connection_name,
                'error': str(e),
                'response_time': time.time() - start_time
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
        try:
            system_connection = self.get_connection("system")
            if not system_connection:
                return False
            
            cursor = system_connection.cursor()
            
            # Check if connection already exists
            cursor.execute("SELECT COUNT(*) FROM user_connections WHERE name = ?", config['name'])
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Update existing connection
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
            else:
                # Insert new connection
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
            
            system_connection.commit()
            cursor.close()
            system_connection.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving connection to database: {e}")
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
            return {
                'success': True,
                'message': f"Connection '{name}' created and tested successfully",
                'test_details': test_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create custom connection '{name}': {e}")
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
            else:
                self.logger.warning(f"Connection '{connection_name}' not found")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to remove connection '{connection_name}': {e}")
            return False
    
    def _remove_connection_from_database(self, connection_name: str) -> bool:
        """Remove connection configuration from database"""
        try:
            system_connection = self.get_connection("system")
            if not system_connection:
                return False
            
            cursor = system_connection.cursor()
            cursor.execute("UPDATE user_connections SET is_active = 0 WHERE name = ?", connection_name)
            rows_affected = cursor.rowcount
            
            system_connection.commit()
            cursor.close()
            system_connection.close()
            
            return rows_affected > 0
            
        except Exception as e:
            self.logger.error(f"Error removing connection from database: {e}")
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
        try:
            system_connection = self.get_connection("system")
            if not system_connection:
                return []
            
            cursor = system_connection.cursor()
            cursor.execute("SELECT name FROM user_connections WHERE is_active = 1")
            rows = cursor.fetchall()
            cursor.close()
            system_connection.close()
            
            return [row[0] for row in rows]
            
        except Exception as e:
            self.logger.error(f"Error loading connections from database: {e}")
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
        try:
            system_connection = self.get_connection("system")
            if not system_connection:
                return None
            
            cursor = system_connection.cursor()
            cursor.execute("""
                SELECT connection_id, name, server_name, port, database_name, 
                       trusted_connection, username, password, description,
                       driver, connection_timeout, command_timeout, encrypt, trust_server_certificate
                FROM user_connections 
                WHERE name = ? AND is_active = 1
            """, connection_name)
            
            row = cursor.fetchone()
            cursor.close()
            system_connection.close()
            
            if not row:
                return None
            
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
            self.logger.error(f"Error getting connection from database: {e}")
            return None


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