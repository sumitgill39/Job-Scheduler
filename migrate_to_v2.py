#!/usr/bin/env python3
"""
Migration utility to convert V1 jobs to V2 YAML format
"""

import sys
import os
import yaml
import json

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.sqlalchemy_models import get_db_session, JobConfiguration, init_database
from core.job_manager import JobManager
from utils.logger import get_logger

logger = get_logger(__name__)

def migrate_job_to_v2(v1_job: JobConfiguration) -> str:
    """Convert a V1 job to V2 YAML format"""
    
    try:
        # Parse V1 configuration
        config = {}
        if v1_job.configuration:
            try:
                config = json.loads(v1_job.configuration)
            except json.JSONDecodeError:
                config = {}
        
        # Build V2 YAML configuration
        v2_config = {
            'id': v1_job.name.replace(' ', '-').replace('_', '-').upper(),
            'name': v1_job.name,
            'type': v1_job.job_type.title(),
            'enabled': v1_job.enabled
        }
        
        # Add job-specific configuration
        if v1_job.job_type == 'powershell':
            # PowerShell job
            script_content = (
                config.get('script_content') or 
                config.get('script') or 
                ''
            )
            
            script_path = config.get('script_path', '')
            
            if script_content:
                v2_config.update({
                    'executionMode': 'inline',
                    'inlineScript': script_content
                })
            elif script_path:
                v2_config.update({
                    'executionMode': 'script',
                    'scriptPath': script_path
                })
            else:
                # Default empty script
                v2_config.update({
                    'executionMode': 'inline',
                    'inlineScript': '# Migrated job - please add your PowerShell script here\nWrite-Host "Job migrated from V1"'
                })
            
            # Add PowerShell-specific settings
            if config.get('execution_policy'):
                v2_config['executionPolicy'] = config['execution_policy']
            
            if config.get('working_directory'):
                v2_config['workingDirectory'] = config['working_directory']
            
            # Convert parameters
            parameters = config.get('parameters', [])
            if parameters:
                v2_config['parameters'] = parameters
        
        elif v1_job.job_type == 'sql':
            # SQL job
            query = (
                config.get('sql_query') or 
                config.get('query') or 
                '-- Migrated job - please add your SQL query here\nSELECT GETDATE() AS current_time;'
            )
            
            v2_config.update({
                'query': query,
                'connection': config.get('connection_name', 'default')
            })
        
        # Add common settings
        timeout = config.get('timeout', 300)
        v2_config['timeout'] = timeout
        
        # Add scheduling if configured
        if v1_job.schedule_enabled and v1_job.schedule_expression:
            schedule_config = {
                'type': v1_job.schedule_type or 'cron',
                'timezone': v1_job.timezone or 'UTC'
            }
            
            if v1_job.schedule_type == 'cron':
                schedule_config['expression'] = v1_job.schedule_expression
            else:
                schedule_config['expression'] = v1_job.schedule_expression
            
            v2_config['schedule'] = schedule_config
        
        # Add retry policy with defaults
        v2_config['retryPolicy'] = {
            'maxRetries': config.get('max_retries', 3),
            'retryDelay': config.get('retry_delay', 30)
        }
        
        # Add metadata
        v2_config['metadata'] = {
            'migratedFrom': 'v1',
            'originalJobId': v1_job.job_id,
            'migrationDate': '2025-09-03T00:00:00Z',
            'originalCreatedDate': v1_job.created_date.isoformat() if v1_job.created_date else None
        }
        
        # Convert to YAML
        yaml_content = yaml.dump(v2_config, default_flow_style=False, allow_unicode=True)
        
        return yaml_content
        
    except Exception as e:
        logger.error(f"Error migrating job {v1_job.job_id}: {e}")
        raise

