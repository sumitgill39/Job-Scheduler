#!/usr/bin/env python3
"""
UTC Job Execution Timing Accuracy Test Suite
Tests the precision and reliability of UTC-based job scheduling
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any
import statistics
import json

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

from core.sql_job import SqlJob
from core.powershell_job import PowerShellJob
from core.execution_logger import ExecutionLogger
from core.job_base import JobStatus
from scheduler.job_scheduler import JobScheduler
import pytz


class UTCTimingAccuracyTester:
    """Test UTC job execution timing accuracy"""
    
    def __init__(self):
        self.test_results: List[Dict[str, Any]] = []
        self.scheduler = JobScheduler()
        self.utc = pytz.UTC
        
    def test_immediate_execution_accuracy(self, num_tests: int = 10) -> Dict[str, Any]:
        """Test accuracy of immediate job execution timing"""
        print(f"\n🔬 Testing immediate execution timing accuracy ({num_tests} tests)...")
        
        execution_delays = []
        precision_data = []
        
        for i in range(num_tests):
            # Create test job
            job = SqlJob(
                job_id=f'utc-timing-test-{i+1}',
                name=f'UTC Timing Test Job {i+1}',
                description='Testing UTC execution timing accuracy',
                sql_query="SELECT GETUTCDATE() as utc_time",
                connection_name='system',
                timeout=30,
                enabled=True
            )
            
            # Record expected execution time (now)
            expected_time = datetime.utcnow()
            
            print(f"  Test {i+1}: Executing at UTC {expected_time.isoformat()}Z")
            
            # Execute job and measure timing
            result = job.run()
            actual_time = datetime.utcnow()
            
            # Calculate delay
            delay_ms = (actual_time - expected_time).total_seconds() * 1000
            execution_delays.append(delay_ms)
            
            # Extract UTC timing metadata
            metadata = result.metadata or {}
            utc_timing = metadata.get('utc_timing', {})
            
            precision_data.append({
                'test_number': i + 1,
                'expected_utc': expected_time.isoformat() + 'Z',
                'actual_utc': actual_time.isoformat() + 'Z',
                'delay_ms': delay_ms,
                'job_status': result.status.value,
                'utc_timing_metadata': utc_timing
            })
            
            time.sleep(0.1)  # Small delay between tests
        
        # Calculate statistics
        avg_delay = statistics.mean(execution_delays)
        median_delay = statistics.median(execution_delays)
        max_delay = max(execution_delays)
        min_delay = min(execution_delays)
        std_dev = statistics.stdev(execution_delays) if len(execution_delays) > 1 else 0
        
        accuracy_result = {
            'test_type': 'immediate_execution',
            'num_tests': num_tests,
            'statistics': {
                'avg_delay_ms': round(avg_delay, 2),
                'median_delay_ms': round(median_delay, 2),
                'max_delay_ms': round(max_delay, 2),
                'min_delay_ms': round(min_delay, 2),
                'std_dev_ms': round(std_dev, 2)
            },
            'precision_assessment': self._assess_precision(execution_delays),
            'detailed_data': precision_data
        }
        
        print(f"  ✅ Average delay: {avg_delay:.2f}ms")
        print(f"  📊 Median delay: {median_delay:.2f}ms")
        print(f"  📈 Max delay: {max_delay:.2f}ms")
        print(f"  📉 Min delay: {min_delay:.2f}ms")
        print(f"  📏 Standard deviation: {std_dev:.2f}ms")
        
        return accuracy_result
    
    def test_scheduled_execution_accuracy(self, num_tests: int = 5) -> Dict[str, Any]:
        """Test accuracy of scheduled job execution timing"""
        print(f"\n⏰ Testing scheduled execution timing accuracy ({num_tests} tests)...")
        
        scheduled_results = []
        
        for i in range(num_tests):
            # Schedule job to run 3 seconds from now
            schedule_delay = 3
            expected_time = datetime.utcnow() + timedelta(seconds=schedule_delay)
            
            job = SqlJob(
                job_id=f'utc-scheduled-test-{i+1}',
                name=f'UTC Scheduled Test Job {i+1}',
                description=f'Testing UTC scheduled execution accuracy - {i+1}',
                sql_query=f"SELECT GETUTCDATE() as execution_time, '{expected_time.isoformat()}Z' as expected_time",
                connection_name='system',
                timeout=30,
                enabled=True
            )
            
            # Store expected time in job metadata for later comparison
            job.scheduled_time = expected_time
            
            print(f"  Test {i+1}: Scheduling for UTC {expected_time.isoformat()}Z")
            
            # Add job to scheduler with one-time schedule
            cron_expr = f"{expected_time.second} {expected_time.minute} {expected_time.hour} {expected_time.day} {expected_time.month} *"
            
            try:
                self.scheduler.add_job(
                    job=job,
                    schedule_type='cron',
                    cron_expression=cron_expr,
                    timezone='UTC'
                )
                
                # Wait for job to execute (with some buffer)
                wait_time = schedule_delay + 2
                print(f"    Waiting {wait_time}s for execution...")
                time.sleep(wait_time)
                
                # Check execution results
                history = job.get_execution_history(1)
                if history:
                    result = history[0]
                    actual_time = result.start_time
                    
                    # Calculate scheduling accuracy
                    delay_ms = (actual_time - expected_time).total_seconds() * 1000
                    
                    scheduled_results.append({
                        'test_number': i + 1,
                        'expected_utc': expected_time.isoformat() + 'Z',
                        'actual_utc': actual_time.isoformat() + 'Z',
                        'scheduling_delay_ms': round(delay_ms, 2),
                        'job_status': result.status.value,
                        'cron_expression': cron_expr
                    })
                    
                    print(f"    ✅ Executed at {actual_time.isoformat()}Z (delay: {delay_ms:.2f}ms)")
                else:
                    scheduled_results.append({
                        'test_number': i + 1,
                        'expected_utc': expected_time.isoformat() + 'Z',
                        'actual_utc': None,
                        'scheduling_delay_ms': None,
                        'job_status': 'not_executed',
                        'cron_expression': cron_expr
                    })
                    print(f"    ❌ Job did not execute as scheduled")
                
                # Remove job from scheduler
                self.scheduler.remove_job(job.job_id)
                
            except Exception as e:
                print(f"    ❌ Scheduling error: {e}")
                scheduled_results.append({
                    'test_number': i + 1,
                    'expected_utc': expected_time.isoformat() + 'Z',
                    'error': str(e),
                    'job_status': 'scheduling_failed'
                })
        
        # Calculate scheduling accuracy statistics
        valid_delays = [r['scheduling_delay_ms'] for r in scheduled_results if r.get('scheduling_delay_ms') is not None]
        
        if valid_delays:
            scheduling_stats = {
                'successful_executions': len(valid_delays),
                'total_tests': num_tests,
                'success_rate': (len(valid_delays) / num_tests) * 100,
                'avg_delay_ms': round(statistics.mean(valid_delays), 2),
                'median_delay_ms': round(statistics.median(valid_delays), 2),
                'max_delay_ms': round(max(valid_delays), 2),
                'min_delay_ms': round(min(valid_delays), 2),
                'std_dev_ms': round(statistics.stdev(valid_delays), 2) if len(valid_delays) > 1 else 0
            }
        else:
            scheduling_stats = {
                'successful_executions': 0,
                'total_tests': num_tests,
                'success_rate': 0,
                'error': 'No successful scheduled executions'
            }
        
        return {
            'test_type': 'scheduled_execution',
            'num_tests': num_tests,
            'statistics': scheduling_stats,
            'detailed_results': scheduled_results
        }
    
    def test_concurrent_execution_accuracy(self, num_concurrent: int = 5) -> Dict[str, Any]:
        """Test UTC timing accuracy under concurrent job execution"""
        print(f"\n🔄 Testing concurrent execution timing accuracy ({num_concurrent} jobs)...")
        
        concurrent_results = []
        threads = []
        results_lock = threading.Lock()
        
        def execute_concurrent_job(job_num: int):
            """Execute a job concurrently"""
            job = SqlJob(
                job_id=f'utc-concurrent-test-{job_num}',
                name=f'UTC Concurrent Test Job {job_num}',
                description=f'Testing UTC concurrent execution accuracy - {job_num}',
                sql_query=f"SELECT GETUTCDATE() as utc_time, {job_num} as job_number",
                connection_name='system',
                timeout=30,
                enabled=True
            )
            
            start_time = datetime.utcnow()
            result = job.run()
            end_time = datetime.utcnow()
            
            execution_time = (end_time - start_time).total_seconds() * 1000
            
            with results_lock:
                concurrent_results.append({
                    'job_number': job_num,
                    'start_utc': start_time.isoformat() + 'Z',
                    'end_utc': end_time.isoformat() + 'Z',
                    'execution_time_ms': round(execution_time, 2),
                    'job_status': result.status.value
                })
        
        # Start all concurrent jobs at the same time
        execution_start = datetime.utcnow()
        print(f"  Starting {num_concurrent} concurrent jobs at UTC {execution_start.isoformat()}Z")
        
        for i in range(num_concurrent):
            thread = threading.Thread(target=execute_concurrent_job, args=(i+1,))
            threads.append(thread)
            thread.start()
        
        # Wait for all jobs to complete
        for thread in threads:
            thread.join()
        
        execution_end = datetime.utcnow()
        total_time = (execution_end - execution_start).total_seconds()
        
        # Analyze concurrent execution results
        execution_times = [r['execution_time_ms'] for r in concurrent_results]
        successful_jobs = [r for r in concurrent_results if r['job_status'] == 'success']
        
        concurrent_stats = {
            'total_jobs': num_concurrent,
            'successful_jobs': len(successful_jobs),
            'success_rate': (len(successful_jobs) / num_concurrent) * 100,
            'total_execution_time_seconds': round(total_time, 2),
            'avg_job_execution_ms': round(statistics.mean(execution_times), 2),
            'median_job_execution_ms': round(statistics.median(execution_times), 2),
            'max_job_execution_ms': round(max(execution_times), 2),
            'min_job_execution_ms': round(min(execution_times), 2)
        }
        
        print(f"  ✅ {len(successful_jobs)}/{num_concurrent} jobs completed successfully")
        print(f"  ⏱️  Total execution time: {total_time:.2f}s")
        print(f"  📊 Average job execution time: {concurrent_stats['avg_job_execution_ms']:.2f}ms")
        
        return {
            'test_type': 'concurrent_execution',
            'num_concurrent': num_concurrent,
            'statistics': concurrent_stats,
            'detailed_results': concurrent_results
        }
    
    def _assess_precision(self, delays: List[float]) -> Dict[str, Any]:
        """Assess timing precision based on delay statistics"""
        avg_delay = statistics.mean(delays)
        max_delay = max(delays)
        
        if max_delay <= 50:  # Within 50ms
            precision_grade = "EXCELLENT"
            precision_score = 95
        elif max_delay <= 100:  # Within 100ms
            precision_grade = "VERY_GOOD"
            precision_score = 85
        elif max_delay <= 250:  # Within 250ms
            precision_grade = "GOOD"
            precision_score = 75
        elif max_delay <= 500:  # Within 500ms
            precision_grade = "ACCEPTABLE"
            precision_score = 65
        elif max_delay <= 1000:  # Within 1s
            precision_grade = "POOR"
            precision_score = 50
        else:
            precision_grade = "UNACCEPTABLE"
            precision_score = 25
        
        return {
            'grade': precision_grade,
            'score': precision_score,
            'assessment': f"Maximum delay: {max_delay:.2f}ms, Average: {avg_delay:.2f}ms"
        }
    
    def run_comprehensive_timing_tests(self) -> Dict[str, Any]:
        """Run all UTC timing accuracy tests"""
        print("=" * 80)
        print("UTC JOB EXECUTION TIMING ACCURACY TEST SUITE")
        print("=" * 80)
        
        all_results = {}
        
        # Test 1: Immediate execution accuracy
        all_results['immediate_execution'] = self.test_immediate_execution_accuracy(10)
        
        # Test 2: Scheduled execution accuracy
        all_results['scheduled_execution'] = self.test_scheduled_execution_accuracy(3)
        
        # Test 3: Concurrent execution accuracy
        all_results['concurrent_execution'] = self.test_concurrent_execution_accuracy(3)
        
        # Generate overall assessment
        overall_assessment = self._generate_overall_assessment(all_results)
        all_results['overall_assessment'] = overall_assessment
        
        return all_results
    
    def _generate_overall_assessment(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate overall timing accuracy assessment"""
        assessments = []
        
        # Assess immediate execution
        immediate = results.get('immediate_execution', {})
        if immediate.get('precision_assessment'):
            assessments.append(immediate['precision_assessment']['score'])
        
        # Assess scheduled execution
        scheduled = results.get('scheduled_execution', {})
        if scheduled.get('statistics', {}).get('success_rate'):
            success_rate = scheduled['statistics']['success_rate']
            if success_rate >= 90:
                assessments.append(90)
            elif success_rate >= 75:
                assessments.append(75)
            elif success_rate >= 50:
                assessments.append(60)
            else:
                assessments.append(30)
        
        # Assess concurrent execution
        concurrent = results.get('concurrent_execution', {})
        if concurrent.get('statistics', {}).get('success_rate'):
            success_rate = concurrent['statistics']['success_rate']
            if success_rate >= 95:
                assessments.append(85)
            elif success_rate >= 80:
                assessments.append(75)
            else:
                assessments.append(50)
        
        if assessments:
            overall_score = statistics.mean(assessments)
            
            if overall_score >= 85:
                grade = "EXCELLENT"
                recommendation = "UTC timing accuracy is excellent for production use"
            elif overall_score >= 75:
                grade = "GOOD"
                recommendation = "UTC timing accuracy is suitable for most production scenarios"
            elif overall_score >= 60:
                grade = "ACCEPTABLE"
                recommendation = "UTC timing accuracy needs monitoring in production"
            else:
                grade = "POOR"
                recommendation = "UTC timing accuracy requires improvement before production use"
        else:
            overall_score = 0
            grade = "UNKNOWN"
            recommendation = "Unable to assess timing accuracy due to test failures"
        
        return {
            'overall_score': round(overall_score, 2),
            'grade': grade,
            'recommendation': recommendation,
            'test_summary': {
                'immediate_execution_tested': 'immediate_execution' in results,
                'scheduled_execution_tested': 'scheduled_execution' in results,
                'concurrent_execution_tested': 'concurrent_execution' in results
            }
        }


