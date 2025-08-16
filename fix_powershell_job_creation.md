# Fix for PowerShell Job Creation Issue

## Problem Summary
The "Create PowerShell Job" button fails to insert job configuration into the database due to missing ODBC drivers on macOS.

## Root Cause
- **Environment**: macOS system trying to connect to SQL Server
- **Missing Component**: ODBC Driver 17 for SQL Server not available on macOS
- **Error**: `Can't open lib 'ODBC Driver 17 for SQL Server' : file not found`

## Error Flow
1. User fills PowerShell job form and clicks "Create PowerShell Job"
2. JavaScript correctly collects form data and sends to `/api/jobs`
3. API endpoint validates data and calls `JobManager.create_job()`
4. JobManager builds job configuration correctly
5. **FAILURE**: `_save_job_to_database()` cannot connect to system database
6. Returns error: "Failed to save job to database"

## Solutions

### Option 1: Install ODBC Driver for macOS (Recommended)

```bash
# Install Microsoft ODBC Driver 18 for SQL Server on macOS
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install mssql-tools18
```

Then update `/config/database_config.yaml`:
```yaml
databases:
  system:
    driver: "{ODBC Driver 18 for SQL Server}"  # Change from 17 to 18
    server: "USDF11DB197\\PROD_DB01"
    port: 3433
    database: "sreutil"
    trusted_connection: false
    username: "svc-devops"
    password: "Welcome@1234"
```

### Option 2: Development SQLite Alternative

Create a development configuration that uses SQLite instead of SQL Server for testing:

```python
# Add to job_manager.py
def _get_development_storage(self):
    """Use SQLite for development on macOS"""
    import sqlite3
    import os
    
    db_path = os.path.join(os.getcwd(), 'dev_jobs.db')
    conn = sqlite3.connect(db_path)
    
    # Create table if not exists
    conn.execute('''
        CREATE TABLE IF NOT EXISTS job_configurations (
            job_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            job_type TEXT NOT NULL,
            configuration TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT DEFAULT 'system'
        )
    ''')
    
    return conn
```

## Verification Steps

1. **Check ODBC drivers available**:
   ```python
   import pyodbc
   print(pyodbc.drivers())
   ```

2. **Test database connection**:
   ```python
   from database.connection_pool import get_connection_pool
   pool = get_connection_pool()
   conn = pool.get_connection("system")
   print("Connection successful" if conn else "Connection failed")
   ```

3. **Test PowerShell job creation** via web UI

## Prevention
- Add environment detection in connection manager
- Provide fallback storage options for development
- Include ODBC driver installation in setup documentation

## Files Affected
- `config/database_config.yaml` (driver version)
- `core/job_manager.py` (connection handling)
- `database/connection_pool.py` (error handling)