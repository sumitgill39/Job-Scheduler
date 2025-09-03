#!/usr/bin/env python3
"""
Test script for the new V2 job management system
"""

import sys
import os
import asyncio

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.sqlalchemy_models import init_database
from core.job_manager import JobManager, create_sample_powershell_yaml
from core.job_executor import JobExecutor

async def test_v2_system():
    """Test the complete V2 job system"""
    print("Testing V2 Job Management System")
    print("=" * 50)
    
    try:
        # Step 1: Initialize database
        print("Step 1: Initializing database...")
        init_result = init_database()
        if not init_result['success']:
            print(f"   Database initialization failed: {init_result}")
            return False
        print("   [OK] Database initialized successfully")
        
        # Step 2: Create job manager and executor
        print("\nStep 2: Initializing V2 components...")
        job_manager = JobManager()
        job_executor = JobExecutor()
        print("   [OK] V2 components initialized")
        
        # Step 3: Create a test job
        print("\nStep 3: Creating test PowerShell job...")
        
        test_yaml = """
id: "PS-TEST-001"
name: "V2 Test Job"
type: "PowerShell"
executionMode: "inline"
inlineScript: |
  Write-Host "=== V2 Job System Test ==="
  Write-Host "Current Time: $(Get-Date)"
  Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)"
  Write-Host "Computer Name: $env:COMPUTERNAME"
  Write-Host "User: $env:USERNAME"
  Write-Host "Working Directory: $(Get-Location)"
  Write-Host "Test completed successfully!"
enabled: true
timeout: 60
retryPolicy:
  maxRetries: 2
  retryDelay: 10
"""
        
        job_definition = {
            'name': 'V2 PowerShell Test Job',
            'description': 'Test job to verify V2 system functionality',
            'yaml_config': test_yaml.strip(),
            'enabled': True
        }
        
        create_result = job_manager.create_job(job_definition)
        if not create_result['success']:
            print(f"   Job creation failed: {create_result}")
            return False
        
        job_id = create_result['job_id']
        print(f"   [OK] Test job created: {job_id}")
        
        # Step 4: Verify job can be retrieved
        print("\nStep 4: Retrieving created job...")
        job_data = job_manager.get_job(job_id)
        if not job_data:
            print("   [ERROR] Failed to retrieve job")
            return False
        
        print(f"   [OK] Job retrieved: {job_data['name']}")
        print(f"   Job version: {job_data.get('version', 'N/A')}")
        print(f"   Job enabled: {job_data.get('enabled', False)}")
        
        # Step 5: Execute the job
        print("\nStep 5: Executing test job...")
        execution_result = job_executor.execute_job(job_id)
        
        print(f"   Execution completed:")
        print(f"   - Success: {execution_result['success']}")
        print(f"   - Status: {execution_result['status']}")
        print(f"   - Duration: {execution_result['duration_seconds']:.2f} seconds")
        print(f"   - Execution ID: {execution_result['execution_id']}")
        
        if execution_result['success']:
            print("   [OK] Job executed successfully")
            if execution_result.get('output'):
                print(f"   Output preview: {execution_result['output'][:200]}...")
        else:
            print(f"   [ERROR] Job execution failed: {execution_result.get('error', 'Unknown error')}")
        
        # Step 6: Check execution history
        print("\nStep 6: Checking execution history...")
        history = job_manager.get_execution_history(job_id, limit=5)
        print(f"   Found {len(history)} execution records")
        
        if history:
            latest = history[0]
            print(f"   Latest execution:")
            print(f"   - ID: {latest['execution_id']}")
            print(f"   - Status: {latest['status']}")
            print(f"   - Duration: {latest.get('duration_seconds', 0):.2f}s")
            print(f"   - Return Code: {latest.get('return_code', 'N/A')}")
        
        # Step 7: List all V2 jobs
        print("\nStep 7: Listing all V2 jobs...")
        all_jobs = job_manager.list_jobs()
        print(f"   Found {len(all_jobs)} V2 jobs in database")
        
        for job in all_jobs:
            print(f"   - {job['name']} ({job['job_id'][:8]}...) - {job.get('last_execution_status', 'never run')}")
        
        # Step 8: Update job
        print("\nStep 8: Testing job update...")
        update_data = {
            'description': 'Updated test job description',
            'enabled': False
        }
        update_result = job_manager.update_job(job_id, update_data)
        
        if update_result['success']:
            print("   [OK] Job updated successfully")
        else:
            print(f"   [ERROR] Job update failed: {update_result}")
        
        # Step 9: Clean up (optional)
        print("\nStep 9: Cleanup (delete test job)...")
        delete_result = job_manager.delete_job(job_id)
        
        if delete_result['success']:
            print("   [OK] Test job deleted successfully")
        else:
            print(f"   [ERROR] Job deletion failed: {delete_result}")
        
        print(f"\n[SUCCESS] V2 System Test Completed Successfully!")
        print("The V2 job management system is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_yaml_samples():
    """Test YAML sample generation"""
    print("\nTesting YAML Sample Generation")
    print("=" * 40)
    
    try:
        from core.job_manager import create_sample_powershell_yaml, create_sample_sql_yaml
        
        print("PowerShell Sample YAML:")
        ps_yaml = create_sample_powershell_yaml()
        print(ps_yaml)
        
        print("\n" + "=" * 40)
        print("SQL Sample YAML:")
        sql_yaml = create_sample_sql_yaml()
        print(sql_yaml)
        
        return True
        
    except Exception as e:
        print(f"X YAML sample generation failed: {e}")
        return False

if __name__ == "__main__":
    print("V2 Job Management System - Comprehensive Test")
    print("=" * 60)
    
    # Test YAML samples first
    yaml_success = test_yaml_samples()
    
    print("\n" + "=" * 60)
    
    # Test the complete V2 system
    system_success = asyncio.run(test_v2_system())
    
    if yaml_success and system_success:
        print("\n[SUCCESS] All tests passed! The V2 system is ready for use.")
        print("\nNext steps:")
        print("1. Run the migration script: python migrate_to_v2.py")
        print("2. Access V2 jobs via the API endpoints:")
        print("   - GET /api/v2/jobs - List all V2 jobs")
        print("   - POST /api/v2/jobs - Create new V2 job")
        print("   - POST /api/v2/jobs/{id}/run - Execute V2 job")
        print("3. Use the YAML format for structured job definitions")
        sys.exit(0)
    else:
        print("\n[ERROR] Some tests failed. Please check the errors above.")
        sys.exit(1)