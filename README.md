# Windows Job Scheduler

A comprehensive Python-based job scheduling system designed specifically for Windows environments, supporting both SQL Server and PowerShell script automation with multi-threading capabilities.

## Features

### 🎯 Core Functionality
- **Multi-threaded job execution** using APScheduler
- **SQL Server job scheduling** with Windows Authentication support
- **PowerShell script automation** (both file and inline scripts)
- **Web-based UI** for easy job management
- **Command-line interface** for advanced users
- **Windows domain account support** for job execution
- **YAML and database storage** options for job configurations

### 🔧 Job Types
1. **SQL Jobs**
   - Execute SQL queries on SQL Server
   - Support for Windows Authentication and SQL Authentication
   - Query result handling and logging
   - Connection pooling and retry logic

2. **PowerShell Jobs**
   - Execute .ps1 script files
   - Run inline PowerShell commands
   - Parameter passing support
   - Execution policy configuration

### 📅 Scheduling Options
- **Cron expressions** for complex scheduling
- **Interval scheduling** (minutes, hours, days)
- **One-time execution** with specific date/time
- **Immediate execution** for testing

### 🖥️ Windows Integration
- **Windows Authentication** support
- **Domain account validation**
- **Windows Event Log** integration
- **PowerShell execution policy** handling
- **Windows service** installation capabilities

## Installation

### Prerequisites
- **Windows 10/11** or **Windows Server 2016+**
- **Python 3.8+** installed
- **SQL Server** with ODBC Driver 17+ (if using SQL jobs)
- **PowerShell 5.1+** (included with Windows)

### Quick Install

1. **Download and extract** the project files
2. **Run the installer**:
   ```cmd
   install.bat
   ```

### Manual Installation

1. **Clone or download** the project
2. **Create virtual environment**:
   ```cmd
   py -m venv venv
   venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```cmd
   py -m pip install -r requirements.txt
   ```

## Quick Start

### 1. Test System Components
```cmd
py main.py --test-system
```

### 2. Start Web Interface
```cmd
start_app.bat
# OR
py main.py --mode web
```
Open browser to: http://localhost:5000

### 3. Start CLI Interface
```cmd
start_cli.bat
# OR
py main.py --mode cli
```

### 4. Start Both Interfaces
```cmd
py main.py --mode both
```

## Configuration

### Database Configuration
Edit `config/database_config.yaml`:

```yaml
databases:
  default:
    driver: "{ODBC Driver 17 for SQL Server}"
    server: "localhost"
    database: "JobScheduler"
    trusted_connection: true  # Windows Authentication
    connection_timeout: 30
```

### Application Configuration
Edit `config/config.yaml`:

```yaml
application:
  name: "Windows Job Scheduler"
  debug: true

web:
  host: "127.0.0.1"
  port: 5000

scheduler:
  max_workers: 10
  thread_pool_size: 20

security:
  allowed_domains: 
    - "dmzprod01"
    - "dmzweb01" 
    - "MGD"
    - "Mercer"
```

## Usage Examples

### Creating a SQL Job (CLI)
```cmd
JobScheduler> create sql
Job name: Daily Sales Report
Description: Generate daily sales report
Enter SQL query (end with empty line):
SELECT COUNT(*) as total_orders, SUM(amount) as total_sales 
FROM orders 
WHERE date >= DATEADD(day, -1, GETDATE())

Connection name [default]: 
Schedule this job (yes/no) [no]: yes
Schedule type (cron/interval/once) [cron]: cron
Cron expression (sec min hour day month dow): 0 0 8 * * 1-5
✓ SQL job created successfully: Daily Sales Report
```

### Creating a PowerShell Job (CLI)
```cmd
JobScheduler> create powershell
Job name: System Cleanup
Description: Clean temporary files
Script type (file/inline) [inline]: inline
Enter PowerShell script (end with empty line):
Get-ChildItem $env:TEMP -Recurse | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } | Remove-Item -Force -Recurse
Write-Host "Cleanup completed"

