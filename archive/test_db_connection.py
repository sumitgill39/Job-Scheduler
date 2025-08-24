#!/usr/bin/env python3
"""
Database Connection Test Script
Test database connectivity using the same database_config.yaml file as the application.
"""

import pyodbc
import time
import yaml
from pathlib import Path

def load_database_config(config_file="config/database_config.yaml"):
    """Load database configuration from YAML file"""
    config_path = Path(config_file)
    
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return None

def test_database_connection(connection_name="system"):
    """Test database connection using configuration from database_config.yaml"""
    
    # Load configuration from YAML file
    config = load_database_config()
    if not config:
        return False
    
    # Get connection configuration
    db_config = config.get('databases', {}).get(connection_name)
    if not db_config:
        print(f"❌ Connection '{connection_name}' not found in configuration")
        available_connections = list(config.get('databases', {}).keys())
        if available_connections:
            print(f"Available connections: {', '.join(available_connections)}")
        return False
    
    # Extract connection parameters from config
    server = db_config.get('server')
    port = db_config.get('port', 1433)
    database = db_config.get('database')
    username = db_config.get('username')
    password = db_config.get('password')
    trusted_connection = db_config.get('trusted_connection', True)
    trust_server_certificate = db_config.get('trust_server_certificate', True)
    driver = db_config.get('driver', '{ODBC Driver 17 for SQL Server}')
    connection_timeout = db_config.get('connection_timeout', 30)
    command_timeout = db_config.get('command_timeout', 300)
    encrypt = db_config.get('encrypt', False)
    
    print("=" * 60)
    print(f"Database Connection Test - '{connection_name}'")
    print("=" * 60)
    print(f"Driver: {driver}")
    print(f"Server: {server}")
    print(f"Port: {port}")
    print(f"Database: {database}")
    print(f"Username: {username}")
    print(f"Password: {'***' if password else 'None'}")
    print(f"Trusted Connection: {trusted_connection}")
    print(f"Trust Server Certificate: {trust_server_certificate}")
    print(f"Encrypt: {encrypt}")
    print(f"Connection Timeout: {connection_timeout}s")
    print(f"Command Timeout: {command_timeout}s")
    print("=" * 60)
    
    # Build connection string components
    components = []
    components.append(f"DRIVER={driver}")
    
    # Handle server with optional port
    if '\\' in server and port and port != 1433:
        # Named instance with custom port
        components.append(f"SERVER={server},{port}")
    elif '\\' in server:
        # Named instance - don't add port for default
        components.append(f"SERVER={server}")
    elif port and port != 1433:
        # Custom port
        components.append(f"SERVER={server},{port}")
    else:
        # Default port or no port specified
        components.append(f"SERVER={server}")
    
    components.append(f"DATABASE={database}")
    
    # Authentication
    if trusted_connection:
        components.append("Trusted_Connection=yes")
    else:
        if username and password:
            components.append(f"UID={username}")
            components.append(f"PWD={password}")
        else:
            print("❌ Username and password required for SQL authentication")
            return False
    
    # Additional settings
    components.append(f"Connection Timeout={connection_timeout}")
    components.append(f"Command Timeout={command_timeout}")
    components.append(f"Encrypt={'yes' if encrypt else 'no'}")
    components.append(f"TrustServerCertificate={'yes' if trust_server_certificate else 'no'}")
    components.append("MARS_Connection=yes")
    
    connection_string = ";".join(components)
    
    start_time = time.time()
    
    try:
        print("Attempting to connect...")
        
        # Test connection
        connection = pyodbc.connect(connection_string)
        print("✅ Connection established successfully!")
        
        # Test query
        cursor = connection.cursor()
        cursor.execute("SELECT @@VERSION as server_version, GETDATE() as current_time")
        result = cursor.fetchone()
        
        print(f"✅ Test query executed successfully!")
        print(f"Server Version: {result[0][:100]}...")
        print(f"Server Time: {result[1]}")
        
        cursor.close()
        connection.close()
        
        response_time = time.time() - start_time
        print(f"✅ Connection test completed in {response_time:.2f} seconds")
        print("✅ DATABASE CONNECTION SUCCESSFUL!")
        
        return True
        
    except Exception as e:
        response_time = time.time() - start_time
        print(f"❌ Connection failed after {response_time:.2f} seconds")
        print(f"❌ Error: {str(e)}")
        
        # Provide troubleshooting hints
        error_str = str(e).lower()
        if "no such host is known" in error_str or "tcp provider" in error_str:
            print("\n🔍 TROUBLESHOOTING:")
            print("   - DNS resolution failed for server name")
            print("   - Check if server name is correct in network")
            print("   - Try using IP address instead of hostname")
            print("   - Verify VPN/network connectivity to production environment")
        elif "login failed" in error_str:
            print("\n🔍 TROUBLESHOOTING:")
            print("   - Check username and password")
            print("   - Verify SQL Server authentication is enabled")
        elif "database" in error_str and "does not exist" in error_str:
            print("\n🔍 TROUBLESHOOTING:")
            print("   - Check database name spelling")
            print("   - Verify database exists on target server")
        
        return False

if __name__ == "__main__":
    import sys
    
    # Allow specifying connection name as command line argument
    connection_name = "system"  # default
    if len(sys.argv) > 1:
        connection_name = sys.argv[1]
    
    print(f"Testing connection: {connection_name}")
    success = test_database_connection(connection_name)
    exit(0 if success else 1)