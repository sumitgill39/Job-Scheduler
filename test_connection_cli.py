"""
Command-line tool to test database connections
Usage: python test_connection_cli.py [connection_name]
"""

import sys
import pyodbc
import time
from database.connection_manager import DatabaseConnectionManager

def test_connection_string_direct(connection_string):
    """Test a connection string directly"""
    print("=" * 80)
    print("DIRECT CONNECTION STRING TEST")
    print("=" * 80)
    
    # Mask password for display
    import re
    display_string = re.sub(r'PWD=[^;]*', 'PWD=***', connection_string)
    print(f"Testing connection string:")
    print(f"  {display_string}")
    print()
    
    start_time = time.time()
    
    try:
        print("Attempting to connect...")
        connection = pyodbc.connect(connection_string)
        
        print("✅ Connection successful!")
        
        print("Testing basic query...")
        cursor = connection.cursor()
        cursor.execute("SELECT 1 as test, @@VERSION as version, DB_NAME() as database")
        result = cursor.fetchone()
        
        if result:
            print(f"  Test result: {result[0]}")
            print(f"  SQL Server version: {result[1][:100]}...")
            print(f"  Current database: {result[2]}")
        
        cursor.close()
        connection.close()
        
        end_time = time.time()
        print(f"✅ Test completed successfully in {end_time - start_time:.2f} seconds")
        
        return True
        
    except Exception as e:
        end_time = time.time()
        print(f"❌ Connection failed after {end_time - start_time:.2f} seconds")
        print(f"Error: {str(e)}")
        
        # Additional error analysis
        error_str = str(e).lower()
        if "login failed" in error_str:
            print("💡 Suggestion: Check username and password")
        elif "server does not exist" in error_str or "network path" in error_str:
            print("💡 Suggestion: Check server name and port")
        elif "database" in error_str and "does not exist" in error_str:
            print("💡 Suggestion: Check database name")
        elif "timeout" in error_str:
            print("💡 Suggestion: Check network connectivity and firewall")
        elif "driver" in error_str:
            print("💡 Suggestion: Install ODBC Driver 17 for SQL Server")
            
        return False

def test_saved_connection(connection_name):
    """Test a saved connection from the database"""
    print("=" * 80)
    print(f"TESTING SAVED CONNECTION: {connection_name}")
    print("=" * 80)
    
    try:
        # Initialize connection manager
        db_manager = DatabaseConnectionManager()
        
        print("Getting connection information...")
        conn_info = db_manager.get_connection_info(connection_name)
        
        if not conn_info:
            print(f"❌ Connection '{connection_name}' not found!")
            print("Available connections:")
            connections = db_manager.list_connections()
            for conn in connections:
                print(f"  - {conn}")
            return False
        
        print(f"Connection details:")
        print(f"  Name: {conn_info.get('name')}")
        print(f"  Server: {conn_info.get('server')}")
        print(f"  Port: {conn_info.get('port')}")
        print(f"  Database: {conn_info.get('database')}")
        print(f"  Auth Type: {'Windows' if conn_info.get('trusted_connection') else 'SQL Server'}")
        print(f"  Username: {conn_info.get('username') or 'N/A'}")
        print()
        
        print("Building connection string...")
        connection_string = db_manager.get_connection_string(connection_name)
        
        print("Testing connection...")
        result = db_manager.test_connection(connection_name)
        
        if result['success']:
            print("✅ Connection test successful!")
            print(f"Response time: {result['response_time']:.2f} seconds")
            if 'server_info' in result:
                print("Server information:")
                for key, value in result['server_info'].items():
                    print(f"  {key}: {value}")
        else:
            print("❌ Connection test failed!")
            print(f"Error: {result['error']}")
            print(f"Response time: {result['response_time']:.2f} seconds")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        import traceback
        traceback.print_exc()
        return False

def list_available_connections():
    """List all available connections"""
    print("=" * 80)
    print("AVAILABLE CONNECTIONS")
    print("=" * 80)
    
    try:
        db_manager = DatabaseConnectionManager()
        connections = db_manager.list_connections()
        
        if not connections:
            print("No connections found.")
            return
        
        print(f"Found {len(connections)} connections:")
        print()
        
        for conn_name in connections:
            conn_info = db_manager.get_connection_info(conn_name)
            if conn_info:
                print(f"📋 {conn_name}")
                print(f"    Server: {conn_info.get('server')}")
                print(f"    Database: {conn_info.get('database')}")
                print(f"    Auth: {'Windows' if conn_info.get('trusted_connection') else 'SQL Server'}")
                print()
            else:
                print(f"❌ {conn_name} (could not load details)")
                print()
                
    except Exception as e:
        print(f"Error listing connections: {e}")

def main():
    if len(sys.argv) > 1:
        connection_name = sys.argv[1]
        
        if connection_name == "--list":
            list_available_connections()
        elif connection_name.startswith("DRIVER="):
            # Direct connection string test
            connection_string = connection_name
            test_connection_string_direct(connection_string)
        else:
            # Test saved connection
            test_saved_connection(connection_name)
    else:
        print("Usage:")
        print("  python test_connection_cli.py [connection_name]")
        print("  python test_connection_cli.py --list")
        print("  python test_connection_cli.py 'DRIVER={...};SERVER=...;...'")
        print()
        print("Examples:")
        print("  python test_connection_cli.py system")
        print("  python test_connection_cli.py TestConnection")
        print("  python test_connection_cli.py --list")
        print()
        
        # Show available connections
        list_available_connections()

if __name__ == "__main__":
    main()