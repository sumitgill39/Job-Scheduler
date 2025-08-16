# Windows Production Deployment Guide

## PowerShell Job Execution Environment Setup

This guide provides deployment instructions for running the Job Scheduler in a Windows environment where PowerShell jobs can execute properly.

## Prerequisites

### 1. Windows Environment Requirements
- **Operating System**: Windows Server 2016+ or Windows 10+
- **PowerShell**: Version 5.1 or later (pre-installed on modern Windows)
- **Python**: Version 3.8+ with pip
- **SQL Server**: Instance accessible from the deployment machine

### 2. Verify PowerShell Availability
```powershell
# Check PowerShell version
$PSVersionTable.PSVersion

# Test PowerShell execution policy
Get-ExecutionPolicy

# Set execution policy if needed (run as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

## Deployment Steps

### Step 1: Environment Setup

```powershell
# Clone repository (if not already done)
git clone https://github.com/your-org/Job-Scheduler.git
cd "Job Scheduler"

# Create Python virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install Python dependencies
pip install -r requirements.txt

# Install SQL Server ODBC Driver (if not installed)
# Download from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

### Step 2: Database Configuration

```yaml
# Update config/database_config.yaml with your SQL Server details
databases:
  system:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "YOUR_SQL_SERVER_NAME\\INSTANCE"
    port: 3433
    database: "sreutil"
    username: "svc-devops"
    password: "YOUR_PASSWORD"
    trusted_connection: false
    connection_timeout: 30
    command_timeout: 300
```

### Step 3: Database Setup

```powershell
# Test database connectivity
python test_connection_system.py

# Run database setup (if tables don't exist)
sqlcmd -S "YOUR_SQL_SERVER\INSTANCE,3433" -d "sreutil" -U "svc-devops" -P "YOUR_PASSWORD" -i database_setup.sql
```

### Step 4: PowerShell Job Validation

```powershell
# Run comprehensive PowerShell validation
python validate_powershell_jobs.py
```

**Expected Results:**
```
📊 Job Creation Test Results: 3/3 passed
🚀 Job Execution Test: PASSED (Windows environment)
📅 Job Scheduling Test: PASSED
🔍 Database Persistence Test: PASSED

🎉 ALL TESTS PASSED!
✅ PowerShell jobs can be created, saved, and executed successfully
✅ Database persistence is working correctly
✅ Job scheduling configuration is properly stored
🚀 PowerShell job system is PRODUCTION READY!
```

### Step 5: Start the Application

```powershell
# Start the Job Scheduler web application
python main.py

# Or run as Windows service (optional)
# See service installation section below
```

## Production Validation Checklist

### ✅ Pre-Deployment Validation

- [ ] **SQL Server Connectivity**
  ```powershell
  python test_connection_system.py
  ```

- [ ] **PowerShell Environment**
  ```powershell
  # Test PowerShell availability
  powershell -Command "Write-Host 'PowerShell is available'"
  
  # Test execution policy
  powershell -Command "Get-ExecutionPolicy"
  ```

- [ ] **Database Schema**
  ```sql
  USE sreutil;
  SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES 
  WHERE TABLE_NAME IN ('job_configurations', 'job_execution_history');
  ```

- [ ] **Python Dependencies**
  ```powershell
  pip list | findstr "pyodbc flask apscheduler"
  ```

### ✅ Post-Deployment Validation

1. **Create Test PowerShell Job**
   ```powershell
   # Use the web UI or API to create a test job
   curl -X POST http://localhost:5000/api/jobs -H "Content-Type: application/json" -d '{
     "name": "Production Test Job",
     "type": "powershell",
     "script_content": "Write-Host \"Production test successful\"; Get-Date",
     "enabled": true
   }'
   ```

2. **Execute Test Job**
   ```powershell
   # Execute the job manually to verify it works
   curl -X POST http://localhost:5000/api/jobs/JOB_ID/run
   ```

3. **Verify Job Logs**
   ```powershell
   # Check execution logs
   curl http://localhost:5000/api/jobs/JOB_ID/logs
   ```

