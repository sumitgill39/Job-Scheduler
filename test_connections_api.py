"""
Test script to debug connections API issues
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_connections_api():
    """Test the connections API functionality"""
    print("=" * 60)
    print("Testing Connections API")
    print("=" * 60)
    
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test direct database query for connections
        print("\n1. Testing direct database query...")
        from database.sqlalchemy_models import get_db_session
        from sqlalchemy import text
        
        with get_db_session() as session:
            result = session.execute(text("SELECT * FROM user_connections"))
            connections = result.fetchall()
            print(f"   [SUCCESS] Found {len(connections)} connections in database")
            
            for conn in connections:
                print(f"   - {conn.name} ({conn.connection_id})")
        
        # Test the connection manager
        print("\n2. Testing connection manager...")
        try:
            # This is where the API error might be occurring
            from core.job_manager import JobManager
            from core.job_executor import JobExecutor
            
            job_manager = JobManager()
            print("   [SUCCESS] Job manager initialized")
            
            # Try to get connections through job manager
            # This is likely where the error occurs
            print("   Attempting to get connections...")
            
        except Exception as e:
            print(f"   [FAILED] Connection manager error: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("Connections API test completed")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[FAILED] Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_connections_api()