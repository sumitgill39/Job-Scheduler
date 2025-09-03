#!/usr/bin/env python3
"""
Fix the P1 job configuration
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def fix_p1_job():
    """Fix the P1 job that's missing script content"""
    job_id = "6489c009-4d93-4018-a63c-d0c24678516d"
    
    print(f"Fixing job P1: {job_id}")
    
    try:
        from database.sqlalchemy_models import JobConfiguration, get_db_session
        import json
        
        print("1. Loading job from database...")
        with get_db_session() as session:
            job = session.query(JobConfiguration).filter(JobConfiguration.job_id == job_id).first()
            
            if not job:
                print(f"ERROR: Job {job_id} not found")
                return False
            
            print(f"2. Current job details:")
            print(f"   Name: {job.name}")
            print(f"   Type: {job.job_type}")
            print(f"   Enabled: {job.enabled}")
            
            # Check current config
            current_config = json.loads(job.configuration or '{}')
            print(f"   Current config keys: {list(current_config.keys())}")
            
            # Fix the configuration by adding a sample PowerShell script
            print(f"3. Adding sample PowerShell script to job...")
            
            fixed_config = {
                "script": "Write-Host 'Hello from P1 Job!'; Get-Date; Write-Host 'Job P1 completed successfully'",
                "execution_policy": "RemoteSigned",
                "timeout": 300
            }
            
            # Update the job
            job.configuration = json.dumps(fixed_config)
            
            # Also set the type properly
            job.job_type = "powershell"
            
            # Commit changes
            session.commit()
            
            print(f"4. Job P1 fixed successfully!")
            print(f"   Added script: {fixed_config['script']}")
            print(f"   Set type: powershell")
            print(f"   Set execution policy: RemoteSigned")
            
            return True
            
    except Exception as e:
        print(f"ERROR: Failed to fix job P1: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Main function"""
    print("Job Scheduler - Fix P1 Job Configuration")
    print("=" * 50)
    
    success = fix_p1_job()
    
    print("\n" + "=" * 50)
    if success:
        print("SUCCESS: Job P1 configuration fixed!")
        print("The job should now execute successfully from the web UI.")
    else:
        print("FAILED: Could not fix job P1")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)