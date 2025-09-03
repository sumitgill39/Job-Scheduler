#!/usr/bin/env python3
"""
Debug the specific failing job from web UI
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def debug_failing_job():
    """Debug the job that's failing in web UI"""
    job_id = "6489c009-4d93-4018-a63c-d0c24678516d"
    
    print(f"Debugging failing job: {job_id}")
    
    try:
        from core.job_manager import JobManager
        
        print("1. Loading job manager...")
        job_manager = JobManager()
        
        print("2. Fetching job data...")
        job_data = job_manager.get_job(job_id)
        
        if not job_data:
            print(f"ERROR: Job {job_id} not found in database")
            return False
        
        print("3. Job data found:")
        print(f"   Name: {job_data.get('name', 'Unknown')}")
        print(f"   Type: {job_data.get('type', 'Unknown')}")
        print(f"   Enabled: {job_data.get('enabled', 'Unknown')}")
        print(f"   Created: {job_data.get('created_at', 'Unknown')}")
        
        # Check job configuration
        config = job_data.get('config', {})
        print(f"\n4. Job configuration:")
        for key, value in config.items():
            if key == 'script' and value:
                print(f"   {key}: {value[:100]}..." if len(str(value)) > 100 else f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")
        
        # Test V2 conversion
        print(f"\n5. Testing V2 conversion...")
        from core.v2.data_models import create_job_from_legacy
        
        try:
            v2_job = create_job_from_legacy(job_data)
            print(f"   V2 Job ID: {v2_job.job_id}")
            print(f"   V2 Job Name: {v2_job.job_name}")
            print(f"   V2 Timezone: {v2_job.timezone}")
            print(f"   V2 Steps: {len(v2_job.steps)}")
            
            # Check step configurations
            for i, step in enumerate(v2_job.steps, 1):
                print(f"   Step {i}: {step.step_name} ({step.step_type})")
                step_config = step.config
                
                # Check PowerShell step configuration specifically
                if step.step_type == "powershell":
                    has_script = bool(step_config.get('script'))
                    has_script_path = bool(step_config.get('script_path'))
                    print(f"     Has script: {has_script}")
                    print(f"     Has script_path: {has_script_path}")
                    
                    if not has_script and not has_script_path:
                        print(f"     [ERROR] ISSUE FOUND: PowerShell step missing both script and script_path!")
                        print(f"     Config keys: {list(step_config.keys())}")
                        
                        # Show the actual config content
                        for config_key, config_value in step_config.items():
                            if isinstance(config_value, str) and len(config_value) > 100:
                                print(f"     {config_key}: {config_value[:100]}...")
                            else:
                                print(f"     {config_key}: {config_value}")
                    else:
                        print(f"     ✓ PowerShell step configuration looks good")
            
            return True
            
        except Exception as conversion_error:
            print(f"   ERROR during V2 conversion: {conversion_error}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            return False
            
    except Exception as e:
        print(f"ERROR: Debug failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def main():
    """Main function"""
    print("Job Scheduler - Debug Failing Job")
    print("=" * 50)
    
    success = debug_failing_job()
    
    print("\n" + "=" * 50)
    if success:
        print("DEBUG COMPLETE: Found job configuration details")
    else:
        print("DEBUG FAILED: Could not analyze job")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)