def save_test_results(results: Dict[str, Any], filename: str = "utc_timing_test_results.json"):
    """Save test results to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n💾 Test results saved to: {filename}")
    except Exception as e:
        print(f"\n❌ Failed to save results: {e}")


def print_test_summary(results: Dict[str, Any]):
    """Print comprehensive test summary"""
    print("\n" + "=" * 80)
    print("UTC TIMING ACCURACY TEST SUMMARY")
    print("=" * 80)
    
    overall = results.get('overall_assessment', {})
    print(f"🏆 Overall Grade: {overall.get('grade', 'UNKNOWN')}")
    print(f"📊 Overall Score: {overall.get('overall_score', 0)}/100")
    print(f"💡 Recommendation: {overall.get('recommendation', 'No recommendation')}")
    
    # Immediate execution summary
    immediate = results.get('immediate_execution', {})
    if immediate:
        print(f"\n⚡ Immediate Execution:")
        stats = immediate.get('statistics', {})
        precision = immediate.get('precision_assessment', {})
        print(f"   • Average delay: {stats.get('avg_delay_ms', 0)}ms")
        print(f"   • Precision grade: {precision.get('grade', 'UNKNOWN')}")
    
    # Scheduled execution summary
    scheduled = results.get('scheduled_execution', {})
    if scheduled:
        print(f"\n⏰ Scheduled Execution:")
        stats = scheduled.get('statistics', {})
        print(f"   • Success rate: {stats.get('success_rate', 0)}%")
        if stats.get('avg_delay_ms') is not None:
            print(f"   • Average scheduling delay: {stats.get('avg_delay_ms', 0)}ms")
    
    # Concurrent execution summary
    concurrent = results.get('concurrent_execution', {})
    if concurrent:
        print(f"\n🔄 Concurrent Execution:")
        stats = concurrent.get('statistics', {})
        print(f"   • Success rate: {stats.get('success_rate', 0)}%")
        print(f"   • Average execution time: {stats.get('avg_job_execution_ms', 0)}ms")


if __name__ == "__main__":
    print("UTC Job Execution Timing Accuracy Test Suite")
    print("This comprehensive test will validate UTC scheduling precision")
    print("Note: Some tests may take several seconds to complete\n")
    
    tester = UTCTimingAccuracyTester()
    
    try:
        # Run comprehensive timing tests
        test_results = tester.run_comprehensive_timing_tests()
        
        # Print summary
        print_test_summary(test_results)
        
        # Save detailed results
        save_test_results(test_results)
        
        print("\n🎉 UTC timing accuracy testing completed!")
        print("📋 Review the detailed results in utc_timing_test_results.json")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()