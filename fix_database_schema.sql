-- =============================================
-- Fix Database Schema for Job Scheduler
-- Add missing columns to match SQLAlchemy models
-- =============================================

USE [sreutil]
GO

PRINT 'Fixing database schema to match SQLAlchemy models...'

-- Check current schema
PRINT 'Current job_configurations table structure:'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_configurations'
ORDER BY ORDINAL_POSITION
GO

-- Add missing description column if it doesn't exist
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'job_configurations' 
    AND COLUMN_NAME = 'description'
)
BEGIN
    PRINT 'Adding description column to job_configurations table...'
    ALTER TABLE [dbo].[job_configurations] 
    ADD [description] NTEXT NULL
    PRINT 'Description column added successfully'
END
ELSE
BEGIN
    PRINT 'Description column already exists'
END
GO

-- Check if execution_metadata column exists in job_execution_history
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_NAME = 'job_execution_history' 
    AND COLUMN_NAME = 'execution_metadata'
)
BEGIN
    PRINT 'Adding execution_metadata column to job_execution_history table...'
    ALTER TABLE [dbo].[job_execution_history] 
    ADD [execution_metadata] NTEXT NULL
    PRINT 'execution_metadata column added successfully'
END
ELSE
BEGIN
    PRINT 'execution_metadata column already exists'
END
GO

-- Verify the updated schema
PRINT 'Updated job_configurations table structure:'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_configurations'
ORDER BY ORDINAL_POSITION
GO

PRINT 'Updated job_execution_history table structure:'
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = 'job_execution_history'
ORDER BY ORDINAL_POSITION
GO

PRINT 'Schema update completed successfully!'