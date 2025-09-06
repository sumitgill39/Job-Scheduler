"""
Individual job execution logging system
Creates detailed logs for each job execution with comprehensive step tracking
"""

import os
from datetime import datetime, timezone
from typing import Dict, Optional, Any, List
from pathlib import Path

from .data_models import JobDefinition, JobExecutionResult, StepResult, StepConfiguration
from utils.logger import get_logger


class JobLogger:
    """Detailed logger for individual job executions"""
    
    def __init__(self, job_id: str, execution_id: str, job_name: str, timezone_name: str):
        self.job_id = job_id
        self.execution_id = execution_id
        self.job_name = job_name
        self.timezone_name = timezone_name
        self.start_time = datetime.now(timezone.utc)
        
        # Create job detail log directory
        tz_dir = timezone_name.replace('/', '_').replace('\\', '_')
        self.log_dir = Path("logs/timezones") / tz_dir / "job_details"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique log file for this execution
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        safe_job_name = "".join(c for c in (job_name or "UnknownJob") if c.isalnum() or c in ('-', '_')).rstrip()[:30]
        execution_suffix = execution_id[:8] if execution_id else "unknown"
        self.log_file = self.log_dir / f"{safe_job_name}_{timestamp}_{execution_suffix}.log"
        
        # Initialize log file
        self._write_header()
        
        self.system_logger = get_logger(f"JobLogger.{job_id}")
        self.system_logger.info(f"Job logger created: {self.log_file}")
    
    def _write_header(self):
        """Write log file header"""
        header = f"""{'=' * 80}
JOB EXECUTION LOG
{'=' * 80}
Job ID: {self.job_id or 'Unknown'}
Job Name: {self.job_name or 'Unknown Job'}
Execution ID: {self.execution_id or 'unknown'}
Timezone: {self.timezone_name or 'UTC'}
Started: {self.start_time.isoformat()}
Log File: {self.log_file.name}
{'=' * 80}

"""
        self._write_to_file(header)
    
    def _write_to_file(self, content: str):
        """Write content to log file"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(content)
                f.flush()
        except Exception as e:
            self.system_logger.error(f"Failed to write to job log file {self.log_file}: {str(e)}")
    
    def _get_timestamp(self) -> str:
        """Get formatted timestamp"""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
    
    def log_execution_start(self, job_definition: JobDefinition):
        """Log job execution start with complete job details"""
        content = f"""
[{self._get_timestamp()}] JOB EXECUTION STARTED
{'=' * 50}

JOB CONFIGURATION:
------------------
Name: {job_definition.job_name}
Description: {job_definition.description}
Timezone: {job_definition.timezone}
Enabled: {job_definition.enabled}
Priority: {job_definition.priority}
Max Retries: {job_definition.max_retries}
Timeout: {job_definition.timeout_seconds} seconds
Tags: {', '.join(job_definition.tags) if job_definition.tags else 'None'}
Created By: {job_definition.created_by or 'System'}
Created At: {job_definition.created_at.isoformat() if job_definition.created_at else 'N/A'}

EXECUTION STEPS:
----------------
"""
        
        for i, step in enumerate(job_definition.steps, 1):
            content += f"""Step {i}: {step.step_name}
  ID: {step.step_id}
  Type: {step.step_type}
  Timeout: {step.timeout or 'Default'} seconds
  Continue on Failure: {step.continue_on_failure}
  Retry Count: {step.retry_count}
  Configuration: {step.config}

"""
        
        if job_definition.metadata:
            content += f"""JOB METADATA:
-------------
{job_definition.metadata}

"""
        
        content += f"{'=' * 50}\nEXECUTION LOG:\n{'=' * 50}\n\n"
        self._write_to_file(content)
    
    def log_execution_context(self, context: Dict[str, Any]):
        """Log execution context information"""
        content = f"""[{self._get_timestamp()}] EXECUTION CONTEXT
Triggered By: {context.get('triggered_by', 'Unknown')}
Environment: {context.get('environment', 'Unknown')}
User Agent: {context.get('user_agent', 'N/A')}
Source IP: {context.get('source_ip', 'N/A')}
Request ID: {context.get('request_id', 'N/A')}

