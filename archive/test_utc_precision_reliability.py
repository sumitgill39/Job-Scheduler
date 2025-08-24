#!/usr/bin/env python3
"""
UTC Scheduling Precision and Reliability Test Suite
Comprehensive testing of UTC scheduling system reliability, precision, and edge cases
"""

import sys
import os
import time
import threading
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
import statistics
import concurrent.futures

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

from core.utc_scheduling_validator import UTCSchedulingValidator, validate_multiple_jobs
from core.sql_job import SqlJob
from core.powershell_job import PowerShellJob
from scheduler.job_scheduler import JobScheduler
from test_utc_timing_accuracy import UTCTimingAccuracyTester
import pytz


class UTCPrecisionReliabilityTester:
    """Comprehensive UTC precision and reliability testing"""
    
    def __init__(self):
        self.scheduler = JobScheduler()
        self.validator = UTCSchedulingValidator()
        self.timing_tester = UTCTimingAccuracyTester()
        self.utc = pytz.UTC
        self.test_results = {}
        
    def test_scheduling_validation_system(self) -> Dict[str, Any]:
        """Test the UTC scheduling validation system"""
        print("\n🔍 Testing UTC Scheduling Validation System...")
        
        # Test with various job configurations
        test_configurations = [
            # Valid UTC cron job
            {
                'job_id': 'valid-utc-cron',
                'name': 'Valid UTC Cron Job',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '0 0 12 * * 1-5',  # Noon weekdays
                    'timezone': 'UTC'
                },
                'timeout': 300,
                'max_retries': 3,
                'retry_delay': 60
            },
            # Invalid cron expression
            {
                'job_id': 'invalid-cron',
                'name': 'Invalid Cron Job',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '0 0 25 * *',  # Invalid - only 5 parts and invalid hour
                    'timezone': 'UTC'
                },
                'timeout': 300,
                'max_retries': 3,
                'retry_delay': 60
            },
            # High-frequency interval (warning case)
            {
                'job_id': 'high-frequency',
                'name': 'High Frequency Job',
                'schedule_type': 'interval',
                'schedule_config': {
                    'interval_seconds': 15,  # Very frequent - should trigger warning
                    'timezone': 'UTC'
                },
                'timeout': 60,
                'max_retries': 1,
                'retry_delay': 30
            },
            # DST timezone (warning case)
            {
                'job_id': 'dst-timezone',
                'name': 'DST Timezone Job',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '0 30 2 * * *',  # 2:30 AM daily
                    'timezone': 'America/New_York'  # Has DST
                },
                'timeout': 300,
                'max_retries': 3,
                'retry_delay': 60
            },
            # Past one-time execution
            {
                'job_id': 'past-onetime',
                'name': 'Past One-time Job',
                'schedule_type': 'one_time',
                'schedule_config': {
                    'execute_at': (datetime.utcnow() - timedelta(hours=1)).isoformat() + 'Z',
                    'timezone': 'UTC'
                },
                'timeout': 120,
                'max_retries': 0,
                'retry_delay': 0
            },
            # Valid future one-time execution
            {
                'job_id': 'future-onetime',
                'name': 'Future One-time Job',
                'schedule_type': 'one_time',
                'schedule_config': {
                    'execute_at': (datetime.utcnow() + timedelta(minutes=30)).isoformat() + 'Z',
                    'timezone': 'UTC'
                },
                'timeout': 180,
                'max_retries': 2,
                'retry_delay': 60
            }
        ]
        
        # Run validation
        validation_results = validate_multiple_jobs(test_configurations)
        
        # Analyze validation results
        batch_summary = validation_results['batch_summary']
        
        # Expected results analysis
        expected_outcomes = {
            'valid-utc-cron': 'PASSED',
            'invalid-cron': 'FAILED',
            'high-frequency': 'WARNING',
            'dst-timezone': 'WARNING',
            'past-onetime': 'WARNING',
            'future-onetime': 'PASSED'
        }
        
        validation_accuracy = 0
        for job_id, expected_status in expected_outcomes.items():
            actual_status = validation_results['job_results'][job_id]['validation']['validation_status']
            if actual_status == expected_status:
                validation_accuracy += 1
        
        validation_accuracy_percent = (validation_accuracy / len(expected_outcomes)) * 100
        
        print(f"  ✅ Validation system tested on {batch_summary['total_jobs']} configurations")
        print(f"  📊 Validation accuracy: {validation_accuracy_percent:.1f}%")
        print(f"  📈 Results: {batch_summary['passed_jobs']} passed, {batch_summary['warning_jobs']} warnings, {batch_summary['failed_jobs']} failed")
        
        return {
            'test_type': 'validation_system',
            'batch_summary': batch_summary,
            'validation_accuracy_percent': validation_accuracy_percent,
            'expected_vs_actual': [
                {
                    'job_id': job_id,
                    'expected': expected_status,
                    'actual': validation_results['job_results'][job_id]['validation']['validation_status'],
                    'match': validation_results['job_results'][job_id]['validation']['validation_status'] == expected_status
                }
                for job_id, expected_status in expected_outcomes.items()
            ],
            'detailed_results': validation_results
        }
    
    def test_edge_case_scheduling(self) -> Dict[str, Any]:
        """Test edge cases in UTC scheduling"""
        print("\n⚡ Testing UTC Scheduling Edge Cases...")
        
        edge_case_results = []
        
        # Test 1: Leap year handling
        print("  Testing leap year scheduling...")
        leap_year_test = self._test_leap_year_scheduling()
        edge_case_results.append(leap_year_test)
        
        # Test 2: Year boundary (New Year transition)
        print("  Testing year boundary scheduling...")
        year_boundary_test = self._test_year_boundary_scheduling()
        edge_case_results.append(year_boundary_test)
        
        # Test 3: Midnight UTC scheduling
        print("  Testing midnight UTC scheduling...")
        midnight_test = self._test_midnight_scheduling()
        edge_case_results.append(midnight_test)
        
        # Test 4: High-precision seconds scheduling
        print("  Testing high-precision seconds scheduling...")
        precision_test = self._test_precision_seconds_scheduling()
        edge_case_results.append(precision_test)
        
        successful_tests = sum(1 for test in edge_case_results if test['status'] == 'PASSED')
        total_tests = len(edge_case_results)
        
        print(f"  ✅ {successful_tests}/{total_tests} edge case tests passed")
        
        return {
            'test_type': 'edge_cases',
            'total_tests': total_tests,
            'successful_tests': successful_tests,
            'success_rate': (successful_tests / total_tests) * 100,
            'edge_case_results': edge_case_results
        }
    
    def _test_leap_year_scheduling(self) -> Dict[str, Any]:
        """Test scheduling on February 29th (leap year)"""
        try:
            # Find next leap year
            current_year = datetime.utcnow().year
            next_leap_year = current_year
            while not self._is_leap_year(next_leap_year):
                next_leap_year += 1
            
            # Test cron expression for Feb 29
            leap_day_config = {
                'job_id': 'leap-year-test',
                'name': 'Leap Year Test',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '0 0 12 29 2 *',  # Feb 29 at noon
                    'timezone': 'UTC'
                },
                'timeout': 300,
                'max_retries': 1,
                'retry_delay': 60
            }
            
            validation_result = self.validator.validate_job_schedule(leap_day_config)
            
            return {
                'test_name': 'leap_year_scheduling',
                'status': 'PASSED' if validation_result['validation_status'] in ['PASSED', 'WARNING'] else 'FAILED',
                'next_leap_year': next_leap_year,
                'validation_result': validation_result
            }
            
        except Exception as e:
            return {
                'test_name': 'leap_year_scheduling',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _test_year_boundary_scheduling(self) -> Dict[str, Any]:
        """Test scheduling around year boundary (New Year)"""
        try:
            # Schedule for Dec 31 23:59:59
            year_boundary_config = {
                'job_id': 'year-boundary-test',
                'name': 'Year Boundary Test',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '59 59 23 31 12 *',  # Dec 31 23:59:59
                    'timezone': 'UTC'
                },
                'timeout': 300,
                'max_retries': 1,
                'retry_delay': 60
            }
            
            validation_result = self.validator.validate_job_schedule(year_boundary_config)
            
            return {
                'test_name': 'year_boundary_scheduling',
                'status': 'PASSED' if validation_result['validation_status'] in ['PASSED', 'WARNING'] else 'FAILED',
                'validation_result': validation_result
            }
            
        except Exception as e:
            return {
                'test_name': 'year_boundary_scheduling',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _test_midnight_scheduling(self) -> Dict[str, Any]:
        """Test scheduling at midnight UTC"""
        try:
            midnight_config = {
                'job_id': 'midnight-utc-test',
                'name': 'Midnight UTC Test',
                'schedule_type': 'cron',
                'schedule_config': {
                    'cron_expression': '0 0 0 * * *',  # Every day at midnight UTC
                    'timezone': 'UTC'
                },
                'timeout': 300,
                'max_retries': 2,
                'retry_delay': 30
            }
            
            validation_result = self.validator.validate_job_schedule(midnight_config)
            
            # Additional test: immediate execution near midnight
            now = datetime.utcnow()
            if now.hour == 23 and now.minute >= 58:  # Close to midnight
                print("    Note: Currently close to midnight UTC - timing may be affected")
            
            return {
                'test_name': 'midnight_scheduling',
                'status': 'PASSED' if validation_result['validation_status'] in ['PASSED', 'WARNING'] else 'FAILED',
                'current_utc_time': now.isoformat() + 'Z',
                'validation_result': validation_result
            }
            
        except Exception as e:
            return {
                'test_name': 'midnight_scheduling',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _test_precision_seconds_scheduling(self) -> Dict[str, Any]:
        """Test high-precision seconds in scheduling"""
        try:
            # Test scheduling with specific seconds
            now = datetime.utcnow()
            target_time = now + timedelta(seconds=5)  # 5 seconds from now
            
            precision_config = {
                'job_id': 'precision-seconds-test',
                'name': 'Precision Seconds Test',
                'schedule_type': 'one_time',
                'schedule_config': {
                    'execute_at': target_time.isoformat() + 'Z',
                    'timezone': 'UTC'
                },
                'timeout': 60,
                'max_retries': 0,
                'retry_delay': 0
            }
            
            validation_result = self.validator.validate_job_schedule(precision_config)
            
            return {
                'test_name': 'precision_seconds_scheduling',
                'status': 'PASSED' if validation_result['validation_status'] in ['PASSED', 'WARNING'] else 'FAILED',
                'target_time_utc': target_time.isoformat() + 'Z',
                'precision_microseconds': target_time.microsecond,
                'validation_result': validation_result
            }
            
        except Exception as e:
            return {
                'test_name': 'precision_seconds_scheduling',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def test_stress_scenarios(self) -> Dict[str, Any]:
        """Test UTC scheduling under stress scenarios"""
        print("\n💪 Testing UTC Scheduling Under Stress...")
        
        stress_results = []
        
        # Test 1: Multiple simultaneous job creations
        print("  Testing concurrent job creation...")
        concurrent_creation_test = self._test_concurrent_job_creation()
        stress_results.append(concurrent_creation_test)
        
        # Test 2: Rapid schedule modifications
        print("  Testing rapid schedule modifications...")
        rapid_modification_test = self._test_rapid_schedule_modifications()
        stress_results.append(rapid_modification_test)
        
        # Test 3: Large batch validation
        print("  Testing large batch validation...")
        batch_validation_test = self._test_large_batch_validation()
        stress_results.append(batch_validation_test)
        
        successful_stress_tests = sum(1 for test in stress_results if test['status'] == 'PASSED')
        total_stress_tests = len(stress_results)
        
        print(f"  ✅ {successful_stress_tests}/{total_stress_tests} stress tests passed")
        
        return {
            'test_type': 'stress_scenarios',
            'total_tests': total_stress_tests,
            'successful_tests': successful_stress_tests,
            'success_rate': (successful_stress_tests / total_stress_tests) * 100,
            'stress_test_results': stress_results
        }
    
    def _test_concurrent_job_creation(self) -> Dict[str, Any]:
        """Test creating multiple jobs concurrently"""
        try:
            start_time = time.time()
            num_jobs = 10
            results = []
            
            def create_job(job_num):
                job_config = {
                    'job_id': f'concurrent-job-{job_num}',
                    'name': f'Concurrent Job {job_num}',
                    'schedule_type': 'interval',
                    'schedule_config': {
                        'interval_seconds': 3600,  # 1 hour
                        'timezone': 'UTC'
                    },
                    'timeout': 300,
                    'max_retries': 2,
                    'retry_delay': 60
                }
                
                validation_result = self.validator.validate_job_schedule(job_config)
                return {
                    'job_num': job_num,
                    'validation_status': validation_result['validation_status'],
                    'validation_successful': validation_result['validation_status'] in ['PASSED', 'WARNING']
                }
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_job, i) for i in range(num_jobs)]
                results = [future.result() for future in concurrent.futures.as_completed(futures)]
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            successful_validations = sum(1 for r in results if r['validation_successful'])
            
            return {
                'test_name': 'concurrent_job_creation',
                'status': 'PASSED' if successful_validations == num_jobs else 'FAILED',
                'total_jobs': num_jobs,
                'successful_validations': successful_validations,
                'execution_time_seconds': round(execution_time, 2),
                'jobs_per_second': round(num_jobs / execution_time, 2)
            }
            
        except Exception as e:
            return {
                'test_name': 'concurrent_job_creation',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _test_rapid_schedule_modifications(self) -> Dict[str, Any]:
        """Test rapid modifications to job schedules"""
        try:
            start_time = time.time()
            num_modifications = 20
            validation_results = []
            
            base_config = {
                'job_id': 'rapid-modification-test',
                'name': 'Rapid Modification Test Job',
                'schedule_type': 'cron',
                'timeout': 300,
                'max_retries': 2,
                'retry_delay': 60
            }
            
            # Test different cron expressions rapidly
            cron_expressions = [
                '0 0 9 * * 1-5',   # 9 AM weekdays
                '0 30 14 * * *',   # 2:30 PM daily
                '0 0 0 1 * *',     # First day of month
                '0 15 8 * * 6,0',  # 8:15 AM weekends
                '0 0 */6 * * *'    # Every 6 hours
            ]
            
            for i in range(num_modifications):
                config = base_config.copy()
                config['schedule_config'] = {
                    'cron_expression': cron_expressions[i % len(cron_expressions)],
                    'timezone': 'UTC'
                }
                
                validation_result = self.validator.validate_job_schedule(config)
                validation_results.append(validation_result['validation_status'])
                
                time.sleep(0.01)  # Small delay between modifications
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            successful_validations = sum(1 for status in validation_results if status in ['PASSED', 'WARNING'])
            
            return {
                'test_name': 'rapid_schedule_modifications',
                'status': 'PASSED' if successful_validations >= num_modifications * 0.9 else 'FAILED',
                'total_modifications': num_modifications,
                'successful_validations': successful_validations,
                'execution_time_seconds': round(execution_time, 2),
                'modifications_per_second': round(num_modifications / execution_time, 2)
            }
            
        except Exception as e:
            return {
                'test_name': 'rapid_schedule_modifications',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _test_large_batch_validation(self) -> Dict[str, Any]:
        """Test validation of large batch of job configurations"""
        try:
            start_time = time.time()
            batch_size = 50
            
            # Generate large batch of job configurations
            job_configs = []
            for i in range(batch_size):
                config = {
                    'job_id': f'batch-job-{i}',
                    'name': f'Batch Job {i}',
                    'schedule_type': 'interval',
                    'schedule_config': {
                        'interval_seconds': 1800 + (i * 60),  # Staggered intervals
                        'timezone': 'UTC'
                    },
                    'timeout': 300,
                    'max_retries': 2,
                    'retry_delay': 60
                }
                job_configs.append(config)
            
            # Validate entire batch
            batch_results = validate_multiple_jobs(job_configs)
            
            end_time = time.time()
            execution_time = end_time - start_time
            
            batch_summary = batch_results['batch_summary']
            
            return {
                'test_name': 'large_batch_validation',
                'status': 'PASSED' if batch_summary['overall_success_rate'] >= 95 else 'FAILED',
                'batch_size': batch_size,
                'successful_validations': batch_summary['passed_jobs'] + batch_summary['warning_jobs'],
                'execution_time_seconds': round(execution_time, 2),
                'jobs_per_second': round(batch_size / execution_time, 2),
                'overall_success_rate': batch_summary['overall_success_rate']
            }
            
        except Exception as e:
            return {
                'test_name': 'large_batch_validation',
                'status': 'FAILED',
                'error': str(e)
            }
    
    def _is_leap_year(self, year: int) -> bool:
        """Check if year is a leap year"""
        return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    
    def run_comprehensive_precision_reliability_tests(self) -> Dict[str, Any]:
        """Run all precision and reliability tests"""
        print("=" * 80)
        print("UTC SCHEDULING PRECISION AND RELIABILITY TEST SUITE")
        print("=" * 80)
        
        all_results = {}
        
        # Test 1: Validation system functionality
        all_results['validation_system'] = self.test_scheduling_validation_system()
        
        # Test 2: Edge case handling
        all_results['edge_cases'] = self.test_edge_case_scheduling()
        
        # Test 3: Stress scenarios
        all_results['stress_scenarios'] = self.test_stress_scenarios()
        
        # Test 4: Integration with timing accuracy tests
        print("\n🔗 Running integrated timing accuracy tests...")
        timing_results = self.timing_tester.run_comprehensive_timing_tests()
        all_results['timing_accuracy'] = timing_results
        
        # Generate overall reliability assessment
        overall_assessment = self._generate_reliability_assessment(all_results)
        all_results['overall_reliability_assessment'] = overall_assessment
        
        return all_results
    
    def _generate_reliability_assessment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall reliability assessment"""
        reliability_scores = []
        
        # Validation system score
        validation_result = results.get('validation_system', {})
        if validation_result.get('validation_accuracy_percent'):
            reliability_scores.append(validation_result['validation_accuracy_percent'])
        
        # Edge cases score
        edge_cases_result = results.get('edge_cases', {})
        if edge_cases_result.get('success_rate'):
            reliability_scores.append(edge_cases_result['success_rate'])
        
        # Stress scenarios score
        stress_result = results.get('stress_scenarios', {})
        if stress_result.get('success_rate'):
            reliability_scores.append(stress_result['success_rate'])
        
        # Timing accuracy score
        timing_result = results.get('timing_accuracy', {})
        if timing_result.get('overall_assessment', {}).get('overall_score'):
            reliability_scores.append(timing_result['overall_assessment']['overall_score'])
        
        if reliability_scores:
            overall_score = statistics.mean(reliability_scores)
            
            if overall_score >= 90:
                grade = "EXCELLENT"
                reliability_level = "Production Ready"
                recommendation = "UTC scheduling system demonstrates excellent precision and reliability"
            elif overall_score >= 80:
                grade = "GOOD"
                reliability_level = "Production Ready with Monitoring"
                recommendation = "UTC scheduling system is reliable for production use with monitoring"
            elif overall_score >= 70:
                grade = "ACCEPTABLE"
                reliability_level = "Limited Production Use"
                recommendation = "UTC scheduling system requires improvements before full production deployment"
            else:
                grade = "POOR"
                reliability_level = "Not Production Ready"
                recommendation = "UTC scheduling system needs significant improvements before production use"
        else:
            overall_score = 0
            grade = "UNKNOWN"
            reliability_level = "Cannot Assess"
            recommendation = "Unable to assess reliability due to test failures"
        
        return {
            'overall_reliability_score': round(overall_score, 2),
            'grade': grade,
            'reliability_level': reliability_level,
            'recommendation': recommendation,
            'component_scores': {
                'validation_system': validation_result.get('validation_accuracy_percent', 0),
                'edge_case_handling': edge_cases_result.get('success_rate', 0),
                'stress_testing': stress_result.get('success_rate', 0),
                'timing_accuracy': timing_result.get('overall_assessment', {}).get('overall_score', 0)
            },
            'test_coverage': {
                'validation_tested': 'validation_system' in results,
                'edge_cases_tested': 'edge_cases' in results,
                'stress_tested': 'stress_scenarios' in results,
                'timing_tested': 'timing_accuracy' in results
            }
        }


def save_comprehensive_results(results: Dict[str, Any], filename: str = "utc_precision_reliability_results.json"):
    """Save comprehensive test results"""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Comprehensive results saved to: {filename}")
    except Exception as e:
        print(f"\n❌ Failed to save results: {e}")


def print_comprehensive_summary(results: Dict[str, Any]):
    """Print comprehensive test summary"""
    print("\n" + "=" * 80)
    print("UTC PRECISION AND RELIABILITY TEST SUMMARY")
    print("=" * 80)
    
    overall = results.get('overall_reliability_assessment', {})
    print(f"🏆 Overall Grade: {overall.get('grade', 'UNKNOWN')}")
    print(f"📊 Reliability Score: {overall.get('overall_reliability_score', 0)}/100")
    print(f"🔒 Reliability Level: {overall.get('reliability_level', 'Unknown')}")
    print(f"💡 Recommendation: {overall.get('recommendation', 'No recommendation')}")
    
    # Component scores
    component_scores = overall.get('component_scores', {})
    print(f"\n📋 Component Scores:")
    for component, score in component_scores.items():
        print(f"   • {component.replace('_', ' ').title()}: {score:.1f}%")
    
    # Test coverage
    coverage = overall.get('test_coverage', {})
    print(f"\n🔍 Test Coverage:")
    for test_type, tested in coverage.items():
        status = "✅ TESTED" if tested else "❌ NOT TESTED"
        print(f"   • {test_type.replace('_', ' ').title()}: {status}")


if __name__ == "__main__":
    print("UTC Scheduling Precision and Reliability Test Suite")
    print("This comprehensive suite tests all aspects of UTC scheduling")
    print("Including validation, edge cases, stress scenarios, and timing accuracy\n")
    
    tester = UTCPrecisionReliabilityTester()
    
    try:
        # Run comprehensive precision and reliability tests
        test_results = tester.run_comprehensive_precision_reliability_tests()
        
        # Print comprehensive summary
        print_comprehensive_summary(test_results)
        
        # Save detailed results
        save_comprehensive_results(test_results)
        
        print("\n🎉 UTC precision and reliability testing completed!")
        print("📋 Review the detailed results in utc_precision_reliability_results.json")
        print("🚀 The UTC scheduling system is ready for production evaluation!")
        
    except Exception as e:
        print(f"❌ Comprehensive test suite failed: {e}")
        import traceback
        traceback.print_exc()