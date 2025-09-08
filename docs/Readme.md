# Job Scheduler V2 - Modern Multi-Timezone Execution Architecture

## Overview

Job Scheduler V2 is a complete redesign of the job execution system, featuring timezone-based queuing, multi-step job workflows, and an extensible architecture for different job types. This system replaces the legacy single-execution model with a modern, scalable approach designed for enterprise requirements.

## Key Features

- **🌍 Timezone-Based Queuing**: Separate execution queues for different timezones
- **📋 Multi-Step Jobs**: Jobs can contain sequential execution steps
- **🔌 Extensible Architecture**: Plugin-based system for new job types
- **⚡ Async Execution Engine**: Modern async/await architecture for performance
- **🔄 Backward Compatibility**: Maintains existing API compatibility
- **📊 Real-time Monitoring**: Comprehensive execution status tracking

## Architecture Overview

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    Job Scheduler V2 Architecture                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │   Web UI/API    │    │  Modern Job API  │    │   Legacy    │ │
│  │   (Flask)       │◄──►│   (V2 Routes)    │◄──►│  API Bridge │ │
│  └─────────────────┘    └──────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           ▼                       ▼                       ▼     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              New Execution Engine                           │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │ │
│  │  │ Timezone Queue  │  │ Timezone Queue  │  │ Timezone    │ │ │
│  │  │     (UTC)       │  │     (EST)       │  │   Queue     │ │ │
│  │  │                 │  │                 │  │   (PST)     │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│           │                       │                       │     │
│           ▼                       ▼                       ▼     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                Step Factory & Executors                     │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │   SQL Step  │  │PowerShell   │  │  Azure DevOps Step  │ │ │
│  │  │  Executor   │  │   Step      │  │      (Future)       │ │ │
│  │  │             │  │  Executor   │  │                     │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Job Submission**: Jobs submitted through Web UI or API
2. **Timezone Routing**: Jobs routed to appropriate timezone queue
3. **Multi-Step Processing**: Each job's steps executed sequentially
4. **Result Aggregation**: Step results combined into final job result
5. **Status Reporting**: Real-time status updates available via API

## Job Structure

### Multi-Step Job Definition

```json
{
  "id": "job_001",
  "name": "Database Maintenance Job",
  "description": "Daily database cleanup and reporting",
  "timezone": "America/New_York",
  "enabled": true,
  "max_retries": 2,
  "timeout_seconds": 3600,
  "steps": [
    {
      "id": "cleanup_step",
      "name": "Database Cleanup",
      "type": "sql",
      "query": "DELETE FROM logs WHERE created_at < DATEADD(day, -30, GETDATE())",
      "connection_name": "prod_db",
      "timeout": 300
    },
    {
      "id": "report_step", 
      "name": "Generate Report",
      "type": "powershell",
      "script_path": "./scripts/generate_report.ps1",
      "parameters": {"date": "{{today}}"},
      "timeout": 600
    }
  ],
  "schedule": {
    "type": "cron",
    "expression": "0 2 * * *"
  }
}
```

## Available Step Types

### SQL Step
- **Purpose**: Execute SQL queries against configured databases
- **Configuration**: Connection name, query, timeout
- **Features**: Transaction support, parameter binding, result caching

### PowerShell Step  
- **Purpose**: Execute PowerShell scripts with parameters
- **Configuration**: Script path or inline script, parameters, execution policy
- **Features**: Secure parameter passing, output capture, error handling

### Azure DevOps Step (Future)
- **Purpose**: Trigger Azure DevOps pipelines and workflows
- **Configuration**: Organization, project, pipeline ID, variables
- **Features**: Build triggering, release management, artifact handling

## API Endpoints

### V2 API Endpoints

- `POST /api/v2/jobs/execute` - Execute job immediately
- `POST /api/v2/jobs/schedule` - Schedule job for future execution
- `GET /api/v2/execution/status` - Get execution engine status
- `GET /api/v2/steps/types` - Get available step types

### Legacy Compatibility
- All existing V1 endpoints remain functional
- Automatic conversion from legacy format to V2 format
- Gradual migration path for existing jobs

## Timezone Management

### Supported Timezones
The system automatically creates queues for any timezone specified in job definitions:
- UTC (default)
- America/New_York (EST/EDT)
- America/Los_Angeles (PST/PDT)
- Europe/London (GMT/BST)
- Asia/Tokyo (JST)
- And any other IANA timezone identifier

