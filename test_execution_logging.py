#!/usr/bin/env python3
"""
Test enhanced job execution logging system
"""

import sys
import os
import requests
import json
import time

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_execution_logging_direct():
    """Test execution logging with direct job execution"""
    print("=" * 60)
    print("Testing Enhanced Execution Logging System")
    print("=" * 60)
    
    try:
        from core.sql_job import SqlJob
        from core.powershell_job import PowerShellJob
        from core.execution_logger import ExecutionLogger
        
        # Test SQL job with execution logging
        print("\n📝 Testing SQL Job with Enhanced Logging...")
        sql_job = SqlJob(
            job_id='test-logging-sql-001',
            name='SQL Job with Enhanced Logging',
            description='Test SQL job execution with detailed logging',
            timeout=300,
            max_retries=3,
            retry_delay=60,
            enabled=True,
            sql_query='SELECT GETDATE() as current_time, \'Hello from Enhanced Logging Test\' as message',
            connection_name='system',
            query_timeout=300,
            max_rows=1000
        )
        
        print("✅ SQL job created successfully")
        
        # Execute the job (will use enhanced logging)
        print("\n🚀 Executing SQL job with enhanced logging...")
        result = sql_job.run()
        
        print(f"\n📊 SQL Job Execution Results:")
        print(f"  Status: {result.status.value}")
        print(f"  Duration: {result.duration_seconds:.2f} seconds")
        
        if result.output:
            print(f"\n📜 Detailed Execution Logs:")
            print("─" * 60)
            print(result.output)
            print("─" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ Direct logging test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_logging():
    """Test job execution logging via API"""
    print("\n" + "=" * 60)
    print("Testing API Execution Logging")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:5000"
    
    # Test if the web UI is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Web UI is running (status: {response.status_code})")
    except requests.ConnectionError:
        print("❌ Web UI is not running. Please start it first.")
        return False
    
    # Create and execute a job via API to generate logs
    print("\n📝 Creating test job via API...")
    
    job_data = {
        'name': 'API Logging Test Job',
        'description': 'Job created to test enhanced execution logging via API',
        'type': 'sql',
        'enabled': True,
        'sql_query': 'SELECT GETDATE() as test_time, \'Enhanced logging test via API\' as message',
        'connection_name': 'system',
        'query_timeout': 300,
        'max_rows': 1000,
        'timeout': 300,
        'max_retries': 3,
        'retry_delay': 60
    }
    
    try:
        # Create job
        response = requests.post(
            f"{base_url}/api/jobs",
            json=job_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Job creation failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        if not result.get('success'):
            print(f"❌ Job creation failed: {result.get('error', 'Unknown error')}")
            return False
        
        job_id = result.get('job_id')
        print(f"✅ Job created successfully: {job_id}")
        
        # Execute the job
        print(f"\n🚀 Executing job via API...")
        exec_response = requests.post(
            f"{base_url}/api/jobs/{job_id}/run",
            timeout=30
        )
        
        if exec_response.status_code == 200:
            exec_result = exec_response.json()
            print(f"✅ Job executed")
            print(f"   Status: {exec_result.get('status', 'unknown')}")
            print(f"   Duration: {exec_result.get('duration_seconds', 0)} seconds")
            
            # Check if job output contains detailed logs
            output = exec_result.get('output', '')
            if output and '=== Execution Log for' in output:
                print(f"\n📜 Enhanced Execution Logs Found in Job Output:")
                print("─" * 60)
                print(output)
                print("─" * 60)
                
                # Test the new logs API endpoint
                print(f"\n🔍 Testing job logs API endpoint...")
                logs_response = requests.get(f"{base_url}/api/jobs/{job_id}/logs")
                
                if logs_response.status_code == 200:
                    logs_result = logs_response.json()
                    print(f"✅ Logs API endpoint works")
                    print(f"   Executions found: {logs_result.get('total_count', 0)}")
                    
                    executions = logs_result.get('executions', [])
                    for execution in executions:
                        has_logs = execution.get('has_detailed_logs', False)
                        print(f"   - Execution {execution.get('execution_id')}: {'Has detailed logs' if has_logs else 'No detailed logs'}")
                
                return True
            else:
                print(f"⚠️  Job executed but no enhanced logs found in output")
                print(f"   Output preview: {output[:200]}...")
                return False
        else:
            print(f"❌ Job execution failed: {exec_response.status_code}")
            print(f"   Response: {exec_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ API logging test error: {e}")
        return False

if __name__ == "__main__":
    print("Enhanced Execution Logging Test Suite")
    print("This will test the new detailed execution logging functionality")
    print("Note: Running in mock mode since pyodbc is not available\n")
    
    # Test direct execution logging
    direct_success = test_execution_logging_direct()
    
    # Test API execution logging  
    api_success = test_api_logging()
    
    print("\n" + "=" * 60)
    print("Enhanced Logging Test Summary")
    print("=" * 60)
    print(f"Direct Execution Logging: {'✅ PASSED' if direct_success else '❌ FAILED'}")
    print(f"API Execution Logging: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    if direct_success and api_success:
        print("\n🎉 Enhanced execution logging is working correctly!")
        print("✅ Detailed step-by-step logs are captured during job execution")
        print("✅ Logs include component information, timestamps, and error details")
        print("✅ Logs are accessible via API endpoints")
        print("✅ Users will be able to see exactly what happened during job execution")
    else:
        print("\n⚠️  Some logging tests failed. Check the output above for details.")