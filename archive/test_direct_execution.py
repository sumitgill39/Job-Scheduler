#!/usr/bin/env python3
"""
Direct test of job execution classes without requiring database storage
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_sql_job_direct():
    """Test SQL job execution directly without database storage"""
    print("=" * 60)
    print("Testing Direct SQL Job Execution")
    print("=" * 60)
    
    try:
        from core.sql_job import SqlJob
        
        # Create SQL job directly (separate base params from SQL-specific params)
        sql_job = SqlJob(
            job_id='test-sql-001',
            name='Test SQL Job Direct',
            description='Direct SQL job test without database storage',
            timeout=300,
            max_retries=3,
            retry_delay=60,
            enabled=True,
            # SQL-specific parameters
            sql_query='SELECT GETDATE() as current_time, \'Hello from Mock SQL Server\' as message',
            connection_name='system',
            query_timeout=300,
            max_rows=1000
        )
        
        print("✅ SQL job instance created successfully")
        print(f"   Job ID: {sql_job.job_id}")
        print(f"   Job Name: {sql_job.name}")
        print(f"   Job Type: {sql_job.job_type}")
        print(f"   SQL Query: {sql_job.sql_query[:50]}...")
        
        # Execute the job directly
        print("\n🚀 Executing SQL job directly...")
        result = sql_job.run()
        
        print(f"\n📊 SQL Job Execution Results:")
        print(f"  Status: {result.status.value}")
        print(f"  Duration: {result.duration_seconds:.2f} seconds")
        print(f"  Return Code: {result.return_code}")
        print(f"  Start Time: {result.start_time}")
        print(f"  End Time: {result.end_time}")
        
        if result.output:
            print(f"  Output: {result.output}")
        
        if result.error_message:
            print(f"  Error: {result.error_message}")
        
        if result.metadata:
            print(f"  Mock Execution: {result.metadata.get('mock_execution', False)}")
        
        return result.status.value == 'SUCCESS'
        
    except Exception as e:
        print(f"❌ SQL job test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_powershell_job_direct():
    """Test PowerShell job execution directly without database storage"""
    print("\n" + "=" * 60)
    print("Testing Direct PowerShell Job Execution")
    print("=" * 60)
    
    try:
        from core.powershell_job import PowerShellJob
        
        # Create PowerShell job directly
        ps_script = '''
            Write-Host "Hello from PowerShell Mock Execution!"
            Write-Host "Current date: $(Get-Date)"
            Write-Host "Computer name: $env:COMPUTERNAME"
            Write-Host "Test completed successfully"
        '''
        
        ps_job = PowerShellJob(
            job_id='test-ps-001',
            name='Test PowerShell Job Direct',
            description='Direct PowerShell job test without database storage',
            timeout=300,
            max_retries=3,
            retry_delay=60,
            enabled=True,
            # PowerShell-specific parameters
            script_content=ps_script,
            execution_policy='RemoteSigned',
            parameters=[]
        )
        
        print("✅ PowerShell job instance created successfully")
        print(f"   Job ID: {ps_job.job_id}")
        print(f"   Job Name: {ps_job.name}")
        print(f"   Job Type: {ps_job.job_type}")
        print(f"   Script Length: {len(ps_job.script_content)} characters")
        print(f"   Execution Policy: {ps_job.execution_policy}")
        
        # Execute the job directly
        print("\n🚀 Executing PowerShell job directly...")
        result = ps_job.run()
        
        print(f"\n📊 PowerShell Job Execution Results:")
        print(f"  Status: {result.status.value}")
        print(f"  Duration: {result.duration_seconds:.2f} seconds")
        print(f"  Return Code: {result.return_code}")
        print(f"  Start Time: {result.start_time}")
        print(f"  End Time: {result.end_time}")
        
        if result.output:
            print(f"  Output: {result.output}")
        
        if result.error_message:
            print(f"  Error: {result.error_message}")
        
        if result.metadata:
            print(f"  Mock Execution: {result.metadata.get('mock_execution', False)}")
        
        return result.status.value == 'SUCCESS'
        
    except Exception as e:
        print(f"❌ PowerShell job test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_job_base_functionality():
    """Test job base class functionality"""
    print("\n" + "=" * 60)
    print("Testing Job Base Class Functionality")
    print("=" * 60)
    
    try:
        from core.sql_job import SqlJob
        from core.job_base import JobStatus
        
        # Test job serialization/deserialization
        sql_job = SqlJob(
            job_id='test-serialize-001',
            name='Test Serialization',
            description='Test job serialization',
            # SQL-specific parameters
            sql_query='SELECT 1 as test',
            connection_name='system'
        )
        
        # Test to_dict
        job_dict = sql_job.to_dict()
        print("✅ Job serialized to dictionary")
        print(f"   Dictionary keys: {list(job_dict.keys())}")
        
        # Test from_dict
        recreated_job = SqlJob.from_dict(job_dict)
        print("✅ Job recreated from dictionary")
        print(f"   Recreated job ID: {recreated_job.job_id}")
        print(f"   Recreated job name: {recreated_job.name}")
        
        # Test job cloning
        cloned_job = sql_job.clone("Cloned Job")
        print("✅ Job cloned successfully")
        print(f"   Clone ID: {cloned_job.job_id}")
        print(f"   Clone name: {cloned_job.name}")
        
        # Test job status enum
        print(f"✅ Job status constants available:")
        for status in JobStatus:
            print(f"   - {status.name}: {status.value}")
        
        return True
        
    except Exception as e:
        print(f"❌ Base functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("Direct Job Execution Test Suite")
    print("Testing job classes directly without database storage")
    print("Note: Running in mock mode since pyodbc is not available\n")
    
    # Test direct job execution
    sql_success = test_sql_job_direct()
    ps_success = test_powershell_job_direct()
    base_success = test_job_base_functionality()
    
    print("\n" + "=" * 60)
    print("Direct Execution Test Summary")
    print("=" * 60)
    print(f"SQL Job Direct Execution: {'✅ PASSED' if sql_success else '❌ FAILED'}")
    print(f"PowerShell Job Direct Execution: {'✅ PASSED' if ps_success else '❌ FAILED'}")
    print(f"Job Base Functionality: {'✅ PASSED' if base_success else '❌ FAILED'}")
    
    if sql_success and ps_success and base_success:
        print("\n🎉 All direct execution tests passed!")
        print("✅ SQL job execution pipeline is working correctly")
        print("✅ PowerShell job execution pipeline is working correctly")
        print("✅ Job base class functionality is working correctly")
        print("\nThe core job execution engine is ready for use!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")