def migrate_all_jobs():
    """Migrate all V1 jobs to V2 format"""
    
    print("Job Migration V1 to V2")
    print("=" * 50)
    
    try:
        # Initialize database to ensure V2 tables exist
        print("Initializing database...")
        init_result = init_database()
        if not init_result['success']:
            print(f"[ERROR] Database initialization failed: {init_result.get('error')}")
            return False
        
        # Initialize V2 job manager
        job_manager = JobManager()
        
        # Get all V1 jobs
        with get_db_session() as session:
            v1_jobs = session.query(JobConfiguration).all()
            
            if not v1_jobs:
                print("[INFO] No V1 jobs found to migrate")
                return True
            
            print(f"[INFO] Found {len(v1_jobs)} V1 jobs to migrate")
            
            migrated_count = 0
            failed_count = 0
            
            for job in v1_jobs:
                try:
                    print(f"\n[MIGRATE] Migrating job: {job.name}")
                    
                    # Convert to V2 YAML
                    yaml_config = migrate_job_to_v2(job)
                    
                    # Create V2 job
                    job_definition = {
                        'name': f"{job.name} (V2)",
                        'description': f"Migrated from V1 job: {job.name}",
                        'yaml_config': yaml_config,
                        'enabled': job.enabled
                    }
                    
                    result = job_manager.create_job(job_definition)
                    
                    if result['success']:
                        print(f"   [SUCCESS] Successfully migrated to V2 job: {result['job_id']}")
                        migrated_count += 1
                        
                        # Show YAML preview (first 10 lines)
                        yaml_lines = yaml_config.split('\n')[:10]
                        print("   [PREVIEW] YAML Preview:")
                        for line in yaml_lines:
                            print(f"   {line}")
                        if len(yaml_config.split('\n')) > 10:
                            print("   ...")
                    else:
                        print(f"   [ERROR] Migration failed: {result['error']}")
                        failed_count += 1
                
                except Exception as e:
                    print(f"   [ERROR] Migration error: {e}")
                    failed_count += 1
            
            print(f"\n[SUMMARY] Migration Summary:")
            print(f"   [SUCCESS] Successfully migrated: {migrated_count}")
            print(f"   [ERROR] Failed migrations: {failed_count}")
            print(f"   [INFO] Total processed: {len(v1_jobs)}")
            
            if migrated_count > 0:
                print(f"\n[SUCCESS] Migration completed! {migrated_count} jobs are now available in V2 format.")
                print("   You can view them in the admin panel under V2 jobs.")
            
            return failed_count == 0
    
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_sample_jobs():
    """Create sample V2 jobs for testing"""
    
    print("\nCreating Sample V2 Jobs")
    print("=" * 30)
    
    job_manager = JobManager()
    
    # Sample PowerShell job
    powershell_yaml = """
id: "PS-SAMPLE-001"
name: "System Health Check"
type: "PowerShell"
executionMode: "inline"
inlineScript: |
  # PowerShell system health check
  Write-Host "=== System Health Check Started ===" -ForegroundColor Green
  
  # Get top 10 processes by CPU usage
  Write-Host "`nTop 10 Processes by CPU:" -ForegroundColor Yellow
  Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 | Format-Table Name, CPU, WorkingSet -AutoSize
  
  # Get running services count
  $runningServices = (Get-Service | Where-Object {$_.Status -eq 'Running'}).Count
  Write-Host "`nRunning Services: $runningServices" -ForegroundColor Cyan
  
  # Get disk space
  Write-Host "`nDisk Space:" -ForegroundColor Yellow
  Get-WmiObject -Class Win32_LogicalDisk | Select-Object DeviceID, 
    @{Name="Size(GB)";Expression={[math]::Round($_.Size/1GB,2)}},
    @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}},
    @{Name="PercentFree";Expression={[math]::Round(($_.FreeSpace/$_.Size)*100,2)}} | Format-Table
  
  Write-Host "=== System Health Check Completed ===" -ForegroundColor Green
enabled: true
timeout: 300
retryPolicy:
  maxRetries: 3
  retryDelay: 30
schedule:
  type: "cron"
  expression: "0 */6 * * *"  # Every 6 hours
  timezone: "UTC"
metadata:
  category: "system-monitoring"
  tags: ["health-check", "monitoring", "system"]
"""
    
    # Sample SQL job
    sql_yaml = """
id: "SQL-SAMPLE-001"
name: "Database Statistics Report"
type: "SQL"
query: |
  -- Database statistics and health report
  SELECT 
      'Database Statistics' as ReportType,
      GETDATE() as GeneratedAt;
  
  -- Table statistics
  SELECT 
      t.name as TableName,
      p.rows as RowCount,
      CAST(ROUND(((SUM(a.total_pages) * 8) / 1024.00), 2) AS DECIMAL(36,2)) as SizeMB
  FROM sys.tables t
  INNER JOIN sys.indexes i ON t.object_id = i.object_id
  INNER JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
  INNER JOIN sys.allocation_units a ON p.partition_id = a.container_id
  WHERE t.name NOT LIKE 'dt%' AND t.is_ms_shipped = 0 AND i.object_id > 255
  GROUP BY t.name, p.rows
  ORDER BY SizeMB DESC;
  
  -- Recent job executions summary
  SELECT 
      TOP 10
      job_name,
      status,
      start_time,
      duration_seconds
  FROM job_execution_history 
  ORDER BY start_time DESC;
connection: "default"
enabled: true
timeout: 600
retryPolicy:
  maxRetries: 2
  retryDelay: 60
schedule:
  type: "cron"
  expression: "0 8 * * 1"  # Monday at 8 AM
  timezone: "UTC"
metadata:
  category: "database-maintenance"
  tags: ["statistics", "reporting", "maintenance"]
"""
    
    # Create sample jobs
    samples = [
        {
            'name': 'System Health Check (Sample)',
            'description': 'Sample PowerShell job for system monitoring',
            'yaml_config': powershell_yaml.strip(),
            'enabled': True
        },
        {
            'name': 'Database Statistics Report (Sample)', 
            'description': 'Sample SQL job for database reporting',
            'yaml_config': sql_yaml.strip(),
            'enabled': True
        }
    ]
    
    created_count = 0
    for sample in samples:
        try:
            result = job_manager.create_job(sample)
            if result['success']:
                print(f"[SUCCESS] Created sample job: {sample['name']}")
                created_count += 1
            else:
                print(f"[ERROR] Failed to create {sample['name']}: {result['error']}")
        except Exception as e:
            print(f"[ERROR] Error creating {sample['name']}: {e}")
    
    print(f"\n[SUMMARY] Created {created_count} sample V2 jobs")
    return created_count > 0

if __name__ == "__main__":
    print("Job Scheduler - Migration to V2 Format")
    print("=" * 60)
    
    # Ask user what to do
    print("Options:")
    print("1. Migrate existing V1 jobs to V2 format")
    print("2. Create sample V2 jobs")
    print("3. Both migrate and create samples")
    
    choice = input("\nEnter your choice (1-3): ").strip()
    
    success = True
    
    if choice in ['1', '3']:
        success = migrate_all_jobs() and success
    
    if choice in ['2', '3']:
        success = create_sample_jobs() and success
    
    if choice not in ['1', '2', '3']:
        print("Invalid choice. Please run again and select 1, 2, or 3.")
        sys.exit(1)
    
    if success:
        print("\n[SUCCESS] Operation completed successfully!")
    else:
        print("\n[ERROR] Operation completed with errors.")
        sys.exit(1)