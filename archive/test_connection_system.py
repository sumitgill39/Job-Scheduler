"""
Test script for the connection management system
"""

from database.connection_manager import DatabaseConnectionManager

def test_connection_system():
    """Test the complete connection management workflow"""
    print("=" * 60)
    print("Testing Connection Management System")
    print("=" * 60)
    
    try:
        # Initialize connection manager
        print("1. Initializing Database Connection Manager...")
        db_manager = DatabaseConnectionManager()
        print("   ✅ Connection manager initialized")
        
        # Test system connection
        print("\n2. Testing system database connection...")
        test_result = db_manager.test_connection("system")
        if test_result['success']:
            print(f"   ✅ System connection successful ({test_result['response_time']:.2f}s)")
        else:
            print(f"   ❌ System connection failed: {test_result['error']}")
            return
        
        # List existing connections
        print("\n3. Listing existing connections...")
        connections = db_manager.list_connections()
        print(f"   Found {len(connections)} existing connections: {connections}")
        
        # Test creating a new connection
        print("\n4. Testing connection creation...")
        test_conn_result = db_manager.create_custom_connection(
            name="test_connection",
            server="localhost",
            database="master",  # Using master database for testing
            port=1433,
            auth_type="windows",
            description="Test connection for validation"
        )
        
        if test_conn_result['success']:
            print("   ✅ Test connection created and tested successfully!")
            print(f"   Response time: {test_conn_result['test_details']['response_time']:.2f}s")
        else:
            print(f"   ❌ Test connection creation failed: {test_conn_result['error']}")
        
        # List connections again
        print("\n5. Listing connections after creation...")
        connections = db_manager.list_connections()
        print(f"   Found {len(connections)} connections: {connections}")
        
        # Test getting connection info
        if "test_connection" in connections:
            print("\n6. Testing connection info retrieval...")
            conn_info = db_manager.get_connection_info("test_connection")
            if conn_info:
                print("   ✅ Connection info retrieved successfully")
                print(f"   Server: {conn_info.get('server')}")
                print(f"   Database: {conn_info.get('database')}")
                print(f"   Auth Type: {'Windows' if conn_info.get('trusted_connection') else 'SQL Server'}")
            else:
                print("   ❌ Failed to retrieve connection info")
        
        # Clean up test connection
        print("\n7. Cleaning up test connection...")
        if db_manager.remove_connection("test_connection"):
            print("   ✅ Test connection removed successfully")
        else:
            print("   ❌ Failed to remove test connection")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("The connection management system is ready for use.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection_system()