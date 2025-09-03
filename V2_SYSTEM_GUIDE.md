# Job Scheduler V2 System Guide

## Overview

The Job Scheduler V2 system introduces a **YAML-based job configuration format** that provides more structured, readable, and maintainable job definitions. This new system runs **independently** of the original V1 system and provides a simplified, reliable execution engine.

## Key Features ✨

### 🎯 **YAML Configuration Format**
- Human-readable job definitions
- Structured configuration with validation
- Support for inline scripts and script files
- Built-in retry policies and scheduling

### 🚀 **Simplified Execution Engine**
- Direct PowerShell and SQL execution
- No complex V2 execution engine dependencies
- Comprehensive logging and error handling
- Performance metrics and statistics

### 📊 **Enhanced Database Schema**
- Dedicated V2 tables (`job_configurations_v2`, `job_execution_history_v2`)
- Built-in performance tracking
- Detailed execution history with step results
- Success rate calculations

### 🔄 **Migration Support**
- Automated migration from V1 to V2 format
- Sample job templates
- Backwards compatibility

## Database Schema

### New Tables Created:

```sql
-- V2 Job Configuration Table
job_configurations_v2:
  - job_id (UUID)
  - name, description, version
  - yaml_configuration (YAML text)
  - enabled, created_date, modified_date
  - Performance tracking fields
  - Execution statistics

-- V2 Execution History Table  
job_execution_history_v2:
  - execution_id (UUID)
  - job_id, job_name, status
  - start_time, end_time, duration_seconds
  - output_log, error_message, return_code
  - step_results (JSON), execution_context
  - Performance metrics (memory, CPU)
```

## YAML Configuration Format

### PowerShell Job Example:
```yaml
id: "PS-001"
name: "System Health Check Script"
type: "PowerShell"
executionMode: "inline"  # or "script"
inlineScript: |
  # PowerShell inline script
  Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
  Get-Service | Where-Object {$_.Status -eq 'Running'}
  Write-Host "System check completed at $(Get-Date)"
enabled: true
timeout: 300  # seconds
schedule:
  type: "cron"
  expression: "0 */6 * * *"  # Every 6 hours
  timezone: "UTC"
retryPolicy:
  maxRetries: 3
  retryDelay: 30
parameters:
  - name: "LogLevel"
    value: "Info"
metadata:
  category: "system-monitoring"
  tags: ["health", "monitoring"]
```

### SQL Job Example:
```yaml
id: "SQL-001"
name: "Database Maintenance Query"
type: "SQL"
query: |
  -- Database maintenance query
  UPDATE STATISTICS dbo.job_configurations;
  DBCC CHECKDB('sreutil') WITH NO_INFOMSGS;
  SELECT table_name, row_count FROM sys.tables;
connection: "default"
enabled: true
timeout: 600
schedule:
  type: "cron"
  expression: "0 2 * * 0"  # Sunday at 2 AM
  timezone: "UTC"
retryPolicy:
  maxRetries: 2
  retryDelay: 60
```

## API Endpoints

### V2 Job Management:
```http
GET    /api/v2/jobs                 # List all V2 jobs
POST   /api/v2/jobs                 # Create new V2 job
GET    /api/v2/jobs/{id}            # Get V2 job details
PUT    /api/v2/jobs/{id}            # Update V2 job
DELETE /api/v2/jobs/{id}            # Delete V2 job
POST   /api/v2/jobs/{id}/run        # Execute V2 job immediately
GET    /api/v2/jobs/{id}/history    # Get execution history
GET    /api/v2/jobs/samples         # Get sample YAML configs
```

## Getting Started

### 1. **Initialize V2 System**
```bash
# Test the V2 system
python test_v2_system.py

# Run database migration
python migrate_to_v2.py
```

### 2. **Create Your First V2 Job**
```python
# Using API
import requests
import yaml

job_config = {
    'id': 'MY-JOB-001',
    'name': 'My First V2 Job',
    'type': 'PowerShell',
    'executionMode': 'inline',
    'inlineScript': 'Write-Host "Hello V2 World!"',
    'enabled': True,
    'timeout': 60
}

yaml_config = yaml.dump(job_config)

response = requests.post('/api/v2/jobs', json={
    'name': 'My First V2 Job',
    'description': 'Testing V2 system',
    'yaml_config': yaml_config,
    'enabled': True
})
```

