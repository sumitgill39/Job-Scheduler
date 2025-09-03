#!/usr/bin/env python3
"""
Create sample V2 executions to populate the execution history
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

async def create_sample_executions():
    """Create several sample V2 executions for testing"""
    print("Creating sample V2 executions...")
    
    try:
        from core.v2.data_models import create_simple_sql_job, create_simple_powershell_job
        from core.v2.execution_engine import get_execution_engine, initialize_execution_engine
        
        print("1. Initializing V2 execution engine...")
        engine = await initialize_execution_engine()
        
        # Sample job definitions
        sample_jobs = [
            {
                "type": "sql",
                "name": "Daily Report Query",
                "content": "SELECT COUNT(*) as total_records, MAX(created_date) as latest_record FROM information_schema.tables",
                "timezone": "UTC"
            },
            {
                "type": "powershell", 
                "name": "System Health Check",
                "content": "Get-Date; Get-ComputerInfo | Select-Object WindowsProductName, TotalPhysicalMemory; Get-Process | Select-Object -First 5 Name, CPU",
                "timezone": "America/New_York"
            },
            {
                "type": "sql",
                "name": "Database Statistics",
                "content": "SELECT name, database_id, create_date FROM sys.databases ORDER BY name",
                "timezone": "Europe/London"
            },
            {
                "type": "powershell",
                "name": "Disk Space Report", 
                "content": "Get-WmiObject -Class Win32_LogicalDisk | Select-Object DeviceID, Size, FreeSpace | Format-Table",
                "timezone": "UTC"
            },
            {
                "type": "sql",
                "name": "Server Information",
                "content": "SELECT @@SERVERNAME as server_name, @@VERSION as sql_version, GETDATE() as current_time",
                "timezone": "UTC"
            }
        ]
        
        print(f"2. Creating {len(sample_jobs)} sample executions...")
        
        results = []
        for i, job_def in enumerate(sample_jobs, 1):
            print(f"   Executing job {i}/{len(sample_jobs)}: {job_def['name']}")
            
            try:
                # Create job based on type
                if job_def["type"] == "sql":
                    job = create_simple_sql_job(
                        name=job_def["name"],
                        query=job_def["content"],
                        connection_name="default",
                        timezone=job_def["timezone"]
                    )
                elif job_def["type"] == "powershell":
                    job = create_simple_powershell_job(
                        name=job_def["name"],
                        script=job_def["content"],
                        timezone=job_def["timezone"]
                    )
                
                # Execute the job
                result = await engine.execute_job_immediately(job)
                
                print(f"     Status: {result.status.value}, Duration: {result.duration_seconds:.2f}s")
                results.append({
                    "name": job_def["name"],
                    "type": job_def["type"], 
                    "timezone": job_def["timezone"],
                    "status": result.status.value,
                    "duration": result.duration_seconds,
                    "execution_id": result.execution_id
                })
                
                # Small delay between executions
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"     ERROR: {str(e)}")
                results.append({
                    "name": job_def["name"],
                    "type": job_def["type"],
                    "timezone": job_def["timezone"],
                    "status": "error",
                    "error": str(e)
                })
        
        print(f"\n3. Execution Summary:")
        print("-" * 60)
        successful = 0
        for result in results:
            status_icon = "✓" if result.get("status") == "success" else "✗"
            timezone = result.get("timezone", "UTC")
            duration = result.get("duration", 0)
            
            print(f"   {status_icon} {result['name']} [{result['type'].upper()}]")
            print(f"     Timezone: {timezone}, Duration: {duration:.2f}s")
            
            if result.get("status") == "success":
                successful += 1
        
        print(f"\nRESULT: {successful}/{len(sample_jobs)} executions completed successfully")
        
        # Wait a moment for database writes
        await asyncio.sleep(2)
        
        # Check database
        print("\n4. Verifying database records...")
        from core.job_manager import JobManager
        job_manager = JobManager()
        history = job_manager.get_all_execution_history(limit=20)
        
        v2_records = []
        for execution in history:
            metadata = execution.get('execution_metadata')
            if metadata:
                try:
                    import json
                    meta_data = json.loads(metadata)
                    if meta_data.get('timezone') and meta_data.get('execution_id'):
                        v2_records.append(execution)
                except:
                    pass
        
        print(f"   Found {len(v2_records)} V2 records in database")
        
        if len(v2_records) > 0:
            print("   Recent V2 executions:")
            for record in v2_records[:5]:
                name = record.get('job_name')
                status = record.get('status')
                duration = record.get('duration_seconds')
                print(f"     - {name}: {status} ({duration:.2f}s)")
        
        return len(v2_records) > 0
        
    except Exception as e:
        print(f"ERROR: Failed to create sample executions: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main function"""
    print("V2 Sample Execution Generator")
    print("=" * 50)
    
    success = await create_sample_executions()
    
    print("\n" + "=" * 50)
    if success:
        print("SUCCESS: Sample executions created and saved to database!")
        print("Check the Execution History page to see them.")
        print("\nThe executions include:")
        print("- SQL queries across multiple timezones")
        print("- PowerShell scripts with system information")
        print("- Detailed execution metadata and step results")
    else:
        print("FAILED: Could not create sample executions")
    
    return success

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    success = asyncio.run(main())
    sys.exit(0 if success else 1)