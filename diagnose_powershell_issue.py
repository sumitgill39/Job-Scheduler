#!/usr/bin/env python3
"""
Diagnostic script to identify PowerShell job saving issues
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def diagnose_environment():
    """Diagnose the current environment and database connectivity"""
    print("=" * 60)
    print("PowerShell Job Saving - Environment Diagnosis")
    print("=" * 60)
    
    # Check Python environment
    print(f"Python version: {sys.version}")
    print(f"Platform: {sys.platform}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check pyodbc availability
    print("\n1. Checking pyodbc availability...")
    try:
        import pyodbc
        print(f"   ✅ pyodbc version: {pyodbc.version}")
        
        # List available drivers
        drivers = pyodbc.drivers()
        print(f"   ✅ Available ODBC drivers: {drivers}")
        
        if "ODBC Driver 17 for SQL Server" in drivers:
            print("   ✅ SQL Server ODBC Driver 17 is available")
        else:
            print("   ⚠️  SQL Server ODBC Driver 17 is NOT available")
            print("   Install from: https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
    except ImportError:
        print("   ❌ pyodbc is NOT installed")
        print("   Install with: pip install pyodbc")
        return False
    except Exception as e:
        print(f"   ❌ pyodbc error: {e}")
        return False
    
    # Check database configuration
    print("\n2. Checking database configuration...")
    try:
        from database.connection_manager import DatabaseConnectionManager
        db_manager = DatabaseConnectionManager()
        print("   ✅ Database connection manager initialized")
        
        # Check system connection
        print("\n3. Testing system database connection...")
        system_conn = db_manager.get_connection("system")
        if system_conn:
            print("   ✅ System database connection successful")
            try:
                cursor = system_conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                print(f"   ✅ Database query successful: {result}")
                system_conn.close()
            except Exception as e:
                print(f"   ❌ Database query failed: {e}")
                return False
        else:
            print("   ❌ System database connection FAILED")
            print("   This is why PowerShell jobs are not saving to database!")
            return False
            
    except Exception as e:
        print(f"   ❌ Database configuration error: {e}")
        return False
    
    # Test PowerShell job creation
    print("\n4. Testing PowerShell job creation...")
    try:
        from core.job_manager import JobManager
        job_manager = JobManager()
        
        test_job = {
            'name': 'Diagnostic PowerShell Test',
            'description': 'Testing PowerShell job creation for diagnostics',
            'type': 'powershell',
            'enabled': True,
            'script_content': 'Write-Host "Diagnostic test successful"',
            'execution_policy': 'RemoteSigned',
            'parameters': [],
            'timeout': 300,
            'max_retries': 3,
            'retry_delay': 60
        }
        
        result = job_manager.create_job(test_job)
        if result['success']:
            print(f"   ✅ PowerShell job created successfully: {result['job_id']}")
            
            # Verify job was saved to database
            saved_job = job_manager.get_job(result['job_id'])
            if saved_job:
                print("   ✅ PowerShell job successfully saved to database")
                print(f"   Job type: {saved_job.get('type')}")
                print(f"   Script content length: {len(saved_job.get('configuration', {}).get('powershell', {}).get('script_content', ''))}")
                return True
            else:
                print("   ❌ PowerShell job was NOT saved to database")
                return False
        else:
            print(f"   ❌ PowerShell job creation failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"   ❌ PowerShell job test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def diagnose_database_connectivity():
    """Specifically diagnose database connectivity issues"""
    print("\n" + "=" * 60)
    print("Database Connectivity Detailed Diagnosis")
    print("=" * 60)
    
    try:
        # Read database configuration
        print("1. Reading database configuration...")
        with open("config/database_config.yaml", 'r') as f:
            import yaml
            config = yaml.safe_load(f)
            
        system_db = config['databases']['system']
        print(f"   Server: {system_db['server']}")
        print(f"   Port: {system_db['port']}")
        print(f"   Database: {system_db['database']}")
        print(f"   Username: {system_db['username']}")
        print(f"   Trusted Connection: {system_db['trusted_connection']}")
        
        # Test raw connection
        print("\n2. Testing raw database connection...")
        import pyodbc
        
        connection_string = (
            f"DRIVER={system_db['driver']};"
            f"SERVER={system_db['server']},{system_db['port']};"
            f"DATABASE={system_db['database']};"
            f"UID={system_db['username']};"
            f"PWD={system_db['password']};"
            f"TrustServerCertificate=yes;"
        )
        
        print(f"   Connection string: {connection_string.replace(system_db['password'], '***')}")
        
        try:
            conn = pyodbc.connect(connection_string, timeout=30)
            print("   ✅ Raw database connection successful")
            
            cursor = conn.cursor()
            cursor.execute("SELECT DB_NAME() as current_database")
            result = cursor.fetchone()
            print(f"   ✅ Connected to database: {result[0]}")
            
            # Check if job_configurations table exists
            cursor.execute("""
                SELECT TABLE_NAME 
                FROM INFORMATION_SCHEMA.TABLES 
                WHERE TABLE_NAME = 'job_configurations'
            """)
            table_result = cursor.fetchone()
            if table_result:
                print("   ✅ job_configurations table exists")
            else:
                print("   ❌ job_configurations table does NOT exist")
                print("   Run: sqlcmd -i database_setup.sql")
            
            conn.close()
            return True
            
        except pyodbc.Error as e:
            print(f"   ❌ Raw database connection failed: {e}")
            print("\n   Possible solutions:")
            print("   - Check if SQL Server is running")
            print("   - Verify server name and port")
            print("   - Check username/password")
            print("   - Verify network connectivity")
            return False
            
    except Exception as e:
        print(f"   ❌ Database diagnosis failed: {e}")
        return False

if __name__ == "__main__":
    print("PowerShell Job Saving - Complete Diagnosis")
    print("This will identify why PowerShell jobs are not saving to the database")
    
    env_ok = diagnose_environment()
    db_ok = diagnose_database_connectivity()
    
    print("\n" + "=" * 60)
    print("DIAGNOSIS SUMMARY")
    print("=" * 60)
    
    if env_ok and db_ok:
        print("✅ ALL SYSTEMS WORKING")
        print("✅ PowerShell jobs should save to database successfully")
    else:
        print("❌ ISSUES FOUND")
        if not env_ok:
            print("❌ Environment/Application issues detected")
        if not db_ok:
            print("❌ Database connectivity issues detected")
        
        print("\nRECOMMENDED ACTIONS:")
        print("1. Fix database connectivity issues")
        print("2. Ensure SQL Server is running and accessible")
        print("3. Verify database configuration in config/database_config.yaml")
        print("4. Run database setup script: sqlcmd -i database_setup.sql")
        print("5. Test connection: python test_connection_system.py")
        
    print("=" * 60)