"""
        self._write_to_file(content)
    
    def log_step_start(self, step: StepConfiguration, step_number: int):
        """Log step execution start"""
        content = f"""[{self._get_timestamp()}] STEP {step_number} STARTED: {step.step_name}
Step ID: {step.step_id}
Step Type: {step.step_type}
Timeout: {step.timeout or 'Default'} seconds
Configuration:
{step.config}

"""
        self._write_to_file(content)
    
    def log_step_progress(self, step_id: str, message: str):
        """Log step progress information"""
        content = f"[{self._get_timestamp()}] STEP PROGRESS [{step_id}]: {message}\n"
        self._write_to_file(content)
    
    def log_step_output(self, step_id: str, output: str):
        """Log step output"""
        content = f"""[{self._get_timestamp()}] STEP OUTPUT [{step_id}]:
{'-' * 40}
{output}
{'-' * 40}

"""
        self._write_to_file(content)
    
    def log_step_error(self, step_id: str, error_message: str, traceback_info: Optional[str] = None):
        """Log step error"""
        content = f"""[{self._get_timestamp()}] STEP ERROR [{step_id}]:
Error: {error_message}
"""
        
        if traceback_info:
            content += f"""
Traceback:
{traceback_info}
"""
        
        content += "\n"
        self._write_to_file(content)
    
    def log_step_completion(self, step_result: StepResult, step_number: int):
        """Log step execution completion"""
        content = f"""[{self._get_timestamp()}] STEP {step_number} COMPLETED: {step_result.step_name}
Status: {step_result.status.value.upper()}
Duration: {step_result.duration_seconds:.3f} seconds
Retry Count: {step_result.retry_count}
"""
        
        if step_result.output:
            output_preview = step_result.output[:500] + "..." if len(step_result.output) > 500 else step_result.output
            content += f"Output: {output_preview}\n"
        
        if step_result.error_message:
            content += f"Error: {step_result.error_message}\n"
        
        if step_result.metadata:
            content += f"Metadata:\n{step_result.metadata}\n"
        
        content += "\n"
        self._write_to_file(content)
    
    def log_retry_attempt(self, step_id: str, attempt: int, max_attempts: int, delay: int):
        """Log retry attempt"""
        content = f"[{self._get_timestamp()}] RETRY ATTEMPT [{step_id}]: {attempt}/{max_attempts}, waiting {delay}s before retry\n"
        self._write_to_file(content)
    
    def log_system_metrics(self, memory_usage: int, cpu_usage: float, disk_io: int, network_io: int = 0):
        """Log system resource metrics during execution"""
        content = f"""[{self._get_timestamp()}] SYSTEM METRICS:
Memory Usage: {memory_usage} MB
CPU Usage: {cpu_usage:.1f}%
Disk I/O: {disk_io} bytes
Network I/O: {network_io} bytes

"""
        self._write_to_file(content)
    
    def log_performance_warning(self, message: str, metric_type: str, value: float, threshold: float):
        """Log performance warning"""
        content = f"[{self._get_timestamp()}] PERFORMANCE WARNING: {message} ({metric_type}: {value:.2f}, threshold: {threshold:.2f})\n"
        self._write_to_file(content)
    
    def log_execution_completion(self, result: JobExecutionResult):
        """Log job execution completion with summary"""
        end_time = datetime.now(timezone.utc)
        
        content = f"""
{'=' * 50}
JOB EXECUTION COMPLETED
{'=' * 50}

EXECUTION SUMMARY:
------------------
Status: {result.status.value.upper()}
Total Duration: {result.duration_seconds:.3f} seconds
Steps Executed: {len(result.step_results)}
Successful Steps: {result.get_successful_steps()}
Failed Steps: {result.get_failed_steps()}
Retry Count: {result.retry_count}
"""
        
        if result.error_message:
            content += f"Error Message: {result.error_message}\n"
        
        content += f"""
STEPS SUMMARY:
--------------
"""
        
        for i, step in enumerate(result.step_results, 1):
            status_emoji = "✓" if step.status.value == "success" else "✗" if step.status.value == "failed" else "?"
            content += f"{i}. {status_emoji} {step.step_name} ({step.step_type}) - {step.status.value.upper()} in {step.duration_seconds:.3f}s\n"
        
        if result.metadata:
            content += f"""