### 3. **Execute Jobs**
```python
# Execute immediately
response = requests.post(f'/api/v2/jobs/{job_id}/run')
result = response.json()

print(f"Success: {result['success']}")
print(f"Status: {result['status']}")
print(f"Duration: {result['duration_seconds']}s")
print(f"Output: {result['output']}")
```

## Migration Process

### Automated Migration:
```bash
python migrate_to_v2.py
```

**Options:**
1. **Migrate existing V1 jobs** - Converts all V1 jobs to V2 YAML format
2. **Create sample V2 jobs** - Adds example jobs for testing
3. **Both migrate and create samples**

### Migration Features:
- ✅ **Automatic YAML conversion** from V1 JSON configuration
- ✅ **Schedule preservation** - Keeps existing cron schedules
- ✅ **Parameter mapping** - Converts PowerShell parameters
- ✅ **Metadata retention** - Preserves creation dates and job IDs
- ✅ **Safe migration** - Creates new jobs without deleting V1 jobs

## V2 System Benefits

### 🎯 **Reliability**
- **Simplified execution** - Direct script execution without complex dependencies
- **Better error handling** - Comprehensive logging and error reporting
- **Timeout management** - Proper process timeout and cleanup
- **Resource tracking** - Memory and CPU usage monitoring

### 📊 **Observability**
- **Detailed execution history** - Step-by-step execution tracking
- **Performance metrics** - Success rates, average durations
- **Rich logging** - Full output capture with timestamps
- **Execution context** - System info, user, timezone

### 🔧 **Maintainability**
- **YAML format** - Human-readable, version-controllable
- **Validation** - Schema validation for job configurations
- **Migration tools** - Easy conversion from V1
- **API-first design** - RESTful API for all operations

### 🚀 **Scalability**
- **Independent execution** - No complex execution engine dependencies
- **Database optimization** - Indexed tables for fast queries  
- **Async execution** - Non-blocking job execution
- **Resource management** - Process cleanup and monitoring

## Testing Your Jobs

### 1. **Create Test Job:**
```bash
python test_v2_system.py
```

### 2. **Manual Testing:**
```python
from core.job_manager import JobManager
from core.job_executor import JobExecutor

# Create job
manager = JobManager()
executor = JobExecutor()

# Execute synchronously (unified executor handles both V1 and V2)
result = executor.execute_job(job_id)
print(f"Job executed: {result['success']}")
```

### 3. **API Testing:**
```bash
# Get sample configurations
curl http://localhost:5000/api/v2/jobs/samples

# Create job
curl -X POST http://localhost:5000/api/v2/jobs \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Job", "yaml_config": "..."}'

# Run job  
curl -X POST http://localhost:5000/api/v2/jobs/{job-id}/run
```

## Troubleshooting

### Common Issues:

**1. YAML Validation Errors:**
```yaml
# ❌ Wrong format
executionMode: inline  # Missing quotes for string values
inlineScript: Write-Host "test"  # Should use | for multi-line

# ✅ Correct format  
executionMode: "inline"
inlineScript: |
  Write-Host "test"
```

**2. PowerShell Execution Errors:**
- Check `timeout` value (default: 300 seconds)
- Verify `executionPolicy` setting
- Ensure script syntax is valid
- Check working directory permissions

**3. SQL Connection Issues:**
- Verify `connection` name exists
- Check database permissions
- Validate SQL syntax
- Monitor timeout settings

### Debug Mode:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show detailed execution logs
executor.execute_job_sync(job_id)
```

## Summary

The V2 system provides a **robust, reliable, and maintainable** job execution platform with:

- ✅ **YAML-based configuration** for better readability
- ✅ **Simplified execution engine** for reliability  
- ✅ **Enhanced database schema** for better performance
- ✅ **Comprehensive API** for automation
- ✅ **Migration tools** for easy adoption
- ✅ **Rich monitoring** and execution history

**The V2 system is production-ready and provides a solid foundation for reliable job execution.**