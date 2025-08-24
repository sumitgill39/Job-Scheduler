#!/usr/bin/env python3
"""
Complete system test for Windows Job Scheduler
Tests all components to ensure Windows compatibility
"""

import sys
import os
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test all critical imports"""
    print("=" * 60)
    print("Testing Critical Imports")
    print("=" * 60)
    
    imports_to_test = [
        ("database.simple_connection_manager", "SimpleDatabaseManager, get_database_manager"),
        ("core.job_manager", "JobManager"),
        ("core.sql_job", "SqlJob"),
        ("core.job_executor", "JobExecutor"),
        ("web_ui.app", "create_app"),
        ("utils.logger", "setup_logger, get_logger"),
    ]
    
    failed_imports = []
    
    for module, items in imports_to_test:
        try:
            exec(f"from {module} import {items}")
            print(f"✅ {module}")
        except ImportError as e:
            print(f"❌ {module}: {e}")
            failed_imports.append((module, str(e)))
        except Exception as e:
            print(f"⚠️  {module}: {e}")
            failed_imports.append((module, str(e)))
    
    return len(failed_imports) == 0, failed_imports

def test_environment_config():
    """Test environment variable configuration"""
    print("\n" + "=" * 60)
    print("Testing Environment Configuration")
    print("=" * 60)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        env_file = Path('.env')
        if env_file.exists():
            load_dotenv(env_file)
            print("✅ .env file loaded")
        else:
            print("❌ .env file not found")
            return False
    except ImportError:
        print("❌ python-dotenv not installed")
        return False
    
    # Check required environment variables
    required_vars = [
        'DB_DRIVER', 'DB_SERVER', 'DB_PORT', 'DB_DATABASE',
        'DB_USERNAME', 'DB_PASSWORD', 'DB_TRUSTED_CONNECTION'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value is None:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
        else:
            # Mask password
            display_value = "***" if "PASSWORD" in var else value
            print(f"✅ {var}: {display_value}")
    
    return len(missing_vars) == 0

def test_database_connection():
    """Test database connectivity"""
    print("\n" + "=" * 60)
    print("Testing Database Connection")
    print("=" * 60)
    
    try:
        from database.simple_connection_manager import SimpleDatabaseManager
        
        # Create database manager
        db_manager = SimpleDatabaseManager()
        print("✅ Database manager created")
        
        # Test connection
        result = db_manager.test_connection()
        if result['success']:
            print(f"✅ Database connection successful")
            print(f"   Response time: {result['response_time']:.2f}s")
            print(f"   Server version: {result.get('server_version', 'Unknown')[:50]}...")
            return True
        else:
            print(f"❌ Database connection failed: {result['error']}")
            return False
            
    except Exception as e:
        print(f"❌ Database test error: {e}")
        traceback.print_exc()
        return False

def test_job_system():
    """Test job management system"""
    print("\n" + "=" * 60)
    print("Testing Job Management System")
    print("=" * 60)
    
    try:
        from core.job_manager import JobManager
        from core.sql_job import SqlJob
        
        # Create job manager
        job_manager = JobManager()
        print("✅ Job manager created")
        
        # Test SQL job creation  
        sql_job = SqlJob(
            sql_query="SELECT 'System test' as message",
            name="System Test Job"
        )
        print("✅ SQL job created")
        
        return True
        
    except Exception as e:
        print(f"❌ Job system test error: {e}")
        traceback.print_exc()
        return False

def test_web_app():
    """Test Flask web application"""
    print("\n" + "=" * 60)
    print("Testing Flask Web Application")
    print("=" * 60)
    
    try:
        from web_ui.app import create_app
        
        # Create Flask app
        app = create_app()
        print("✅ Flask app created")
        
        # Check if database manager is attached
        if hasattr(app, 'db_manager') and app.db_manager:
            print("✅ Database manager attached to app")
        else:
            print("⚠️  Database manager not attached to app")
        
        return True
        
    except Exception as e:
        print(f"❌ Flask app test error: {e}")
        traceback.print_exc()
        return False

def main():
    """Run complete system test"""
    print("🔍 Windows Job Scheduler - Complete System Test")
    print("=" * 60)
    
    # Run all tests
    tests = [
        ("Imports", test_imports),
        ("Environment Config", test_environment_config),
        ("Database Connection", test_database_connection),
        ("Job System", test_job_system),
        ("Web Application", test_web_app),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success, None))
        except Exception as e:
            results.append((test_name, False, str(e)))
    
    # Summary
    print("\n" + "=" * 60)
    print("SYSTEM TEST SUMMARY")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, success, error in results:
        if success:
            print(f"✅ {test_name}: PASSED")
            passed += 1
        else:
            print(f"❌ {test_name}: FAILED")
            if error:
                print(f"   Error: {error}")
    
    print("\n" + "=" * 60)
    print(f"OVERALL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 SYSTEM READY FOR WINDOWS DEPLOYMENT!")
        return True
    else:
        print("💥 SYSTEM HAS ISSUES - FIX REQUIRED BEFORE DEPLOYMENT")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)