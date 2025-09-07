-- =============================================
-- Agent-Based Job Execution System - Database Migration Script
-- =============================================
-- This script adds agent support to the existing Job Scheduler
-- WITHOUT breaking any existing functionality
-- 
-- Target Database: SQL Server (SUMEETGILL7E47\MSSQLSERVER01)
-- Database: sreutil
-- Version: 1.0
-- Created: 2025-01-27
-- =============================================

USE [sreutil]
GO

PRINT '============================================='
PRINT 'Agent System Database Migration'
PRINT 'Adding agent support to Job Scheduler'
PRINT '============================================='

-- =============================================
-- STEP 1: Create Agent Registry Table
-- =============================================
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='agent_registry' AND xtype='U')
BEGIN
    PRINT 'Creating agent_registry table...'
    
    CREATE TABLE [dbo].[agent_registry] (
        -- Primary identification
        [agent_id] NVARCHAR(50) PRIMARY KEY,
        [agent_name] NVARCHAR(255) NOT NULL,
        [hostname] NVARCHAR(255) NOT NULL,
        [ip_address] NVARCHAR(50) NOT NULL,
        
        -- Agent capabilities and pool assignment
        [agent_pool] NVARCHAR(100) DEFAULT 'default',
        [capabilities] NTEXT, -- JSON array of capabilities
        [max_parallel_jobs] INT DEFAULT 1,
        [agent_version] NVARCHAR(20),
        
        -- System information
        [os_info] NVARCHAR(255),
        [cpu_cores] INT,
        [memory_gb] INT,
        [disk_space_gb] INT,
        
        -- Status and health
        [status] NVARCHAR(20) DEFAULT 'offline', -- online, offline, maintenance, error
        [last_heartbeat] DATETIME,
        [last_job_completed] DATETIME,
        
        -- Resource utilization
        [current_jobs] INT DEFAULT 0,
        [cpu_percent] FLOAT,
        [memory_percent] FLOAT,
        [disk_percent] FLOAT,
        
        -- Authentication
        [api_key_hash] NVARCHAR(255), -- Hashed API key for agent authentication
        [jwt_secret] NVARCHAR(500), -- Encrypted JWT secret
        
        -- Metadata
        [registered_date] DATETIME DEFAULT GETDATE(),
        [last_updated] DATETIME DEFAULT GETDATE(),
        [is_active] BIT DEFAULT 1,
        [is_approved] BIT DEFAULT 0 -- Requires admin approval
    )
    
    -- Create indexes for performance
    CREATE INDEX IX_agent_registry_pool ON [dbo].[agent_registry]([agent_pool])
    CREATE INDEX IX_agent_registry_status ON [dbo].[agent_registry]([status])
    CREATE INDEX IX_agent_registry_heartbeat ON [dbo].[agent_registry]([last_heartbeat])
    CREATE INDEX IX_agent_registry_active ON [dbo].[agent_registry]([is_active])
    
    PRINT '  - agent_registry table created with indexes'
END
ELSE
BEGIN
    PRINT '  - agent_registry table already exists (skipping)'
END
GO

-- =============================================
-- STEP 2: Create Agent Job Assignments Table
-- =============================================
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='agent_job_assignments' AND xtype='U')
BEGIN
    PRINT 'Creating agent_job_assignments table...'
    
    CREATE TABLE [dbo].[agent_job_assignments] (
        -- Assignment identification
        [assignment_id] NVARCHAR(36) PRIMARY KEY DEFAULT NEWID(), -- UUID
        [execution_id] NVARCHAR(36) NOT NULL, -- FK to job_execution_history_v2
        [job_id] NVARCHAR(36) NOT NULL, -- FK to job_configurations_v2
        [agent_id] NVARCHAR(50), -- FK to agent_registry (NULL for local execution)
        
        -- Assignment details
        [assignment_type] NVARCHAR(20) DEFAULT 'local', -- local, agent
        [assignment_strategy] NVARCHAR(50), -- default_pool, specific_agent
        
        -- Assignment status
        [assignment_status] NVARCHAR(20) DEFAULT 'assigned',
        -- assigned, accepted, running, completed, failed, timeout, cancelled
        [assigned_at] DATETIME DEFAULT GETDATE(),
        [accepted_at] DATETIME,
        [started_at] DATETIME,
        [completed_at] DATETIME,
        
        -- Resource allocation
        [priority] INT DEFAULT 5, -- 1-10 (10 = highest)
        [timeout_minutes] INT DEFAULT 60,
        [max_retries] INT DEFAULT 0,
        [retry_count] INT DEFAULT 0,
        
        -- Results (for agent jobs)
        [return_code] INT,
        [output_summary] NVARCHAR(500), -- Brief output summary
        
        -- Foreign key constraints
        CONSTRAINT FK_agent_assignments_agent 
            FOREIGN KEY ([agent_id]) 
            REFERENCES [dbo].[agent_registry]([agent_id])
            ON DELETE SET NULL
    )
    
    -- Create indexes
    CREATE INDEX IX_agent_assignments_execution ON [dbo].[agent_job_assignments]([execution_id])
    CREATE INDEX IX_agent_assignments_job ON [dbo].[agent_job_assignments]([job_id])
    CREATE INDEX IX_agent_assignments_agent ON [dbo].[agent_job_assignments]([agent_id])
    CREATE INDEX IX_agent_assignments_status ON [dbo].[agent_job_assignments]([assignment_status])
    CREATE INDEX IX_agent_assignments_assigned ON [dbo].[agent_job_assignments]([assigned_at])
    CREATE INDEX IX_agent_assignments_type ON [dbo].[agent_job_assignments]([assignment_type])
    
    PRINT '  - agent_job_assignments table created with indexes'
