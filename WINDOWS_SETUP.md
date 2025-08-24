# Windows Setup Guide

This guide covers setting up the Windows Job Scheduler on a Windows system.

## Prerequisites

### 1. Python 3.8 or higher
Download from: https://python.org/downloads/
- Choose "Add Python to PATH" during installation

### 2. SQL Server ODBC Driver 17
Download from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
- Required for database connectivity

### 3. PowerShell (Built-in on Windows)
- Windows PowerShell 5.1 (included with Windows 10/11)
- Or PowerShell 7+ (recommended): https://github.com/PowerShell/PowerShell/releases

## Installation Steps

### 1. Clone the Repository
```cmd
git clone https://github.com/your-repo/job-scheduler.git
cd job-scheduler
```

### 2. Install Python Dependencies
```cmd
pip install -r requirements.txt
```

The requirements.txt includes Windows-specific packages:
- `pywin32` - Windows API access
- `psutil` - System monitoring
- `pyodbc` - SQL Server connectivity

### 3. Configure Database Connection

Create a `.env` file in the project root:

```env
# Database Configuration
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=YOUR_SERVER\INSTANCE_NAME
DB_PORT=3433
DB_DATABASE=your_database
DB_USERNAME=your_username
DB_PASSWORD=your_password
DB_TRUSTED_CONNECTION=false
DB_CONNECTION_TIMEOUT=30
DB_COMMAND_TIMEOUT=300
DB_ENCRYPT=false
DB_TRUST_SERVER_CERTIFICATE=true

# Connection Pool Settings
DB_POOL_MAX_CONNECTIONS=10
DB_POOL_MIN_CONNECTIONS=2
DB_POOL_CONNECTION_LIFETIME=3600

# Retry Settings
DB_MAX_RETRIES=3
DB_RETRY_DELAY=5
DB_BACKOFF_FACTOR=2
```

### 4. Test the Installation
```cmd
python test_windows_connection.py
```

This will verify:
- ✓ Environment configuration loading
- ✓ Database connection string format
- ✓ Windows-specific compatibility
- ✓ PowerShell detection
- ✓ ODBC driver availability

## Running the Application

### Web Interface (Recommended)
```cmd
python main.py --mode web
```
- Opens automatically at: http://127.0.0.1:5000
- Full dashboard with job management
- Real-time execution monitoring

### CLI Interface
```cmd
python main.py --mode cli
```
- Command-line job management
- Interactive job creation/editing

### Both Interfaces
```cmd
python main.py --mode both
```
- Web dashboard + CLI access

## Windows-Specific Features

### 1. PowerShell Job Execution
- Automatic PowerShell detection (5.1 or 7+)
- Support for execution policies
- Windows credential integration
- Working directory management

### 2. SQL Server Integration
- Named instance support (`SERVER\INSTANCE`)
- Windows or SQL Server authentication
- Connection pooling for performance
- Automatic retry with backoff

### 3. Windows Service Integration
- Run as Windows service (optional)
- Event log integration
- Administrator privilege detection

## Database Setup

### Required Tables
The application expects these SQL Server tables:

```sql
-- Job configurations
CREATE TABLE job_configurations (
    job_id UNIQUEIDENTIFIER PRIMARY KEY,
    name NVARCHAR(255) NOT NULL,
    job_type NVARCHAR(50) NOT NULL,
    configuration NVARCHAR(MAX) NOT NULL,
    enabled BIT DEFAULT 1,
    created_date DATETIME2 DEFAULT GETDATE(),
    modified_date DATETIME2,
    created_by NVARCHAR(255) DEFAULT SYSTEM_USER
);

-- Job execution history
CREATE TABLE job_execution_history (
    execution_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    job_id UNIQUEIDENTIFIER NOT NULL,
    job_name NVARCHAR(255) NOT NULL,
    status NVARCHAR(50) NOT NULL,
    start_time DATETIME2 DEFAULT GETDATE(),
    end_time DATETIME2,
    duration_seconds INT,
    output NVARCHAR(MAX),
    error_message NVARCHAR(MAX),
    return_code INT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    metadata NVARCHAR(MAX)
);
```

### Setup Script
Run the database setup:
```cmd
python -c "from database.simple_connection_manager import get_database_manager; get_database_manager().initialize_database()"
```

## Troubleshooting

### Common Issues

#### 1. "ODBC Driver not found"
- Install SQL Server ODBC Driver 17
- Verify with: `odbcad32.exe` (ODBC Data Source Administrator)

#### 2. "PowerShell execution policy error"
- Run as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

#### 3. "Access denied to database"
- Verify SQL Server credentials
- Check firewall settings (port 1433 or custom port)
- Test connection with SQL Server Management Studio

#### 4. "Import error: win32api"
- Install Windows-specific packages:
```cmd
pip install pywin32
python Scripts/pywin32_postinstall.py -install
```

### Verification Commands

Test database connectivity:
```cmd
python -c "from database.simple_connection_manager import get_database_manager; print(get_database_manager().test_connection())"
```

Test PowerShell detection:
```cmd
python -c "from utils.windows_utils import WindowsUtils; print(WindowsUtils().get_powershell_path())"
```

## Security Considerations

### 1. Credentials
- Store credentials in `.env` file (not in code)
- Add `.env` to `.gitignore`
- Use SQL Server authentication for service accounts
- Consider Azure Key Vault for production

### 2. PowerShell Execution
- Review execution policy settings
- Validate script content before execution
- Use restricted working directories
- Monitor script outputs for sensitive data

### 3. Network Security
- Use encrypted connections (TrustServerCertificate=yes only for internal networks)
- Configure SQL Server firewall rules
- Monitor connection attempts

## Production Deployment

### 1. Windows Service
- Use `sc create` to install as Windows service
- Configure service account with appropriate permissions
- Set up automatic startup

### 2. Monitoring
- Windows Event Log integration
- Performance counters
- Database connection health checks

### 3. Backup Strategy
- Regular database backups
- Configuration file backups
- Log file rotation

## Support

For issues specific to Windows deployment:
1. Check Windows Event Logs
2. Review PowerShell execution logs
3. Verify SQL Server connectivity with SQL Server Management Studio
4. Test ODBC connection with odbcad32.exe

For general application issues, refer to the main README.md file.