EXECUTION METADATA:
-------------------
{result.metadata}
"""
        
        content += f"""
{'=' * 50}
Execution completed at: {end_time.isoformat()}
Log file: {self.log_file}
{'=' * 50}
"""
        
        self._write_to_file(content)
    
    def log_data_lineage(self, step_id: str, input_sources: List[str], output_destinations: List[str], 
                        records_processed: int, data_size: Optional[int] = None):
        """Log data lineage information for compliance"""
        content = f"""[{self._get_timestamp()}] DATA LINEAGE [{step_id}]:
Input Sources: {', '.join(input_sources) if input_sources else 'None'}
Output Destinations: {', '.join(output_destinations) if output_destinations else 'None'}
Records Processed: {records_processed}
Data Size: {data_size if data_size else 'Unknown'} bytes

"""
        self._write_to_file(content)
    
    def log_security_event(self, event_type: str, description: str, severity: str = "INFO"):
        """Log security-related events"""
        content = f"[{self._get_timestamp()}] SECURITY [{severity}]: {event_type} - {description}\n"
        self._write_to_file(content)
    
    def log_compliance_check(self, check_type: str, passed: bool, details: str):
        """Log compliance check results"""
        status = "PASSED" if passed else "FAILED"
        content = f"[{self._get_timestamp()}] COMPLIANCE CHECK [{check_type}]: {status} - {details}\n"
        self._write_to_file(content)
    
    def get_log_file_path(self) -> Path:
        """Get the path to the log file"""
        return self.log_file
    
    def get_log_size(self) -> int:
        """Get the size of the log file in bytes"""
        try:
            return self.log_file.stat().st_size
        except FileNotFoundError:
            return 0
    
    def archive_log(self, archive_dir: Optional[Path] = None) -> Path:
        """Archive the log file"""
        if not archive_dir:
            archive_dir = self.log_dir.parent / "archived"
        
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Create archive filename with timestamp
        archive_name = f"archived_{self.log_file.name}"
        archive_path = archive_dir / archive_name
        
        # Move log file to archive
        self.log_file.rename(archive_path)
        
        self.system_logger.info(f"Job log archived: {archive_path}")
        return archive_path
    
    def get_log_summary(self) -> str:
        """Get log summary as text"""
        return f"""Log Summary:
Job ID: {self.job_id}
Execution ID: {self.execution_id}
Job Name: {self.job_name}
Timezone: {self.timezone_name}
Log File: {self.log_file}
Log Size: {self.get_log_size()} bytes
Start Time: {self.start_time.isoformat()}
Created At: {datetime.now(timezone.utc).isoformat()}"""


def create_job_logger(job_id: str, execution_id: str, job_name: str, timezone_name: str) -> JobLogger:
    """Create a new job logger instance"""
    return JobLogger(job_id, execution_id, job_name, timezone_name)


def get_job_logs(timezone_name: str, job_id: Optional[str] = None) -> List[Path]:
    """Get list of job log files for a timezone"""
    tz_dir = timezone_name.replace('/', '_').replace('\\', '_')
    log_dir = Path("logs/timezones") / tz_dir / "job_details"
    
    if not log_dir.exists():
        return []
    
    pattern = f"*{job_id}*" if job_id else "*"
    return sorted(log_dir.glob(f"{pattern}.log"), key=lambda x: x.stat().st_mtime, reverse=True)


def search_job_logs(timezone_name: str, search_term: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """Search through job logs for specific terms"""
    results = []
    log_files = get_job_logs(timezone_name)
    
    for log_file in log_files[:max_results]:
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if search_term.lower() in content.lower():
                    # Extract job info from filename
                    parts = log_file.stem.split('_')
                    results.append({
                        "file": str(log_file),
                        "job_name": parts[0] if len(parts) > 0 else "unknown",
                        "timestamp": parts[1] if len(parts) > 1 else "unknown",
                        "execution_id": parts[2] if len(parts) > 2 else "unknown",
                        "size": log_file.stat().st_size,
                        "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                    })
        except Exception:
            continue  # Skip files that can't be read
    
    return results