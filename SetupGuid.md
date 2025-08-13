# Windows Job Scheduler - Complete Setup Guide

This guide will walk you through setting up the complete Windows Job Scheduler project from scratch.

## 📋 Prerequisites

### System Requirements
- **Windows 10/11** or **Windows Server 2016+**
- **Python 3.8 or higher** (recommended: Python 3.11)
- **SQL Server** (any edition) with **ODBC Driver 17+**
- **PowerShell 5.1+** (included with Windows)
- **Administrator privileges** (recommended for full functionality)

### Verify Prerequisites

1. **Check Python Version:**
   ```cmd
   py --version
   ```

2. **Check PowerShell Version:**
   ```powershell
   $PSVersionTable.PSVersion
   ```

3. **Check Available ODBC Drivers:**
   ```cmd
   py -c "import pyodbc; print(pyodbc.drivers())"
   ```

## 🚀 Quick Installation

### Option 1: Automated Installation

1. **Download the project files** to your desired directory
2. **Run the installer:**
   ```cmd
   install.bat
   ```
3. **Test the installation:**
   ```cmd
   py main.py --test-system
   ```

### Option 2: Manual Installation

1. **Create project directory:**
   ```cmd
   mkdir job_scheduler
   cd job_scheduler
   ```

2. **Create virtual environment:**
   ```cmd
   py -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```cmd
   py -m pip install --upgrade pip
   py -m pip install -r requirements.txt
   ```

4. **Create required directories:**
   ```cmd
   mkdir logs config scripts\sample_scripts
   ```

## 📁 Project Structure

Create the following directory structure:

```
job_scheduler/
├── config/
│   ├── __init__.py
│   ├── config.yaml
│   └── database_config.yaml
├── core/
│   ├── __init__.py
│   ├── job_base.py
│   ├── sql_job.py
│   ├── powershell_job.py
│   └── scheduler_manager.py
├── database/
│   ├── __init__.py
│   ├── connection_manager.py
│   └── job_storage.py
├── web_ui/
│   ├── __init__.py
│   ├── app.py
│   ├── routes.py
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── job_list.html
│       ├── create_job.html
│       ├── job_details.html
│       └── error.html
├── cli/
│   ├── __init__.py
│   └── cli_manager.py
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── windows_utils.py
│   └── validators.py
├── logs/
├── scripts/
│   └── sample_scripts/
│       └── test_script.ps1
├── main.py
├── requirements.txt
├── setup.py
├── install.bat
├── start_app.bat
├── start_cli.bat
└── README.md
```

## ⚙️ Configuration

### 1. Database Configuration

Edit `config/database_config.yaml`:

```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"
    database: "JobScheduler"
    trusted_connection: true
    connection_timeout: 30
    command_timeout: 300
```

### 2. Application Configuration

Edit `config/config.yaml`:

```yaml
application:
  name: "Windows Job Scheduler"
  debug: true

web:
  host: "127.0.0.1"
  port: 5000
  secret_key: "change-this-in-production"

scheduler:
  max_workers: 10
  thread_pool_size: 20

security:
  allowed_domains: 
    - "YOURDOMAIN"
    - "LOCALHOST"
```

### 3. SQL Server Setup (Optional)

If using database storage instead of YAML:

```sql
-- Create database
CREATE DATABASE JobScheduler;

-- Use the database
USE JobScheduler;

-- The application will create tables automatically
```

## 🧪 Testing the Installation

### 1. System Test
```cmd
py main.py --test-system
```

This will test:
- Python environment
- Windows utilities
- PowerShell execution
- Database connections
- Job creation

### 2. Manual Component Tests

**Test PowerShell:**
```cmd
py -c "from utils.windows_utils import WindowsUtils; w=WindowsUtils(); print(w.execute_powershell_command('Get-Date'))"
```

**Test Database Connection:**
```cmd
py -c "from database.connection_manager import DatabaseConnectionManager; d=DatabaseConnectionManager(); print(d.test_connection())"
```

**Test Job Creation:**
```cmd
py -c "from core.scheduler_manager import SchedulerManager; s=SchedulerManager('yaml'); print('Scheduler created successfully')"
```

## 🏃 Running the Application

### 1. Web Interface (Recommended)
```cmd
start_app.bat
```
Or manually:
```cmd
py main.py --mode web
```
Access at: http://localhost:5000

### 2. CLI Interface
```cmd
start_cli.bat
```
Or manually:
```cmd
py main.py --mode cli
```

### 3. Both Interfaces
```cmd
py main.py --mode both
```

## 🔧 Troubleshooting

### Common Issues

**1. "ODBC Driver not found"**
- Download and install "ODBC Driver 17 for SQL Server" from Microsoft
- Verify installation: `py -c "import pyodbc; print(pyodbc.drivers())"`

**2. "PowerShell execution policy error"**
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**3. "Module not found" errors**
- Ensure virtual environment is activated: `venv\Scripts\activate`
- Reinstall requirements: `py -m pip install -r requirements.txt`

**4. "Permission denied" errors**
- Run Command Prompt as Administrator
- Check Windows Firewall settings for Python
- Verify user has necessary permissions

**5. Web interface shows "Template not found"**
- Ensure all HTML template files are created in `web_ui/templates/`
- Check file permissions

### Database Connection Issues

**For Windows Authentication:**
```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"
    database: "master"  # Start with master database
    trusted_connection: true
```

**For SQL Authentication:**
```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"
    database: "master"
    trusted_connection: false
    username: "sa"
    password: "YourPassword"
```

### Logging

Check logs for detailed error information:
- Application logs: `logs/scheduler.log`
- Windows Event Viewer: Application logs
- Console output during startup

## 🎯 First Steps After Installation

### 1. Create Your First Job

**Via Web Interface:**
1. Go to http://localhost:5000
2. Click "Create Job"
3. Choose "SQL Job" or "PowerShell Job"
4. Fill in the details
5. Save and run

**Via CLI:**
```cmd
py main.py --mode cli
JobScheduler> create sql
```

### 2. Test Job Examples

**SQL Job Example:**
```sql
SELECT 
    GETDATE() as current_time,
    @@SERVERNAME as server_name,
    'Test successful' as message
```

**PowerShell Job Example:**
```powershell
Write-Host "Job started at: $(Get-Date)"
Write-Host "Computer: $env:COMPUTERNAME"
Write-Host "User: $env:USERNAME"
Write-Host "Job completed successfully!"
```

## 📈 Production Deployment

### 1. Security Considerations
- Change default secret keys
- Use HTTPS for web interface
- Configure proper Windows authentication
- Set up proper logging and monitoring
- Regular backup of job configurations

### 2. Performance Optimization
- Adjust `max_workers` based on system capacity
- Configure appropriate timeouts
- Set up log rotation
- Monitor system resources

### 3. Service Installation
```cmd
# Install as Windows Service (future feature)
py main.py --install-service
```

## 🆘 Getting Help

1. **Check the logs:** `logs/scheduler.log`
2. **Run system test:** `py main.py --test-system`
3. **Verify configuration files**
4. **Check Windows Event Viewer**
5. **Review this setup guide**

## 📚 Next Steps

1. **Read the main README.md** for detailed usage instructions
2. **Explore the CLI commands** using `help` in CLI mode
3. **Create your first scheduled jobs**
4. **Set up monitoring and alerting**
5. **Configure backup and disaster recovery**

---

**Congratulations! 🎉** 

Your Windows Job Scheduler is now ready to use. You can now create and schedule SQL Server and PowerShell jobs with a modern web interface and powerful CLI tools.