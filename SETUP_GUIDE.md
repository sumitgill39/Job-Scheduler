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

### Option 1: Using Batch Files (Easiest)

1. **Download/clone the project** to your desired directory
2. **Open Command Prompt as Administrator**
3. **Navigate to the project directory:**
   ```cmd
   cd "path\to\Job Scheduler"
   ```
4. **Run the web interface:**
   ```cmd
   start.bat
   ```
   OR **Run the CLI interface:**
   ```cmd
   start_cli.bat
   ```

### Option 2: Manual Installation

1. **Create virtual environment:**
   ```cmd
   py -m venv venv
   venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```cmd
   py -m pip install --upgrade pip
   py -m pip install -r requirements.txt
   ```

3. **Test the installation:**
   ```cmd
   py main.py --test-system
   ```

## ⚙️ Configuration

### 1. Database Configuration (Required for SQL Jobs)

Edit `config/database_config.yaml`:

```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"  # Change to your SQL Server
    database: "master"   # Start with master database
    trusted_connection: true  # Windows Authentication
    connection_timeout: 30
    command_timeout: 300
```

### 2. Application Configuration

Edit `config/config.yaml`:

```yaml
security:
  allowed_domains: 
    - "YOURDOMAIN"     # Replace with your Windows domain
    - "LOCALHOST"
    - "WORKGROUP"
```

## 🧪 Testing the Installation

### 1. System Test
```cmd
py main.py --test-system
```

This will test all components and show you if everything is working.

### 2. Quick Manual Tests

**Test if basic imports work:**
```cmd
py -c "from core.scheduler_manager import SchedulerManager; print('OK')"
```

**Test PowerShell execution:**
```cmd
py -c "from utils.windows_utils import WindowsUtils; w=WindowsUtils(); result=w.execute_powershell_command('Write-Host Hello'); print('PowerShell OK' if result['success'] else 'PowerShell Failed')"
```

## 🏃 Running the Application

### Web Interface (Recommended)
```cmd
start.bat
```
Then open: http://localhost:5000

### CLI Interface
```cmd
start_cli.bat
```

### Both Interfaces
```cmd
py main.py --mode both
```

## 🔧 Troubleshooting

### Common Issues & Solutions

**❌ "pyodbc.InterfaceError: ('IM002', '[IM002] [Microsoft][ODBC Driver Manager] Data source name not found and no default driver specified')"**

**✅ Solution:** Install ODBC Driver 17 for SQL Server:
1. Download from [Microsoft](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)
2. Install the driver
3. Verify: `py -c "import pyodbc; print(pyodbc.drivers())"`

---

**❌ "PowerShell execution policy error"**

**✅ Solution:** Set execution policy:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

**❌ "ModuleNotFoundError: No module named 'win32api'"**

**✅ Solution:** Install pywin32:
```cmd
pip install pywin32
```

---

**❌ "No such file or directory: 'logs/scheduler.log'"**

**✅ Solution:** Create logs directory:
```cmd
mkdir logs
```

---

**❌ Web interface shows "500 Internal Server Error"**

**✅ Solutions:**
1. Check console output for errors
2. Ensure all template files exist
3. Check `logs/scheduler.log`
4. Run: `py main.py --test-system`

---

**❌ "Permission denied" errors**

**✅ Solutions:**
1. Run Command Prompt as Administrator
2. Check Windows Firewall settings
3. Ensure user has necessary permissions

### Database Connection Issues

**For Windows Authentication (Recommended):**
```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"  # or your server name/IP
    database: "master"
    trusted_connection: true
```

**For SQL Server Authentication:**
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

**Test Database Connection:**
```cmd
py -c "from database.connection_manager import DatabaseConnectionManager; dm = DatabaseConnectionManager(); result = dm.test_connection(); print('DB OK' if result['success'] else f'DB Error: {result.get(\"error\")}')"
```

## 🎯 Creating Your First Job

### Via Web Interface:
1. Start: `start.bat`
2. Go to: http://localhost:5000
3. Click "Create Job"
4. Choose job type and fill details

### Via CLI:
```cmd
start_cli.bat
JobScheduler> create sql
# Follow the prompts
```

### Example Jobs

**SQL Job:**
```sql
SELECT 
    GETDATE() as current_time,
    @@SERVERNAME as server_name,
    'Hello from SQL Server!' as message
```

**PowerShell Job:**
```powershell
Write-Host "Job started at: $(Get-Date)"
Write-Host "Computer: $env:COMPUTERNAME" 
Write-Host "User: $env:USERNAME"
Write-Host "PowerShell version: $($PSVersionTable.PSVersion)"
Write-Host "Job completed successfully!"
```

## 📁 Important Files

- `start.bat` - Start web interface
- `start_cli.bat` - Start CLI interface  
- `main.py` - Main application
- `config/config.yaml` - Application settings
- `config/database_config.yaml` - Database connections
- `logs/scheduler.log` - Application logs
- `requirements.txt` - Python dependencies

## 🆘 Getting Help

1. **Check logs:** `logs/scheduler.log`
2. **Run system test:** `py main.py --test-system` 
3. **Check console output** for error messages
4. **Verify all files** are present and configured
5. **Test individual components** using the commands above

## 🎉 Success!

If you see the web interface at http://localhost:5000 or the CLI prompt, congratulations! Your Windows Job Scheduler is ready to use.

**Next Steps:**
1. Create your first job
2. Test job execution  
3. Set up scheduling
4. Monitor job results

---

Need help? Check the main README.md for detailed usage instructions and examples.