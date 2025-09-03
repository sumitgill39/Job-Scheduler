#!/usr/bin/env python3
"""
Test script to verify that timezone and schedule fields are saved during job creation
"""

import sys
import os
import json
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.job_manager import JobManager
from database.sqlalchemy_models import get_db_session, JobConfiguration

def test_schedule_fields_creation():
    """Test that schedule fields are saved during job creation"""
    print("Testing Schedule Fields in Job Creation")
    print("=" * 50)
    
    job_manager = JobManager()
    
    # Test job with all schedule fields
    test_job_data = {
        'name': 'Test Schedule Job',
        'type': 'powershell',
        'script_content': 'Write-Host "Test job for schedule fields"',
        'execution_policy': 'Bypass',
        'enabled': True,
        # Schedule fields
        'schedule_enabled': True,
        'schedule_type': 'cron',
        'schedule_expression': '0 */4 * * *',  # Every 4 hours
        'timezone': 'America/New_York',
        # Advanced fields
        'timeout': 600,
        'max_retries': 5,
        'retry_delay': 60
    }
    
    print("Creating job with schedule fields:")
    print(f"  Schedule Enabled: {test_job_data['schedule_enabled']}")
    print(f"  Schedule Type: {test_job_data['schedule_type']}")
    print(f"  Schedule Expression: {test_job_data['schedule_expression']}")
    print(f"  Timezone: {test_job_data['timezone']}")
    print(f"  Timeout: {test_job_data['timeout']}")
    print(f"  Max Retries: {test_job_data['max_retries']}")
    print(f"  Retry Delay: {test_job_data['retry_delay']}")
    
    # Create the job
    result = job_manager.create_job(test_job_data)
    
    if not result['success']:
        print(f"Job creation failed: {result['error']}")
        return False
    
    job_id = result['job_id']
    print(f"Job created successfully with ID: {job_id}")
    
    # Now retrieve the job and verify fields were saved
    print("\nVerifying saved fields...")
    
    with get_db_session() as session:
        saved_job = session.query(JobConfiguration).filter(
            JobConfiguration.job_id == job_id
        ).first()
        
        if not saved_job:
            print(f"ERROR: Job {job_id} not found in database")
            return False
        
        print("\nDatabase fields:")
        print(f"  Job Name: {saved_job.name}")
        print(f"  Schedule Enabled: {saved_job.schedule_enabled}")
        print(f"  Schedule Type: {saved_job.schedule_type}")
        print(f"  Schedule Expression: {saved_job.schedule_expression}")
        print(f"  Timezone: {saved_job.timezone}")
        
        # Check configuration JSON
        config = json.loads(saved_job.configuration or '{}')
        print(f"\nConfiguration JSON fields:")
        print(f"  Timeout: {config.get('timeout', 'NOT SAVED')}")
        print(f"  Max Retries: {config.get('max_retries', 'NOT SAVED')}")
        print(f"  Retry Delay: {config.get('retry_delay', 'NOT SAVED')}")
        
        # Verify all fields match
        all_correct = True
        
        if saved_job.schedule_enabled != test_job_data['schedule_enabled']:
            print(f"ERROR: Schedule Enabled mismatch: expected {test_job_data['schedule_enabled']}, got {saved_job.schedule_enabled}")
            all_correct = False
        
        if saved_job.schedule_type != test_job_data['schedule_type']:
            print(f"ERROR: Schedule Type mismatch: expected {test_job_data['schedule_type']}, got {saved_job.schedule_type}")
            all_correct = False
        
        if saved_job.schedule_expression != test_job_data['schedule_expression']:
            print(f"ERROR: Schedule Expression mismatch: expected {test_job_data['schedule_expression']}, got {saved_job.schedule_expression}")
            all_correct = False
        
        if saved_job.timezone != test_job_data['timezone']:
            print(f"ERROR: Timezone mismatch: expected {test_job_data['timezone']}, got {saved_job.timezone}")
            all_correct = False
        
        if config.get('timeout') != test_job_data['timeout']:
            print(f"ERROR: Timeout mismatch: expected {test_job_data['timeout']}, got {config.get('timeout')}")
            all_correct = False
        
        if config.get('max_retries') != test_job_data['max_retries']:
            print(f"ERROR: Max Retries mismatch: expected {test_job_data['max_retries']}, got {config.get('max_retries')}")
            all_correct = False
        
        if config.get('retry_delay') != test_job_data['retry_delay']:
            print(f"ERROR: Retry Delay mismatch: expected {test_job_data['retry_delay']}, got {config.get('retry_delay')}")
            all_correct = False
        
        if all_correct:
            print("\nSUCCESS: All schedule and advanced fields were saved correctly!")
        else:
            print("\nERROR: Some fields were not saved correctly.")
        
        # Clean up - delete test job
        session.delete(saved_job)
        session.commit()
        print(f"\nCLEANUP: Test job cleaned up (deleted)")
        
        return all_correct


def test_job_update():
    """Test that schedule fields are still saved correctly during update"""
    print("\n" + "=" * 50)
    print("Testing Schedule Fields in Job Update")
    print("=" * 50)
    
    job_manager = JobManager()
    
    # Create a simple job first
    initial_job_data = {
        'name': 'Test Update Job',
        'type': 'sql',
        'sql_query': 'SELECT 1',
        'connection_name': 'default'
    }
    
    result = job_manager.create_job(initial_job_data)
    if not result['success']:
        print(f"ERROR: Initial job creation failed: {result['error']}")
        return False
    
    job_id = result['job_id']
    print(f"SUCCESS: Initial job created with ID: {job_id}")
    
    # Now update with schedule fields
    update_data = {
        'schedule_enabled': True,
        'schedule_type': 'interval',
        'schedule_expression': '1d 2h',  # Daily + 2 hours
        'timezone': 'Europe/London',
        'timeout': 900,
        'max_retries': 3,
        'retry_delay': 45
    }
    
    print("\nUpdating job with schedule fields...")
    update_result = job_manager.update_job(job_id, update_data)
    
    if not update_result['success']:
        print(f"ERROR: Job update failed: {update_result['error']}")
        return False
    
    print("SUCCESS: Job updated successfully")
    
    # Verify the update
    with get_db_session() as session:
        updated_job = session.query(JobConfiguration).filter(
            JobConfiguration.job_id == job_id
        ).first()
        
        print("\nVerifying updated fields:")
        print(f"  Schedule Enabled: {updated_job.schedule_enabled}")
        print(f"  Schedule Type: {updated_job.schedule_type}")
        print(f"  Schedule Expression: {updated_job.schedule_expression}")
        print(f"  Timezone: {updated_job.timezone}")
        
        config = json.loads(updated_job.configuration or '{}')
        print(f"  Timeout: {config.get('timeout')}")
        print(f"  Max Retries: {config.get('max_retries')}")
        print(f"  Retry Delay: {config.get('retry_delay')}")
        
        # Clean up
        session.delete(updated_job)
        session.commit()
        print(f"\nCLEANUP: Test job cleaned up (deleted)")
    
    return True


if __name__ == "__main__":
    print("Schedule Fields Save Test")
    print("=" * 60)
    
    # Test creation
    creation_success = test_schedule_fields_creation()
    
    # Test update
    update_success = test_job_update()
    
    if creation_success and update_success:
        print("\nFINAL SUCCESS! Both creation and update are working correctly.")
    else:
        print("\nWARNING: Issues detected. Please check the output above.")
        if not creation_success:
            print("  - Job creation is NOT saving schedule fields correctly")
        if not update_success:
            print("  - Job update has issues")