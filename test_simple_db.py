#!/usr/bin/env python3
"""
Test script for the new SimpleDatabaseManager
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database.simple_connection_manager import SimpleDatabaseManager

def main():
    print("=" * 60)
    print("Simple Database Manager Test")
    print("=" * 60)
    
    # Show environment variables being used
    print("Environment Configuration:")
    print(f"  DB_SERVER: {os.getenv('DB_SERVER', 'NOT SET')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', 'NOT SET')}")
    print(f"  DB_DATABASE: {os.getenv('DB_DATABASE', 'NOT SET')}")
    print(f"  DB_USERNAME: {os.getenv('DB_USERNAME', 'NOT SET')}")
    print(f"  DB_PASSWORD: {'SET' if os.getenv('DB_PASSWORD') else 'NOT SET'}")
    print(f"  DB_TRUSTED_CONNECTION: {os.getenv('DB_TRUSTED_CONNECTION', 'NOT SET')}")
    print("=" * 60)
    
    try:
        # Create database manager
        print("Creating database manager...")
        db = SimpleDatabaseManager()
        print("✅ Database manager created")
        
        # Test connection
        print("Testing connection...")
        result = db.test_connection()
        
        if result['success']:
            print("✅ CONNECTION SUCCESSFUL!")
            print(f"   Response time: {result['response_time']:.2f} seconds")
            print(f"   Server version: {result['server_version']}")
            print(f"   Server time: {result['server_time']}")
            
            # Try a simple query
            print("\nTesting query execution...")
            query_result = db.execute_query("SELECT 'Hello World' as message, GETDATE() as timestamp")
            if query_result['success']:
                print("✅ QUERY SUCCESSFUL!")
                print(f"   Data: {query_result['data']}")
            else:
                print(f"❌ Query failed: {query_result['error']}")
            
        else:
            print("❌ CONNECTION FAILED!")
            print(f"   Error: {result['error']}")
            print(f"   Response time: {result['response_time']:.2f} seconds")
        
        # Shutdown
        print("\nShutting down database manager...")
        db.shutdown()
        print("✅ Shutdown complete")
        
        return result['success']
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)