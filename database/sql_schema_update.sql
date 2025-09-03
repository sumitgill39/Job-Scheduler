-- =====================================================
-- SQL Schema Update for Enhanced PowerShell Configuration
-- Job Scheduler Database Schema Enhancement
-- Date: 2025-09-02
-- =====================================================

USE sreutil;
GO

-- Check if we're connected to the right database
PRINT 'Connected to database: ' + DB_NAME();
GO

-- =====================================================
-- Step 1: Add Enhanced Scheduling Fields to job_configurations table
-- =====================================================

PRINT 'Step 1: Adding enhanced scheduling fields to job_configurations table...';

-- Check if columns already exist before adding them
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'schedule_enabled')
BEGIN
    ALTER TABLE job_configurations ADD schedule_enabled BIT DEFAULT 0;
    PRINT '  ✓ Added column: schedule_enabled (BIT, DEFAULT 0)';
END
ELSE
    PRINT '  ⚠ Column schedule_enabled already exists';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'schedule_type')
BEGIN
    ALTER TABLE job_configurations ADD schedule_type VARCHAR(50) NULL;
    PRINT '  ✓ Added column: schedule_type (VARCHAR(50))';
END
ELSE
    PRINT '  ⚠ Column schedule_type already exists';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'schedule_expression')
BEGIN
    ALTER TABLE job_configurations ADD schedule_expression VARCHAR(255) NULL;
    PRINT '  ✓ Added column: schedule_expression (VARCHAR(255))';
END
ELSE
    PRINT '  ⚠ Column schedule_expression already exists';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'timezone')
BEGIN
    ALTER TABLE job_configurations ADD timezone VARCHAR(50) DEFAULT 'UTC';
    PRINT '  ✓ Added column: timezone (VARCHAR(50), DEFAULT ''UTC'')';
END
ELSE
    PRINT '  ⚠ Column timezone already exists';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'next_run_time')
BEGIN
    ALTER TABLE job_configurations ADD next_run_time DATETIME NULL;
    PRINT '  ✓ Added column: next_run_time (DATETIME)';
END
ELSE
    PRINT '  ⚠ Column next_run_time already exists';

IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
               WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'last_run_time')
BEGIN
    ALTER TABLE job_configurations ADD last_run_time DATETIME NULL;
    PRINT '  ✓ Added column: last_run_time (DATETIME)';
END
ELSE
    PRINT '  ⚠ Column last_run_time already exists';

GO

-- =====================================================
-- Step 2: Create Indexes for Performance Optimization
-- =====================================================

PRINT 'Step 2: Creating performance indexes...';

-- Index for schedule_enabled column
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_job_configurations_schedule_enabled')
BEGIN
    CREATE INDEX ix_job_configurations_schedule_enabled ON job_configurations (schedule_enabled);
    PRINT '  ✓ Created index: ix_job_configurations_schedule_enabled';
END
ELSE
    PRINT '  ⚠ Index ix_job_configurations_schedule_enabled already exists';

-- Index for next_run_time column (critical for scheduler queries)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_job_configurations_next_run_time')
BEGIN
    CREATE INDEX ix_job_configurations_next_run_time ON job_configurations (next_run_time);
    PRINT '  ✓ Created index: ix_job_configurations_next_run_time';
END
ELSE
    PRINT '  ⚠ Index ix_job_configurations_next_run_time already exists';

-- Index for timezone column
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_job_configurations_timezone')
BEGIN
    CREATE INDEX ix_job_configurations_timezone ON job_configurations (timezone);
    PRINT '  ✓ Created index: ix_job_configurations_timezone';
END
ELSE
    PRINT '  ⚠ Index ix_job_configurations_timezone already exists';

-- Composite index for scheduler queries (schedule_enabled + next_run_time)
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'ix_job_configurations_scheduler_query')
BEGIN
    CREATE INDEX ix_job_configurations_scheduler_query ON job_configurations (schedule_enabled, next_run_time) 
    WHERE schedule_enabled = 1;
    PRINT '  ✓ Created composite index: ix_job_configurations_scheduler_query';
END
ELSE
    PRINT '  ⚠ Index ix_job_configurations_scheduler_query already exists';

GO

-- =====================================================
-- Step 3: Verify Enhanced Schema Structure
-- =====================================================

PRINT 'Step 3: Verifying enhanced schema structure...';

