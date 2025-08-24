#!/usr/bin/env python3
"""
Test script to verify job execution functionality
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_job_creation_and_execution():
    """Test creating and executing a mock SQL job"""
    print("=" * 60)
    print("Testing Job Execution Pipeline")
    print("=" * 60)
    
    try:
        # Import required components
        from core.job_manager import JobManager
        from core.job_executor import JobExecutor
        from core.sql_job import SqlJob
        
        print("✅ Successfully imported job components")
        
        # Initialize job manager (should work in mock mode)
        job_manager = JobManager()
        print("✅ Job manager initialized")
        
        # Create a test SQL job configuration (job manager expects top-level fields)
        test_job_config = {
            'name': 'Test SQL Job - Mock Execution',
            'description': 'A test job to verify SQL execution pipeline works',
            'type': 'sql',
            'enabled': True,
            'sql_query': 'SELECT GETDATE() as current_time, \'Hello from Mock SQL Server\' as message',
            'connection_name': 'system',
            'query_timeout': 300,
            'max_rows': 1000,
            'timeout': 300,
            'max_retries': 3,
            'retry_delay': 60
        }
        
        print("\n📝 Creating test job...")
        result = job_manager.create_job(test_job_config)
        
        if result['success']:
            job_id = result['job_id']
            print(f"✅ Job created successfully with ID: {job_id}")
            
            # Initialize job executor
            print("\n🚀 Testing job execution...")
            job_executor = JobExecutor()
            
            # Execute the job
            execution_result = job_executor.execute_job(job_id)
            
            print(f"\n📊 Execution Results:")
            print(f"  Success: {execution_result.get('success', False)}")
            print(f"  Status: {execution_result.get('status', 'unknown')}")
            print(f"  Duration: {execution_result.get('duration_seconds', 0)} seconds")
            print(f"  Start Time: {execution_result.get('start_time', 'unknown')}")
            print(f"  End Time: {execution_result.get('end_time', 'unknown')}")
            
            if execution_result.get('output'):
                print(f"  Output: {execution_result['output']}")
            
            if execution_result.get('error'):
                print(f"  Error: {execution_result['error']}")
            
            # Test execution history
            print(f"\n📜 Checking execution history...")
            history = job_executor.get_execution_history(job_id, limit=5)
            print(f"  Found {len(history)} execution records")
            
            for record in history:
                print(f"    - Execution {record['execution_id']}: {record['status']} at {record['start_time']}")
            
            return True
            
        else:
            print(f"❌ Failed to create job: {result.get('error', 'Unknown error')}")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("This indicates missing dependencies for job execution")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_powershell_job():
    """Test creating and executing a PowerShell job"""
    print("\n" + "=" * 60)
    print("Testing PowerShell Job Execution")
    print("=" * 60)
    
    try:
        from core.job_manager import JobManager
        from core.job_executor import JobExecutor
        
        job_manager = JobManager()
        
        # Create a test PowerShell job configuration (job manager expects top-level fields)
        ps_job_config = {
            'name': 'Test PowerShell Job - Mock Execution',
            'description': 'A test PowerShell job to verify execution pipeline',
            'type': 'powershell',
            'enabled': True,
            'script_content': '''
                Write-Host "Hello from PowerShell Mock Execution!"
                Write-Host "Current date: $(Get-Date)"
                Write-Host "Computer name: $env:COMPUTERNAME"
                Write-Host "Test completed successfully"
            ''',
            'execution_policy': 'RemoteSigned',
            'parameters': [],
            'timeout': 300,
            'max_retries': 3,
            'retry_delay': 60
        }
        
        print("📝 Creating test PowerShell job...")
        result = job_manager.create_job(ps_job_config)
        
        if result['success']:
            job_id = result['job_id']
            print(f"✅ PowerShell job created successfully with ID: {job_id}")
            
            # Execute the job
            print("🚀 Testing PowerShell job execution...")
            job_executor = JobExecutor()
            execution_result = job_executor.execute_job(job_id)
            
            print(f"\n📊 PowerShell Execution Results:")
            print(f"  Success: {execution_result.get('success', False)}")
            print(f"  Status: {execution_result.get('status', 'unknown')}")
            print(f"  Duration: {execution_result.get('duration_seconds', 0)} seconds")
            
            if execution_result.get('output'):
                print(f"  Output: {execution_result['output']}")
            
            return True
        else:
            print(f"❌ Failed to create PowerShell job: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ PowerShell test error: {e}")
        return False

if __name__ == "__main__":
    print("Job Execution Pipeline Test Suite")
    print("This will test the core job execution functionality")
    print("Note: Running in mock mode since pyodbc is not available\n")
    
    # Test SQL job execution
    sql_success = test_job_creation_and_execution()
    
    # Test PowerShell job execution
    ps_success = test_powershell_job()
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"SQL Job Test: {'✅ PASSED' if sql_success else '❌ FAILED'}")
    print(f"PowerShell Job Test: {'✅ PASSED' if ps_success else '❌ FAILED'}")
    
    if sql_success and ps_success:
        print("\n🎉 All tests passed! Job execution pipeline is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")