END
ELSE
BEGIN
    PRINT '  - agent_job_assignments table already exists (skipping)'
END
GO

-- =============================================
-- STEP 3: Add Agent Support Columns to Existing Tables
-- =============================================
PRINT 'Adding agent support to existing tables...'

-- Add agent support to job_configurations_v2 (backward compatible)
IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('job_configurations_v2') 
               AND name = 'execution_type')
BEGIN
    ALTER TABLE [dbo].[job_configurations_v2]
    ADD [execution_type] NVARCHAR(20) DEFAULT 'local' -- local, agent
    
    PRINT '  - Added execution_type to job_configurations_v2'
END

IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('job_configurations_v2') 
               AND name = 'preferred_agent_pool')
BEGIN
    ALTER TABLE [dbo].[job_configurations_v2]
    ADD [preferred_agent_pool] NVARCHAR(100) DEFAULT NULL
    
    PRINT '  - Added preferred_agent_pool to job_configurations_v2'
END

-- Add agent tracking to job_execution_history_v2
IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('job_execution_history_v2') 
               AND name = 'executed_on_agent')
BEGIN
    ALTER TABLE [dbo].[job_execution_history_v2]
    ADD [executed_on_agent] NVARCHAR(50) DEFAULT NULL
    
    PRINT '  - Added executed_on_agent to job_execution_history_v2'
END

IF NOT EXISTS (SELECT * FROM sys.columns 
               WHERE object_id = OBJECT_ID('job_execution_history_v2') 
               AND name = 'assignment_id')
BEGIN
    ALTER TABLE [dbo].[job_execution_history_v2]
    ADD [assignment_id] NVARCHAR(36) DEFAULT NULL
    
    PRINT '  - Added assignment_id to job_execution_history_v2'
END
GO