-- Display current job_configurations table structure
PRINT 'Current job_configurations table structure:';
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_configurations'
ORDER BY ORDINAL_POSITION;

-- Display indexes
PRINT 'Current indexes on job_configurations:';
SELECT 
    i.name AS IndexName,
    i.type_desc AS IndexType,
    c.name AS ColumnName
FROM sys.indexes i
JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
WHERE i.object_id = OBJECT_ID('job_configurations')
ORDER BY i.name, ic.index_column_id;

GO

-- =====================================================
-- Step 4: Update Configuration Field for Enhanced PowerShell Support
-- =====================================================

PRINT 'Step 4: Optimizing configuration field for large PowerShell scripts...';

-- Check current configuration field definition
DECLARE @CurrentDataType VARCHAR(50);
SELECT @CurrentDataType = DATA_TYPE 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_configurations' AND COLUMN_NAME = 'configuration';

PRINT 'Current configuration field type: ' + @CurrentDataType;

-- The TEXT field should already handle large scripts, but let's verify
IF @CurrentDataType = 'text'
    PRINT '  ✓ Configuration field is TEXT - supports up to 2GB of PowerShell script content';
ELSE IF @CurrentDataType LIKE 'varchar%'
    PRINT '  ⚠ Configuration field is VARCHAR - may need to consider TEXT for very large scripts';

GO

-- =====================================================
-- Step 5: Create Sample Data Verification Query
-- =====================================================

PRINT 'Step 5: Creating verification queries...';

-- Sample query to show enhanced job configuration structure
PRINT 'Sample enhanced job configuration data:';
SELECT TOP 3
    job_id,
    name,
    job_type,
    enabled,
    schedule_enabled,
    schedule_type,
    timezone,
    next_run_time,
    last_run_time,
    LEN(configuration) as configuration_size,
    created_date
FROM job_configurations
ORDER BY created_date DESC;

GO

-- =====================================================
-- Step 6: Create Useful Views for Management
-- =====================================================

PRINT 'Step 6: Creating management views...';

-- Create view for scheduled jobs
IF NOT EXISTS (SELECT * FROM sys.views WHERE name = 'vw_scheduled_jobs')
BEGIN
    EXEC('CREATE VIEW vw_scheduled_jobs AS
    SELECT 
        job_id,
        name,
        job_type,
        schedule_type,
        schedule_expression,
        timezone,
        next_run_time,
        last_run_time,
        enabled,
        schedule_enabled,
        created_date,
        LEN(configuration) as script_size
    FROM job_configurations 
    WHERE schedule_enabled = 1');
    PRINT '  ✓ Created view: vw_scheduled_jobs';
END
ELSE
    PRINT '  ⚠ View vw_scheduled_jobs already exists';

-- Create view for PowerShell jobs with large scripts
IF NOT EXISTS (SELECT * FROM sys.views WHERE name = 'vw_powershell_jobs')
BEGIN
    EXEC('CREATE VIEW vw_powershell_jobs AS
    SELECT 
        job_id,
        name,
        schedule_enabled,
        timezone,
        next_run_time,
        enabled,
        LEN(configuration) as script_size,
        CASE 
            WHEN LEN(configuration) > 5000 THEN ''Large Script''
            WHEN LEN(configuration) > 1000 THEN ''Medium Script''
            ELSE ''Small Script''
        END as script_category,
        created_date,
        modified_date
    FROM job_configurations 
    WHERE job_type = ''powershell''');
    PRINT '  ✓ Created view: vw_powershell_jobs';
END
ELSE
    PRINT '  ⚠ View vw_powershell_jobs already exists';

GO

-- =====================================================
-- Step 7: Final Summary
-- =====================================================

PRINT '=====================================================';
PRINT 'SQL Schema Update Completed Successfully!';
PRINT '=====================================================';

PRINT 'Enhanced Features Added:';
PRINT '  ✓ Timezone-aware scheduling fields';
PRINT '  ✓ Schedule configuration (cron, interval, once)';
PRINT '  ✓ Performance indexes for scheduler queries';
PRINT '  ✓ Support for complex PowerShell scripts';
PRINT '  ✓ Management views for monitoring';

PRINT '';
PRINT 'Database is now ready for enhanced PowerShell job scheduling!';
PRINT '=====================================================';

GO