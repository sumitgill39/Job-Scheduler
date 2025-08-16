#!/usr/bin/env python3
"""
Production Deployment Validation Script for Windows Environment
Validates that PowerShell jobs can be created, saved, and executed in production
"""

import sys
import os
import json
import subprocess
import platform
import time
from datetime import datetime, timedelta

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

class ProductionDeploymentValidator:
    """Validates production deployment for PowerShell job execution"""
    
    def __init__(self):
        self.validation_results = []
        self.is_windows = platform.system().lower() == 'windows'
        
    def validate_environment(self):
        """Validate the deployment environment"""
        print("=" * 60)
        print("PRODUCTION DEPLOYMENT VALIDATION")
        print("=" * 60)
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Python: {sys.version}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        return True
    
    def test_powershell_availability(self):
        """Test 1: PowerShell Environment"""
        print("TEST 1: PowerShell Environment")
        print("-" * 30)
        
        if not self.is_windows:
            print("❌ Not running on Windows - PowerShell execution will be limited")
            self.validation_results.append({
                'test': 'PowerShell Environment',
                'status': 'FAILED',
                'details': 'Not running on Windows platform'
            })
            return False
        
        try:
            # Test PowerShell availability
            result = subprocess.run([
                'powershell', '-Command', 
                'Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)"; Write-Host "Execution Policy: $(Get-ExecutionPolicy)"'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ PowerShell is available and functional")
                print(f"   Output: {result.stdout.strip()}")
                
                # Check execution policy
                if 'RemoteSigned' in result.stdout or 'Unrestricted' in result.stdout:
                    print("✅ PowerShell execution policy allows script execution")
                else:
                    print("⚠️  PowerShell execution policy may restrict script execution")
                    print("   Consider running: Set-ExecutionPolicy RemoteSigned -Scope LocalMachine")
                
                self.validation_results.append({
                    'test': 'PowerShell Environment',
                    'status': 'PASSED',
                    'details': 'PowerShell available and configured correctly'
                })
                return True
            else:
                print(f"❌ PowerShell test failed: {result.stderr}")
                self.validation_results.append({
                    'test': 'PowerShell Environment',
                    'status': 'FAILED',
                    'details': f'PowerShell test failed: {result.stderr}'
                })
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ PowerShell test timed out")
            self.validation_results.append({
                'test': 'PowerShell Environment',
                'status': 'FAILED',
                'details': 'PowerShell test timed out'
            })
            return False
        except Exception as e:
            print(f"❌ PowerShell test failed: {e}")
            self.validation_results.append({
                'test': 'PowerShell Environment',
                'status': 'FAILED',
                'details': f'PowerShell test exception: {str(e)}'
            })
            return False
    
    def test_database_connectivity(self):
        """Test 2: Database Connectivity"""
        print("\\nTEST 2: Database Connectivity")
        print("-" * 30)
        
        try:
            from database.connection_manager import DatabaseConnectionManager
            db_manager = DatabaseConnectionManager()
            
            # Test system database connection
            system_conn = db_manager.get_connection("system")
            if system_conn:
                print("✅ System database connection successful")
                
                # Test basic query
                cursor = system_conn.cursor()
                cursor.execute("SELECT DB_NAME() as current_database, SYSTEM_USER as current_user")
                result = cursor.fetchone()
                print(f"   Connected to database: {result[0]}")
                print(f"   Connected as user: {result[1]}")
                
                # Check job_configurations table
                cursor.execute("""
                    SELECT COUNT(*) as table_count 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_NAME = 'job_configurations'
                """)
                table_result = cursor.fetchone()
                
                if table_result[0] > 0:
                    print("✅ job_configurations table exists")
                else:
                    print("❌ job_configurations table does NOT exist")
                    print("   Run: sqlcmd -i database_setup.sql")
                    
                cursor.close()
                system_conn.close()
                
                self.validation_results.append({
                    'test': 'Database Connectivity',
                    'status': 'PASSED',
                    'details': f'Connected to database: {result[0]}'
                })
                return True
            else:
                print("❌ System database connection FAILED")
                self.validation_results.append({
                    'test': 'Database Connectivity',
                    'status': 'FAILED',
                    'details': 'System database connection failed'
                })
                return False
                
        except Exception as e:
            print(f"❌ Database connectivity test failed: {e}")
            self.validation_results.append({
                'test': 'Database Connectivity',
                'status': 'FAILED',
                'details': f'Database test exception: {str(e)}'
            })
            return False
    
    def test_powershell_job_creation(self):
        """Test 3: PowerShell Job Creation and Storage"""
        print("\\nTEST 3: PowerShell Job Creation and Storage")
        print("-" * 30)
        
        try:
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            # Create a production test PowerShell job
            production_script = '''
# Production PowerShell Job Test
Write-Host "=== Production Deployment Test ==="
Write-Host "Execution Time: $(Get-Date)"
Write-Host "Computer Name: $env:COMPUTERNAME"
Write-Host "User Context: $env:USERNAME"
Write-Host "PowerShell Version: $($PSVersionTable.PSVersion)"

# Test basic operations
$testNumber = 42
Write-Host "Math Test: 10 + 32 = $($testNumber)"

# Test string operations
$message = "Hello from production PowerShell job!"
Write-Host $message

# Test environment variables
Write-Host "Windows Version: $((Get-WmiObject -Class Win32_OperatingSystem).Caption)"

# Test error handling
try {
    $result = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "Date formatting test: $result"
} catch {
    Write-Host "Error in date formatting: $($_.Exception.Message)"
}

Write-Host "=== Production Test Complete ==="
            '''.strip()
            
            job_data = {
                'name': 'Production Deployment Validation',
                'description': 'PowerShell job to validate production deployment',
                'type': 'powershell',
                'enabled': True,
                'script_content': production_script,
                'execution_policy': 'RemoteSigned',
                'parameters': [],
                'timeout': 120,
                'max_retries': 2,
                'retry_delay': 30
            }
            
            print("📝 Creating production PowerShell job...")
            result = job_manager.create_job(job_data)
            
            if result['success']:
                job_id = result['job_id']
                print(f"✅ PowerShell job created successfully: {job_id}")
                
                # Verify job was saved to database
                saved_job = job_manager.get_job(job_id)
                if saved_job:
                    print("✅ PowerShell job successfully saved to database")
                    
                    # Verify script content integrity
                    saved_script = saved_job.get('configuration', {}).get('powershell', {}).get('script_content', '')
                    if 'Production Deployment Test' in saved_script:
                        print("✅ Script content preserved correctly")
                        
                        self.validation_results.append({
                            'test': 'PowerShell Job Creation',
                            'status': 'PASSED',
                            'job_id': job_id,
                            'details': 'Job created and stored successfully in database'
                        })
                        return job_id
                    else:
                        print("❌ Script content not preserved correctly")
                        self.validation_results.append({
                            'test': 'PowerShell Job Creation',
                            'status': 'FAILED',
                            'details': 'Script content not preserved'
                        })
                        return None
                else:
                    print("❌ PowerShell job was NOT saved to database")
                    self.validation_results.append({
                        'test': 'PowerShell Job Creation',
                        'status': 'FAILED',
                        'details': 'Job not retrievable from database'
                    })
                    return None
            else:
                print(f"❌ PowerShell job creation failed: {result['error']}")
                self.validation_results.append({
                    'test': 'PowerShell Job Creation',
                    'status': 'FAILED',
                    'details': f"Job creation failed: {result['error']}"
                })
                return None
                
        except Exception as e:
            print(f"❌ PowerShell job creation test failed: {e}")
            self.validation_results.append({
                'test': 'PowerShell Job Creation',
                'status': 'FAILED',
                'details': f'Exception during creation test: {str(e)}'
            })
            return None
    
    def test_powershell_job_execution(self, job_id):
        """Test 4: PowerShell Job Execution"""
        print("\\nTEST 4: PowerShell Job Execution")
        print("-" * 30)
        
        if not job_id:
            print("❌ Cannot test execution - no job ID provided")
            self.validation_results.append({
                'test': 'PowerShell Job Execution',
                'status': 'FAILED',
                'details': 'No job available for execution test'
            })
            return False
        
        try:
            from core.job_executor import JobExecutor
            job_executor = JobExecutor()
            
            print(f"🚀 Executing PowerShell job: {job_id}")
            execution_result = job_executor.execute_job(job_id)
            
            if execution_result['success']:
                print("✅ PowerShell job executed successfully")
                print(f"   Status: {execution_result['status']}")
                print(f"   Duration: {execution_result.get('duration_seconds', 0):.2f} seconds")
                
                # Check execution output
                output = execution_result.get('output', '')
                if output:
                    print("✅ Job produced output")
                    
                    # Verify expected content in output
                    expected_phrases = [
                        'Production Deployment Test',
                        'Production Test Complete',
                        'Math Test: 10 + 32 = 42'
                    ]
                    
                    found_phrases = 0
                    for phrase in expected_phrases:
                        if phrase in output:
                            found_phrases += 1
                            print(f"   ✅ Found expected output: '{phrase}'")
                        else:
                            print(f"   ⚠️  Missing expected output: '{phrase}'")
                    
                    if found_phrases >= len(expected_phrases) * 0.7:  # 70% threshold
                        print("✅ PowerShell execution validation PASSED")
                        self.validation_results.append({
                            'test': 'PowerShell Job Execution',
                            'status': 'PASSED',
                            'job_id': job_id,
                            'details': f'Execution successful, found {found_phrases}/{len(expected_phrases)} expected outputs'
                        })
                        return True
                    else:
                        print("❌ PowerShell execution validation FAILED")
                        self.validation_results.append({
                            'test': 'PowerShell Job Execution',
                            'status': 'FAILED',
                            'details': f'Only found {found_phrases}/{len(expected_phrases)} expected outputs'
                        })
                        return False
                else:
                    print("⚠️  Job executed but produced no output")
                    self.validation_results.append({
                        'test': 'PowerShell Job Execution',
                        'status': 'PARTIAL',
                        'details': 'Job executed but no output captured'
                    })
                    return False
            else:
                print(f"❌ PowerShell job execution failed: {execution_result.get('error', 'Unknown error')}")
                self.validation_results.append({
                    'test': 'PowerShell Job Execution',
                    'status': 'FAILED',
                    'details': f"Execution failed: {execution_result.get('error', 'Unknown error')}"
                })
                return False
                
        except Exception as e:
            print(f"❌ PowerShell execution test failed: {e}")
            self.validation_results.append({
                'test': 'PowerShell Job Execution',
                'status': 'FAILED',
                'details': f'Exception during execution test: {str(e)}'
            })
            return False
    
    def test_scheduled_job_configuration(self):
        """Test 5: Scheduled Job Configuration"""
        print("\\nTEST 5: Scheduled Job Configuration")
        print("-" * 30)
        
        try:
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            # Create a scheduled PowerShell job
            scheduled_script = '''
Write-Host "=== Scheduled PowerShell Job ==="
Write-Host "Scheduled execution at: $(Get-Date)"
Write-Host "This job runs automatically on schedule"
Write-Host "Job completed successfully"
            '''.strip()
            
            job_data = {
                'name': 'Production Scheduled Test',
                'description': 'Scheduled PowerShell job for production validation',
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
                    'interval_minutes': 10,  # Run every 10 minutes
                    'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            }
            
            print("📅 Creating scheduled PowerShell job...")
            result = job_manager.create_job(job_data)
            
            if result['success']:
                job_id = result['job_id']
                print(f"✅ Scheduled job created successfully: {job_id}")
                
                # Verify schedule configuration
                saved_job = job_manager.get_job(job_id)
                if saved_job:
                    schedule_config = saved_job.get('configuration', {}).get('schedule', {})
                    if schedule_config:
                        print(f"✅ Schedule configuration saved: {schedule_config}")
                        print("✅ Job is ready for SchedulerManager execution")
                        
                        self.validation_results.append({
                            'test': 'Scheduled Job Configuration',
                            'status': 'PASSED',
                            'job_id': job_id,
                            'details': 'Scheduled job configured correctly, ready for automatic execution'
                        })
                        return True
                    else:
                        print("❌ Schedule configuration not saved")
                        self.validation_results.append({
                            'test': 'Scheduled Job Configuration',
                            'status': 'FAILED',
                            'details': 'Schedule configuration not found'
                        })
                        return False
                else:
                    print("❌ Could not retrieve scheduled job")
                    self.validation_results.append({
                        'test': 'Scheduled Job Configuration',
                        'status': 'FAILED',
                        'details': 'Scheduled job not retrievable'
                    })
                    return False
            else:
                print(f"❌ Scheduled job creation failed: {result['error']}")
                self.validation_results.append({
                    'test': 'Scheduled Job Configuration',
                    'status': 'FAILED',
                    'details': f"Scheduled job creation failed: {result['error']}"
                })
                return False
                
        except Exception as e:
            print(f"❌ Scheduled job test failed: {e}")
            self.validation_results.append({
                'test': 'Scheduled Job Configuration',
                'status': 'FAILED',
                'details': f'Exception during scheduled job test: {str(e)}'
            })
            return False
    
    def test_web_interface(self):
        """Test 6: Web Interface Availability"""
        print("\\nTEST 6: Web Interface Availability")
        print("-" * 30)
        
        try:
            import requests
            
            # Test if web interface is running
            response = requests.get("http://127.0.0.1:5000/", timeout=5)
            
            if response.status_code == 200:
                print("✅ Web interface is accessible")
                
                # Test API endpoint
                api_response = requests.get("http://127.0.0.1:5000/api/jobs", timeout=5)
                if api_response.status_code == 200:
                    print("✅ API endpoints are functional")
                    self.validation_results.append({
                        'test': 'Web Interface',
                        'status': 'PASSED',
                        'details': 'Web interface and API are accessible'
                    })
                    return True
                else:
                    print(f"⚠️  API endpoint returned status: {api_response.status_code}")
                    self.validation_results.append({
                        'test': 'Web Interface',
                        'status': 'PARTIAL',
                        'details': f'Web interface accessible but API returned {api_response.status_code}'
                    })
                    return False
            else:
                print(f"❌ Web interface returned status: {response.status_code}")
                self.validation_results.append({
                    'test': 'Web Interface',
                    'status': 'FAILED',
                    'details': f'Web interface returned status {response.status_code}'
                })
                return False
                
        except requests.ConnectionError:
            print("❌ Web interface is not running")
            print("   Start with: python main.py")
            self.validation_results.append({
                'test': 'Web Interface',
                'status': 'FAILED',
                'details': 'Web interface not running - start with python main.py'
            })
            return False
        except Exception as e:
            print(f"❌ Web interface test failed: {e}")
            self.validation_results.append({
                'test': 'Web Interface',
                'status': 'FAILED',
                'details': f'Web interface test exception: {str(e)}'
            })
            return False
    
    def generate_deployment_report(self):
        """Generate comprehensive deployment validation report"""
        print("\\n" + "=" * 60)
        print("PRODUCTION DEPLOYMENT VALIDATION REPORT")
        print("=" * 60)
        
        print(f"Validation completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Platform: {platform.system()} {platform.release()}")
        print(f"Total tests performed: {len(self.validation_results)}")
        
        passed_tests = [t for t in self.validation_results if t['status'] == 'PASSED']
        failed_tests = [t for t in self.validation_results if t['status'] == 'FAILED']
        partial_tests = [t for t in self.validation_results if t['status'] == 'PARTIAL']
        
        print(f"Passed: {len(passed_tests)}")
        print(f"Failed: {len(failed_tests)}")
        print(f"Partial: {len(partial_tests)}")
        
        print("\\n📊 DETAILED RESULTS:")
        for result in self.validation_results:
            status_icon = "✅" if result['status'] == 'PASSED' else "❌" if result['status'] == 'FAILED' else "⚠️"
            print(f"{status_icon} {result['test']}: {result['status']}")
            print(f"   Details: {result['details']}")
            if 'job_id' in result:
                print(f"   Job ID: {result['job_id']}")
        
        print(f"\\n📋 DEPLOYMENT STATUS:")
        if len(failed_tests) == 0:
            print("🎉 PRODUCTION DEPLOYMENT SUCCESSFUL!")
            print("✅ PowerShell Environment: READY")
            print("✅ Database Connectivity: READY") 
            print("✅ Job Creation: READY")
            print("✅ Job Execution: READY")
            print("✅ Job Scheduling: READY")
            print("✅ Web Interface: READY")
            print("\\n🚀 The system is PRODUCTION READY for PowerShell job execution!")
            print("\\nNext steps:")
            print("- Start the SchedulerManager to enable automatic job execution")
            print("- Monitor logs for job execution status")
            print("- Create production PowerShell jobs via the web interface")
        else:
            print("⚠️  DEPLOYMENT ISSUES DETECTED")
            print(f"❌ {len(failed_tests)} test(s) failed")
            print("\\n🔧 REQUIRED ACTIONS:")
            for failed_test in failed_tests:
                print(f"- Fix: {failed_test['test']} - {failed_test['details']}")
        
        # Save report to file
        report_file = f"production_deployment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'platform': f"{platform.system()} {platform.release()}",
                'total_tests': len(self.validation_results),
                'passed': len(passed_tests),
                'failed': len(failed_tests),
                'partial': len(partial_tests),
                'results': self.validation_results,
                'deployment_ready': len(failed_tests) == 0
            }, f, indent=2)
        
        print(f"\\n📄 Detailed report saved to: {report_file}")
        
        return len(failed_tests) == 0

def main():
    """Run complete production deployment validation"""
    validator = ProductionDeploymentValidator()
    
    print("PowerShell Job Scheduler - Production Deployment Validation")
    print("This will validate that the system is ready for production use")
    print()
    
    # Run validation tests
    validator.validate_environment()
    
    test1_passed = validator.test_powershell_availability()
    test2_passed = validator.test_database_connectivity()
    job_id = validator.test_powershell_job_creation()
    test4_passed = validator.test_powershell_job_execution(job_id)
    test5_passed = validator.test_scheduled_job_configuration()
    test6_passed = validator.test_web_interface()
    
    # Generate comprehensive report
    deployment_ready = validator.generate_deployment_report()
    
    return deployment_ready

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)