Parameters (space-separated): 
Schedule this job (yes/no) [no]: yes
Schedule type (cron/interval/once) [cron]: interval
Interval in minutes: 60
✓ PowerShell job created successfully: System Cleanup
```

### Web Interface Features
- **Dashboard** with job overview and statistics
- **Job Creation Wizard** with validation
- **Real-time job monitoring** and status updates
- **Execution history** with detailed logs
- **Schedule management** with visual cron builder
- **Job import/export** functionality

## CLI Commands Reference

### Job Management
```cmd
list                    # List all jobs
list enabled           # List enabled jobs only
show <job_id>          # Show job details
create sql             # Create SQL job
create powershell      # Create PowerShell job
run <job_id>           # Run job immediately
delete <job_id>        # Delete job
enable <job_id>        # Enable job
disable <job_id>       # Disable job
```

### Monitoring
```cmd
status                 # Show scheduler status
history <job_id>       # Show execution history
```

### System
```cmd
clear                  # Clear screen
quit                   # Exit CLI
```

## Project Structure

```
job_scheduler/
├── config/                 # Configuration files
│   ├── config.yaml        # Main configuration
│   └── database_config.yaml # Database connections
├── core/                  # Core job management
│   ├── job_base.py       # Base job class
│   ├── sql_job.py        # SQL job implementation
│   ├── powershell_job.py # PowerShell job implementation
│   └── scheduler_manager.py # Main scheduler
├── database/              # Database connectivity
│   ├── connection_manager.py # SQL Server connections
│   └── job_storage.py    # Job persistence
├── web_ui/               # Web interface
│   ├── app.py           # Flask application
│   ├── routes.py        # Web routes
│   └── templates/       # HTML templates
├── cli/                  # Command line interface
│   └── cli_manager.py   # CLI implementation
├── utils/                # Utilities
│   ├── logger.py        # Logging system
│   ├── windows_utils.py # Windows-specific utilities
│   └── validators.py    # Input validation
├── logs/                 # Log files
├── scripts/             # Sample scripts
└── main.py              # Application entry point
```

## Security Considerations

### Domain Accounts
- Jobs can run under specific Windows domain accounts
- Configurable allowed domains list
- Validation of account formats and permissions

### SQL Security
- Windows Authentication recommended
- Query validation to prevent dangerous operations
- Connection string security

### PowerShell Security
- Configurable execution policies
- Script content validation
- Parameter sanitization

## Troubleshooting

### Common Issues

**"ODBC Driver not found"**
```cmd
# Install ODBC Driver 17 for SQL Server
# Download from Microsoft's website
```

**"PowerShell execution policy error"**
```cmd
# Check execution policy
Get-ExecutionPolicy
# Set policy (as administrator)
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**"Permission denied"**
- Ensure running with appropriate Windows permissions
- Check domain account permissions for job execution
- Verify SQL Server connection permissions

### Logging
- Application logs: `logs/scheduler.log`
- Windows Event Log integration for errors
- Per-job execution logging

### Database Connection Issues
```cmd
# Test connections
py main.py --test-system

# Check ODBC drivers
py -c "import pyodbc; print(pyodbc.drivers())"
```

## Development

### Adding New Job Types
1. Create new job class inheriting from `JobBase`
2. Implement `execute()` method
3. Add job type to `SchedulerManager._create_job_from_config()`
4. Update CLI and web UI for job creation

### Custom Storage Backends
1. Implement storage interface in `database/job_storage.py`
2. Add storage type to `JobStorage.__init__()`
3. Update configuration options

## API Reference

### Core Classes
- `JobBase`: Base class for all job types
- `SqlJob`: SQL Server job implementation
- `PowerShellJob`: PowerShell script job implementation
- `SchedulerManager`: Main scheduler and job manager
- `JobStorage`: Job persistence layer

### Key Methods
```python
# Create jobs
scheduler.create_sql_job(name, query, connection)
scheduler.create_powershell_job(name, script_path=path)

# Manage jobs
scheduler.add_job(job, schedule)
scheduler.remove_job(job_id)
scheduler.run_job_once(job_id)

# Monitoring
scheduler.get_scheduler_status()
scheduler.get_job_status(job_id)
scheduler.get_execution_history(job_id)
```

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure Windows compatibility
5. Submit pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files
3. Test system components with `--test-system`
4. Create an issue with system information and logs

## Version History

### v1.0.0
- Initial release
- SQL Server and PowerShell job support
- Web and CLI interfaces
- Windows Authentication
- Multi-threading with APScheduler
- YAML and database storage options