4. **Test Scheduled Execution**
   ```powershell
   # Create a job with a schedule (every 5 minutes for testing)
   curl -X POST http://localhost:5000/api/jobs -H "Content-Type: application/json" -d '{
     "name": "Scheduled Test Job",
     "type": "powershell", 
     "script_content": "Write-Host \"Scheduled execution at $(Get-Date)\"",
     "enabled": true,
     "schedule": {
       "type": "interval",
       "interval_minutes": 5
     }
   }'
   ```

## Windows Service Installation (Optional)

To run the Job Scheduler as a Windows service:

### 1. Install NSSM (Non-Sucking Service Manager)
```powershell
# Download NSSM from https://nssm.cc/download
# Extract to C:\nssm
```

### 2. Create Service
```powershell
# Run as Administrator
C:\nssm\win64\nssm.exe install "JobScheduler"

# Configure service paths:
# Path: C:\Path\To\Job Scheduler\venv\Scripts\python.exe
# Startup directory: C:\Path\To\Job Scheduler
# Arguments: main.py

# Set service to start automatically
C:\nssm\win64\nssm.exe set "JobScheduler" Start SERVICE_AUTO_START

# Start the service
net start JobScheduler
```

## Monitoring and Troubleshooting

### 1. Application Logs
- Location: `logs/job_scheduler.log`
- Monitor for job execution status and errors

### 2. PowerShell Execution Logs
- Check Windows Event Viewer: Windows PowerShell
- Application logs for detailed execution information

### 3. Common Issues

**Issue: PowerShell execution fails**
```powershell
# Check execution policy
Get-ExecutionPolicy -List

# Set policy if needed (as Administrator)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

**Issue: Database connection fails**
```powershell
# Test SQL Server connectivity
sqlcmd -S "SERVER\INSTANCE,PORT" -U "USERNAME" -P "PASSWORD" -Q "SELECT 1"

# Check firewall settings
Test-NetConnection -ComputerName "SQL_SERVER" -Port 3433
```

**Issue: Jobs not executing**
```powershell
# Check scheduler manager logs
grep "SCHEDULER" logs/job_scheduler.log

# Verify job is enabled
curl http://localhost:5000/api/jobs | findstr "enabled"
```

## Performance Optimization

### 1. Database Connection Pooling
- Monitor connection pool usage in logs
- Adjust pool size in configuration if needed

### 2. PowerShell Job Optimization
- Use `-NoProfile` parameter for faster startup
- Avoid loading unnecessary modules
- Set appropriate timeout values

### 3. Logging Configuration
```yaml
# config/logging_config.yaml
logging:
  level: INFO  # Use DEBUG only for troubleshooting
  max_file_size: 50MB
  backup_count: 5
```

## Security Considerations

### 1. PowerShell Execution
- Use specific execution policy (RemoteSigned recommended)
- Validate script content before execution
- Run with least privilege service account

### 2. Database Security
- Use dedicated service account for SQL Server access
- Encrypt connection strings
- Enable SQL Server audit logging

### 3. Web Interface Security
- Configure HTTPS in production
- Implement authentication/authorization
- Use firewall to restrict access

## Production Readiness Checklist

- [ ] PowerShell jobs can be created via web UI
- [ ] PowerShell jobs save to database successfully  
- [ ] PowerShell jobs execute without errors
- [ ] Scheduled PowerShell jobs run automatically
- [ ] Job execution logs are captured and viewable
- [ ] Special characters in scripts are handled correctly
- [ ] Error handling and retries work properly
- [ ] Database connectivity is stable
- [ ] Application runs as Windows service (if required)
- [ ] Monitoring and alerting is configured

## Success Validation

Run this final validation script on the Windows deployment:

```powershell
# Final deployment validation
python validate_production_deployment.py
```

This should report:
```
✅ PowerShell Environment: READY
✅ Database Connectivity: READY  
✅ Job Creation: READY
✅ Job Execution: READY
✅ Job Scheduling: READY
✅ Web Interface: READY

🎉 PRODUCTION DEPLOYMENT SUCCESSFUL!
```

The system is now ready for production use with full PowerShell job execution capabilities.