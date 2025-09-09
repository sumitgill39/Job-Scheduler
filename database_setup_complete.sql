-- =============================================
-- Windows Job Scheduler - Complete Database Setup Script V2.1
-- =============================================
-- This script creates ALL required tables, indexes, and initial data
-- for the Windows Job Scheduler application to function properly.
-- 
-- Target Database: SQL Server (SUMEETGILL7E47\MSSQLSERVER01)
-- Database: sreutil
-- Authentication: Windows Authentication (Trusted Connection)
-- Version: 2.1 (Includes Agent Management & Passive Agent Support)
-- Created: 2025-09-06, Updated: 2025-09-08
-- =============================================

USE [sreutil]
GO

PRINT '============================================='
PRINT 'Windows Job Scheduler V2.1 Database Setup'
PRINT 'Starting complete database initialization...'
PRINT '(Includes Agent Management & Passive Agent Support)'
PRINT '============================================='

-- =============================================
-- STEP 1: Drop existing tables if they exist (Clean Start)
-- =============================================
PRINT 'Step 1: Cleaning up existing tables...'

-- Drop in dependency order
IF EXISTS (SELECT * FROM sysobjects WHERE name='agent_job_assignments' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[agent_job_assignments]
    PRINT '  - Dropped existing agent_job_assignments'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='job_execution_history_v2' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[job_execution_history_v2]
    PRINT '  - Dropped existing job_execution_history_v2'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='job_configurations_v2' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[job_configurations_v2]
    PRINT '  - Dropped existing job_configurations_v2'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='agent_registry' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[agent_registry]
    PRINT '  - Dropped existing agent_registry'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='user_connections' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[user_connections]
    PRINT '  - Dropped existing user_connections'
END

-- Drop old V1 tables if they exist
IF EXISTS (SELECT * FROM sysobjects WHERE name='job_configurations' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[job_configurations]
    PRINT '  - Dropped old V1 job_configurations'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='job_execution_history' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[job_execution_history]
    PRINT '  - Dropped old V1 job_execution_history'
END

IF EXISTS (SELECT * FROM sysobjects WHERE name='job_execution_history_V2' AND xtype='U')
BEGIN
    DROP TABLE [dbo].[job_execution_history_V2]
    PRINT '  - Dropped misnamed job_execution_history_V2'
END

PRINT 'Step 1: Table cleanup completed'
GO

-- =============================================
-- STEP 2: Create user_connections table
-- =============================================
PRINT 'Step 2: Creating user_connections table...'

CREATE TABLE [dbo].[user_connections] (
    -- Primary key and identification
    [connection_id] NVARCHAR(100) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    
    -- Connection details
    [server_name] NVARCHAR(255) NOT NULL,
    [port] INT DEFAULT 1433,
    [database_name] NVARCHAR(255) NOT NULL,
    
    -- Authentication
    [trusted_connection] BIT DEFAULT 1,
    [username] NVARCHAR(255) NULL,
    [password] NVARCHAR(500) NULL,  -- Encrypted passwords
    
    -- Connection configuration
    [driver] NVARCHAR(255) DEFAULT '{ODBC Driver 17 for SQL Server}',
    [connection_timeout] INT DEFAULT 30,
    [command_timeout] INT DEFAULT 300,
    [encrypt] BIT DEFAULT 0,
    [trust_server_certificate] BIT DEFAULT 1,
    
    -- Metadata
    [description] NVARCHAR(1000) NULL,
    [created_date] DATETIME DEFAULT GETDATE(),
    [modified_date] DATETIME DEFAULT GETDATE(),
    [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER,
    [is_active] BIT DEFAULT 1
)

-- Create indexes for user_connections
CREATE INDEX IX_user_connections_name ON [dbo].[user_connections]([name])
CREATE INDEX IX_user_connections_active ON [dbo].[user_connections]([is_active])
CREATE INDEX IX_user_connections_server ON [dbo].[user_connections]([server_name])
CREATE INDEX IX_user_connections_created ON [dbo].[user_connections]([created_date])

PRINT '  - user_connections table created with 4 indexes'
GO

-- =============================================
-- STEP 2.5: Create agent_registry table (Agent Management)
-- =============================================
PRINT 'Step 2.5: Creating agent_registry table...'

CREATE TABLE [dbo].[agent_registry] (
    -- Primary identification
    [agent_id] NVARCHAR(50) PRIMARY KEY,
    [agent_name] NVARCHAR(255) NOT NULL,
    [hostname] NVARCHAR(255) NOT NULL,
    [ip_address] NVARCHAR(50) NOT NULL,
    
    -- Passive agent connection info
    [agent_port] INT NULL,                    -- Port for passive agents
    [agent_endpoint] NVARCHAR(255) NULL,     -- Full endpoint URL for passive agents
    
    -- Agent capabilities and pool assignment
    [agent_pool] NVARCHAR(100) DEFAULT 'default',
    [capabilities] NTEXT NULL,               -- JSON array of capabilities
    [max_parallel_jobs] INT DEFAULT 1,
    [agent_version] NVARCHAR(20) NULL,
    
    -- System information
    [os_info] NVARCHAR(255) NULL,
    [cpu_cores] INT NULL,
    [memory_gb] INT NULL,
    [disk_space_gb] INT NULL,
    
    -- Status and health
    [status] NVARCHAR(20) DEFAULT 'offline', -- online, offline, maintenance, error
    [last_heartbeat] DATETIME NULL,
    [last_job_completed] DATETIME NULL,
    [current_jobs] INT DEFAULT 0,
    [cpu_percent] FLOAT NULL,
    [memory_percent] FLOAT NULL,
    [disk_percent] FLOAT NULL,
    
    -- Security and authentication
    [api_key_hash] NVARCHAR(255) NULL,
    [jwt_secret] NVARCHAR(255) NULL,
    
    -- Metadata
    [registered_date] DATETIME DEFAULT GETDATE(),
    [last_updated] DATETIME DEFAULT GETDATE(),
    [is_active] BIT DEFAULT 1,
    [is_approved] BIT DEFAULT 0              -- Require manual approval
)

-- Create indexes for agent_registry
CREATE INDEX IX_agent_registry_pool ON [dbo].[agent_registry]([agent_pool])
CREATE INDEX IX_agent_registry_status ON [dbo].[agent_registry]([status])
CREATE INDEX IX_agent_registry_active ON [dbo].[agent_registry]([is_active])
CREATE INDEX IX_agent_registry_approved ON [dbo].[agent_registry]([is_approved])
CREATE INDEX IX_agent_registry_heartbeat ON [dbo].[agent_registry]([last_heartbeat])
CREATE INDEX IX_agent_registry_hostname ON [dbo].[agent_registry]([hostname])
CREATE INDEX IX_agent_registry_ip_address ON [dbo].[agent_registry]([ip_address])
CREATE INDEX IX_agent_registry_endpoint ON [dbo].[agent_registry]([agent_endpoint])

PRINT '  - agent_registry table created with 8 indexes'
GO

-- =============================================
-- STEP 2.6: Create agent_job_assignments table (Job Assignment Tracking)
-- =============================================
PRINT 'Step 2.6: Creating agent_job_assignments table...'

CREATE TABLE [dbo].[agent_job_assignments] (
    -- Primary key and references
    [assignment_id] NVARCHAR(36) PRIMARY KEY, -- UUID
    [execution_id] NVARCHAR(36) NOT NULL,     -- Links to job_execution_history_v2
    [job_id] NVARCHAR(36) NOT NULL,           -- Links to job_configurations_v2
    [agent_id] NVARCHAR(50) NOT NULL,         -- Links to agent_registry
    
    -- Assignment details
    [pool_id] NVARCHAR(100) NULL,
    [assignment_status] NVARCHAR(20) DEFAULT 'assigned', -- assigned, running, completed, failed, cancelled
    [assigned_at] DATETIME DEFAULT GETDATE(),
    [started_at] DATETIME NULL,
    [completed_at] DATETIME NULL,
    
    -- Results
    [result_status] NVARCHAR(20) NULL,        -- success, failed, timeout, error
    [result_message] NTEXT NULL,
    [output_log] NTEXT NULL,
    [error_log] NTEXT NULL,
    
    -- Metadata
    [created_date] DATETIME DEFAULT GETDATE(),
    [last_updated] DATETIME DEFAULT GETDATE()
)

-- Create indexes for agent_job_assignments
CREATE INDEX IX_agent_job_assignments_execution_id ON [dbo].[agent_job_assignments]([execution_id])
CREATE INDEX IX_agent_job_assignments_job_id ON [dbo].[agent_job_assignments]([job_id])
CREATE INDEX IX_agent_job_assignments_agent_id ON [dbo].[agent_job_assignments]([agent_id])
CREATE INDEX IX_agent_job_assignments_status ON [dbo].[agent_job_assignments]([assignment_status])
CREATE INDEX IX_agent_job_assignments_assigned_at ON [dbo].[agent_job_assignments]([assigned_at])
CREATE INDEX IX_agent_job_assignments_pool_id ON [dbo].[agent_job_assignments]([pool_id])

-- Create foreign key constraints
ALTER TABLE [dbo].[agent_job_assignments]
ADD CONSTRAINT FK_agent_job_assignments_agent_id 
FOREIGN KEY ([agent_id]) REFERENCES [dbo].[agent_registry]([agent_id])
ON DELETE CASCADE

PRINT '  - agent_job_assignments table created with 6 indexes and 1 foreign key'
GO

-- =============================================
-- STEP 3: Create job_configurations_v2 table (V2 Schema)
-- =============================================
PRINT 'Step 3: Creating job_configurations_v2 table...'

CREATE TABLE [dbo].[job_configurations_v2] (
    -- Primary key and basic info
    [job_id] NVARCHAR(36) PRIMARY KEY,  -- UUID
    [name] NVARCHAR(255) NOT NULL,
    [description] NTEXT NULL,
    [version] NVARCHAR(20) DEFAULT '2.0',
    
    -- Job configuration in YAML format (V2 Feature)
    [yaml_configuration] NTEXT NOT NULL,  -- YAML string - MAIN CONFIG
    
    -- Metadata and status
    [enabled] BIT DEFAULT 1,
    [created_date] DATETIME DEFAULT GETDATE(),
    [modified_date] DATETIME DEFAULT GETDATE(),
    [created_by] NVARCHAR(255) DEFAULT 'system',
    
    -- Execution tracking (V2 Enhanced)
    [last_execution_id] NVARCHAR(36) NULL,  -- Last execution UUID
    [last_execution_status] NVARCHAR(50) NULL,  -- success, failed, running, pending
    [last_execution_time] DATETIME NULL,
    [next_scheduled_time] DATETIME NULL,
    
    -- Performance metrics (V2 Analytics)
    [total_executions] INT DEFAULT 0,
    [successful_executions] INT DEFAULT 0,
    [failed_executions] INT DEFAULT 0,
    [average_duration_seconds] FLOAT NULL
)

-- Create comprehensive indexes for job_configurations_v2
CREATE INDEX IX_job_configurations_v2_enabled ON [dbo].[job_configurations_v2]([enabled])
CREATE INDEX IX_job_configurations_v2_name ON [dbo].[job_configurations_v2]([name])
CREATE INDEX IX_job_configurations_v2_created_date ON [dbo].[job_configurations_v2]([created_date])
CREATE INDEX IX_job_configurations_v2_last_execution_status ON [dbo].[job_configurations_v2]([last_execution_status])
CREATE INDEX IX_job_configurations_v2_next_scheduled_time ON [dbo].[job_configurations_v2]([next_scheduled_time])
CREATE INDEX IX_job_configurations_v2_version ON [dbo].[job_configurations_v2]([version])
CREATE INDEX IX_job_configurations_v2_last_execution_time ON [dbo].[job_configurations_v2]([last_execution_time])

PRINT '  - job_configurations_v2 table created with 7 performance indexes'
GO

-- =============================================
-- STEP 4: Create job_execution_history_v2 table (Enhanced V2 Schema)
-- =============================================
PRINT 'Step 4: Creating job_execution_history_v2 table...'

CREATE TABLE [dbo].[job_execution_history_v2] (
    -- Primary key (UUID, not auto-increment)
    [execution_id] NVARCHAR(36) PRIMARY KEY,  -- UUID for execution tracking
    [job_id] NVARCHAR(36) NOT NULL,  -- Foreign key to job_configurations_v2
    
    -- Basic execution details
    [job_name] NVARCHAR(255) NULL,
    [status] NVARCHAR(50) NOT NULL,  -- pending, running, success, failed, timeout, cancelled
    [start_time] DATETIME NULL,
    [end_time] DATETIME NULL,
    [duration_seconds] FLOAT NULL,
    
    -- Results and logging (V2 Enhanced)
    [output_log] NTEXT NULL,  -- Execution output/logs (renamed from 'output')
    [error_message] NTEXT NULL,
    [return_code] INT NULL,
    
    -- V2 New Features: Step-by-step execution details
    [step_results] NTEXT NULL,  -- JSON array of step results
    
    -- V2 New Features: Execution context
    [execution_mode] NVARCHAR(50) NULL,  -- scheduled, manual, api
    [executed_by] NVARCHAR(255) DEFAULT 'system',
    [execution_timezone] NVARCHAR(50) NULL,  -- Timezone tracking
    [server_info] NTEXT NULL,  -- JSON with server/system info
    
    -- V2 New Features: Performance metrics
    [memory_usage_mb] FLOAT NULL,
    [cpu_time_seconds] FLOAT NULL,
    
    -- V2 Enhanced: Retry information
    [retry_count] INT DEFAULT 0,
    [max_retries] INT DEFAULT 0,
    [is_retry] BIT DEFAULT 0,
    [parent_execution_id] NVARCHAR(36) NULL,  -- Original execution if this is a retry
    
    -- Agent execution support (New for V2.1)
    [executed_on_agent] NVARCHAR(50) NULL,   -- Agent ID that executed this job
    [assignment_id] NVARCHAR(36) NULL        -- Links to agent_job_assignments
)

-- Create comprehensive indexes for job_execution_history_v2
CREATE INDEX IX_job_execution_history_v2_job_id ON [dbo].[job_execution_history_v2]([job_id])
CREATE INDEX IX_job_execution_history_v2_status ON [dbo].[job_execution_history_v2]([status])
CREATE INDEX IX_job_execution_history_v2_start_time ON [dbo].[job_execution_history_v2]([start_time])
CREATE INDEX IX_job_execution_history_v2_execution_mode ON [dbo].[job_execution_history_v2]([execution_mode])
CREATE INDEX IX_job_execution_history_v2_end_time ON [dbo].[job_execution_history_v2]([end_time])
CREATE INDEX IX_job_execution_history_v2_duration ON [dbo].[job_execution_history_v2]([duration_seconds])
CREATE INDEX IX_job_execution_history_v2_executed_by ON [dbo].[job_execution_history_v2]([executed_by])
CREATE INDEX IX_job_execution_history_v2_is_retry ON [dbo].[job_execution_history_v2]([is_retry])
CREATE INDEX IX_job_execution_history_v2_parent_execution ON [dbo].[job_execution_history_v2]([parent_execution_id])
CREATE INDEX IX_job_execution_history_v2_executed_on_agent ON [dbo].[job_execution_history_v2]([executed_on_agent])
CREATE INDEX IX_job_execution_history_v2_assignment_id ON [dbo].[job_execution_history_v2]([assignment_id])

-- Create foreign key constraint
ALTER TABLE [dbo].[job_execution_history_v2]
ADD CONSTRAINT FK_job_execution_history_v2_job_id 
FOREIGN KEY ([job_id]) REFERENCES [dbo].[job_configurations_v2]([job_id])
ON DELETE CASCADE

-- Add foreign key constraints for agent support
ALTER TABLE [dbo].[job_execution_history_v2]
ADD CONSTRAINT FK_job_execution_history_v2_agent_id 
FOREIGN KEY ([executed_on_agent]) REFERENCES [dbo].[agent_registry]([agent_id])
ON DELETE SET NULL

ALTER TABLE [dbo].[job_execution_history_v2]
ADD CONSTRAINT FK_job_execution_history_v2_assignment_id 
FOREIGN KEY ([assignment_id]) REFERENCES [dbo].[agent_job_assignments]([assignment_id])
ON DELETE NO ACTION

PRINT '  - job_execution_history_v2 table created with 11 indexes and 3 foreign keys'
GO

-- =============================================
-- STEP 5: Insert default connection configurations
-- =============================================
PRINT 'Step 5: Inserting default connection configurations...'

-- Insert system connection (for internal use)
INSERT INTO [dbo].[user_connections] (
    [connection_id], [name], [server_name], [database_name], 
    [trusted_connection], [description], [created_by]
) VALUES (
    'system', 
    'System Database Connection', 
    'DESKTOP-4ADGDVE\SQLEXPRESS', 
    'sreutil',
    1,
    'Default system connection for internal operations',
    'SYSTEM_SETUP'
)

-- Insert default connection template
INSERT INTO [dbo].[user_connections] (
    [connection_id], [name], [server_name], [database_name], 
    [trusted_connection], [description], [created_by]
) VALUES (
    'default', 
    'Default SQL Server Connection', 
    'DESKTOP-4ADGDVE\SQLEXPRESS', 
    'sreutil',
    1,
    'Default connection template for SQL jobs',
    'SYSTEM_SETUP'
)

-- Insert sample external connection
INSERT INTO [dbo].[user_connections] (
    [connection_id], [name], [server_name], [database_name], 
    [trusted_connection], [description], [created_by]
) VALUES (
    'sample_external', 
    'Sample External Database', 
    'localhost', 
    'tempdb',
    1,
    'Sample connection for external database operations',
    'SYSTEM_SETUP'
)

PRINT '  - Inserted 3 default connection configurations'
GO

-- =============================================
-- STEP 6: Insert sample job configurations for testing
-- =============================================
PRINT 'Step 6: Inserting sample job configurations...'

-- Sample SQL job
INSERT INTO [dbo].[job_configurations_v2] (
    [job_id], [name], [description], [yaml_configuration], 
    [enabled], [created_by]
) VALUES (
    'sample-sql-job-001',
    'System Health Check SQL Job',
    'Sample SQL job that checks system database health',
    'name: "System Health Check SQL Job"
type: "sql"
connection: "system"
query: |
  SELECT 
    GETDATE() as current_time,
    @@VERSION as sql_version,
    DB_NAME() as database_name,
    ''System health check completed successfully'' as message
schedule:
  type: "interval"
  interval:
    minutes: 30
  timezone: "UTC"
timeout: 60
max_retries: 2',
    1,
    'SYSTEM_SETUP'
)

-- Sample PowerShell job
INSERT INTO [dbo].[job_configurations_v2] (
    [job_id], [name], [description], [yaml_configuration], 
    [enabled], [created_by]
) VALUES (
    'sample-powershell-job-001',
    'System Information PowerShell Job',
    'Sample PowerShell job that gathers system information',
    'name: "System Information PowerShell Job"
type: "powershell"
inlineScript: |
  Write-Output "=== System Information ==="
  Write-Output "Computer Name: $($env:COMPUTERNAME)"
  Write-Output "User: $($env:USERNAME)"
  Write-Output "OS: $(Get-WmiObject -Class Win32_OperatingSystem | Select-Object -ExpandProperty Caption)"
  Write-Output "PowerShell Version: $($PSVersionTable.PSVersion)"
  Write-Output "Current Time: $(Get-Date)"
  Write-Output "=== Job Completed Successfully ==="
executionPolicy: "RemoteSigned"
schedule:
  type: "cron"
  cron: "0 0 8 * * *"  # Daily at 8 AM
  timezone: "UTC"
timeout: 120
max_retries: 1',
    1,
    'SYSTEM_SETUP'
)

-- Sample disabled job for testing
INSERT INTO [dbo].[job_configurations_v2] (
    [job_id], [name], [description], [yaml_configuration], 
    [enabled], [created_by]
) VALUES (
    'sample-disabled-job-001',
    'Disabled Test Job',
    'Sample disabled job for testing job management',
    'name: "Disabled Test Job"
type: "sql"
connection: "system"
query: |
  SELECT ''This job is disabled for testing'' as message
schedule:
  type: "interval"
  interval:
    hours: 1
timeout: 30',
    0,  -- Disabled
    'SYSTEM_SETUP'
)

PRINT '  - Inserted 3 sample job configurations (2 enabled, 1 disabled)'
GO

-- =============================================
-- STEP 6.5: Insert sample agent configurations for testing
-- =============================================
PRINT 'Step 6.5: Inserting sample agent configurations...'

-- Sample passive agent
INSERT INTO [dbo].[agent_registry] (
    [agent_id], [agent_name], [hostname], [ip_address], [agent_port], 
    [agent_endpoint], [agent_pool], [capabilities], [max_parallel_jobs], 
    [agent_version], [os_info], [cpu_cores], [memory_gb], [disk_space_gb],
    [status], [is_approved]
) VALUES (
    'sample-passive-agent-001',
    'Sample Passive Agent',
    'DEVELOPMENT-HOST',
    '127.0.0.1',
    8081,
    'http://127.0.0.1:8081',
    'development',
    '["powershell", "cmd", "python", "passive_execution"]',
    3,
    '1.0.0-passive',
    'Windows 11 Pro',
    4,
    16,
    500,
    'offline',
    1
)

-- Sample active agent (for comparison)
INSERT INTO [dbo].[agent_registry] (
    [agent_id], [agent_name], [hostname], [ip_address], [agent_pool], 
    [capabilities], [max_parallel_jobs], [agent_version], [os_info], 
    [cpu_cores], [memory_gb], [disk_space_gb], [status], [is_approved]
) VALUES (
    'sample-active-agent-001',
    'Sample Active Agent',
    'PRODUCTION-HOST',
    '10.0.1.100',
    'production',
    '["powershell", "python", "shell"]',
    2,
    '1.0.0',
    'Windows Server 2019',
    8,
    32,
    1000,
    'offline',
    1
)

PRINT '  - Inserted 2 sample agent configurations (1 passive, 1 active)'
GO

-- =============================================
-- STEP 7: Create stored procedures for maintenance
-- =============================================
PRINT 'Step 7: Creating maintenance stored procedures...'

-- Procedure to clean old execution history
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_cleanup_execution_history]') AND type in (N'P', N'PC'))
    DROP PROCEDURE [dbo].[sp_cleanup_execution_history]
GO

CREATE PROCEDURE [dbo].[sp_cleanup_execution_history]
    @days_to_keep INT = 90
AS
BEGIN
    SET NOCOUNT ON
    
    DECLARE @cutoff_date DATETIME = DATEADD(day, -@days_to_keep, GETDATE())
    DECLARE @deleted_count INT
    
    DELETE FROM [dbo].[job_execution_history_v2]
    WHERE [start_time] < @cutoff_date
    
    SET @deleted_count = @@ROWCOUNT
    
    PRINT 'Cleaned up ' + CAST(@deleted_count AS NVARCHAR(10)) + ' execution history records older than ' + CAST(@days_to_keep AS NVARCHAR(10)) + ' days'
END
GO

-- Procedure to update job statistics
IF EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[sp_update_job_statistics]') AND type in (N'P', N'PC'))
    DROP PROCEDURE [dbo].[sp_update_job_statistics]
GO

CREATE PROCEDURE [dbo].[sp_update_job_statistics]
    @job_id NVARCHAR(36) = NULL
AS
BEGIN
    SET NOCOUNT ON
    
    -- Update statistics for specific job or all jobs
    UPDATE jc SET
        jc.total_executions = stats.total_executions,
        jc.successful_executions = stats.successful_executions,
        jc.failed_executions = stats.failed_executions,
        jc.average_duration_seconds = stats.avg_duration
    FROM [dbo].[job_configurations_v2] jc
    INNER JOIN (
        SELECT 
            job_id,
            COUNT(*) as total_executions,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_executions,
            SUM(CASE WHEN status IN ('failed', 'timeout', 'error') THEN 1 ELSE 0 END) as failed_executions,
            AVG(duration_seconds) as avg_duration
        FROM [dbo].[job_execution_history_v2]
        WHERE (@job_id IS NULL OR job_id = @job_id)
        GROUP BY job_id
    ) stats ON jc.job_id = stats.job_id
    
    PRINT 'Updated job statistics for ' + CAST(@@ROWCOUNT AS NVARCHAR(10)) + ' jobs'
END
GO

PRINT '  - Created 2 maintenance stored procedures'
GO

-- =============================================
-- STEP 8: Create views for reporting
-- =============================================
PRINT 'Step 8: Creating reporting views...'

-- View for job summary with latest execution
IF EXISTS (SELECT * FROM sys.views WHERE object_id = OBJECT_ID(N'[dbo].[vw_job_summary]'))
    DROP VIEW [dbo].[vw_job_summary]
GO

CREATE VIEW [dbo].[vw_job_summary]
AS
SELECT 
    jc.job_id,
    jc.name as job_name,
    jc.description,
    jc.enabled,
    jc.created_date,
    jc.total_executions,
    jc.successful_executions,
    jc.failed_executions,
    CASE 
        WHEN jc.total_executions > 0 
        THEN ROUND((CAST(jc.successful_executions AS FLOAT) / jc.total_executions) * 100, 2)
        ELSE 0 
    END as success_rate_percent,
    jc.average_duration_seconds,
    jc.last_execution_status,
    jc.last_execution_time,
    jc.next_scheduled_time,
    CASE 
        WHEN jc.enabled = 1 AND jc.next_scheduled_time IS NOT NULL THEN 'Scheduled'
        WHEN jc.enabled = 1 THEN 'Manual'
        ELSE 'Disabled'
    END as job_status
FROM [dbo].[job_configurations_v2] jc
GO

-- View for execution history with duration formatting
IF EXISTS (SELECT * FROM sys.views WHERE object_id = OBJECT_ID(N'[dbo].[vw_execution_history]'))
    DROP VIEW [dbo].[vw_execution_history]
GO

CREATE VIEW [dbo].[vw_execution_history]
AS
SELECT 
    eh.execution_id,
    eh.job_id,
    jc.name as job_name,
    eh.status,
    eh.start_time,
    eh.end_time,
    eh.duration_seconds,
    CASE 
        WHEN eh.duration_seconds IS NULL THEN 'N/A'
        WHEN eh.duration_seconds < 60 THEN CAST(ROUND(eh.duration_seconds, 2) AS NVARCHAR(10)) + ' seconds'
        WHEN eh.duration_seconds < 3600 THEN CAST(ROUND(eh.duration_seconds / 60, 2) AS NVARCHAR(10)) + ' minutes'
        ELSE CAST(ROUND(eh.duration_seconds / 3600, 2) AS NVARCHAR(10)) + ' hours'
    END as duration_formatted,
    eh.execution_mode,
    eh.executed_by,
    eh.return_code,
    eh.retry_count,
    eh.is_retry,
    DATALENGTH(eh.output_log) as output_length,
    CASE WHEN eh.error_message IS NOT NULL THEN 1 ELSE 0 END as has_error
FROM [dbo].[job_execution_history_v2] eh
LEFT JOIN [dbo].[job_configurations_v2] jc ON eh.job_id = jc.job_id
GO

PRINT '  - Created 2 reporting views'
GO

-- =============================================
-- STEP 9: Set up database permissions and security
-- =============================================
PRINT 'Step 9: Setting up database permissions...'

-- Grant necessary permissions to the application
-- Note: In production, create a specific database user for the application
-- For development with Windows Authentication, these permissions are typically inherited

-- Create database roles for job scheduler
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'job_scheduler_readers')
    CREATE ROLE job_scheduler_readers
GO

IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'job_scheduler_writers')
    CREATE ROLE job_scheduler_writers
