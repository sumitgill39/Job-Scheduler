"""
Test script for Local SQL Express Database Connection
Tests the updated database configuration
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_connection():
    """Test database connection with new local SQL Express settings"""
    print("=" * 60)
    print("Testing Local SQL Express Database Connection")
    print("=" * 60)
    
    try:
        # Test environment variables
        print("\n1. Testing Environment Variables:")
        from dotenv import load_dotenv
        load_dotenv()
        
        print(f"   DB_SERVER: {os.getenv('DB_SERVER', 'Not Set')}")
        print(f"   DB_DATABASE: {os.getenv('DB_DATABASE', 'Not Set')}")
        print(f"   DB_TRUSTED_CONNECTION: {os.getenv('DB_TRUSTED_CONNECTION', 'Not Set')}")
        print(f"   DB_DRIVER: {os.getenv('DB_DRIVER', 'Not Set')}")
        
        # Test SQLAlchemy connection
        print("\n2. Testing SQLAlchemy Database Engine:")
        from database.sqlalchemy_models import database_engine
        
        # Test database connection
        print("   Creating database engine...")
        connection_test = database_engine.test_connection()
        
        if connection_test['success']:
            print("   [SUCCESS] Database connection successful!")
            print(f"   Message: {connection_test['message']}")
        else:
            print("   [FAILED] Database connection failed!")
            print(f"   Error: {connection_test['error']}")
            return False
        
        # Test table creation
        print("\n3. Testing Database Table Creation:")
        try:
            database_engine.create_tables()
            print("   [SUCCESS] Database tables created/verified successfully!")
        except Exception as e:
            print(f"   [FAILED] Table creation failed: {e}")
            return False
        
        # Test session creation
        print("\n4. Testing Database Session:")
        try:
            from database.sqlalchemy_models import get_db_session
            with get_db_session() as session:
                print("   [SUCCESS] Database session created successfully!")
                
                # Test a simple query
                from sqlalchemy import text
                result = session.execute(text("SELECT GETDATE() as [current_time], DB_NAME() as [database_name]"))
                row = result.fetchone()
                print(f"   Current Time: {row[0]}")
                print(f"   Database: {row[1]}")
                
        except Exception as e:
            print(f"   [FAILED] Session test failed: {e}")
            return False
        
        print("\n" + "=" * 60)
        print("[SUCCESS] ALL DATABASE TESTS PASSED!")
        print("Your local SQL Express instance is ready for the Job Scheduler.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[CRITICAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)