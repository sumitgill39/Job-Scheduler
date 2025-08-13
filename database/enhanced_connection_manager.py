"""
Enhanced Database Connection Manager for Windows Job Scheduler
Handles YAML-based and SQL database storage for connections
"""

import os
import yaml
import time
import uuid
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from utils.logger import get_logger
from .connection_manager import DatabaseConnectionManager

# Import pyodbc with error handling
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None


@dataclass
class ConnectionInfo:
    """Connection information data class"""
    name: str
    server: str
    database: str
    port: int = 1433
    auth_type: str = "windows"  # "windows" or "sql"
    username: Optional[str] = None
    password: Optional[str] = None
    description: str = ""
    created_date: str = ""
    modified_date: str = ""
    is_active: bool = True
    last_tested: Optional[str] = None
    last_test_result: Optional[str] = None
    connection_timeout: int = 30
    command_timeout: int = 300
    encrypt: bool = False
    trust_server_certificate: bool = True

    def __post_init__(self):
        if not self.created_date:
            self.created_date = datetime.now().isoformat()
        if not self.modified_date:
            self.modified_date = self.created_date


class EnhancedConnectionManager:
    """Enhanced connection manager with YAML and SQL storage support"""
    
    def __init__(self, storage_type: str = "yaml", storage_config: Dict = None):
        self.logger = get_logger(__name__)
        self.storage_type = storage_type
        self.storage_config = storage_config or {}
        
        # Connection storage paths
        self.yaml_connections_dir = Path("config/connections")
        self.yaml_connections_dir.mkdir(parents=True, exist_ok=True)
        
        # Legacy connection manager for backward compatibility
        self.legacy_manager = DatabaseConnectionManager()
        
        # Connection cache and monitoring
        self._connection_cache = {}
        self._connection_status = {}
        self._monitoring_enabled = True
        self._monitoring_interval = 300  # 5 minutes
        self._monitoring_thread = None
        
        self.logger.info(f"Enhanced Connection Manager initialized with storage: {storage_type}")
        
        # Start monitoring in a try-catch to avoid initialization failures
        try:
            self._start_monitoring()
        except Exception as e:
            self.logger.warning(f"Could not start connection monitoring: {e}")
            self._monitoring_enabled = False
    
    def create_connection(self, connection_info: ConnectionInfo) -> Tuple[bool, str]:
        """Create a new database connection"""
        try:
            # Validate connection info
            validation_result = self._validate_connection_info(connection_info)
            if not validation_result[0]:
                return False, validation_result[1]
            
            # Test the connection before saving
            test_result = self.test_connection_info(connection_info)
            if not test_result["success"]:
                return False, f"Connection test failed: {test_result['error']}"
            
            # Update test results
            connection_info.last_tested = datetime.now().isoformat()
            connection_info.last_test_result = "success"
            connection_info.modified_date = datetime.now().isoformat()
            
            # Save connection
            if self.storage_type == "yaml":
                success = self._save_connection_yaml(connection_info)
            elif self.storage_type == "database":
                success = self._save_connection_database(connection_info)
            else:
                return False, f"Unsupported storage type: {self.storage_type}"
            
            if success:
                # Update cache
                self._connection_cache[connection_info.name] = connection_info
                self._connection_status[connection_info.name] = {
                    "status": "online",
                    "last_checked": datetime.now(),
                    "response_time": test_result.get("response_time", 0),
                    "error": None
                }
                
                self.logger.info(f"Connection '{connection_info.name}' created successfully")
                return True, "Connection created successfully"
            else:
                return False, "Failed to save connection"
                
        except Exception as e:
            self.logger.error(f"Error creating connection: {e}")
            return False, str(e)
    
    def get_connection(self, name: str) -> Optional[ConnectionInfo]:
        """Get connection by name"""
        try:
            # Check cache first
            if name in self._connection_cache:
                return self._connection_cache[name]
            
            # Load from storage
            if self.storage_type == "yaml":
                connection = self._load_connection_yaml(name)
            elif self.storage_type == "database":
                connection = self._load_connection_database(name)
            else:
                return None
            
            if connection:
                self._connection_cache[name] = connection
                
            return connection
            
        except Exception as e:
            self.logger.error(f"Error getting connection '{name}': {e}")
            return None
    
    def list_connections(self) -> List[Dict[str, Any]]:
        """List all connections with status information"""
        try:
            connections = []
            
            if self.storage_type == "yaml":
                connection_names = self._list_yaml_connections()
            elif self.storage_type == "database":
                connection_names = self._list_database_connections()
            else:
                return []
            
            for name in connection_names:
                connection = self.get_connection(name)
                if connection:
                    status_info = self._connection_status.get(name, {
                        "status": "unknown",
                        "last_checked": None,
                        "response_time": 0,
                        "error": None
                    })
                    
                    connections.append({
                        "name": connection.name,
                        "server": connection.server,
                        "database": connection.database,
                        "port": connection.port,
                        "auth_type": connection.auth_type,
                        "description": connection.description,
                        "created_date": connection.created_date,
                        "modified_date": connection.modified_date,
                        "is_active": connection.is_active,
                        "last_tested": connection.last_tested,
                        "status": status_info["status"],
                        "last_checked": status_info["last_checked"].isoformat() if status_info["last_checked"] else None,
                        "response_time": status_info["response_time"],
                        "error": status_info["error"]
                    })
            
            return connections
            
        except Exception as e:
            self.logger.error(f"Error listing connections: {e}")
            return []
    
    def update_connection(self, name: str, connection_info: ConnectionInfo) -> Tuple[bool, str]:
        """Update an existing connection"""
        try:
            # Check if connection exists
            existing = self.get_connection(name)
            if not existing:
                return False, f"Connection '{name}' not found"
            
            # Validate connection info
            validation_result = self._validate_connection_info(connection_info)
            if not validation_result[0]:
                return False, validation_result[1]
            
            # Test the connection
            test_result = self.test_connection_info(connection_info)
            if not test_result["success"]:
                return False, f"Connection test failed: {test_result['error']}"
            
            # Update timestamps and test results
            connection_info.created_date = existing.created_date  # Keep original creation date
            connection_info.modified_date = datetime.now().isoformat()
            connection_info.last_tested = datetime.now().isoformat()
            connection_info.last_test_result = "success"
            
            # Save updated connection
            if self.storage_type == "yaml":
                # If name changed, delete old file
                if name != connection_info.name:
                    self._delete_connection_yaml(name)
                success = self._save_connection_yaml(connection_info)
            elif self.storage_type == "database":
                success = self._update_connection_database(name, connection_info)
            else:
                return False, f"Unsupported storage type: {self.storage_type}"
            
            if success:
                # Update cache
                if name != connection_info.name:
                    # Remove old cache entry if name changed
                    self._connection_cache.pop(name, None)
                    self._connection_status.pop(name, None)
                
                self._connection_cache[connection_info.name] = connection_info
                self._connection_status[connection_info.name] = {
                    "status": "online",
                    "last_checked": datetime.now(),
                    "response_time": test_result.get("response_time", 0),
                    "error": None
                }
                
                self.logger.info(f"Connection '{connection_info.name}' updated successfully")
                return True, "Connection updated successfully"
            else:
                return False, "Failed to save connection"
                
        except Exception as e:
            self.logger.error(f"Error updating connection: {e}")
            return False, str(e)
    
    def delete_connection(self, name: str) -> Tuple[bool, str]:
        """Delete a connection"""
        try:
            # Check if connection exists
            if not self.get_connection(name):
                return False, f"Connection '{name}' not found"
            
            # Delete from storage
            if self.storage_type == "yaml":
                success = self._delete_connection_yaml(name)
            elif self.storage_type == "database":
                success = self._delete_connection_database(name)
            else:
                return False, f"Unsupported storage type: {self.storage_type}"
            
            if success:
                # Remove from cache
                self._connection_cache.pop(name, None)
                self._connection_status.pop(name, None)
                
                self.logger.info(f"Connection '{name}' deleted successfully")
                return True, "Connection deleted successfully"
            else:
                return False, "Failed to delete connection"
                
        except Exception as e:
            self.logger.error(f"Error deleting connection: {e}")
            return False, str(e)
    
    def test_connection_info(self, connection_info: ConnectionInfo) -> Dict[str, Any]:
        """Test a connection without saving it"""
        if not HAS_PYODBC:
            return {
                "success": False,
                "error": "pyodbc not available - ODBC drivers not installed",
                "response_time": 0
            }
        
        start_time = time.time()
        
        try:
            # Build connection string
            connection_string = self._build_connection_string(connection_info)
            
            self.logger.debug(f"Testing connection to {connection_info.server}\\{connection_info.database}")
            
            # Test connection
            connection = pyodbc.connect(
                connection_string,
                timeout=connection_info.connection_timeout
            )
            
            cursor = connection.cursor()
            cursor.execute("SELECT 1 as test, @@VERSION as version, DB_NAME() as current_db")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            
            response_time = time.time() - start_time
            
            return {
                "success": True,
                "message": "Connection successful",
                "response_time": response_time,
                "server_info": {
                    "test_result": result[0] if result else None,
                    "version": result[1][:100] if result and len(result) > 1 else "Unknown",
                    "current_database": result[2] if result and len(result) > 2 else "Unknown"
                }
            }
            
        except pyodbc.Error as e:
            response_time = time.time() - start_time
            error_msg = str(e)
            
            # Extract user-friendly error messages
            if "Login failed" in error_msg:
                error_msg = "Login failed - check username and password"
            elif "Server does not exist" in error_msg or "Named Pipes Provider" in error_msg:
                error_msg = "Server not found - check server name and port"
            elif "Database" in error_msg and "does not exist" in error_msg:
                error_msg = "Database not found - check database name"
            elif "timeout" in error_msg.lower():
                error_msg = "Connection timeout - check server accessibility"
            
            self.logger.error(f"Connection test failed for {connection_info.name}: {e}")
            
            return {
                "success": False,
                "error": error_msg,
                "response_time": response_time
            }
            
        except Exception as e:
            response_time = time.time() - start_time
            self.logger.error(f"Unexpected error testing connection: {e}")
            
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "response_time": response_time
            }
    
    def test_connection(self, connection_info: ConnectionInfo) -> Tuple[bool, Optional[str]]:
        """Test a database connection"""
        try:
            # Build connection string
            conn_str_parts = [
                f"DRIVER={{ODBC Driver 17 for SQL Server}}",
                f"SERVER={connection_info.server},{connection_info.port}",
                f"DATABASE={connection_info.database}"
            ]

            if connection_info.auth_type == "sql":
                conn_str_parts.extend([
                    f"UID={connection_info.username}",
                    f"PWD={connection_info.password}"
                ])
            else:
                conn_str_parts.append("Trusted_Connection=yes")

            if connection_info.encrypt:
                conn_str_parts.append("Encrypt=yes")
            else:
                conn_str_parts.append("Encrypt=no")

            if connection_info.trust_server_certificate:
                conn_str_parts.append("TrustServerCertificate=yes")

            conn_str_parts.append(f"Connection Timeout={connection_info.connection_timeout}")
            
            conn_str = ";".join(conn_str_parts)

            # Try to connect
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return True, None

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False, str(e)

    def save_connection(self, connection_info: ConnectionInfo) -> bool:
        """Save a database connection"""
        try:
            # Update timestamps
            connection_info.modified_date = datetime.now().isoformat()
            
            # Convert to dict for storage
            conn_data = asdict(connection_info)
            
            # Store in YAML file
            config_dir = Path(self.config_path).parent
            connections_file = config_dir / "connections.yaml"
            
            # Load existing connections
            connections = {}
            if connections_file.exists():
                with open(connections_file, 'r') as f:
                    connections = yaml.safe_load(f) or {}
            
            # Add/update connection
            connections[connection_info.name] = conn_data
            
            # Save back to file
            with open(connections_file, 'w') as f:
                yaml.safe_dump(connections, f)
            
            return True

        except Exception as e:
            self.logger.error(f"Failed to save connection: {e}")
            return False

    def _build_connection_string(self, connection_info: ConnectionInfo) -> str:
        """Build a connection string from connection info"""
        parts = [
            f"DRIVER={{ODBC Driver 17 for SQL Server}}",
            f"SERVER={connection_info.server},{connection_info.port}",
            f"DATABASE={connection_info.database}"
        ]

        if connection_info.auth_type == "windows":
            parts.append("Trusted_Connection=yes")
        else:
            parts.extend([
                f"UID={connection_info.username}",
                f"PWD={connection_info.password}"
            ])

        if connection_info.encrypt:
            parts.append("Encrypt=yes")
        else:
            parts.append("Encrypt=no")

        if connection_info.trust_server_certificate:
            parts.append("TrustServerCertificate=yes")

        parts.append(f"Connect Timeout={connection_info.connection_timeout}")

        return ";".join(parts)
    
    # YAML Storage Methods
    
    def _save_connection_yaml(self, connection_info: ConnectionInfo) -> bool:
        """Save connection to YAML file"""
        try:
            yaml_file = self.yaml_connections_dir / f"{connection_info.name}.yaml"
            
            # Convert to dict and remove sensitive data if needed
            data = asdict(connection_info)
            
            # Optionally encrypt password (simple base64 for now)
            if data.get("password"):
                import base64
                data["password"] = base64.b64encode(data["password"].encode()).decode()
                data["_encrypted"] = True
            
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, default_flow_style=False, indent=2)
            
            self.logger.debug(f"Saved connection '{connection_info.name}' to YAML")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving connection to YAML: {e}")
            return False
    
    def _load_connection_yaml(self, name: str) -> Optional[ConnectionInfo]:
        """Load connection from YAML file"""
        try:
            yaml_file = self.yaml_connections_dir / f"{name}.yaml"
            
            if not yaml_file.exists():
                return None
            
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Decrypt password if encrypted
            if data.get("_encrypted") and data.get("password"):
                import base64
                data["password"] = base64.b64decode(data["password"].encode()).decode()
                data.pop("_encrypted", None)
            
            return ConnectionInfo(**data)
            
        except Exception as e:
            self.logger.error(f"Error loading connection from YAML: {e}")
            return None
    
    def _delete_connection_yaml(self, name: str) -> bool:
        """Delete connection YAML file"""
        try:
            yaml_file = self.yaml_connections_dir / f"{name}.yaml"
            
            if yaml_file.exists():
                yaml_file.unlink()
                self.logger.debug(f"Deleted connection '{name}' from YAML")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error deleting connection YAML: {e}")
            return False
    
    def _list_yaml_connections(self) -> List[str]:
        """List all YAML connection files"""
        try:
            # Ensure directory exists
            if not self.yaml_connections_dir.exists():
                self.logger.debug(f"Connections directory does not exist: {self.yaml_connections_dir}")
                return []
            
            connection_files = list(self.yaml_connections_dir.glob("*.yaml"))
            connection_names = [f.stem for f in connection_files]
            
            self.logger.debug(f"Found {len(connection_names)} YAML connection files")
            return connection_names
            
        except Exception as e:
            self.logger.error(f"Error listing YAML connections: {e}")
            return []
    
    # SQL Database Storage Methods (for future implementation)
    
    def _save_connection_database(self, connection_info: ConnectionInfo) -> bool:
        """Save connection to SQL database"""
        # TODO: Implement when app has its own database
        self.logger.warning("Database storage not yet implemented")
        return False
    
    def _load_connection_database(self, name: str) -> Optional[ConnectionInfo]:
        """Load connection from SQL database"""
        # TODO: Implement when app has its own database
        return None
    
    def _update_connection_database(self, name: str, connection_info: ConnectionInfo) -> bool:
        """Update connection in SQL database"""
        # TODO: Implement when app has its own database
        return False
    
    def _delete_connection_database(self, name: str) -> bool:
        """Delete connection from SQL database"""
        # TODO: Implement when app has its own database
        return False
    
    def _list_database_connections(self) -> List[str]:
        """List connections from SQL database"""
        # TODO: Implement when app has its own database
        return []
    
    # Monitoring Methods
    
    def _start_monitoring(self):
        """Start connection monitoring thread"""
        if self._monitoring_enabled and not self._monitoring_thread:
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_worker,
                daemon=True,
                name="ConnectionMonitor"
            )
            self._monitoring_thread.start()
            self.logger.info("Connection monitoring started")
    
    def _stop_monitoring(self):
        """Stop connection monitoring"""
        self._monitoring_enabled = False
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=5)
            self._monitoring_thread = None
            self.logger.info("Connection monitoring stopped")
    
    def _monitoring_worker(self):
        """Background worker for connection monitoring"""
        while self._monitoring_enabled:
            try:
                # Get all active connections
                connections = self.list_connections()
                
                for conn in connections:
                    if not self._monitoring_enabled:
                        break
                    
                    if conn["is_active"]:
                        # Check if connection needs testing
                        last_checked = self._connection_status.get(conn["name"], {}).get("last_checked")
                        
                        if (not last_checked or 
                            datetime.now() - last_checked > timedelta(seconds=self._monitoring_interval)):
                            
                            # Test connection silently
                            self.test_connection(conn["name"])
                
                # Sleep for a portion of the monitoring interval
                time.sleep(min(30, self._monitoring_interval // 10))  # Check every 30 seconds or 1/10 of interval
                
            except Exception as e:
                self.logger.error(f"Error in connection monitoring: {e}")
                time.sleep(60)  # Sleep longer on error
    
    def set_monitoring_interval(self, seconds: int):
        """Set the monitoring interval in seconds"""
        self._monitoring_interval = max(60, seconds)  # Minimum 1 minute
        self.logger.info(f"Connection monitoring interval set to {self._monitoring_interval} seconds")
    
    def enable_monitoring(self, enabled: bool = True):
        """Enable or disable connection monitoring"""
        if enabled and not self._monitoring_enabled:
            self._monitoring_enabled = True
            self._start_monitoring()
        elif not enabled and self._monitoring_enabled:
            self._stop_monitoring()
    
    def __del__(self):
        """Cleanup when object is destroyed"""
        self._stop_monitoring()


# Global instance - will be initialized when first accessed
_enhanced_connection_manager = None

def get_enhanced_connection_manager():
    """Get the global enhanced connection manager instance"""
    global _enhanced_connection_manager
    if _enhanced_connection_manager is None:
        _enhanced_connection_manager = EnhancedConnectionManager()
    return _enhanced_connection_manager

# For backward compatibility
enhanced_connection_manager = get_enhanced_connection_manager()