GO

-- Grant permissions to roles
GRANT SELECT ON [dbo].[job_configurations_v2] TO job_scheduler_readers
GRANT SELECT ON [dbo].[job_execution_history_v2] TO job_scheduler_readers
GRANT SELECT ON [dbo].[user_connections] TO job_scheduler_readers
GRANT SELECT ON [dbo].[vw_job_summary] TO job_scheduler_readers
GRANT SELECT ON [dbo].[vw_execution_history] TO job_scheduler_readers

GRANT SELECT, INSERT, UPDATE, DELETE ON [dbo].[job_configurations_v2] TO job_scheduler_writers
GRANT SELECT, INSERT, UPDATE, DELETE ON [dbo].[job_execution_history_v2] TO job_scheduler_writers
GRANT SELECT, INSERT, UPDATE, DELETE ON [dbo].[user_connections] TO job_scheduler_writers
GRANT EXECUTE ON [dbo].[sp_cleanup_execution_history] TO job_scheduler_writers
GRANT EXECUTE ON [dbo].[sp_update_job_statistics] TO job_scheduler_writers

PRINT '  - Created database roles and granted permissions'
GO

-- =============================================
-- STEP 10: Verify installation and display summary
-- =============================================
PRINT 'Step 10: Verifying installation...'

-- Check all tables exist
DECLARE @table_count INT
SELECT @table_count = COUNT(*)
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE' 
AND TABLE_NAME IN ('user_connections', 'agent_registry', 'agent_job_assignments', 'job_configurations_v2', 'job_execution_history_v2')