### Queue Behavior
- Each timezone maintains its own execution queue
- Jobs scheduled based on local timezone time
- Automatic daylight saving time handling
- Load balancing across timezone queues

## File Structure

### Core Files
```
core/
├── new_execution_engine.py      # Main execution engine
├── modern_job_api.py           # V2 API implementation  
├── timezone_job_queue.py       # Timezone-based queuing
├── job_definition.py           # Job data structures
├── execution_steps/            # Step implementations
│   ├── __init__.py
│   ├── base_step.py           # Abstract base class
│   ├── sql_step.py            # SQL execution
│   ├── powershell_step.py     # PowerShell execution
│   └── azure_devops_step.py   # Azure DevOps (future)
└── step_factory.py            # Step creation factory
```

### Database Schema
```
database/
├── v2_models.py               # V2 SQLAlchemy models
└── migrations/
    └── v2_schema.sql          # Database migration script
```

### Web Interface
```
web_ui/
├── v2_routes.py              # V2 Flask routes
├── templates/v2/             # Modern UI templates
└── static/v2/                # V2 assets
```

## Getting Started

### Prerequisites
- Python 3.8+
- SQLAlchemy database


### Installation
1. **Database Migration**: Run V2 schema migration
2. **Dependencies**: Install new Python packages
3. **Configuration**: Update timezone settings
4. **Testing**: Validate with sample jobs

### Creating Your First V2 Job

```python
# Example: Multi-step database maintenance job
job_data = {
    "name": "Daily Maintenance",
    "timezone": "America/New_York", 
    "steps": [
        {
            "type": "sql",
            "query": "EXEC sp_cleanup_logs",
            "connection_name": "main_db"
        },
        {
            "type": "powershell", 
            "script": "Send-StatusEmail.ps1",
            "parameters": {"status": "completed"}
        }
    ]
}

# Execute immediately
result = modern_job_api.execute_job_immediately(job_data)

# Or schedule for later
scheduled_time = datetime(2024, 12, 25, 9, 0, 0)  # 9 AM on Christmas
result = modern_job_api.schedule_job(job_data, scheduled_time)
```

## Migration Guide

### Phase 1: Parallel Operation
- V2 system runs alongside V1
- New jobs use V2 architecture
- Existing jobs continue on V1

### Phase 2: Data Migration  
- Convert existing job definitions to V2 format
- Migrate execution history
- Update scheduled jobs

### Phase 3: Full Cutover
- Disable V1 endpoints
- Remove legacy code
- Complete V2 adoption

## Monitoring & Troubleshooting

### Execution Status
```bash
# Get real-time execution status
curl http://localhost:5000/api/v2/execution/status

# Response includes:
# - Active timezone queues
# - Running job counts
# - Queue depths
# - System health metrics
```

### Logging
- Enhanced structured logging
- Timezone-aware timestamps
- Step-level execution tracking
- Performance metrics

### Common Issues
- **Timezone Configuration**: Ensure IANA timezone identifiers
- **Step Dependencies**: Verify step execution order
- **Resource Limits**: Monitor queue depths and execution times
- **Database Connections**: Validate connection pool settings

## Performance & Scaling

### Capacity Planning
- **Concurrent Jobs**: Up to 50 concurrent executions per timezone
- **Step Execution**: Parallel step processing within jobs
- **Queue Management**: Automatic queue balancing and overflow handling

### Optimization Features
- Connection pooling for database steps
- Script caching for PowerShell steps
- Result caching for expensive operations
- Automatic retry with exponential backoff

## Security

### Step Isolation
- Each step executes in isolated context
- Secure parameter passing
- No cross-step data leakage

### Access Control
- API key authentication for V2 endpoints
- Role-based step type access
- Audit logging for all executions

### Data Protection
- Encrypted parameter storage
- Secure credential management
- PII handling compliance

## Support & Documentation

### Additional Resources
- **EDD Document**: `docs/EDD_JobExecution_V2.md` - Complete technical specifications
- **API Documentation**: Generated from OpenAPI specifications
- **Examples**: `examples/` directory with sample jobs
- **Migration Tools**: `tools/migration/` utilities for V1 to V2 conversion

### Getting Help
- Check execution logs in `logs/scheduler.log`
- Review API response error messages
- Consult EDD for detailed technical information
- Contact system administrators for database issues

---

**Job Scheduler V2** - Built for scale, designed for the future of enterprise job execution.