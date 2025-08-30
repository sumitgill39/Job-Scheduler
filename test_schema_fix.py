"""
Test script to verify database schema fix
Tests job creation after adding the description column
"""

import os
import sys
from pathlib import Path
import uuid

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_schema_fix():
    """Test database schema after adding missing columns"""
    print("=" * 60)
    print("Testing Database Schema Fix")
    print("=" * 60)
    
    try:
        # Load environment variables
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test database connection
        print("\n1. Testing database connection...")
        from database.sqlalchemy_models import get_db_session, JobConfiguration
        
        with get_db_session() as session:
            print("   [SUCCESS] Database session created")
            
            # Test creating a job configuration record
            print("\n2. Testing job configuration creation...")
            test_job = JobConfiguration(
                job_id=str(uuid.uuid4()),
                name="Schema Test Job",
                job_type="sql",
                description="Test job to verify schema fix",
                configuration='{"test": true}',
                enabled=True,
                created_by="schema_test"
            )
            
            session.add(test_job)
            session.commit()
            print(f"   [SUCCESS] Created test job: {test_job.job_id}")
            
            # Test querying the record back
            print("\n3. Testing job configuration query...")
            retrieved_job = session.query(JobConfiguration).filter_by(
                job_id=test_job.job_id
            ).first()
            
            if retrieved_job:
                print(f"   [SUCCESS] Retrieved job: {retrieved_job.name}")
                print(f"   Description: {retrieved_job.description}")
                print(f"   Job Type: {retrieved_job.job_type}")
                print(f"   Enabled: {retrieved_job.enabled}")
            else:
                print("   [FAILED] Could not retrieve test job")
                return False
            
            # Clean up test job
            session.delete(retrieved_job)
            session.commit()
            print(f"   [SUCCESS] Cleaned up test job")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Database schema fix verified!")
        print("The job creation error should now be resolved.")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[FAILED] Schema test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_schema_fix()
    sys.exit(0 if success else 1)