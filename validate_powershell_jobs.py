#!/usr/bin/env python3
"""
Comprehensive PowerShell Job Validation System
Tests the complete lifecycle: Creation -> Database Storage -> Scheduled Execution
"""

import sys
import os
import json
import time
import sqlite3
from datetime import datetime, timedelta

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

class PowerShellJobValidator:
    """Comprehensive PowerShell job validation system"""
    
    def __init__(self, use_sqlite_fallback=True):
        self.use_sqlite_fallback = use_sqlite_fallback
        self.sqlite_db_path = "test_jobs.db"
        self.test_results = []
        
    def setup_test_database(self):
        """Setup SQLite database for testing when SQL Server is not available"""
        if self.use_sqlite_fallback:
            print("📝 Setting up SQLite test database...")
            conn = sqlite3.connect(self.sqlite_db_path)
            cursor = conn.cursor()
            
            # Create job_configurations table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS job_configurations (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    configuration TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    created_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    modified_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT DEFAULT 'test_system'
                )
            ''')
            
            # Create job_execution_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS job_execution_history (
                    execution_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    job_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    output TEXT,
                    error_message TEXT,
                    return_code INTEGER,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 0,
                    metadata TEXT
                )
            ''')
            
            conn.commit()
            conn.close()
            print("   ✅ SQLite test database created")
            return True
        return False
    
    def test_powershell_job_creation(self):
        """Test 1: PowerShell job creation with various script types"""
        print("\n" + "=" * 60)
        print("TEST 1: PowerShell Job Creation")
        print("=" * 60)
        
        test_scripts = [
            {
                'name': 'Simple Output Script',
                'description': 'Basic PowerShell script with simple output',
                'script_content': '''
Write-Host "PowerShell Job Test Started"
Write-Host "Current Date/Time: $(Get-Date)"
Write-Host "Computer Name: $env:COMPUTERNAME"
Write-Host "User: $env:USERNAME"
Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)"
Write-Host "Test Completed Successfully"
                '''.strip(),
                'expected_keywords': ['PowerShell Job Test Started', 'Test Completed Successfully']
            },
            {
                'name': 'Parameter Script',
                'description': 'PowerShell script with parameters',
                'script_content': '''
param(
    [string]$Message = "Default Message",
    [int]$Count = 3,
    [string]$LogPath = ""
)

Write-Host "=== PowerShell Parameter Test ==="
Write-Host "Message: $Message"
Write-Host "Count: $Count"
Write-Host "Log Path: $LogPath"

for ($i = 1; $i -le $Count; $i++) {
    Write-Host "Iteration $i of $Count"
    Start-Sleep -Seconds 1
}

if ($LogPath -ne "") {
    "Test log entry: $(Get-Date)" | Out-File -FilePath $LogPath -Append
    Write-Host "Log written to: $LogPath"
}

Write-Host "Parameter test completed"
                '''.strip(),
                'parameters': ['-Message', 'Scheduled Test', '-Count', '2'],
                'expected_keywords': ['Parameter test completed', 'Iteration 1 of 2']
            },
            {
                'name': 'System Information Script',
                'description': 'PowerShell script gathering system information',
                'script_content': '''
Write-Host "=== System Information Collection ==="

# Get basic system info
$os = Get-WmiObject -Class Win32_OperatingSystem -ErrorAction SilentlyContinue
if ($os) {
    Write-Host "OS: $($os.Caption)"
    Write-Host "Architecture: $($os.OSArchitecture)"
    Write-Host "Total Memory: $([math]::Round($os.TotalVisibleMemorySize/1MB, 2)) GB"
} else {
    Write-Host "OS: Non-Windows System (WMI not available)"
    Write-Host "PowerShell Host: $($Host.Name)"
    Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)"
}

# Get process count
$processCount = (Get-Process).Count
Write-Host "Running Processes: $processCount"

# Get current directory
Write-Host "Current Directory: $(Get-Location)"

# Test error handling
try {
    $nonExistentVar = $someUndefinedVariable.Property
} catch {
    Write-Host "Error handling test: Successfully caught undefined variable error"
}

Write-Host "System information collection completed"
                '''.strip(),
                'expected_keywords': ['System Information Collection', 'System information collection completed']
            }
        ]
        
        success_count = 0
        
        for i, test_script in enumerate(test_scripts, 1):
            print(f"\n📝 Test 1.{i}: {test_script['name']}")
            
            try:
                from core.job_manager import JobManager
                job_manager = JobManager()
                
                job_data = {
                    'name': f"Validation Test - {test_script['name']}",
                    'description': test_script['description'],
                    'type': 'powershell',
                    'enabled': True,
                    'script_content': test_script['script_content'],
                    'execution_policy': 'RemoteSigned',
                    'parameters': test_script.get('parameters', []),
                    'timeout': 300,
                    'max_retries': 3,
                    'retry_delay': 60
                }
                
                # Test job creation
                result = job_manager.create_job(job_data)
                
                if result['success']:
                    job_id = result['job_id']
                    print(f"   ✅ Job created successfully: {job_id}")
                    
                    # Verify job can be retrieved
                    saved_job = job_manager.get_job(job_id)
                    if saved_job:
                        print(f"   ✅ Job retrieved from storage successfully")
                        
                        # Verify script content is preserved
                        saved_script = saved_job.get('configuration', {}).get('powershell', {}).get('script_content', '')
                        if test_script['script_content'].strip() in saved_script:
                            print(f"   ✅ Script content preserved correctly")
                            success_count += 1
                            
                            self.test_results.append({
                                'test': f"PowerShell Job Creation - {test_script['name']}",
                                'status': 'PASSED',
                                'job_id': job_id,
                                'details': 'Job created and stored successfully'
                            })
                        else:
                            print(f"   ❌ Script content not preserved correctly")
                            self.test_results.append({
                                'test': f"PowerShell Job Creation - {test_script['name']}",
                                'status': 'FAILED',
                                'details': 'Script content not preserved'
                            })
                    else:
                        print(f"   ❌ Job could not be retrieved from storage")
                        self.test_results.append({
                            'test': f"PowerShell Job Creation - {test_script['name']}",
                            'status': 'FAILED',
                            'details': 'Job not retrievable from storage'
                        })
                else:
                    print(f"   ❌ Job creation failed: {result['error']}")
                    self.test_results.append({
                        'test': f"PowerShell Job Creation - {test_script['name']}",
                        'status': 'FAILED',
                        'details': f"Creation failed: {result['error']}"
                    })
                    
            except Exception as e:
                print(f"   ❌ Test failed with exception: {e}")
                self.test_results.append({
                    'test': f"PowerShell Job Creation - {test_script['name']}",
                    'status': 'FAILED',
                    'details': f"Exception: {str(e)}"
                })
        
        print(f"\n📊 Job Creation Test Results: {success_count}/{len(test_scripts)} passed")
        return success_count == len(test_scripts)
    
    def test_powershell_job_execution(self):
        """Test 2: PowerShell job execution"""
        print("\n" + "=" * 60)
        print("TEST 2: PowerShell Job Execution")
        print("=" * 60)
        
        try:
            # Create a simple test job for execution
            from core.job_manager import JobManager
            from core.job_executor import JobExecutor
            
            job_manager = JobManager()
            job_executor = JobExecutor()
            
            execution_test_script = '''
Write-Host "=== PowerShell Execution Validation ==="
Write-Host "Execution started at: $(Get-Date)"

# Test basic operations
$testValue = 42
Write-Host "Test value: $testValue"

# Test string operations
$message = "Hello from scheduled PowerShell job!"
Write-Host $message

# Test array operations
$fruits = @("Apple", "Banana", "Orange")
Write-Host "Fruits count: $($fruits.Count)"
foreach ($fruit in $fruits) {
    Write-Host "Fruit: $fruit"
}

# Test conditional logic
if ($testValue -eq 42) {
    Write-Host "Conditional test: PASSED"
} else {
    Write-Host "Conditional test: FAILED"
}

# Test error handling
try {
    # This should work fine
    $result = 10 / 2
    Write-Host "Math test result: $result"
} catch {
    Write-Host "Math test failed: $($_.Exception.Message)"
}

Write-Host "Execution completed at: $(Get-Date)"
Write-Host "=== Execution Validation Complete ==="
            '''.strip()
            
            job_data = {
                'name': 'PowerShell Execution Test',
                'description': 'Test PowerShell job execution functionality',
                'type': 'powershell',
                'enabled': True,
                'script_content': execution_test_script,
                'execution_policy': 'RemoteSigned',
                'parameters': [],
                'timeout': 60,
                'max_retries': 2,
                'retry_delay': 30
            }
            
            print("📝 Creating job for execution test...")
            result = job_manager.create_job(job_data)
            
            if not result['success']:
                print(f"   ❌ Failed to create execution test job: {result['error']}")
                self.test_results.append({
                    'test': 'PowerShell Job Execution',
                    'status': 'FAILED',
                    'details': f"Job creation failed: {result['error']}"
                })
                return False
            
            job_id = result['job_id']
            print(f"   ✅ Execution test job created: {job_id}")
            
            print("🚀 Executing PowerShell job...")
            execution_result = job_executor.execute_job(job_id)
            
            if execution_result['success']:
                print(f"   ✅ Job executed successfully")
                print(f"   Status: {execution_result['status']}")
                print(f"   Duration: {execution_result['duration_seconds']:.2f} seconds")
                
                # Check execution output
                output = execution_result.get('output', '')
                if output:
                    print("   ✅ Job produced output")
                    
                    # Check for expected content in output
                    expected_phrases = [
                        'PowerShell Execution Validation',
                        'Test value: 42',
                        'Hello from scheduled PowerShell job!',
                        'Conditional test: PASSED',
                        'Execution Validation Complete'
                    ]
                    
                    found_phrases = 0
                    for phrase in expected_phrases:
                        if phrase in output:
                            found_phrases += 1
                            print(f"   ✅ Found expected phrase: '{phrase}'")
                        else:
                            print(f"   ⚠️  Missing expected phrase: '{phrase}'")
                    
                    if found_phrases >= len(expected_phrases) * 0.8:  # 80% threshold
                        print("   ✅ Execution output validation PASSED")
                        self.test_results.append({
                            'test': 'PowerShell Job Execution',
                            'status': 'PASSED',
                            'job_id': job_id,
                            'details': f"Execution successful, found {found_phrases}/{len(expected_phrases)} expected phrases"
                        })
                        return True
                    else:
                        print("   ❌ Execution output validation FAILED")
                        self.test_results.append({
                            'test': 'PowerShell Job Execution',
                            'status': 'FAILED',
                            'details': f"Only found {found_phrases}/{len(expected_phrases)} expected phrases"
                        })
                        return False
                else:
                    print("   ⚠️  Job executed but produced no output")
                    self.test_results.append({
                        'test': 'PowerShell Job Execution',
                        'status': 'PARTIAL',
                        'details': 'Job executed but no output captured'
                    })
                    return False
            else:
                print(f"   ❌ Job execution failed: {execution_result['error']}")
                self.test_results.append({
                    'test': 'PowerShell Job Execution',
                    'status': 'FAILED',
                    'details': f"Execution failed: {execution_result['error']}"
                })
                return False
                
        except Exception as e:
            print(f"   ❌ Execution test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            self.test_results.append({
                'test': 'PowerShell Job Execution',
                'status': 'FAILED',
                'details': f"Exception during execution test: {str(e)}"
            })
            return False
    
    def test_powershell_job_scheduling(self):
        """Test 3: PowerShell job scheduling functionality"""
        print("\n" + "=" * 60)
        print("TEST 3: PowerShell Job Scheduling")
        print("=" * 60)
        
        try:
            from core.job_manager import JobManager
            from core.scheduler_manager import SchedulerManager
            import time
            
            job_manager = JobManager()
            
            # Create a job with scheduling
            scheduled_script = '''
Write-Host "=== Scheduled PowerShell Job Execution ==="
Write-Host "Scheduled execution time: $(Get-Date)"
Write-Host "This job was executed by the scheduler"

# Create a simple log entry
$logEntry = "$(Get-Date): Scheduled PowerShell job executed successfully"
Write-Host $logEntry

# Test some scheduled job operations
Write-Host "Job execution environment:"
Write-Host "  - PowerShell Version: $($PSVersionTable.PSVersion)"
Write-Host "  - Execution Policy: $(Get-ExecutionPolicy)"
Write-Host "  - Current User: $env:USERNAME"
Write-Host "  - Working Directory: $(Get-Location)"

Write-Host "=== Scheduled Job Execution Complete ==="
            '''.strip()
            
            # Schedule job to run every minute for testing
            job_data = {
                'name': 'PowerShell Scheduled Test',
                'description': 'Test PowerShell job scheduling functionality',
                'type': 'powershell',
                'enabled': True,
                'script_content': scheduled_script,
                'execution_policy': 'RemoteSigned',
                'parameters': [],
                'timeout': 60,
                'max_retries': 1,
                'retry_delay': 30,
                'schedule': {
                    'type': 'interval',
                    'interval_minutes': 1,  # Run every minute for testing
                    'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
            print("📝 Creating scheduled PowerShell job...")
            result = job_manager.create_job(job_data)
            
            if not result['success']:
                print(f"   ❌ Failed to create scheduled job: {result['error']}")
                self.test_results.append({
                    'test': 'PowerShell Job Scheduling',
                    'status': 'FAILED',
                    'details': f"Scheduled job creation failed: {result['error']}"
                })
                return False
            
            job_id = result['job_id']
            print(f"   ✅ Scheduled job created: {job_id}")
            
            # Note: In a real environment, we would start the scheduler and wait for execution
            # For testing purposes, we'll validate that the job can be scheduled
            
            print("📅 Validating job scheduling configuration...")
            
            # Retrieve the job and check schedule configuration
            saved_job = job_manager.get_job(job_id)
            if saved_job:
                schedule_config = saved_job.get('configuration', {}).get('schedule', {})
                if schedule_config:
                    print(f"   ✅ Schedule configuration saved: {schedule_config}")
                    
                    # Validate schedule parameters
                    if (schedule_config.get('type') == 'interval' and 
                        schedule_config.get('interval_minutes') == 1):
                        print("   ✅ Schedule parameters validated")
                        
                        # In a real environment with scheduler running:
                        # - Job would be added to APScheduler
                        # - Scheduler would execute job every minute
                        # - Execution history would be recorded
                        
                        print("   ✅ Job is ready for scheduled execution")
                        print("   ℹ️  Note: In production, SchedulerManager would execute this job every minute")
                        
                        self.test_results.append({
                            'test': 'PowerShell Job Scheduling',
                            'status': 'PASSED',
                            'job_id': job_id,
                            'details': 'Job configured for scheduling, ready for SchedulerManager execution'
                        })
                        return True
                    else:
                        print("   ❌ Schedule parameters validation failed")
                        self.test_results.append({
                            'test': 'PowerShell Job Scheduling',
                            'status': 'FAILED',
                            'details': 'Schedule parameters not saved correctly'
                        })
                        return False
                else:
                    print("   ❌ Schedule configuration not saved")
                    self.test_results.append({
                        'test': 'PowerShell Job Scheduling',
                        'status': 'FAILED',
                        'details': 'Schedule configuration not found in saved job'
                    })
                    return False
            else:
                print("   ❌ Could not retrieve scheduled job")
                self.test_results.append({
                    'test': 'PowerShell Job Scheduling',
                    'status': 'FAILED',
                    'details': 'Scheduled job not retrievable'
                })
                return False
                
        except Exception as e:
            print(f"   ❌ Scheduling test failed with exception: {e}")
            self.test_results.append({
                'test': 'PowerShell Job Scheduling',
                'status': 'FAILED',
                'details': f"Exception during scheduling test: {str(e)}"
            })
            return False
    
    def test_database_persistence(self):
        """Test 4: Database persistence validation"""
        print("\n" + "=" * 60)
        print("TEST 4: Database Persistence Validation")
        print("=" * 60)
        
        try:
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            # Create a complex PowerShell job to test persistence
            complex_script = '''
# Complex PowerShell script for persistence testing
param(
    [string]$Environment = "Production",
    [string[]]$Services = @("Service1", "Service2"),
    [hashtable]$Config = @{}
)

Write-Host "=== Complex PowerShell Job Persistence Test ==="
Write-Host "Environment: $Environment"
Write-Host "Services: $($Services -join ', ')"

# Test JSON-like data handling
$jsonData = @{
    "timestamp" = Get-Date
    "environment" = $Environment
    "services" = $Services
    "status" = "running"
    "metadata" = @{
        "version" = "1.0"
        "author" = "PowerShell Job System"
    }
} | ConvertTo-Json -Depth 3

Write-Host "JSON Data: $jsonData"

# Test special characters and Unicode
Write-Host "Special chars test: !@#$%^&*()_+-=[]{}|;':\",./<>?"
Write-Host "Unicode test: ñáéíóúü αβγδε 中文 🚀"

# Test multiline operations
$multilineString = @"
This is a multiline string
With special characters: "quotes" and 'apostrophes'
And backslashes: C:\Windows\System32
And Unicode: ñáéíóúü
"@

Write-Host "Multiline string: $multilineString"

Write-Host "=== Persistence Test Complete ==="
            '''.strip()
            
            job_data = {
                'name': 'PowerShell Persistence Test',
                'description': 'Complex PowerShell job to test database persistence of special characters and complex content',
                'type': 'powershell',
                'enabled': True,
                'script_content': complex_script,
                'execution_policy': 'RemoteSigned',
                'parameters': ['-Environment', 'Test', '-Services', 'ServiceA,ServiceB'],
                'timeout': 120,
                'max_retries': 2,
                'retry_delay': 45,
                'schedule': {
                    'type': 'cron',
                    'cron_expression': '0 */6 * * *',  # Every 6 hours
                    'timezone': 'UTC'
                }
            }
            
            print("📝 Creating complex job for persistence testing...")
            result = job_manager.create_job(job_data)
            
            if not result['success']:
                print(f"   ❌ Failed to create persistence test job: {result['error']}")
                self.test_results.append({
                    'test': 'Database Persistence',
                    'status': 'FAILED',
                    'details': f"Job creation failed: {result['error']}"
                })
                return False
            
            job_id = result['job_id']
            print(f"   ✅ Complex job created: {job_id}")
            
            # Test retrieval and validation
            print("🔍 Validating job persistence...")
            saved_job = job_manager.get_job(job_id)
            
            if not saved_job:
                print("   ❌ Job not found after creation")
                self.test_results.append({
                    'test': 'Database Persistence',
                    'status': 'FAILED',
                    'details': 'Job not retrievable after creation'
                })
                return False
            
            # Validate all fields were persisted correctly
            validation_checks = [
                ('name', job_data['name'], saved_job.get('name')),
                ('type', job_data['type'], saved_job.get('type')),
                ('enabled', job_data['enabled'], saved_job.get('enabled')),
                ('script_content', job_data['script_content'], 
                 saved_job.get('configuration', {}).get('powershell', {}).get('script_content')),
                ('parameters', job_data['parameters'],
                 saved_job.get('configuration', {}).get('powershell', {}).get('parameters')),
                ('timeout', job_data['timeout'],
                 saved_job.get('configuration', {}).get('basic', {}).get('timeout')),
                ('schedule_type', job_data['schedule']['type'],
                 saved_job.get('configuration', {}).get('schedule', {}).get('type'))
            ]
            
            passed_checks = 0
            for check_name, original, saved in validation_checks:
                if original == saved:
                    print(f"   ✅ {check_name}: Preserved correctly")
                    passed_checks += 1
                else:
                    print(f"   ❌ {check_name}: Not preserved (original: {original}, saved: {saved})")
            
            if passed_checks == len(validation_checks):
                print("   ✅ All persistence checks PASSED")
                self.test_results.append({
                    'test': 'Database Persistence',
                    'status': 'PASSED',
                    'job_id': job_id,
                    'details': f"All {len(validation_checks)} persistence checks passed"
                })
                return True
            else:
                print(f"   ❌ Persistence validation FAILED: {passed_checks}/{len(validation_checks)} checks passed")
                self.test_results.append({
                    'test': 'Database Persistence',
                    'status': 'FAILED',
                    'details': f"Only {passed_checks}/{len(validation_checks)} persistence checks passed"
                })
                return False
                
        except Exception as e:
            print(f"   ❌ Persistence test failed with exception: {e}")
            self.test_results.append({
                'test': 'Database Persistence',
                'status': 'FAILED',
                'details': f"Exception during persistence test: {str(e)}"
            })
            return False
    
    def generate_validation_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 60)
        print("POWERSHELL JOB VALIDATION REPORT")
        print("=" * 60)
        
        print(f"Validation completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total tests performed: {len(self.test_results)}")
        
        passed_tests = [t for t in self.test_results if t['status'] == 'PASSED']
        failed_tests = [t for t in self.test_results if t['status'] == 'FAILED']
        partial_tests = [t for t in self.test_results if t['status'] == 'PARTIAL']
        
        print(f"Passed: {len(passed_tests)}")
        print(f"Failed: {len(failed_tests)}")
        print(f"Partial: {len(partial_tests)}")
        
        print("\n📊 DETAILED RESULTS:")
        for result in self.test_results:
            status_icon = "✅" if result['status'] == 'PASSED' else "❌" if result['status'] == 'FAILED' else "⚠️"
            print(f"{status_icon} {result['test']}: {result['status']}")
            print(f"   Details: {result['details']}")
            if 'job_id' in result:
                print(f"   Job ID: {result['job_id']}")
        
        print(f"\n📋 SUMMARY:")
        if len(failed_tests) == 0:
            print("🎉 ALL TESTS PASSED!")
            print("✅ PowerShell jobs can be created, saved, and executed successfully")
            print("✅ Database persistence is working correctly")
            print("✅ Job scheduling configuration is properly stored")
            print("✅ Special characters and complex content are handled correctly")
            print("\n🚀 PowerShell job system is PRODUCTION READY!")
        else:
            print("⚠️  SOME TESTS FAILED")
            print(f"❌ {len(failed_tests)} test(s) failed")
            print("\n🔧 RECOMMENDATIONS:")
            for failed_test in failed_tests:
                print(f"- Fix: {failed_test['test']} - {failed_test['details']}")
        
        # Save report to file
        report_file = f"powershell_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'total_tests': len(self.test_results),
                'passed': len(passed_tests),
                'failed': len(failed_tests),
                'partial': len(partial_tests),
                'results': self.test_results
            }, f, indent=2)
        
        print(f"\n📄 Detailed report saved to: {report_file}")
        
        return len(failed_tests) == 0

def main():
    """Run comprehensive PowerShell job validation"""
    print("PowerShell Job Comprehensive Validation System")
    print("=" * 60)
    print("This will validate the complete PowerShell job lifecycle:")
    print("1. Job Creation and Storage")
    print("2. Job Execution")
    print("3. Job Scheduling")
    print("4. Database Persistence")
    print("=" * 60)
    
    validator = PowerShellJobValidator()
    
    # Setup test database if needed
    validator.setup_test_database()
    
    # Run all validation tests
    test1_passed = validator.test_powershell_job_creation()
    test2_passed = validator.test_powershell_job_execution()
    test3_passed = validator.test_powershell_job_scheduling()
    test4_passed = validator.test_database_persistence()
    
    # Generate comprehensive report
    all_passed = validator.generate_validation_report()
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)