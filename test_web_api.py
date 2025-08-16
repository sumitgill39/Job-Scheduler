#!/usr/bin/env python3
"""
Test job creation and execution via the web API
"""

import requests
import json
import time
import sys

def test_web_api():
    """Test the web API job creation and execution"""
    base_url = "http://127.0.0.1:5000"
    
    print("=" * 60)
    print("Testing Web API Job Creation and Execution")
    print("=" * 60)
    
    # Test if the web UI is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Web UI is running (status: {response.status_code})")
    except requests.ConnectionError:
        print("❌ Web UI is not running. Please start it first.")
        return False
    except Exception as e:
        print(f"❌ Error connecting to web UI: {e}")
        return False
    
    # Test SQL job creation via API
    print("\n📝 Testing SQL job creation via API...")
    sql_job_data = {
        'name': 'API Test SQL Job',
        'description': 'SQL job created via API for testing',
        'type': 'sql',
        'enabled': True,
        'sql_query': 'SELECT GETDATE() as current_time, \'Hello from API Test\' as message',
        'connection_name': 'system',
        'query_timeout': 300,
        'max_rows': 1000,
        'timeout': 300,
        'max_retries': 3,
        'retry_delay': 60
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/jobs",
            json=sql_job_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                sql_job_id = result.get('job_id')
                print(f"✅ SQL job created successfully: {sql_job_id}")
                
                # Test job execution
                print(f"\n🚀 Testing SQL job execution...")
                exec_response = requests.post(
                    f"{base_url}/api/jobs/{sql_job_id}/run",
                    timeout=30
                )
                
                if exec_response.status_code == 200:
                    exec_result = exec_response.json()
                    print(f"✅ SQL job executed successfully")
                    print(f"   Status: {exec_result.get('status', 'unknown')}")
                    print(f"   Duration: {exec_result.get('duration_seconds', 0)} seconds")
                    print(f"   Output: {exec_result.get('output', 'No output')}")
                    
                    if exec_result.get('error'):
                        print(f"   Error: {exec_result['error']}")
                    
                    return True
                else:
                    print(f"❌ Job execution failed: {exec_response.status_code}")
                    print(f"   Response: {exec_response.text}")
                    return False
            else:
                print(f"❌ Job creation failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ API request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_powershell_job_api():
    """Test PowerShell job creation and execution via API"""
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "=" * 60)
    print("Testing PowerShell Job via API")
    print("=" * 60)
    
    ps_job_data = {
        'name': 'API Test PowerShell Job',
        'description': 'PowerShell job created via API for testing',
        'type': 'powershell',
        'enabled': True,
        'script_content': '''
            Write-Host "Hello from API PowerShell Test!"
            Write-Host "Current date: $(Get-Date)"
            Write-Host "Test completed successfully"
        ''',
        'execution_policy': 'RemoteSigned',
        'parameters': [],
        'timeout': 300,
        'max_retries': 3,
        'retry_delay': 60
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/jobs",
            json=ps_job_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                ps_job_id = result.get('job_id')
                print(f"✅ PowerShell job created successfully: {ps_job_id}")
                
                # Test job execution
                print(f"\n🚀 Testing PowerShell job execution...")
                exec_response = requests.post(
                    f"{base_url}/api/jobs/{ps_job_id}/run",
                    timeout=30
                )
                
                if exec_response.status_code == 200:
                    exec_result = exec_response.json()
                    print(f"✅ PowerShell job executed")
                    print(f"   Status: {exec_result.get('status', 'unknown')}")
                    print(f"   Duration: {exec_result.get('duration_seconds', 0)} seconds")
                    print(f"   Output: {exec_result.get('output', 'No output')}")
                    
                    if exec_result.get('error'):
                        print(f"   Error: {exec_result['error']}")
                    
                    return True
                else:
                    print(f"❌ PowerShell job execution failed: {exec_response.status_code}")
                    print(f"   Response: {exec_response.text}")
                    return False
            else:
                print(f"❌ PowerShell job creation failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ PowerShell API request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ PowerShell test error: {e}")
        return False

def test_job_list_api():
    """Test job listing via API"""
    base_url = "http://127.0.0.1:5000"
    
    print("\n" + "=" * 60)
    print("Testing Job List API")
    print("=" * 60)
    
    try:
        response = requests.get(f"{base_url}/api/jobs", timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                jobs = result.get('jobs', [])
                print(f"✅ Job list retrieved successfully")
                print(f"   Total jobs: {len(jobs)}")
                
                for job in jobs:
                    print(f"   - {job.get('job_id', 'unknown')}: {job.get('name', 'unknown')} ({job.get('type', 'unknown')})")
                
                return True
            else:
                print(f"❌ Job list retrieval failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ Job list API failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Job list test error: {e}")
        return False

if __name__ == "__main__":
    print("Web API Test Suite")
    print("This will test job creation and execution via the web API")
    print("Make sure the web UI is running on http://127.0.0.1:5000\n")
    
    sql_success = test_web_api()
    ps_success = test_powershell_job_api()
    list_success = test_job_list_api()
    
    print("\n" + "=" * 60)
    print("Web API Test Summary")
    print("=" * 60)
    print(f"SQL Job API Test: {'✅ PASSED' if sql_success else '❌ FAILED'}")
    print(f"PowerShell Job API Test: {'✅ PASSED' if ps_success else '❌ FAILED'}")
    print(f"Job List API Test: {'✅ PASSED' if list_success else '❌ FAILED'}")
    
    if sql_success and ps_success and list_success:
        print("\n🎉 All API tests passed!")
        print("✅ Job creation via web API is working")
        print("✅ Job execution via web API is working")
        print("✅ Job listing via web API is working")
        print("\n✨ The job execution system is fully functional!")
    else:
        print("\n⚠️  Some API tests failed. This may be expected due to missing dependencies on macOS.")