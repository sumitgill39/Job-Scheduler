"""
UTC Scheduling Validation System
Validates and ensures proper UTC-based job scheduling
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from croniter import croniter
import pytz
import re
from enum import Enum


class ValidationLevel(Enum):
    """Validation severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationResult:
    """Represents a validation result"""
    
    def __init__(self, level: ValidationLevel, message: str, details: Dict[str, Any] = None):
        self.level = level
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'level': self.level.value,
            'message': self.message,
            'details': self.details,
            'timestamp': self.timestamp.isoformat() + 'Z'
        }


class UTCSchedulingValidator:
    """Comprehensive UTC scheduling validation system"""
    
    def __init__(self):
        self.utc = pytz.UTC
        self.validation_results: List[ValidationResult] = []
    
    def validate_job_schedule(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive validation of job schedule configuration
        
        Args:
            job_data: Job configuration dictionary
            
        Returns:
            Dict containing validation results and recommendations
        """
        self.validation_results.clear()
        
        # Extract scheduling parameters
        schedule_type = job_data.get('schedule_type', '')
        schedule_config = job_data.get('schedule_config', {})
        timezone = schedule_config.get('timezone', 'UTC')
        
        # Validate schedule type
        self._validate_schedule_type(schedule_type, schedule_config)
        
        # Validate timezone configuration
        self._validate_timezone_config(timezone)
        
        # Validate specific schedule configurations
        if schedule_type == 'cron':
            self._validate_cron_schedule(schedule_config)
        elif schedule_type == 'interval':
            self._validate_interval_schedule(schedule_config)
        elif schedule_type == 'one_time':
            self._validate_onetime_schedule(schedule_config)
        
        # Validate job execution window
        self._validate_execution_window(job_data)
        
        # Generate validation summary
        return self._generate_validation_summary()
    
    def _validate_schedule_type(self, schedule_type: str, schedule_config: Dict[str, Any]):
        """Validate schedule type configuration"""
        valid_types = ['cron', 'interval', 'one_time']
        
        if not schedule_type:
            self.validation_results.append(ValidationResult(
                ValidationLevel.CRITICAL,
                "Schedule type is required but not specified",
                {'valid_types': valid_types}
            ))
            return
        
        if schedule_type not in valid_types:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid schedule type: {schedule_type}",
                {'provided_type': schedule_type, 'valid_types': valid_types}
            ))
        else:
            self.validation_results.append(ValidationResult(
                ValidationLevel.INFO,
                f"Schedule type '{schedule_type}' is valid"
            ))
    
    def _validate_timezone_config(self, timezone: str):
        """Validate timezone configuration"""
        if not timezone:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING,
                "No timezone specified, defaulting to UTC"
            ))
            return
        
        try:
            tz = pytz.timezone(timezone)
            
            if timezone == 'UTC':
                self.validation_results.append(ValidationResult(
                    ValidationLevel.INFO,
                    "Using UTC timezone - excellent choice for global consistency",
                    {'timezone': timezone}
                ))
            else:
                # Check if timezone has DST transitions
                now = datetime.now(tz)
                dst_info = self._check_dst_transitions(tz, now)
                
                if dst_info['has_dst']:
                    self.validation_results.append(ValidationResult(
                        ValidationLevel.WARNING,
                        f"Timezone '{timezone}' has DST transitions which may affect scheduling",
                        {
                            'timezone': timezone,
                            'dst_info': dst_info,
                            'recommendation': 'Consider using UTC for consistent scheduling'
                        }
                    ))
                else:
                    self.validation_results.append(ValidationResult(
                        ValidationLevel.INFO,
                        f"Timezone '{timezone}' is valid and has no DST transitions",
                        {'timezone': timezone}
                    ))
                    
        except Exception as e:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid timezone: {timezone}",
                {'timezone': timezone, 'error': str(e)}
            ))
    
    def _validate_cron_schedule(self, schedule_config: Dict[str, Any]):
        """Validate cron schedule configuration"""
        cron_expression = schedule_config.get('cron_expression', '')
        
        if not cron_expression:
            self.validation_results.append(ValidationResult(
                ValidationLevel.CRITICAL,
                "Cron expression is required for cron schedule type"
            ))
            return
        
        # Validate cron expression format (expecting 6 parts: second minute hour day month day_of_week)
        parts = cron_expression.strip().split()
        
        if len(parts) != 6:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Cron expression must have 6 parts (second minute hour day month day_of_week), got {len(parts)}",
                {
                    'expression': cron_expression,
                    'parts_found': len(parts),
                    'expected_format': 'second minute hour day month day_of_week'
                }
            ))
            return
        
        # Validate each part of cron expression
        cron_validations = self._validate_cron_parts(parts)
        self.validation_results.extend(cron_validations)
        
        # Test cron expression with croniter
        try:
            # Convert 6-part to 5-part for croniter (remove seconds)
            croniter_expr = ' '.join(parts[1:])
            cron = croniter(croniter_expr, datetime.utcnow())
            
            # Get next few execution times
            next_runs = []
            for _ in range(5):
                next_runs.append(cron.get_next(datetime))
            
            self.validation_results.append(ValidationResult(
                ValidationLevel.INFO,
                "Cron expression is valid and parseable",
                {
                    'expression': cron_expression,
                    'next_5_executions_utc': [dt.isoformat() + 'Z' for dt in next_runs]
                }
            ))
            
            # Validate execution frequency
            self._validate_execution_frequency(next_runs)
            
        except Exception as e:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid cron expression: {cron_expression}",
                {'expression': cron_expression, 'error': str(e)}
            ))
    
    def _validate_cron_parts(self, parts: List[str]) -> List[ValidationResult]:
        """Validate individual parts of cron expression"""
        validations = []
        part_names = ['second', 'minute', 'hour', 'day', 'month', 'day_of_week']
        ranges = [(0, 59), (0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
        
        for i, (part, name, (min_val, max_val)) in enumerate(zip(parts, part_names, ranges)):
            try:
                if part == '*':
                    continue
                elif '-' in part:
                    # Range validation
                    start, end = part.split('-')
                    start_int, end_int = int(start), int(end)
                    if not (min_val <= start_int <= max_val and min_val <= end_int <= max_val):
                        validations.append(ValidationResult(
                            ValidationLevel.ERROR,
                            f"Invalid range in {name}: {part} (valid range: {min_val}-{max_val})"
                        ))
                elif '/' in part:
                    # Step validation
                    base, step = part.split('/')
                    if base != '*':
                        base_int = int(base)
                        if not (min_val <= base_int <= max_val):
                            validations.append(ValidationResult(
                                ValidationLevel.ERROR,
                                f"Invalid step base in {name}: {base} (valid range: {min_val}-{max_val})"
                            ))
                elif ',' in part:
                    # List validation
                    values = [int(v.strip()) for v in part.split(',')]
                    for val in values:
                        if not (min_val <= val <= max_val):
                            validations.append(ValidationResult(
                                ValidationLevel.ERROR,
                                f"Invalid value in {name} list: {val} (valid range: {min_val}-{max_val})"
                            ))
                else:
                    # Single value validation
                    val = int(part)
                    if not (min_val <= val <= max_val):
                        validations.append(ValidationResult(
                            ValidationLevel.ERROR,
                            f"Invalid {name} value: {val} (valid range: {min_val}-{max_val})"
                        ))
            except ValueError:
                validations.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Invalid {name} format: {part}"
                ))
        
        return validations
    
    def _validate_interval_schedule(self, schedule_config: Dict[str, Any]):
        """Validate interval schedule configuration"""
        interval_seconds = schedule_config.get('interval_seconds')
        
        if interval_seconds is None:
            self.validation_results.append(ValidationResult(
                ValidationLevel.CRITICAL,
                "Interval seconds is required for interval schedule type"
            ))
            return
        
        try:
            interval_seconds = int(interval_seconds)
            
            if interval_seconds <= 0:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.ERROR,
                    f"Interval must be positive, got {interval_seconds}"
                ))
            elif interval_seconds < 60:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Very short interval ({interval_seconds}s) may cause high system load",
                    {'interval_seconds': interval_seconds, 'recommendation': 'Consider intervals >= 60s'}
                ))
            elif interval_seconds > 86400 * 7:  # 1 week
                self.validation_results.append(ValidationResult(
                    ValidationLevel.INFO,
                    f"Long interval ({interval_seconds}s = {interval_seconds/86400:.1f} days) detected",
                    {'interval_seconds': interval_seconds}
                ))
            else:
                self.validation_results.append(ValidationResult(
                    ValidationLevel.INFO,
                    f"Interval configuration is valid: {interval_seconds}s ({interval_seconds/60:.1f} minutes)",
                    {'interval_seconds': interval_seconds}
                ))
                
        except (ValueError, TypeError):
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid interval seconds: {interval_seconds} (must be a positive integer)"
            ))
    
    def _validate_onetime_schedule(self, schedule_config: Dict[str, Any]):
        """Validate one-time schedule configuration"""
        execute_at = schedule_config.get('execute_at')
        
        if not execute_at:
            self.validation_results.append(ValidationResult(
                ValidationLevel.CRITICAL,
                "Execute time is required for one-time schedule type"
            ))
            return
        
        try:
            # Parse execute_at time
            if isinstance(execute_at, str):
                # Try to parse ISO format
                exec_time = datetime.fromisoformat(execute_at.replace('Z', '+00:00'))
            else:
                exec_time = execute_at
            
            # Ensure timezone awareness
            if exec_time.tzinfo is None:
                exec_time = self.utc.localize(exec_time)
            
            now_utc = datetime.now(self.utc)
            
            if exec_time <= now_utc:
                time_diff = now_utc - exec_time
                self.validation_results.append(ValidationResult(
                    ValidationLevel.WARNING,
                    f"Scheduled execution time is in the past ({time_diff.total_seconds():.1f}s ago)",
                    {
                        'scheduled_utc': exec_time.isoformat(),
                        'current_utc': now_utc.isoformat(),
                        'recommendation': 'Update to a future time'
                    }
                ))
            else:
                time_until = exec_time - now_utc
                self.validation_results.append(ValidationResult(
                    ValidationLevel.INFO,
                    f"One-time execution scheduled for {exec_time.isoformat()} (in {time_until.total_seconds():.1f}s)",
                    {
                        'scheduled_utc': exec_time.isoformat(),
                        'time_until_execution_seconds': time_until.total_seconds()
                    }
                ))
                
        except Exception as e:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid execute_at time format: {execute_at}",
                {'execute_at': str(execute_at), 'error': str(e)}
            ))
    
    def _validate_execution_window(self, job_data: Dict[str, Any]):
        """Validate job execution window and constraints"""
        timeout = job_data.get('timeout', 300)
        max_retries = job_data.get('max_retries', 3)
        retry_delay = job_data.get('retry_delay', 60)
        
        # Validate timeout
        if timeout <= 0:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid timeout: {timeout} (must be positive)"
            ))
        elif timeout > 3600:  # 1 hour
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING,
                f"Very long timeout: {timeout}s ({timeout/60:.1f} minutes)",
                {'recommendation': 'Consider shorter timeouts to prevent hanging jobs'}
            ))
        
        # Validate retry configuration
        if max_retries < 0:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid max_retries: {max_retries} (must be non-negative)"
            ))
        elif max_retries > 10:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING,
                f"High retry count: {max_retries}",
                {'recommendation': 'Consider lower retry counts to prevent excessive failures'}
            ))
        
        if retry_delay <= 0:
            self.validation_results.append(ValidationResult(
                ValidationLevel.ERROR,
                f"Invalid retry_delay: {retry_delay} (must be positive)"
            ))
    
    def _validate_execution_frequency(self, next_runs: List[datetime]):
        """Validate execution frequency to prevent system overload"""
        if len(next_runs) < 2:
            return
        
        intervals = []
        for i in range(1, len(next_runs)):
            interval = (next_runs[i] - next_runs[i-1]).total_seconds()
            intervals.append(interval)
        
        min_interval = min(intervals)
        avg_interval = sum(intervals) / len(intervals)
        
        if min_interval < 30:
            self.validation_results.append(ValidationResult(
                ValidationLevel.WARNING,
                f"Very frequent execution detected (minimum {min_interval}s between runs)",
                {
                    'min_interval_seconds': min_interval,
                    'avg_interval_seconds': avg_interval,
                    'recommendation': 'Consider reducing execution frequency to prevent system overload'
                }
            ))
        elif min_interval < 60:
            self.validation_results.append(ValidationResult(
                ValidationLevel.INFO,
                f"Frequent execution detected (minimum {min_interval}s between runs)",
                {
                    'min_interval_seconds': min_interval,
                    'avg_interval_seconds': avg_interval
                }
            ))
    
    def _check_dst_transitions(self, tz, reference_time: datetime) -> Dict[str, Any]:
        """Check for DST transitions in timezone"""
        try:
            # Check next 12 months for DST transitions
            transitions = []
            current = reference_time
            
            for _ in range(365):  # Check daily for a year
                current += timedelta(days=1)
                if current.dst() != (current - timedelta(days=1)).dst():
                    transitions.append({
                        'date': current.date().isoformat(),
                        'type': 'spring_forward' if current.dst() > (current - timedelta(days=1)).dst() else 'fall_back'
                    })
            
            return {
                'has_dst': len(transitions) > 0,
                'transitions_next_year': transitions[:10],  # Limit to first 10
                'total_transitions': len(transitions)
            }
        except:
            return {'has_dst': False, 'error': 'Could not determine DST info'}
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """Generate comprehensive validation summary"""
        # Count results by level
        level_counts = {level.value: 0 for level in ValidationLevel}
        for result in self.validation_results:
            level_counts[result.level.value] += 1
        
        # Determine overall validation status
        if level_counts['critical'] > 0:
            overall_status = 'FAILED'
            overall_message = 'Critical validation errors prevent job scheduling'
        elif level_counts['error'] > 0:
            overall_status = 'FAILED'
            overall_message = 'Validation errors must be fixed before scheduling'
        elif level_counts['warning'] > 0:
            overall_status = 'WARNING'
            overall_message = 'Job can be scheduled but warnings should be reviewed'
        else:
            overall_status = 'PASSED'
            overall_message = 'All validations passed successfully'
        
        return {
            'validation_status': overall_status,
            'overall_message': overall_message,
            'summary': {
                'total_validations': len(self.validation_results),
                'critical_issues': level_counts['critical'],
                'errors': level_counts['error'],
                'warnings': level_counts['warning'],
                'info_messages': level_counts['info']
            },
            'validation_results': [result.to_dict() for result in self.validation_results],
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations based on validation results"""
        recommendations = []
        
        # Check for timezone recommendations
        has_non_utc = any(
            'timezone' in result.details and result.details['timezone'] != 'UTC'
            for result in self.validation_results
            if result.details
        )
        
        if has_non_utc:
            recommendations.append("Consider using UTC timezone for global consistency and to avoid DST complications")
        
        # Check for frequency recommendations
        has_frequency_warning = any(
            'frequent execution' in result.message.lower()
            for result in self.validation_results
        )
        
        if has_frequency_warning:
            recommendations.append("Review execution frequency to ensure optimal system performance")
        
        # Check for timeout recommendations
        has_timeout_warning = any(
            'timeout' in result.message.lower()
            for result in self.validation_results
        )
        
        if has_timeout_warning:
            recommendations.append("Review timeout settings to balance job completion vs system responsiveness")
        
        return recommendations


def validate_multiple_jobs(jobs_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate multiple job configurations"""
    validator = UTCSchedulingValidator()
    results = {}
    
    for i, job_data in enumerate(jobs_data):
        job_id = job_data.get('job_id', f'job_{i+1}')
        job_name = job_data.get('name', f'Job {i+1}')
        
        validation_result = validator.validate_job_schedule(job_data)
        results[job_id] = {
            'job_name': job_name,
            'validation': validation_result
        }
    
    # Generate batch summary
    total_jobs = len(jobs_data)
    passed_jobs = sum(1 for r in results.values() if r['validation']['validation_status'] == 'PASSED')
    warning_jobs = sum(1 for r in results.values() if r['validation']['validation_status'] == 'WARNING')
    failed_jobs = sum(1 for r in results.values() if r['validation']['validation_status'] == 'FAILED')
    
    return {
        'batch_summary': {
            'total_jobs': total_jobs,
            'passed_jobs': passed_jobs,
            'warning_jobs': warning_jobs,
            'failed_jobs': failed_jobs,
            'overall_success_rate': (passed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        },
        'job_results': results
    }


if __name__ == "__main__":
    # Test the validator with sample job configurations
    test_jobs = [
        {
            'job_id': 'test-cron-utc',
            'name': 'Test Cron Job UTC',
            'schedule_type': 'cron',
            'schedule_config': {
                'cron_expression': '0 30 9 * * 1-5',  # 9:30 AM weekdays
                'timezone': 'UTC'
            },
            'timeout': 300,
            'max_retries': 3,
            'retry_delay': 60
        },
        {
            'job_id': 'test-interval',
            'name': 'Test Interval Job',
            'schedule_type': 'interval',
            'schedule_config': {
                'interval_seconds': 1800,  # 30 minutes
                'timezone': 'UTC'
            },
            'timeout': 600,
            'max_retries': 2,
            'retry_delay': 120
        },
        {
            'job_id': 'test-onetime',
            'name': 'Test One-time Job',
            'schedule_type': 'one_time',
            'schedule_config': {
                'execute_at': (datetime.utcnow() + timedelta(hours=1)).isoformat() + 'Z',
                'timezone': 'UTC'
            },
            'timeout': 180,
            'max_retries': 1,
            'retry_delay': 30
        }
    ]
    
    print("UTC Scheduling Validation System Test")
    print("=" * 50)
    
    validation_results = validate_multiple_jobs(test_jobs)
    
    # Print batch summary
    batch = validation_results['batch_summary']
    print(f"Total Jobs: {batch['total_jobs']}")
    print(f"Passed: {batch['passed_jobs']}")
    print(f"Warnings: {batch['warning_jobs']}")
    print(f"Failed: {batch['failed_jobs']}")
    print(f"Success Rate: {batch['overall_success_rate']:.1f}%")
    
    # Print individual results
    for job_id, result in validation_results['job_results'].items():
        print(f"\n{result['job_name']} ({job_id}):")
        print(f"  Status: {result['validation']['validation_status']}")
        print(f"  Message: {result['validation']['overall_message']}")