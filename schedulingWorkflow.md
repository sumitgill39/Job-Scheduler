Complete Scheduling Workflow: From JSON to Output Generation

  Here's exactly how the scheduling system works from creation to
  execution and output generation:

  ┌─────────────────────────────────────────────────────────────────
  ────────────────┐
  │                           SCHEDULING WORKFLOW
                 │
  └─────────────────────────────────────────────────────────────────
  ────────────────┘

  📋 STEP 1: JOB CREATION WITH SCHEDULE
     ├─ User creates job via web UI with JSON configuration
     ├─ Job data includes: { name, type, configuration, schedule }
     └─ integrated_scheduler.py:94 → create_job_with_schedule()

  📋 STEP 2: JOB STORAGE & SCHEDULING
     ├─ job_manager.py → create_job() → saves to SQL Server database
     ├─ integrated_scheduler.py:116 → schedule_job() → adds to
  APScheduler
     └─ Creates trigger: CronTrigger/IntervalTrigger/DateTrigger

  📋 STEP 3: BACKGROUND SCHEDULING
     ├─ APScheduler runs in background thread
     ├─ When schedule triggers → calls _execute_scheduled_job()
     └─ integrated_scheduler.py:269 → _execute_scheduled_job()

  📋 STEP 4: JOB EXECUTION ENGINE
     ├─ job_executor.py:57 → execute_job()
     ├─ Loads job config from database
     ├─ Creates job instance: SqlJob or PowerShellJob
     └─ Logs execution start to job_execution_history table

  📋 STEP 5: TYPE-SPECIFIC EXECUTION
     ┌─ SQL JOBS (sql_job.py):
     │  ├─ Parses JSON: { sql: { query, connection_name, timeout } }
     │  ├─ Gets database connection from connection pool  
     │  ├─ Executes SQL query with pyodbc
     │  ├─ Handles SELECT (returns rows) vs non-SELECT (rows 
  affected)
     │  └─ Formats output: "Query executed successfully. Returned X 
  rows."
     │
     └─ POWERSHELL JOBS (powershell_job.py):
        ├─ Parses JSON: { powershell: { script_content, parameters }
   }
        ├─ Creates temporary .ps1 file from script_content
        ├─ Executes via windows_utils.execute_powershell_script()
        ├─ Captures stdout/stderr from PowerShell process
        └─ Returns formatted output with execution results

  📋 STEP 6: RESULT PROCESSING & LOGGING
     ├─ job_executor.py:125 → _log_execution_completion()
     ├─ Updates job_execution_history with:
     │  ├─ Status (SUCCESS/FAILED/TIMEOUT)
     │  ├─ Duration in seconds
     │  ├─ Output text (first 1000 chars for API)
     │  ├─ Error messages (if any)
     │  └─ Full metadata as JSON
     └─ Database stores complete execution history

  JSON Configuration Examples:

  SQL Job JSON:

  {
    "name": "Daily Sales Report",
    "job_type": "sql",
    "configuration": {
      "sql": {
        "query": "SELECT COUNT(*) as sales_count FROM orders WHERE 
  date = GETDATE()",
        "connection_name": "production_db",
        "query_timeout": 300,
        "max_rows": 1000
      },
      "basic": {
        "timeout": 600,
        "max_retries": 3
      }
    },
    "schedule": {
      "type": "cron",
      "cron": "0 0 8 * * 1-5"  // 8 AM weekdays
    }
  }

  PowerShell Job JSON:

  {
    "name": "System Cleanup",
    "job_type": "powershell",
    "configuration": {
      "powershell": {
        "script_content": "Get-ChildItem C:\\Temp -Recurse | 
  Remove-Item -Force",
        "execution_policy": "Bypass",
        "timeout": 300
      }
    },
    "schedule": {
      "type": "interval",
      "interval": {
        "hours": 24
      }
    }
  }

  Output Generation Process:

  SQL Jobs Output:

  1. SELECT Queries: Returns structured data with columns and rows
  2. Non-SELECT: Returns rows affected count
  3. Format: "Query executed successfully. Returned 45 rows."
  4. Metadata: Full result set stored in JSON metadata field

  PowerShell Jobs Output:

  1. Captures: stdout, stderr, exit code from PowerShell process
  2. Format: Raw PowerShell console output
  3. Success: Returns script output text
  4. Failure: Returns error messages and stack traces

  Database Storage:

  All results stored in job_execution_history table:
  - status: SUCCESS/FAILED/TIMEOUT
  - output: Text summary (truncated for API responses)
  - error_message: Error details if failed
  - metadata: Full JSON with complete results, timing, parameters
  - duration_seconds: Execution time
  - start_time/end_time: Timestamps

  The system provides complete audit trail of all scheduled job
  executions with full output capture and structured logging.