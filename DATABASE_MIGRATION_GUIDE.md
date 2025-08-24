# Database Configuration Migration Guide

## Overview
The Windows Job Scheduler has been completely migrated from YAML-based database configuration to a more stable environment variable (.env) based system.

## What Changed

### ❌ OLD SYSTEM (Removed)
- `config/database_config.yaml` - Complex YAML parsing
- `database/connection_manager.py` - Complex connection management
- `database/connection_pool.py` - Old connection pool
- Multiple configuration sources causing conflicts

### ✅ NEW SYSTEM (Active)
- `.env` file - Simple environment variables
- `database/simple_connection_manager.py` - Robust connection manager
- Centralized configuration with proper connection pooling
- No more YAML parsing issues

## Configuration Files

### 1. Production Settings: `.env` 
**Location**: `/path/to/project/.env`
**Status**: Contains real credentials, NOT committed to Git

```env
# Database Configuration
DB_DRIVER=ODBC Driver 17 for SQL Server
DB_SERVER=USDF11DB197CI1\PRD_DB01
DB_PORT=3433
DB_DATABASE=sreutil
DB_USERNAME=svc
DB_PASSWORD=SbuJL9FH&m8X7Q
DB_TRUSTED_CONNECTION=false
DB_CONNECTION_TIMEOUT=30
DB_COMMAND_TIMEOUT=300
DB_ENCRYPT=false
DB_TRUST_SERVER_CERTIFICATE=true

# Connection Pool Settings
DB_POOL_MAX_CONNECTIONS=10
DB_POOL_MIN_CONNECTIONS=2
DB_POOL_CONNECTION_LIFETIME=3600

# Retry Settings
DB_MAX_RETRIES=3
DB_RETRY_DELAY=5
DB_BACKOFF_FACTOR=2
```

### 2. Template: `.env.template`
**Location**: `/path/to/project/.env.template`  
**Status**: Reference file, IS committed to Git

## Files Updated

### Core Files Modified:
1. `web_ui/app.py` - Uses new database manager
2. `web_ui/routes.py` - Updated all database calls
3. `core/job_manager.py` - Uses new connection system
4. `core/sql_job.py` - Updated connection handling
5. `utils/logger.py` - Fixed logger inheritance

### New Files Added:
1. `database/simple_connection_manager.py` - New robust database manager
2. `.env` - Production configuration
3. `.env.template` - Configuration template

## Testing

### Test Scripts:
1. **Simple Test**: `python3 test_simple_db.py`
2. **Connection Test**: `python3 test_db_connection.py` (still works with new system)

### Manual Testing:
```bash
# Start application
python3 main.py --mode web

# Check logs
tail -f logs/scheduler.log
```

## Troubleshooting

### If Application Still Uses YAML:
1. **Check imports** - Make sure no files still import old connection managers
2. **Restart application** - The new system loads on startup
3. **Check .env file exists** - Must be in project root

### Connection Issues:
1. **Verify .env file** - Check all DB_* variables are set
2. **Check server name** - Must include backslash escape: `USDF11DB197CI1\\PRD_DB01`
3. **Test connection** - Run `python3 test_simple_db.py`

### Log Analysis:
Look for these log entries:
- `[POOL]` - Connection pool operations
- `[CONNECTION_STRING]` - Configuration being used
- `[CONNECTION_CREATE]` - Connection attempts

## Security Notes

### ✅ Secure (New System):
- Production credentials in `.env` (not committed)
- Environment variables (standard practice)
- Password not logged (masked as ***)

### ❌ Previous Issues (Fixed):
- Credentials in YAML files in Git
- Complex configuration parsing
- Connection stability issues

## Migration Benefits

1. **Stability** - No more YAML parsing errors
2. **Security** - Credentials not in Git repository
3. **Simplicity** - Single configuration source
4. **Industry Standard** - Environment variables are best practice
5. **Debugging** - Clear, detailed logging
6. **Connection Pooling** - Proper connection reuse and cleanup

## Next Steps

1. **On Windows Machine**:
   - Pull latest code from Git
   - Create/update `.env` file with production credentials
   - Test connection: `python test_simple_db.py`
   - Start application: `python main.py --mode web`

2. **Verify Everything Works**:
   - Check logs show new system: `[POOL]` entries
   - Test database connectivity in web UI
   - Verify job creation/execution

The new system should be much more stable and easier to troubleshoot!