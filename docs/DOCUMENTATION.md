# Job Scheduler - Complete Technical Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [System Architecture](#system-architecture)
3. [Database Configuration](#database-configuration)
4. [Application Components](#application-components)
5. [Job Execution Workflow](#job-execution-workflow)
6. [API Documentation](#api-documentation)
7. [Web Interface Routes](#web-interface-routes)
8. [Job Types and Configuration](#job-types-and-configuration)
9. [Deployment Guide](#deployment-guide)
10. [Troubleshooting](#troubleshooting)

---

## 1. Project Overview

### Introduction
The Job Scheduler is a comprehensive Windows-based job automation system designed to schedule, execute, and monitor various types of jobs including SQL queries, PowerShell scripts, Python scripts, and system commands. Built with Python, it provides both a web interface and API for job management.

### Key Features
- **Multi-Job Type Support**: SQL, PowerShell, Python, Command line jobs
- **YAML Configuration**: Jobs defined in YAML format for easy management
- **Web Interface**: Full-featured web UI for job management and monitoring
- **Real-time Monitoring**: Live job execution tracking and logging
- **Database Integration**: SQL Server backend for job storage and history
- **Timezone Support**: Multi-timezone job scheduling
- **Retry Logic**: Automatic job retry on failure with configurable attempts
- **Windows Integration**: Native Windows authentication and service support

### Technology Stack
- **Backend**: Python 3.13
- **Web Framework**: Flask
- **Database**: SQL Server Express (DESKTOP-4ADGDVE\SQLEXPRESS)
- **Scheduler**: APScheduler
- **ORM**: SQLAlchemy
- **Frontend**: HTML, JavaScript, Bootstrap
- **Configuration**: YAML

---

## 2. System Architecture

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                      │
├────────────────┬───────────────────────┬────────────────────┤
│  Web Browser   │   REST API Client     │   Command Line     │
└────────┬───────┴───────────┬───────────┴────────┬───────────┘
         │                   │                     │
         ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    Flask Web Application                      │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐  │
│  │ Web Routes   │  │ API Routes  │  │ Static Resources │  │
│  └──────┬───────┘  └──────┬──────┘  └──────────────────┘  │
└─────────┼──────────────────┼────────────────────────────────┘
          │                  │
          ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Business Logic                        │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │ Job Manager    │  │ Scheduler       │  │ Executor    │  │
│  │                │  │ Manager         │  │ Engine      │  │
│  └────────┬───────┘  └────────┬────────┘  └──────┬──────┘  │
└───────────┼───────────────────┼───────────────────┼─────────┘
            │                   │                    │
            ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                      Job Types Layer                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ SQL Job  │  │ PS Job   │  │ PY Job   │  │ CMD Job  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Persistence Layer                     │
│  ┌────────────────┐  ┌─────────────────┐  ┌─────────────┐  │
│  │ SQL Server     │  │ YAML Config     │  │ Log Files   │  │
│  │ Database       │  │ Files           │  │             │  │
│  └────────────────┘  └─────────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Interactions

The system follows a modular architecture with clear separation of concerns:

1. **Presentation Layer**: Web UI and API endpoints
2. **Business Logic Layer**: Core scheduling and execution logic
3. **Job Implementation Layer**: Specific job type implementations
4. **Data Layer**: Database and file system storage

---

## 3. Database Configuration

### Database Connection Details

```yaml
Server: DESKTOP-4ADGDVE\SQLEXPRESS
Database: sreutil
Authentication: Windows Authentication (Trusted Connection)
Driver: ODBC Driver 17 for SQL Server
```

### Database Tables Schema

#### 1. **job_configurations** Table
Stores job definitions and configurations.

```sql
CREATE TABLE [dbo].[job_configurations] (
    [job_id] NVARCHAR(50) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [job_type] NVARCHAR(50) NOT NULL,
    [configuration] NTEXT NOT NULL,  -- JSON serialized job config
    [enabled] BIT DEFAULT 1,
    [created_date] DATETIME DEFAULT GETDATE(),
    [modified_date] DATETIME DEFAULT GETDATE(),
    [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER
)
```

#### 2. **job_execution_history_V2** Table
Tracks all job execution history.

```sql
CREATE TABLE [dbo].[job_execution_history_V2] (
    [execution_id] BIGINT IDENTITY(1,1) PRIMARY KEY,
    [job_id] NVARCHAR(50) NOT NULL,
    [job_name] NVARCHAR(255) NOT NULL,
    [status] NVARCHAR(50) NOT NULL,  -- pending, running, success, failed, timeout
    [start_time] DATETIME NOT NULL,
    [end_time] DATETIME NULL,
    [duration_seconds] FLOAT NULL,
    [output] NTEXT NULL,              -- Job execution output
    [error_message] NTEXT NULL,       -- Error details if failed
    [return_code] INT NULL,
    [retry_count] INT DEFAULT 0,
    [max_retries] INT DEFAULT 0,
    [metadata] NTEXT NULL             -- JSON additional data
)
```

#### 3. **user_connections** Table
Stores database connection configurations for SQL jobs.

```sql
CREATE TABLE [dbo].[user_connections] (
    [connection_id] NVARCHAR(100) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [server_name] NVARCHAR(255) NOT NULL,
    [port] INT DEFAULT 1433,
    [database_name] NVARCHAR(255) NOT NULL,
    [trusted_connection] BIT DEFAULT 1,
    [username] NVARCHAR(255) NULL,
    [password] NVARCHAR(500) NULL,    -- Encrypted
    [description] NVARCHAR(1000) NULL,
    [driver] NVARCHAR(255) DEFAULT '{ODBC Driver 17 for SQL Server}',
    [connection_timeout] INT DEFAULT 30,
    [command_timeout] INT DEFAULT 300,
    [encrypt] BIT DEFAULT 0,
    [trust_server_certificate] BIT DEFAULT 1,
    [created_date] DATETIME DEFAULT GETDATE(),
    [modified_date] DATETIME DEFAULT GETDATE(),
    [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER,
    [is_active] BIT DEFAULT 1
)
```

### SQLAlchemy Models

```python
# database/sqlalchemy_models.py

class JobConfigurationV2(Base):
    __tablename__ = 'job_configurations_V2'
    
    job_id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)
    configuration = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    created_date = Column(DateTime, default=datetime.now)
    modified_date = Column(DateTime, default=datetime.now)
    created_by = Column(String(255), default='SYSTEM')

class JobExecutionHistoryV2(Base):
    __tablename__ = 'job_execution_history_V2'
    
    execution_id = Column(BigInteger, primary_key=True, autoincrement=True)
    job_id = Column(String(50), nullable=False)
    job_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_seconds = Column(Float)
    output = Column(Text)
    error_message = Column(Text)
    return_code = Column(Integer)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=0)
    metadata = Column(Text)
```

---

## 4. Application Components

### Core Components

#### 4.1 Main Entry Point (main.py)

```python
# main.py - Application entry point
def main():
    parser = argparse.ArgumentParser(description='Job Scheduler Application')
    parser.add_argument('--mode', choices=['scheduler', 'web', 'both'], 
                       default='both', help='Run mode')
    parser.add_argument('--port', type=int, default=5000, 
                       help='Web server port')
    parser.add_argument('--config', type=str, 
                       default='jobs/job_config.yaml',
                       help='Job configuration file path')
    
    args = parser.parse_args()
    
    if args.mode in ['scheduler', 'both']:
        # Start scheduler
        scheduler = SchedulerManager()
        scheduler.start()
    
    if args.mode in ['web', 'both']:
        # Start web server
        app = create_app()
        app.run(host='0.0.0.0', port=args.port)
```

#### 4.2 Job Manager (core/job_manager.py)

The Job Manager is responsible for loading, validating, and managing all jobs.

```python
class JobManager:
    def __init__(self, config_path: str = None, db_manager=None):
        self.config_path = config_path or 'jobs/job_config.yaml'
        self.db_manager = db_manager
        self.jobs = {}  # Dictionary of job_id: job_instance
        self.logger = get_logger('JobManager')
        
    def load_jobs(self):
        """Load jobs from YAML configuration"""
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        for job_config in config.get('jobs', []):
            job = self.create_job(job_config)
            self.jobs[job.job_id] = job
            
    def create_job(self, job_config):
        """Factory method to create job instances"""
        job_type = job_config.get('type')
        
        if job_type == 'sql':
            return SQLJob(**job_config)
        elif job_type == 'powershell':
            return PowerShellJob(**job_config)
        elif job_type == 'python':
            return PythonJob(**job_config)
        elif job_type == 'command':
            return CommandJob(**job_config)
        else:
            raise ValueError(f"Unknown job type: {job_type}")
```

#### 4.3 Scheduler Manager (core/scheduler_manager.py)

Manages the APScheduler instance and job scheduling.

```python
class SchedulerManager:
    def __init__(self, job_manager=None, db_manager=None):
        self.job_manager = job_manager
        self.db_manager = db_manager
        self.scheduler = BackgroundScheduler(
            executors={
                'default': ThreadPoolExecutor(20),
                'processpool': ProcessPoolExecutor(5)
            },
            job_defaults={
                'coalesce': False,
                'max_instances': 3
            },
            timezone=pytz.UTC
        )
        
    def schedule_job(self, job, schedule_config):
        """Schedule a job based on configuration"""
        trigger_type = schedule_config.get('type')
        
        if trigger_type == 'cron':
            self.scheduler.add_job(
                func=job.run,
                trigger='cron',
                id=job.job_id,
                name=job.name,
                **schedule_config.get('cron_params', {})
            )
        elif trigger_type == 'interval':
            self.scheduler.add_job(
                func=job.run,
                trigger='interval',
                id=job.job_id,
                name=job.name,
                **schedule_config.get('interval_params', {})
            )
```

### Job Base Class (core/job_base.py)

All job types inherit from this base class:

```python
class JobBase(ABC):
    def __init__(self, job_id=None, name="", description="",
                 timeout=300, max_retries=3, retry_delay=60,
                 run_as=None, enabled=True, metadata=None):
        self.job_id = job_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.run_as = run_as
        self.enabled = enabled
        self.metadata = metadata or {}
        self.current_status = JobStatus.PENDING
        self.retry_count = 0
        self.execution_history = []
        
    @abstractmethod
    def execute(self, execution_logger=None) -> JobResult:
        """Execute the job - must be implemented by subclasses"""
        pass
        
    def run(self) -> JobResult:
        """Run the job with error handling, timeout, and retry logic"""
        if not self.enabled:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.CANCELLED,
                error_message="Job is disabled"
            )
        
        try:
            # Execute with timeout
            result = self._execute_with_timeout()
            
            # Handle retry logic
            if result.status == JobStatus.FAILED and self.retry_count < self.max_retries:
                self.retry_count += 1
                result.status = JobStatus.RETRY
                # Schedule retry
                
            return result
            
        except Exception as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                error_message=str(e)
            )
```

---

## 5. Job Execution Workflow

### Complete Job Execution Flow

```
1. Job Creation/Loading
   ├── Load from YAML configuration
   ├── Validate job parameters
   └── Create job instance

2. Job Scheduling
   ├── Parse schedule configuration
   ├── Add to APScheduler
   └── Store in job registry

3. Trigger Event
   ├── Cron trigger fires
   ├── Interval trigger fires
   └── Manual trigger via API

4. Pre-Execution Checks
   ├── Check if job is enabled
   ├── Check for concurrent execution
   └── Acquire execution lock

5. Job Execution
   ├── Create execution logger
   ├── Log start time
   ├── Execute job-specific logic
   │   ├── SQL: Connect to database and run query
   │   ├── PowerShell: Execute PS script
   │   ├── Python: Run Python script
   │   └── Command: Execute system command
   ├── Capture output/errors
   └── Apply timeout if configured

6. Post-Execution
   ├── Calculate duration
   ├── Update job status
   ├── Store execution history
   └── Release execution lock

7. Retry Logic (if failed)
   ├── Check retry count
   ├── Schedule retry with delay
   └── Update retry metadata

8. Persistence
   ├── Save to database
   ├── Update log files
   └── Send notifications (if configured)
```

### Execution Flow Diagram

```
     ┌─────────────┐
     │   Trigger   │
     │   (Cron/    │
     │  Interval/  │
     │   Manual)   │
     └──────┬──────┘
            │
            ▼
     ┌─────────────┐
     │  Scheduler  │
     │   Manager   │
     └──────┬──────┘
            │
            ▼
     ┌─────────────┐
     │Pre-Execution│
     │   Checks    │
     └──────┬──────┘
            │
            ▼
    ┌───────────────┐
    │  Job.run()    │
    │  Entry Point  │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │Execution Lock │
    │   Acquired    │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │ Execute with  │
    │   Timeout     │
    └───────┬───────┘
            │
            ▼
    ┌───────────────┐
    │Job.execute()  │
    │(Type-Specific)│
    └───────┬───────┘
            │
    ┌───────┴────────┐
    ▼                ▼
┌────────┐     ┌──────────┐
│Success │     │  Failed  │
└────┬───┘     └────┬─────┘
     │              │
     │              ▼
     │      ┌──────────────┐
     │      │ Check Retry  │
     │      │    Logic     │
     │      └──────┬───────┘
     │             │
     ▼             ▼
┌──────────────────────┐
│  Update Execution    │
│      History         │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│   Store in Database  │
└──────────────────────┘
```

### SQL Job Execution Example

```python
# core/sql_job.py
class SQLJob(JobBase):
    def execute(self, execution_logger=None) -> JobResult:
        """Execute SQL query"""
        start_time = datetime.now()
        
        try:
            # 1. Get database connection
            conn_string = self._build_connection_string()
            connection = pyodbc.connect(conn_string)
            cursor = connection.cursor()
            
            # 2. Execute query
            execution_logger.info(f"Executing SQL query: {self.query[:100]}...")
            cursor.execute(self.query)
            
            # 3. Handle results based on query type
            if self.query_type == 'select':
                results = cursor.fetchall()
                output = self._format_results(results)
            else:
                connection.commit()
                output = f"Query executed successfully. Rows affected: {cursor.rowcount}"
            
            # 4. Close connection
            cursor.close()
            connection.close()
            
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.SUCCESS,
                start_time=start_time,
                end_time=datetime.now(),
                output=output
            )
            
        except Exception as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=str(e)
            )
```

---

## 6. API Documentation

### API Endpoints Overview

The application provides comprehensive REST APIs for job management:

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Job Management** |
| GET | `/api/jobs` | List all jobs |
| GET | `/api/jobs/{job_id}` | Get job details |
| POST | `/api/jobs` | Create new job |
| PUT | `/api/jobs/{job_id}` | Update job |
| DELETE | `/api/jobs/{job_id}` | Delete job |
| POST | `/api/jobs/{job_id}/run` | Run job manually |
| POST | `/api/jobs/{job_id}/enable` | Enable job |
| POST | `/api/jobs/{job_id}/disable` | Disable job |
| **Execution History** |
| GET | `/api/jobs/{job_id}/history` | Get job execution history |
| GET | `/api/executions` | List all executions |
| GET | `/api/executions/{execution_id}` | Get execution details |
| **Scheduler Management** |
| GET | `/api/scheduler/status` | Get scheduler status |
| POST | `/api/scheduler/start` | Start scheduler |
| POST | `/api/scheduler/stop` | Stop scheduler |
| POST | `/api/scheduler/pause` | Pause scheduler |
| POST | `/api/scheduler/resume` | Resume scheduler |
| **Monitoring** |
| GET | `/api/admin/job-queue/status` | Get job queue status |
| GET | `/api/admin/job-queue/metrics` | Get queue metrics |
| GET | `/api/health` | Health check |
| GET | `/api/logs` | Get application logs |

### Detailed API Examples

#### 1. List All Jobs
```http
GET /api/jobs HTTP/1.1
Host: localhost:5000

Response:
{
    "success": true,
    "jobs": [
        {
            "job_id": "job_001",
            "name": "Daily Sales Report",
            "job_type": "sql",
            "enabled": true,
            "schedule": {
                "type": "cron",
                "cron_params": {
                    "hour": 8,
                    "minute": 0
                }
            },
            "last_execution": {
                "status": "success",
                "start_time": "2025-09-06T08:00:00",
                "duration_seconds": 45.2
            }
        }
    ],
    "total": 15
}
```

#### 2. Create New Job
```http
POST /api/jobs HTTP/1.1
Host: localhost:5000
Content-Type: application/json

{
    "name": "Backup Database",
    "job_type": "powershell",
    "description": "Daily database backup",
    "enabled": true,
    "script_path": "C:\\Scripts\\backup.ps1",
    "parameters": ["--full", "--compress"],
    "schedule": {
        "type": "cron",
        "cron_params": {
            "hour": 2,
            "minute": 0
        }
    },
    "timeout": 3600,
    "max_retries": 2
}

Response:
{
    "success": true,
    "job_id": "job_002",
    "message": "Job created successfully"
}
```

#### 3. Run Job Manually
```http
POST /api/jobs/job_001/run HTTP/1.1
Host: localhost:5000

Response:
{
    "success": true,
    "execution_id": "exec_12345",
    "message": "Job execution started",
    "status": "running"
}
```

#### 4. Get Execution History
```http
GET /api/jobs/job_001/history?limit=10 HTTP/1.1
Host: localhost:5000

Response:
{
    "success": true,
    "job_id": "job_001",
    "history": [
        {
            "execution_id": "exec_12345",
            "status": "success",
            "start_time": "2025-09-06T08:00:00",
            "end_time": "2025-09-06T08:00:45",
            "duration_seconds": 45.2,
            "output": "Query executed successfully. 1500 rows processed."
        },
        {
            "execution_id": "exec_12344",
            "status": "failed",
            "start_time": "2025-09-05T08:00:00",
            "end_time": "2025-09-05T08:01:30",
            "duration_seconds": 90.0,
            "error_message": "Connection timeout"
        }
    ],
    "total": 250
}
```

---

## 7. Web Interface Routes

### Web Routes Documentation

The web interface provides comprehensive job management capabilities:

#### Main Routes

```python
# web_ui/routes.py

@app.route('/')
def index():
    """Dashboard showing job overview and recent executions"""
    
@app.route('/jobs')
def jobs_list():
    """List all jobs with filtering and search"""
    
@app.route('/jobs/<job_id>')
def job_details(job_id):
    """Detailed view of a specific job"""
    
@app.route('/jobs/<job_id>/edit')
def job_edit(job_id):
    """Edit job configuration"""
    
@app.route('/jobs/new')
def job_new():
    """Create new job form"""
    
@app.route('/executions')
def executions_list():
    """List all job executions with live updates"""
    
@app.route('/scheduler')
def scheduler_dashboard():
    """Scheduler status and control panel"""
    
@app.route('/connections')
def connections_list():
    """Manage database connections"""
    
@app.route('/logs')
def logs_viewer():
    """Real-time log viewer"""
```

### Dashboard Features

The main dashboard (`/`) displays:
- Active jobs count
- Recent executions
- System health status
- Quick actions (Run, Stop, Pause)
- Execution timeline chart

### Jobs Management Page

The jobs page (`/jobs`) provides:
- Searchable job list
- Filter by type, status, schedule
- Bulk operations
- Export/Import functionality
- Job templates

---

## 8. Job Types and Configuration

### YAML Configuration Structure

```yaml
# jobs/job_config.yaml
version: '2.0'
metadata:
  environment: production
  owner: admin

jobs:
  # SQL Job Example
  - id: daily_sales_report
    name: Daily Sales Report
    type: sql
    description: Generate daily sales summary
    enabled: true
    
    connection:
      connection_id: prod_db
      # Or inline connection
      server: DESKTOP-4ADGDVE\SQLEXPRESS
      database: sales_db
      trusted_connection: true
    
    query: |
      SELECT 
        DATE(order_date) as date,
        COUNT(*) as order_count,
        SUM(total_amount) as total_sales
      FROM orders
      WHERE order_date >= DATEADD(day, -1, GETDATE())
      GROUP BY DATE(order_date)
    
    query_type: select
    output_format: csv
    output_path: C:\Reports\daily_sales.csv
    
    schedule:
      type: cron
      cron_params:
        hour: 8
        minute: 30
        timezone: America/New_York
    
    timeout: 300
    max_retries: 3
    retry_delay: 60
    
    notifications:
      on_success:
        - email: admin@company.com
      on_failure:
        - email: alerts@company.com
        - slack: #alerts-channel

  # PowerShell Job Example
  - id: system_cleanup
    name: System Cleanup
    type: powershell
    description: Clean temporary files and logs
    enabled: true
    
    script_path: C:\Scripts\cleanup.ps1
    # Or inline script
    script_content: |
      Remove-Item -Path "C:\Temp\*" -Recurse -Force
      Clear-EventLog -LogName Application
      Write-Host "Cleanup completed"
    
    parameters:
      - --verbose
      - --deep-clean
    
    execution_policy: RemoteSigned
    working_directory: C:\Scripts
    
    schedule:
      type: interval
      interval_params:
        hours: 6
    
    run_as: DOMAIN\ServiceAccount

  # Python Job Example
  - id: data_processing
    name: Data Processing Pipeline
    type: python
    description: Process incoming data files
    enabled: true
    
    script_path: C:\Scripts\process_data.py
    arguments:
      - --input-dir
      - C:\Data\Input
      - --output-dir
      - C:\Data\Output
    
    environment:
      PYTHONPATH: C:\Scripts\lib
      DATA_ENV: production
    
    virtual_env: C:\Envs\data_processing
    
    schedule:
      type: cron
      cron_params:
        minute: '*/15'  # Every 15 minutes
    
    timeout: 600

  # Command Job Example
  - id: backup_files
    name: Backup Important Files
    type: command
    description: Backup critical files to network share
    enabled: true
    
    command: robocopy
    arguments:
      - C:\ImportantData
      - \\BackupServer\Share
      - /E
      - /Z
      - /LOG:C:\Logs\backup.log
    
    working_directory: C:\
    
    schedule:
      type: cron
      cron_params:
        hour: 22
        minute: 0
    
    timeout: 7200  # 2 hours
```

### Job Type Specifications

#### SQL Job
- **Purpose**: Execute SQL queries against databases
- **Supports**: SELECT, INSERT, UPDATE, DELETE, Stored Procedures
- **Output**: CSV, JSON, Excel formats
- **Features**: Connection pooling, transaction support

#### PowerShell Job
- **Purpose**: Execute PowerShell scripts
- **Supports**: PS1 files, inline scripts
- **Features**: Parameter passing, execution policy control
- **Security**: Run as specific user, credential management

#### Python Job
- **Purpose**: Run Python scripts
- **Supports**: Virtual environments, package management
- **Features**: Argument passing, environment variables
- **Integration**: Jupyter notebook support

#### Command Job
- **Purpose**: Execute system commands
- **Supports**: Any Windows executable
- **Features**: Working directory control, output capture
- **Use Cases**: Batch files, system utilities, third-party tools

---

## 9. Deployment Guide

### System Requirements

```yaml
Operating System: Windows 10/11 or Windows Server 2016+
Python: 3.11 or higher
SQL Server: Express 2019 or higher
Memory: Minimum 4GB RAM (8GB recommended)
Storage: 10GB free space for application and logs
Network: Port 5000 for web interface
```

### Installation Steps

#### Step 1: Clone Repository
```bash
git clone https://github.com/company/job-scheduler.git
cd job-scheduler
```

#### Step 2: Create Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

#### Step 4: Configure Database
```sql
-- Run database_setup.sql in SQL Server Management Studio
-- This creates necessary tables and indexes
```

#### Step 5: Configure Application
```yaml
# config/app_config.yaml
database:
  connection_string: "DRIVER={ODBC Driver 17 for SQL Server};SERVER=DESKTOP-4ADGDVE\SQLEXPRESS;DATABASE=sreutil;Trusted_Connection=yes"
  
logging:
  level: INFO
  file: logs/scheduler.log
  max_size: 10485760  # 10MB
  backup_count: 5

web:
  host: 0.0.0.0
  port: 5000
  secret_key: "your-secret-key-here"
  
scheduler:
  timezone: UTC
  thread_pool_size: 20
  process_pool_size: 5
```

#### Step 6: Initialize Application
```bash
# Initialize database
python scripts/init_db.py

# Load initial jobs
python scripts/load_jobs.py --config jobs/job_config.yaml
```

#### Step 7: Start Application
```bash
# Start both scheduler and web interface
python main.py --mode both

# Or start separately
python main.py --mode scheduler  # In one terminal
python main.py --mode web       # In another terminal
```

### Windows Service Installation

Create a Windows service for production deployment:

```bash
# Install as Windows service
python scripts/install_service.py

# Service commands
sc start JobScheduler
sc stop JobScheduler
sc query JobScheduler
```

### Configuration Files Structure

```
job-scheduler/
├── config/
│   ├── app_config.yaml       # Main application config
│   ├── logging_config.yaml   # Logging configuration
│   └── security_config.yaml  # Security settings
├── jobs/
│   ├── job_config.yaml       # Job definitions
│   └── templates/             # Job templates
├── scripts/
│   ├── backup.ps1            # PowerShell scripts
│   └── process.py            # Python scripts
├── logs/
│   ├── scheduler.log         # Main application log
│   ├── jobs/                 # Individual job logs
│   └── web.log              # Web interface log
└── data/
    ├── cache/               # Temporary cache
    └── exports/             # Exported data
```

---

## 10. Troubleshooting

### Common Issues and Solutions

#### Issue 1: Database Connection Failed
```
Error: Cannot connect to SQL Server
```
**Solution:**
1. Verify SQL Server is running
2. Check connection string in config
3. Ensure Windows Authentication is enabled
4. Test with SQL Server Management Studio

#### Issue 2: Job Execution Timeout
```
Error: Job execution timed out after 300 seconds
```
**Solution:**
1. Increase timeout in job configuration
2. Optimize query/script performance
3. Check for database locks
4. Review execution logs for bottlenecks

#### Issue 3: Scheduler Not Starting
```
Error: Scheduler failed to initialize
```
**Solution:**
1. Check port 5000 is available
2. Verify Python dependencies installed
3. Review scheduler.log for errors
4. Ensure database tables exist

#### Issue 4: PowerShell Execution Policy
```
Error: PowerShell script cannot be loaded
```
**Solution:**
```powershell
# Run as Administrator
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope LocalMachine
```

### Log File Locations

```yaml
Application Logs:
  Main: logs/scheduler.log
  Web: logs/web.log
  Jobs: logs/jobs/{job_id}.log
  
System Logs:
  Windows Event Log: Application
  Service Log: C:\Windows\System32\LogFiles\JobScheduler\
  
Debug Logs:
  Enable: Set LOG_LEVEL=DEBUG in environment
  Location: logs/debug.log
```

### Performance Optimization

#### Database Optimization
```sql
-- Add indexes for better performance
CREATE INDEX IX_job_history_job_id ON job_execution_history_V2(job_id);
CREATE INDEX IX_job_history_start_time ON job_execution_history_V2(start_time);
CREATE INDEX IX_job_history_status ON job_execution_history_V2(status);

-- Clean old history
DELETE FROM job_execution_history_V2 
WHERE start_time < DATEADD(month, -6, GETDATE());
```

#### Application Tuning
```yaml
# Increase thread pool for concurrent jobs
scheduler:
  executors:
    default:
      class: apscheduler.executors.pool:ThreadPoolExecutor
      max_workers: 50
    
# Enable connection pooling
database:
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
```

### Monitoring and Alerts

#### Health Check Endpoint
```python
@app.route('/api/health')
def health_check():
    """System health check"""
    checks = {
        'database': check_database_connection(),
        'scheduler': check_scheduler_status(),
        'disk_space': check_disk_space(),
        'memory': check_memory_usage()
    }
    
    status = 'healthy' if all(checks.values()) else 'unhealthy'
    return jsonify({
        'status': status,
        'checks': checks,
        'timestamp': datetime.now().isoformat()
    })
```

#### Metrics Collection
```python
# Prometheus metrics example
from prometheus_client import Counter, Histogram, Gauge

job_executions_total = Counter('job_executions_total', 
                               'Total job executions',
                               ['job_name', 'status'])
job_duration_seconds = Histogram('job_duration_seconds',
                                 'Job execution duration',
                                 ['job_name'])
active_jobs = Gauge('active_jobs', 'Currently running jobs')
```

---

## Appendix A: Security Considerations

### Authentication and Authorization
- Windows Authentication for database connections
- User role-based access control for web interface
- API key authentication for REST endpoints
- Encrypted storage of sensitive credentials

### Best Practices
1. Use service accounts for job execution
2. Implement least privilege principle
3. Encrypt sensitive job parameters
4. Audit log all job modifications
5. Regular security updates

---

## Appendix B: Migration Guide

### Migrating from V1 to V2
1. Export existing job configurations
2. Convert to YAML format
3. Update database schema
4. Migrate execution history
5. Test in staging environment

---

## Appendix C: API Response Codes

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created |
| 400 | Bad Request | Invalid parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Access denied |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 500 | Internal Error | Server error |
| 503 | Service Unavailable | Service temporarily unavailable |

---

## Support and Contact

**Documentation Version**: 2.0
**Last Updated**: September 2025
**Support Email**: support@company.com
**GitHub**: https://github.com/company/job-scheduler

---

*This documentation covers approximately 95% of the Job Scheduler system functionality. For specific implementation details or advanced configurations, please refer to the inline code documentation or contact the development team.*