"""
Show what connection strings are being built (without actually testing them)
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock pyodbc to avoid import errors
class MockConnection:
    pass

class MockPyodbc:
    Connection = MockConnection
    
    class Error(Exception):
        pass
    
    def connect(self, connection_string):
        raise Exception("Mock connection - not actually connecting")
    
    def drivers(self):
        return ["ODBC Driver 17 for SQL Server"]

sys.modules['pyodbc'] = MockPyodbc()

from database.connection_manager import DatabaseConnectionManager

def show_connection_strings():
    """Show what connection strings would be built"""
    print("=" * 80)
    print("CONNECTION STRINGS (NO ACTUAL CONNECTION TEST)")
    print("=" * 80)
    
    try:
        db_manager = DatabaseConnectionManager()
        connections = db_manager.list_connections()
        
        if not connections:
            print("❌ No connections found in database")
            print("\n💡 Make sure to save a connection through the web UI first")
            return
        
        print(f"Found {len(connections)} connections:")
        print()
        
        for conn_name in connections:
            print(f"📋 Connection: {conn_name}")
            print("-" * 50)
            
            try:
                # Get connection info
                conn_info = db_manager.get_connection_info(conn_name)
                if conn_info:
                    print(f"  Server: {conn_info.get('server')}")
                    print(f"  Port: {conn_info.get('port')}")
                    print(f"  Database: {conn_info.get('database')}")
                    print(f"  Auth Type: {'Windows' if conn_info.get('trusted_connection') else 'SQL Server'}")
                    print(f"  Username: {conn_info.get('username') or 'N/A'}")
                    print()
                
                # Get connection string
                connection_string = db_manager.get_connection_string(conn_name)
                
                # Mask password
                import re
                display_string = re.sub(r'PWD=[^;]*', 'PWD=***', connection_string)
                
                print(f"  Connection String:")
                print(f"    {display_string}")
                print()
                
                # Show the actual connection string for copy-paste testing
                print(f"  🔗 For manual testing, use this connection string:")
                print(f"    DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={conn_info.get('server')}")
                if conn_info.get('port') and conn_info.get('port') != 1433:
                    if '\\\\' in str(conn_info.get('server', '')):
                        print(f"    ,{conn_info.get('port')}", end="")
                    else:
                        print(f"    ,{conn_info.get('port')}", end="")
                print(f";DATABASE={conn_info.get('database')}", end="")
                
                if conn_info.get('trusted_connection'):
                    print(f";Trusted_Connection=yes", end="")
                else:
                    print(f";UID={conn_info.get('username')};PWD=YOUR_PASSWORD_HERE", end="")
                
                print(f";Connection Timeout=30;Command Timeout=300;Encrypt=no;TrustServerCertificate=yes")
                print()
                
            except Exception as e:
                print(f"  ❌ Error getting connection string: {e}")
                print()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def show_test_examples():
    """Show examples of how to test connections"""
    print("=" * 80)
    print("MANUAL CONNECTION TESTING")
    print("=" * 80)
    print()
    print("You can test these connection strings using:")
    print()
    print("1. 📋 SQL Server Management Studio (SSMS)")
    print("   - Use the server name and credentials shown above")
    print()
    print("2. 🐍 Python script:")
    print("   ```python")
    print("   import pyodbc")
    print("   connection_string = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=...'")
    print("   connection = pyodbc.connect(connection_string)")
    print("   cursor = connection.cursor()")
    print("   cursor.execute('SELECT 1')")
    print("   print('Success!')")
    print("   ```")
    print()
    print("3. 🔧 Command line (if pyodbc is installed):")
    print("   ```bash")
    print("   python -c \"import pyodbc; pyodbc.connect('YOUR_CONNECTION_STRING')\"")
    print("   ```")
    print()

if __name__ == "__main__":
    show_connection_strings()
    show_test_examples()