IF @table_count = 5
BEGIN
    PRINT '  ✓ All 5 required tables created successfully'
END
ELSE
BEGIN
    PRINT '  ✗ ERROR: Missing tables! Expected 5, found ' + CAST(@table_count AS NVARCHAR(10))
END

-- Check indexes
SELECT 
    t.TABLE_NAME,
    COUNT(*) as index_count
FROM INFORMATION_SCHEMA.TABLES t
LEFT JOIN sys.indexes i ON OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME) = i.object_id
WHERE t.TABLE_TYPE = 'BASE TABLE' 
AND t.TABLE_NAME IN ('user_connections', 'agent_registry', 'agent_job_assignments', 'job_configurations_v2', 'job_execution_history_v2')
AND i.type > 0  -- Exclude heap
GROUP BY t.TABLE_NAME
ORDER BY t.TABLE_NAME

-- Check sample data
SELECT 'user_connections' as table_name, COUNT(*) as record_count FROM [dbo].[user_connections]
UNION ALL
SELECT 'agent_registry', COUNT(*) FROM [dbo].[agent_registry]
UNION ALL
SELECT 'agent_job_assignments', COUNT(*) FROM [dbo].[agent_job_assignments]
UNION ALL
SELECT 'job_configurations_v2', COUNT(*) FROM [dbo].[job_configurations_v2]
UNION ALL
SELECT 'job_execution_history_v2', COUNT(*) FROM [dbo].[job_execution_history_v2]

