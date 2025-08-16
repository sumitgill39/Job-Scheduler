# PowerShell Job Database Saving Issues - Troubleshooting Guide

## Problem: PowerShell Jobs Not Saving to Database

If PowerShell jobs are failing to save to the `job_configurations` table, follow this troubleshooting guide.

## 1. Check Database Connectivity

### Test Database Connection
```bash
cd "Job Scheduler"
python test_connection_system.py
```

Expected output:
```
✅ Database connection successful
✅ System database 'sreutil' is accessible
✅ Tables exist: job_configurations, job_execution_history
```

If connection fails, check:

### A. SQL Server Service Status
```powershell
Get-Service -Name "*SQL*" | Where-Object {$_.Status -eq "Running"}
```

### B. SQL Server Configuration
- **Server**: `USDF11DB197\PROD_DB01`
- **Port**: `3433`
- **Database**: `sreutil`
- **Username**: `svc-devops`
- **Password**: `Welcome@1234`

### C. Network Connectivity
```powershell
Test-NetConnection -ComputerName "USDF11DB197" -Port 3433
```

## 2. Verify Database Schema

### Check if Tables Exist
```sql
USE sreutil;
GO

-- Check if job_configurations table exists
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_NAME = 'job_configurations';

-- Check table structure
SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_configurations';
```

### Expected Table Structure
```sql
CREATE TABLE [dbo].[job_configurations] (
    [job_id] NVARCHAR(50) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [job_type] NVARCHAR(50) NOT NULL,
    [configuration] NTEXT NOT NULL,
    [enabled] BIT DEFAULT 1,
    [created_date] DATETIME DEFAULT GETDATE(),
    [modified_date] DATETIME DEFAULT GETDATE(),
    [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER
);
```

## 3. Debug PowerShell Job Saving Process

### Enable Debug Logging
Add to `config/database_config.yaml`:
```yaml
logging:
  level: DEBUG
  log_sql_queries: true
```

### Test PowerShell Job Creation
```python
from core.job_manager import JobManager

job_manager = JobManager()

test_job = {
    'name': 'Debug PowerShell Test',
    'description': 'Test PowerShell job for debugging',
    'type': 'powershell',
    'enabled': True,
    'script_content': 'Write-Host "Debug test"',
    'execution_policy': 'RemoteSigned',
    'parameters': [],
    'timeout': 300,
    'max_retries': 3,
    'retry_delay': 60
}

result = job_manager.create_job(test_job)
print(f"Result: {result}")
```

### Check Logs
Look for these log entries:
```
[JOB_MANAGER] Creating powershell job 'Debug PowerShell Test'
[JOB_MANAGER] PowerShell config created: {...}
[JOB_MANAGER] Configuration JSON being saved to database:
[JOB_MANAGER] Successfully created job 'Debug PowerShell Test' with ID: xxx
```

## 4. Common Issues and Solutions

### Issue A: "pyodbc not available"
**Solution**: Install SQL Server drivers
```bash
# Download Microsoft ODBC Driver 17 for SQL Server
# Install from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

pip install pyodbc
```

### Issue B: "Connection timeout"
**Solution**: Check network and firewall
```powershell
# Check if SQL Server is listening on port 3433
netstat -an | findstr :3433

# Test telnet connectivity
telnet USDF11DB197 3433
```

### Issue C: "Authentication failed"
**Solution**: Verify SQL Server authentication
```sql
-- Check if SQL Server authentication is enabled
SELECT SERVERPROPERTY('IsIntegratedSecurityOnly') as AuthenticationMode;
-- 0 = Mixed Mode (SQL Server and Windows)
-- 1 = Windows Authentication only

-- Check if user exists
SELECT name FROM sys.sql_logins WHERE name = 'svc-devops';

-- Check user permissions
SELECT 
    p.permission_name,
    p.state_desc,
    dp.name as principal_name
FROM sys.database_permissions p
JOIN sys.database_principals dp ON p.grantee_principal_id = dp.principal_id
WHERE dp.name = 'svc-devops';
```

### Issue D: "Invalid object name 'job_configurations'"
**Solution**: Run database setup script
```bash
cd "Job Scheduler"
sqlcmd -S "USDF11DB197\PROD_DB01,3433" -d "sreutil" -U "svc-devops" -P "Welcome@1234" -i database_setup.sql
```

## 5. Manual Database Test

### Test Direct SQL Insert
```sql
USE sreutil;
GO

-- Test manual insert
INSERT INTO job_configurations 
(job_id, name, job_type, configuration, enabled, created_date, created_by)
VALUES 
(
    'test-ps-001',
    'Manual Test PowerShell Job',
    'powershell',
    '{"basic":{"timeout":300,"max_retries":3,"retry_delay":60,"run_as":""},"powershell":{"script_content":"Write-Host \\"Manual test\\"","script_path":"","execution_policy":"RemoteSigned","working_directory":"","parameters":[]}}',
    1,
    GETDATE(),
    'manual_test'
);

-- Verify insert
SELECT * FROM job_configurations WHERE job_id = 'test-ps-001';
```

## 6. Production Deployment Checklist

### Before Deploying:
- [ ] SQL Server is running and accessible
- [ ] Database `sreutil` exists
- [ ] User `svc-devops` has appropriate permissions
- [ ] Tables are created (run `database_setup.sql`)
- [ ] Network connectivity is working (port 3433)
- [ ] Python dependencies are installed (`pip install -r requirements.txt`)

### Test Commands:
```bash
# 1. Test database connectivity
python test_connection_system.py

# 2. Test job creation
python -c "
from core.job_manager import JobManager
jm = JobManager()
result = jm.create_job({
    'name': 'Production Test',
    'type': 'powershell', 
    'script_content': 'Write-Host \"Production test\"',
    'enabled': True
})
print(result)
"

# 3. Start the application
python main.py
```

## 7. Alternative Solution: Local Database

If the main database server is unavailable, you can use SQL Server Express locally:

### Install SQL Server Express
1. Download SQL Server Express
2. Create database `sreutil`
3. Update `config/database_config.yaml`:

```yaml
databases:
  system:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost\\SQLEXPRESS"
    database: "sreutil"
    trusted_connection: true  # Use Windows authentication
    connection_timeout: 30
    command_timeout: 300
```

This guide should help resolve PowerShell job saving issues in the production environment.