-- =============================================
-- STEP 4: Create Agent Pools Table (Simple Version)
-- =============================================
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='agent_pools' AND xtype='U')
BEGIN
    PRINT 'Creating agent_pools table...'
    
    CREATE TABLE [dbo].[agent_pools] (
        -- Pool identification
        [pool_id] NVARCHAR(100) PRIMARY KEY,
        [pool_name] NVARCHAR(255) NOT NULL,
        [description] NTEXT,
        
        -- Pool configuration
        [max_agents] INT DEFAULT 10,
        [load_balancing_strategy] NVARCHAR(50) DEFAULT 'round_robin',
        -- Options: round_robin, least_loaded, random
        
        -- Pool status
        [is_active] BIT DEFAULT 1,
        [created_date] DATETIME DEFAULT GETDATE(),
        [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER
    )
    
    -- Insert default pool
    INSERT INTO [dbo].[agent_pools] (pool_id, pool_name, description)
    VALUES ('default', 'Default Agent Pool', 'Default pool for general agent jobs')
    
    PRINT '  - agent_pools table created with default pool'
END
ELSE
BEGIN
    PRINT '  - agent_pools table already exists (skipping)'
END
GO

-- =============================================
-- STEP 5: Create Views for Backward Compatibility
-- =============================================
PRINT 'Creating compatibility views...'

-- Create view for jobs (shows both local and agent jobs)
IF EXISTS (SELECT * FROM sys.views WHERE name = 'v_all_jobs')
    DROP VIEW [dbo].[v_all_jobs]
GO

CREATE VIEW [dbo].[v_all_jobs] AS
SELECT 
    job_id,
    name,
    description,
    version,
    yaml_configuration,
    enabled,
    ISNULL(execution_type, 'local') as execution_type,
    preferred_agent_pool,
    created_date,
    modified_date,
    created_by,
    last_execution_status,
    last_execution_time,
    next_scheduled_time,
    total_executions,
    successful_executions,
    failed_executions
FROM [dbo].[job_configurations_v2]
GO

PRINT '  - Created v_all_jobs view'

-- Create view for execution history with agent info
IF EXISTS (SELECT * FROM sys.views WHERE name = 'v_execution_history_with_agent')
    DROP VIEW [dbo].[v_execution_history_with_agent]
GO

CREATE VIEW [dbo].[v_execution_history_with_agent] AS
SELECT 
    eh.*,
    ISNULL(eh.executed_on_agent, 'LOCAL') as execution_location,
    ar.agent_name,
    ar.hostname as agent_hostname,
    ar.agent_pool,
    aja.assignment_status,
    aja.assigned_at as agent_assigned_at,
    aja.started_at as agent_started_at,
    aja.completed_at as agent_completed_at
FROM [dbo].[job_execution_history_v2] eh
LEFT JOIN [dbo].[agent_job_assignments] aja ON eh.assignment_id = aja.assignment_id
LEFT JOIN [dbo].[agent_registry] ar ON aja.agent_id = ar.agent_id
GO

PRINT '  - Created v_execution_history_with_agent view'

-- =============================================
-- STEP 6: Create Stored Procedures for Agent Operations
-- =============================================
PRINT 'Creating stored procedures for agent operations...'

-- Procedure to register an agent
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_register_agent')
    DROP PROCEDURE [dbo].[sp_register_agent]
GO

CREATE PROCEDURE [dbo].[sp_register_agent]
    @agent_id NVARCHAR(50),
    @agent_name NVARCHAR(255),
    @hostname NVARCHAR(255),
    @ip_address NVARCHAR(50),
    @capabilities NTEXT = NULL,
    @max_parallel_jobs INT = 1,
    @agent_pool NVARCHAR(100) = 'default'
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Check if agent already exists
    IF EXISTS (SELECT 1 FROM agent_registry WHERE agent_id = @agent_id)
    BEGIN
        -- Update existing agent
        UPDATE agent_registry
        SET agent_name = @agent_name,
            hostname = @hostname,
            ip_address = @ip_address,
            capabilities = @capabilities,
            max_parallel_jobs = @max_parallel_jobs,
            agent_pool = @agent_pool,
            last_updated = GETDATE()
        WHERE agent_id = @agent_id
        
        SELECT 'UPDATED' as Result, @agent_id as agent_id
    END
    ELSE
    BEGIN
        -- Insert new agent
        INSERT INTO agent_registry (
            agent_id, agent_name, hostname, ip_address,
            capabilities, max_parallel_jobs, agent_pool
        )
        VALUES (
            @agent_id, @agent_name, @hostname, @ip_address,
            @capabilities, @max_parallel_jobs, @agent_pool
        )
        
        SELECT 'CREATED' as Result, @agent_id as agent_id
    END
END
GO

PRINT '  - Created sp_register_agent procedure'

-- Procedure to update agent heartbeat
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_update_agent_heartbeat')
    DROP PROCEDURE [dbo].[sp_update_agent_heartbeat]
GO

CREATE PROCEDURE [dbo].[sp_update_agent_heartbeat]
    @agent_id NVARCHAR(50),
    @status NVARCHAR(20),
    @current_jobs INT = 0,
    @cpu_percent FLOAT = NULL,
    @memory_percent FLOAT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE agent_registry
    SET last_heartbeat = GETDATE(),
        status = @status,
        current_jobs = @current_jobs,
        cpu_percent = @cpu_percent,
        memory_percent = @memory_percent,
        last_updated = GETDATE()
    WHERE agent_id = @agent_id
    
    SELECT @@ROWCOUNT as UpdatedRows
END
GO

PRINT '  - Created sp_update_agent_heartbeat procedure'

-- Procedure to get available agent for job
IF EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_get_available_agent')
    DROP PROCEDURE [dbo].[sp_get_available_agent]
GO

CREATE PROCEDURE [dbo].[sp_get_available_agent]
    @agent_pool NVARCHAR(100) = 'default',
    @required_capabilities NTEXT = NULL
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Simple round-robin selection of available agent
    SELECT TOP 1
        agent_id,
        agent_name,
        hostname,
        current_jobs,
        max_parallel_jobs
    FROM agent_registry
    WHERE is_active = 1
        AND is_approved = 1
        AND status = 'online'
        AND agent_pool = @agent_pool
        AND current_jobs < max_parallel_jobs
        AND DATEDIFF(MINUTE, last_heartbeat, GETDATE()) < 5 -- Active in last 5 minutes
    ORDER BY 
        current_jobs ASC, -- Least loaded first
        last_job_completed ASC -- Longest idle first
END
GO

PRINT '  - Created sp_get_available_agent procedure'

-- =============================================
-- STEP 7: Migration Summary
-- =============================================
PRINT ''
PRINT '============================================='
PRINT 'Migration Summary:'
PRINT '  - Agent tables created successfully'
PRINT '  - Existing tables enhanced with agent support'
PRINT '  - Backward compatibility maintained'
PRINT '  - All existing jobs will continue as "local" execution'
PRINT '  - Agent jobs can be added without affecting existing jobs'
PRINT '============================================='
PRINT 'Migration completed successfully!'
GO