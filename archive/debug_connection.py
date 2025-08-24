"""
Debug connection test to see what connection string is being built
"""

from database.connection_manager import DatabaseConnectionManager

def test_connection_string():
    """Test connection string building"""
    print("=" * 60)
    print("Debug Connection String Building")
    print("=" * 60)
    
    # Test the exact values you're using in the UI
    server = "USDF11DB197\\PROD_DB01"
    port = 3433
    database = "sreutil"  # or whatever database you're testing with
    auth_type = "sql"  # or "windows"
    username = "svc-devops"
    password = "Welcome@1234"
    
    print(f"Testing with:")
    print(f"  Server: {server}")
    print(f"  Port: {port}")
    print(f"  Database: {database}")
    print(f"  Auth Type: {auth_type}")
    print(f"  Username: {username}")
    print(f"  Password: {'*' * len(password)}")
    
    try:
        db_manager = DatabaseConnectionManager()
        
        # Test direct connection
        print(f"\n1. Testing direct connection...")
        result = db_manager._test_connection_direct(
            server=server,
            database=database,
            port=port,
            auth_type=auth_type,
            username=username,
            password=password
        )
        
        print(f"Result: {result}")
        
        if not result['success']:
            print(f"\n❌ Connection failed: {result['error']}")
        else:
            print(f"\n✅ Connection successful!")
            print(f"Response time: {result['response_time']:.2f}s")
            if 'server_info' in result:
                print(f"Server info: {result['server_info']}")
        
    except Exception as e:
        print(f"\n❌ Exception occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection_string()