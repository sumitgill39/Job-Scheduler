-- =============================================
-- Create user_connections table for SQL connections
-- This table stores SQL connection configurations
-- =============================================

USE [sreutil]
GO

PRINT 'Creating user_connections table...'

-- Check if table exists
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='user_connections' AND xtype='U')
BEGIN
    PRINT 'Creating user_connections table...'
    
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
        [driver] NVARCHAR(255) DEFAULT 'ODBC Driver 17 for SQL Server',
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
    
    -- Insert a default connection for local SQL Express
    INSERT INTO [dbo].[user_connections] (
        [connection_id],
        [name],
        [server_name],
        [port],
        [database_name],
        [trusted_connection],
        [description],
        [created_by]
    ) VALUES (
        'default',
        'Local SQL Express',
        'DESKTOP-4ADGDVE\SQLEXPRESS',
        1433,
        'sreutil',
        1,
        'Default local SQL Express connection',
        'system'
    )
    
    PRINT 'Default connection added successfully'
    
END
ELSE
BEGIN
    PRINT 'Table user_connections already exists'
END
GO

-- Verify the table structure
PRINT 'user_connections table structure:'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'user_connections'
ORDER BY ORDINAL_POSITION
GO

-- Show existing connections
PRINT 'Existing connections:'
SELECT 
    connection_id,
    name,
    server_name,
    database_name,
    trusted_connection,
    is_active
FROM [dbo].[user_connections]
GO

PRINT 'user_connections table setup completed successfully!'