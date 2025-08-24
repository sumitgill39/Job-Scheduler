# Archive Folder

This folder contains test files, debug scripts, and temporary files that were used during development and migration but are not needed for production operation.

## Test Files
- `test_*.py` - Various test scripts for different components
- `test_complete_system.py` - Comprehensive system test
- `test_simple_db.py` - Simple database connection test
- `test_auth_method.py` - Authentication method verification
- `test_db_connection.py` - Original database connection test (YAML-based)

## Debug Files  
- `debug_*.py` - Debugging scripts for troubleshooting
- `debug_env_loading.py` - Environment variable loading debug
- `debug_connection.py` - Connection debugging
- `debug_sql_query.py` - SQL query debugging

## Migration/Fix Files
- `fix_*.py` - Scripts used to migrate from old to new database system
- `fix_routes_db.py` - Fixed routes to use new database manager
- `fix_job_manager.py` - Fixed job manager connection handling

## Setup/Utility Files
- `setup_system_db.py` - System database setup (legacy)
- `show_connection_strings.py` - Connection string debugging utility

## Usage

These files can be used for:
- **Testing** - Run tests to verify system functionality
- **Debugging** - Troubleshoot issues during development
- **Migration** - Reference for future database migrations
- **Learning** - Understand how different components work

To run any test file:
```bash
cd archive
python3 test_complete_system.py
```

## Note

The main application in the root directory does not depend on any files in this archive folder. These files are kept for reference and debugging purposes only.