#!/usr/bin/env python3
"""
Quick Logging Test - Tests the V2 logging system without Unicode issues
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test basic imports"""
    print("\n=== IMPORT TEST ===")
    try:
        from core.v2.timezone_logger import get_timezone_logger
        from core.v2.job_logger import create_job_logger
        print("[OK] Core logging imports successful")
        return True
    except Exception as e:
        print(f"[ERROR] Import failed: {e}")
        return False

def test_directory_creation():
    """Test directory creation"""
    print("\n=== DIRECTORY TEST ===")
    
    directories = ["logs", "logs/timezones", "logs/system", "logs/audit", "logs/performance"]
    
    for directory in directories:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            if Path(directory).exists():
                print(f"[OK] Created: {directory}")
            else:
                print(f"[ERROR] Failed to create: {directory}")
                return False
        except Exception as e:
            print(f"[ERROR] Exception creating {directory}: {e}")
            return False
    
    return True

def test_timezone_logger():
    """Test timezone logger creation and file writing"""
    print("\n=== TIMEZONE LOGGER TEST ===")
    
    test_timezones = ["UTC", "America/New_York", "Europe/London"]
    
    for tz in test_timezones:
        try:
            print(f"Testing timezone: {tz}")
            
            from core.v2.timezone_logger import get_timezone_logger
            logger = get_timezone_logger(tz)
            
            if not logger:
                print(f"[ERROR] Failed to create logger for {tz}")
                return False
            
            print(f"[OK] Logger created for {tz}")
            
            # Test logging
            logger.log_job_queued("test_job_001", "Test Job", datetime.now(timezone.utc), 0)
            logger.log_job_started("test_job_001", "Test Job", "exec_test_001")
            logger.log_job_completed("test_job_001", "Test Job", "exec_test_001", "success", 1.5)
            
            print(f"[OK] Logged messages for {tz}")
            
            # Check log file
            log_file = logger.get_log_file_path()
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "test_job_001" in content:
                        print(f"[OK] Log file contains expected content: {log_file}")
                    else:
                        print(f"[ERROR] Log file missing expected content: {log_file}")
                        return False
            else:
                print(f"[ERROR] Log file not created: {log_file}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Exception testing {tz}: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return False
    
    return True

def test_job_logger():
    """Test job logger creation"""
    print("\n=== JOB LOGGER TEST ===")
    
    try:
        from core.v2.job_logger import create_job_logger
        from core.v2.data_models import JobDefinition, StepConfiguration
        
        # Create job logger
        job_logger = create_job_logger("test_job", "exec_001", "Test Job", "UTC")
        
        if not job_logger:
            print("[ERROR] Failed to create job logger")
            return False
        
        print("[OK] Job logger created")
        
        # Create test job definition for logging
        step_config = StepConfiguration(
            step_id="test_step",
            step_name="Test Step", 
            step_type="sql",
            config={"query": "SELECT 1", "connection_name": "default"}
        )
        
        job_def = JobDefinition(
            job_id="test_job",
            job_name="Test Job",
            description="Test job for logging",
            timezone="UTC",
            steps=[step_config]
        )
        
        # Test logging
        job_logger.log_execution_start(job_def)
        job_logger.log_step_start(step_config, 1)
        job_logger.log_step_progress("test_step", "Testing progress")
        job_logger.log_step_output("test_step", "Test output")
        
        print("[OK] Job logging methods executed")
        
        # Check log file
        log_file = job_logger.get_log_file_path()
        if log_file.exists() and log_file.stat().st_size > 0:
            print(f"[OK] Job log file created: {log_file}")
            print(f"     File size: {log_file.stat().st_size} bytes")
        else:
            print(f"[ERROR] Job log file missing or empty: {log_file}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception testing job logger: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False
    
    return True

def test_file_separation():
    """Test that different timezones create separate files"""
    print("\n=== FILE SEPARATION TEST ===")
    
    try:
        from core.v2.timezone_logger import get_timezone_logger
        
        # Test with different timezones
        test_cases = [
            ("UTC", "utc_test_msg"),
            ("America/New_York", "est_test_msg"),
            ("Europe/London", "gmt_test_msg")
        ]
        
        # Create unique messages for each timezone
        for tz, unique_msg in test_cases:
            logger = get_timezone_logger(tz)
            logger.log_job_started("separation_test", unique_msg, f"exec_{unique_msg}")
        
        # Check that messages appear in correct files only
        for tz, unique_msg in test_cases:
            logger = get_timezone_logger(tz)
            log_file = logger.get_log_file_path()
            
            if not log_file.exists():
                print(f"[ERROR] Log file missing for {tz}: {log_file}")
                return False
            
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if unique_msg not in content:
                    print(f"[ERROR] Message '{unique_msg}' not found in {tz} log file")
                    return False
            
            print(f"[OK] Message '{unique_msg}' found in correct {tz} log file")
            
            # Check it doesn't appear in other timezone files
            for other_tz, other_msg in test_cases:
                if other_tz != tz:
                    other_logger = get_timezone_logger(other_tz)
                    other_log_file = other_logger.get_log_file_path()
                    
                    if other_log_file.exists():
                        with open(other_log_file, 'r', encoding='utf-8') as f:
                            other_content = f.read()
                            if unique_msg in other_content:
                                print(f"[ERROR] Message '{unique_msg}' leaked from {tz} to {other_tz}")
                                return False
        
        print("[OK] File separation working correctly")
        return True
        
    except Exception as e:
        print(f"[ERROR] Exception testing file separation: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

def list_log_files():
    """List all log files created"""
    print("\n=== LOG FILES CREATED ===")
    
    if not Path("logs").exists():
        print("[ERROR] No logs directory found")
        return
    
    for log_file in Path("logs").rglob("*.log"):
        size = log_file.stat().st_size
        print(f"[FILE] {log_file} ({size} bytes)")

def check_dependencies():
    """Check required dependencies"""
    print("\n=== DEPENDENCY CHECK ===")
    
    dependencies = ["pytz", "yaml"]
    all_good = True
    
    for dep in dependencies:
        try:
            __import__(dep)
            print(f"[OK] {dep} available")
        except ImportError:
            print(f"[ERROR] {dep} not installed")
            all_good = False
    
    return all_good

def main():
    """Main test function"""
    print("Job Scheduler V2 - Quick Logging Test")
    print("=" * 40)
    
    tests = [
        ("Dependencies", check_dependencies),
        ("Imports", test_imports),
        ("Directories", test_directory_creation),
        ("Timezone Logger", test_timezone_logger),
        ("Job Logger", test_job_logger),
        ("File Separation", test_file_separation),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\nRunning {test_name} test...")
        try:
            result = test_func()
            results[test_name] = result
            status = "[PASS]" if result else "[FAIL]"
            print(f"{status} {test_name}")
        except Exception as e:
            print(f"[ERROR] {test_name} test crashed: {e}")
            results[test_name] = False
    
    # Show log files created
    list_log_files()
    
    # Summary
    print("\n" + "=" * 40)
    print("TEST SUMMARY")
    print("=" * 40)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"Tests passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {test_name}")
    
    if passed == total:
        print("\n[SUCCESS] All logging tests passed!")
        print("The timezone-based logging system is working correctly.")
    else:
        print(f"\n[ISSUES] {total - passed} tests failed.")
        print("Please review the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)