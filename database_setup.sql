-- =============================================
-- Job Scheduler Database Setup Script
-- =============================================
-- Run this script in SSMS to create the database and tables
-- Server: DESKTOP-4ADGDVE\SQLEXPRESS
-- Authentication: Windows Authentication (Trusted Connection)
-- Database: sreutil

-- Step 1: Use the existing sreutil database
USE [sreutil]
GO

PRINT 'Using existing sreutil database'

-- Step 3: Create user_connections table for storing SQL connections
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='user_connections' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[user_connections] (
        [connection_id] NVARCHAR(100) PRIMARY KEY,
        [name] NVARCHAR(255) NOT NULL,
        [server_name] NVARCHAR(255) NOT NULL,
        [port] INT DEFAULT 1433,
        [database_name] NVARCHAR(255) NOT NULL,
        [trusted_connection] BIT DEFAULT 1,
        [username] NVARCHAR(255) NULL,
        [password] NVARCHAR(500) NULL,
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
    
    -- Create indexes for better performance
    CREATE INDEX IX_user_connections_name ON [dbo].[user_connections]([name])
    CREATE INDEX IX_user_connections_active ON [dbo].[user_connections]([is_active])
    
    PRINT 'Table user_connections created successfully with indexes'
END
ELSE
BEGIN
    PRINT 'Table user_connections already exists'
END
GO

-- Step 4: Create job_configurations table (for job storage)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='job_configurations' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[job_configurations] (
        [job_id] NVARCHAR(50) PRIMARY KEY,
        [name] NVARCHAR(255) NOT NULL,
        [job_type] NVARCHAR(50) NOT NULL,
        [configuration] NTEXT NOT NULL,
        [enabled] BIT DEFAULT 1,
        [created_date] DATETIME DEFAULT GETDATE(),
        [modified_date] DATETIME DEFAULT GETDATE(),
        [created_by] NVARCHAR(255) DEFAULT SYSTEM_USER
    )
    
    -- Create indexes
    CREATE INDEX IX_job_configurations_name ON [dbo].[job_configurations]([name])
    CREATE INDEX IX_job_configurations_type ON [dbo].[job_configurations]([job_type])
    
    PRINT 'Table job_configurations created successfully'
END
ELSE
BEGIN
    PRINT 'Table job_configurations already exists'
END
GO

-- Step 5: Create job_execution_history table (for execution tracking)
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='job_execution_history' AND xtype='U')
BEGIN
    CREATE TABLE [dbo].[job_execution_history] (
        [execution_id] BIGINT IDENTITY(1,1) PRIMARY KEY,
        [job_id] NVARCHAR(50) NOT NULL,
        [job_name] NVARCHAR(255) NOT NULL,
        [status] NVARCHAR(50) NOT NULL,
        [start_time] DATETIME NOT NULL,
        [end_time] DATETIME NULL,
        [duration_seconds] FLOAT NULL,
        [output] NTEXT NULL,
        [error_message] NTEXT NULL,
        [return_code] INT NULL,
        [retry_count] INT DEFAULT 0,
        [max_retries] INT DEFAULT 0,
        [metadata] NTEXT NULL
    )
    
    -- Create indexes
    CREATE INDEX IX_job_history_job_id ON [dbo].[job_execution_history]([job_id])
    CREATE INDEX IX_job_history_start_time ON [dbo].[job_execution_history]([start_time])
    CREATE INDEX IX_job_history_status ON [dbo].[job_execution_history]([status])
    
    PRINT 'Table job_execution_history created successfully'
END
ELSE
BEGIN
    PRINT 'Table job_execution_history already exists'
END
GO

-- Step 6: Verify tables were created
SELECT 
    TABLE_NAME,
    TABLE_TYPE
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME

PRINT '============================================='
PRINT 'Job Scheduler Database Setup Complete!'
PRINT 'Database: sreutil'
PRINT 'Tables Created:'
PRINT '  - user_connections (stores SQL connection configs)'
PRINT '  - job_configurations (stores job definitions)'  
PRINT '  - job_execution_history (stores execution logs)'
PRINT '============================================='