-- Display final summary
PRINT ''
PRINT '============================================='
PRINT 'Windows Job Scheduler V2.1 Database Setup'
PRINT 'INSTALLATION COMPLETED SUCCESSFULLY!'
PRINT '(Includes Agent Management & Passive Agent Support)'
PRINT '============================================='
PRINT ''
PRINT 'Database: sreutil'
PRINT 'Server: SUMEETGILL7E47\MSSQLSERVER01'
PRINT ''
PRINT 'TABLES CREATED:'
PRINT '  ✓ user_connections (4 indexes)'
PRINT '  ✓ agent_registry (8 indexes) [Agent Management]'
PRINT '  ✓ agent_job_assignments (6 indexes + 1 FK) [Job Assignment Tracking]'
PRINT '  ✓ job_configurations_v2 (7 indexes) [V2 Schema]'
PRINT '  ✓ job_execution_history_v2 (11 indexes + 3 FKs) [V2 Schema + Agent Support]'
PRINT ''
PRINT 'INITIAL DATA:'
PRINT '  ✓ 3 default database connections'
PRINT '  ✓ 2 sample agent configurations (1 passive, 1 active)'
PRINT '  ✓ 3 sample job configurations'
PRINT ''
PRINT 'MAINTENANCE FEATURES:'
PRINT '  ✓ 2 stored procedures for cleanup and statistics'
PRINT '  ✓ 2 reporting views for dashboard'
PRINT '  ✓ Database roles and permissions'
PRINT ''
PRINT 'NEXT STEPS:'
PRINT '  1. Update .env file with database connection string'
PRINT '  2. Run Python application to test connectivity'
PRINT '  3. Access web UI at http://localhost:5000'
PRINT '  4. Review sample jobs in the dashboard'
PRINT ''
PRINT 'MAINTENANCE:'
PRINT '  - Run sp_cleanup_execution_history monthly'
PRINT '  - Run sp_update_job_statistics for accurate metrics'
PRINT ''
PRINT '============================================='