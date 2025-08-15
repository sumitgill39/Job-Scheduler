#!/usr/bin/env python3
"""
Debug script to check if SQL queries are being saved in job_configurations table
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("SQL Query Storage Debug Script")
print("=" * 60)

try:
    from core.job_manager import JobManager
    from database.connection_pool import get_connection_pool
    
    print("✅ Successfully imported database components")
    
    # Test 1: Check if we can create a JobManager
    job_manager = JobManager()
    print("✅ JobManager created successfully")
    
    # Test 2: List existing jobs and check their configurations
    print("\n📋 EXISTING JOBS IN DATABASE:")
    jobs = job_manager.list_jobs()
    print(f"Found {len(jobs)} jobs:")
    
    for job in jobs:
        print(f"\n🔍 Job: {job['name']} (ID: {job['job_id'][:8]}...)")
        print(f"   Type: {job['type']}")
        print(f"   Enabled: {job['enabled']}")
        
        # Get full job configuration
        full_job = job_manager.get_job(job['job_id'])
        if full_job:
            config = full_job.get('configuration', {})
            
            if job['type'] == 'sql':
                sql_config = config.get('sql', {})
                sql_query = sql_config.get('query', 'NO_QUERY_FOUND')
                connection_name = sql_config.get('connection_name', 'NO_CONNECTION')
                
                print(f"   📄 SQL Configuration:")
                print(f"      Connection: {connection_name}")
                print(f"      Query: '{sql_query}'")
                print(f"      Query Length: {len(sql_query) if sql_query != 'NO_QUERY_FOUND' else 0}")
                
                if sql_query == 'NO_QUERY_FOUND' or not sql_query or sql_query.strip() == '':
                    print(f"      ❌ PROBLEM: SQL query is missing or empty!")
                else:
                    print(f"      ✅ SQL query is properly saved")
                    
            print(f"   📋 Full Configuration Keys: {list(config.keys())}")
            
            # Show raw JSON configuration
            print(f"   🔧 Raw JSON Configuration:")
            config_json = json.dumps(config, indent=6)
            print(f"      {config_json}")
        else:
            print(f"   ❌ Could not retrieve full job configuration")
    
    # Test 3: Create a test job to see if SQL query gets saved
    print(f"\n🧪 TESTING JOB CREATION:")
    test_job_data = {
        'name': 'DEBUG Test SQL Job',
        'type': 'sql',
        'description': 'Debug test to check SQL query storage',
        'sql_query': 'SELECT COUNT(*) as debug_test FROM information_schema.tables WHERE table_type = \'BASE TABLE\'',
        'connection_name': 'system',
        'enabled': True,
        'timeout': 300,
        'max_retries': 3,
        'retry_delay': 60
    }
    
    print(f"Creating test job with SQL query: '{test_job_data['sql_query']}'")
    
    result = job_manager.create_job(test_job_data)
    if result['success']:
        test_job_id = result['job_id']
        print(f"✅ Test job created successfully: {test_job_id}")
        
        # Retrieve the test job and check if SQL query was saved
        test_job = job_manager.get_job(test_job_id)
        if test_job:
            test_config = test_job.get('configuration', {})
            test_sql_config = test_config.get('sql', {})
            saved_query = test_sql_config.get('query', 'NO_QUERY')
            
            print(f"📤 Original query: '{test_job_data['sql_query']}'")
            print(f"📥 Saved query:    '{saved_query}'")
            
            if saved_query == test_job_data['sql_query']:
                print(f"✅ SUCCESS: SQL query was saved correctly!")
            else:
                print(f"❌ FAILURE: SQL query was not saved correctly!")
                print(f"   Expected: '{test_job_data['sql_query']}'")
                print(f"   Got:      '{saved_query}'")
        else:
            print(f"❌ Could not retrieve test job after creation")
    else:
        print(f"❌ Failed to create test job: {result['error']}")

except ImportError as e:
    print(f"❌ Import error (database dependencies missing): {e}")
    print("This is expected if pyodbc is not available")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Debug script completed")
print("=" * 60)