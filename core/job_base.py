"""
Base classes for Job Scheduler
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
import threading
import sys
from dataclasses import dataclass, field
from utils.logger import get_logger, JobLogger


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRY = "retry"


@dataclass
class JobResult:
    """Job execution result"""
    job_id: str
    job_name: str
    status: JobStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    output: str = ""
    error_message: str = ""
    return_code: Optional[int] = None
    retry_count: int = 0
    max_retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate duration if end_time is set"""
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'job_id': self.job_id,
            'job_name': self.job_name,
            'status': self.status.value,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'output': self.output,
            'error_message': self.error_message,
            'return_code': self.return_code,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'metadata': self.metadata
        }


class JobBase(ABC):
    """Base class for all job types"""
    
    def __init__(self, job_id: str = None, name: str = "", description: str = "",
                 timeout: int = 300, max_retries: int = 3, retry_delay: int = 60,
                 run_as: str = None, enabled: bool = True, metadata: Dict[str, Any] = None):
        """
        Initialize base job
        
        Args:
            job_id: Unique job identifier
            name: Job name
            description: Job description
            timeout: Execution timeout in seconds
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries in seconds
            run_as: User account to run as (Windows domain account)
            enabled: Whether job is enabled
            metadata: Additional job metadata
        """
        self.job_id = job_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.run_as = run_as
        self.enabled = enabled
        self.metadata = metadata or {}
        
        # Execution state
        self.current_status = JobStatus.PENDING
        self.last_run_time: Optional[datetime] = None
        self.next_run_time: Optional[datetime] = None
        self.retry_count = 0
        self.execution_history: List[JobResult] = []
        self.is_running = False
        self._execution_lock = threading.Lock()
        
        # Logging
        self.logger = get_logger(f"Job.{self.__class__.__name__}")
        self.job_logger = JobLogger(self.name, self.job_id)
        
        # Job type (to be set by subclasses)
        self.job_type = "base"
        
        self.logger.debug(f"Initialized job: {self.name} ({self.job_id})")
    
    @abstractmethod
    def execute(self, execution_logger=None) -> JobResult:
        """
        Execute the job
        
        Returns:
            JobResult: Execution result
        """
        pass
    
    def run(self) -> JobResult:
        """
        Run the job with error handling, timeout, and retry logic
        
        Returns:
            JobResult: Execution result
        """
        if not self.enabled:
            result = JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.CANCELLED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message="Job is disabled"
            )
            self.execution_history.append(result)
            return result
        
        with self._execution_lock:
            if self.is_running:
                result = JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.FAILED,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    error_message="Job is already running"
                )
                self.execution_history.append(result)
                return result
            
            self.is_running = True
        
        start_time = datetime.now()
        self.last_run_time = start_time
        self.current_status = JobStatus.RUNNING
        
        # Create execution logger for detailed logging
        from .execution_logger import ExecutionLogger
        execution_logger = ExecutionLogger(self.job_id, self.name)
        execution_logger.info(f"Starting job execution (attempt {self.retry_count + 1}/{self.max_retries + 1})", "JOB_BASE")
        
        self.job_logger.info(f"Starting job execution (attempt {self.retry_count + 1}/{self.max_retries + 1})")
        
        try:
            # Execute with timeout
            execution_logger.debug("Starting job execution with timeout", "JOB_BASE", {
                'timeout': self.timeout,
                'job_type': getattr(self, 'job_type', 'unknown')
            })
            result = self._execute_with_timeout(execution_logger)
            
            # Update status based on result
            if result.status == JobStatus.SUCCESS:
                self.retry_count = 0  # Reset retry count on success
                self.job_logger.info(f"Job completed successfully in {result.duration_seconds:.2f} seconds")
            elif result.status == JobStatus.FAILED and self.retry_count < self.max_retries:
                self.retry_count += 1
                result.status = JobStatus.RETRY
                self.job_logger.warning(f"Job failed, will retry ({self.retry_count}/{self.max_retries})")
                # Schedule retry (this would be handled by the scheduler)
            else:
                self.job_logger.error(f"Job failed permanently after {self.retry_count} retries")
            
            self.current_status = result.status
            result.retry_count = self.retry_count
            result.max_retries = self.max_retries
            
        except Exception as e:
            self.job_logger.exception(f"Unexpected error during job execution: {e}")
            result = JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=f"Unexpected error: {str(e)}",
                retry_count=self.retry_count,
                max_retries=self.max_retries
            )
            self.current_status = JobStatus.FAILED
        
        finally:
            self.is_running = False
        
        # Add to execution history
        self.execution_history.append(result)
        
        # Keep only last 100 executions
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
        
        return result
    
    def _execute_with_timeout(self, execution_logger=None) -> JobResult:
        """Execute job with timeout handling"""
        import threading
        import signal
        import sys
        
        start_time = datetime.now()
        result_container = [None]
        exception_container = [None]
        
        def execute_job():
            try:
                if execution_logger:
                    execution_logger.info("Calling job-specific execute method", "TIMEOUT_HANDLER")
                result_container[0] = self.execute(execution_logger)
            except Exception as e:
                if execution_logger:
                    execution_logger.error(f"Exception in execute method: {str(e)}", "TIMEOUT_HANDLER")
                exception_container[0] = e
        
        # Windows doesn't support SIGALRM, so use threading for timeout
        if sys.platform == "win32":
            # Use threading for timeout on Windows
            thread = threading.Thread(target=execute_job, daemon=True)
            thread.start()
            thread.join(timeout=self.timeout)
            
            if thread.is_alive():
                # Thread is still running, job timed out
                if execution_logger:
                    execution_logger.error(f"Job execution timed out after {self.timeout} seconds", "TIMEOUT_HANDLER")
                self.job_logger.error(f"Job execution timed out after {self.timeout} seconds")
                
                timeout_logs = execution_logger.get_formatted_logs() if execution_logger else "No detailed logs available"
                
                return JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.TIMEOUT,
                    start_time=start_time,
                    end_time=datetime.now(),
                    output=timeout_logs,
                    error_message=f"Job execution timed out after {self.timeout} seconds",
                    retry_count=self.retry_count,
                    max_retries=self.max_retries
                )
        else:
            # Use threading-based timeout for Unix systems (safer for background threads)
            # Signal handling doesn't work in APScheduler background threads
            thread = threading.Thread(target=execute_job, daemon=True)
            thread.start()
            thread.join(timeout=self.timeout)
            
            if thread.is_alive():
                # Thread is still running, job timed out
                if execution_logger:
                    execution_logger.error(f"Job execution timed out after {self.timeout} seconds", "TIMEOUT_HANDLER")
                self.job_logger.error(f"Job execution timed out after {self.timeout} seconds")
                
                timeout_logs = execution_logger.get_formatted_logs() if execution_logger else "No detailed logs available"
                
                return JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.TIMEOUT,
                    start_time=start_time,
                    end_time=datetime.now(),
                    output=timeout_logs,
                    error_message=f"Job execution timed out after {self.timeout} seconds",
                    retry_count=self.retry_count,
                    max_retries=self.max_retries
                )
        
        # Check if job completed successfully
        if exception_container[0]:
            raise exception_container[0]
        
        if result_container[0]:
            result = result_container[0]
            result.start_time = start_time
            if not result.end_time:
                result.end_time = datetime.now()
            
            # Append execution logs to the result output
            if execution_logger:
                execution_logger.info(f"Job execution completed with status: {result.status.value}", "JOB_BASE")
                detailed_logs = execution_logger.get_formatted_logs()
                
                # Combine existing output with detailed logs
                if result.output:
                    result.output = f"{result.output}\n\n{detailed_logs}"
                else:
                    result.output = detailed_logs
            
            return result
        
        # If we get here, something went wrong
        return JobResult(
            job_id=self.job_id,
            job_name=self.name,
            status=JobStatus.FAILED,
            start_time=start_time,
            end_time=datetime.now(),
            error_message="Job execution completed but no result returned",
            retry_count=self.retry_count,
            max_retries=self.max_retries
        )
    
    def cancel(self) -> bool:
        """
        Cancel job execution
        
        Returns:
            bool: True if cancellation was successful
        """
        if self.is_running:
            self.current_status = JobStatus.CANCELLED
            self.job_logger.info("Job cancellation requested")
            # Note: Actual cancellation implementation depends on job type
            return True
        return False
    
    def get_status(self) -> JobStatus:
        """Get current job status"""
        return self.current_status
    
    def get_last_result(self) -> Optional[JobResult]:
        """Get last execution result"""
        return self.execution_history[-1] if self.execution_history else None
    
    def get_execution_history(self, limit: int = 10) -> List[JobResult]:
        """Get execution history"""
        return self.execution_history[-limit:] if self.execution_history else []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary"""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'description': self.description,
            'job_type': self.job_type,
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'run_as': self.run_as,
            'enabled': self.enabled,
            'metadata': self.metadata,
            'current_status': self.current_status.value,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None,
            'next_run_time': self.next_run_time.isoformat() if self.next_run_time else None,
            'retry_count': self.retry_count,
            'is_running': self.is_running
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobBase':
        """Create job from dictionary (to be implemented by subclasses)"""
        raise NotImplementedError("Subclasses must implement from_dict method")
    
    def __str__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}(name='{self.name}', id='{self.job_id}', status='{self.current_status.value}')"
    
    def __repr__(self) -> str:
        """Detailed string representation"""
        return (f"{self.__class__.__name__}(job_id='{self.job_id}', name='{self.name}', "
                f"type='{self.job_type}', status='{self.current_status.value}', "
                f"enabled={self.enabled}, is_running={self.is_running})")


if __name__ == "__main__":
    # Test base job functionality
    class TestJob(JobBase):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.job_type = "test"
        
        def execute(self) -> JobResult:
            import time
            time.sleep(1)  # Simulate work
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.SUCCESS,
                start_time=datetime.now(),
                end_time=datetime.now(),
                output="Test job completed successfully"
            )
    
    # Test job creation and execution
    job = TestJob(name="Test Job", description="A test job")
    print(f"Created job: {job}")
    
    result = job.run()
    print(f"Execution result: {result.status.value}")
    print(f"Output: {result.output}")
    print(f"Duration: {result.duration_seconds} seconds")