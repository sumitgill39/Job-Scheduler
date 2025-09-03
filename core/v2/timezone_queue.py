"""
Timezone-aware job queue system for Job Scheduler V2
Manages separate execution queues per timezone with priority scheduling
"""

import asyncio
import heapq
import threading
from datetime import datetime, timezone as dt_timezone
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
import pytz
import uuid
import time

from .data_models import JobDefinition, JobExecutionResult, JobStatus, ExecutionContext
from .timezone_logger import TimezoneLogger
from .job_logger import JobLogger, create_job_logger
from .step_framework import StepFactory, ExecutionStep
from utils.logger import get_logger


class QueueStatus(Enum):
    """Queue status enumeration"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class QueuedJob:
    """Represents a job in the queue with scheduling information"""
    job: JobDefinition
    scheduled_time: datetime
    priority: int = 0
    queue_time: datetime = field(default_factory=lambda: datetime.now(dt_timezone.utc))
    execution_id: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if not self.execution_id:
            timestamp = self.scheduled_time.strftime("%Y%m%d_%H%M%S")
            self.execution_id = f"exec_{timestamp}_{str(uuid.uuid4())[:8]}"
    
    def __lt__(self, other: "QueuedJob") -> bool:
        """Compare for priority queue (higher priority first, then earlier scheduled time)"""
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.scheduled_time < other.scheduled_time  # Earlier time first
    
    def get_wait_time(self) -> float:
        """Get how long this job has been waiting in queue"""
        return (datetime.now(dt_timezone.utc) - self.queue_time).total_seconds()
    
    def is_ready_to_execute(self) -> bool:
        """Check if job is ready to execute based on scheduled time"""
        return datetime.now(dt_timezone.utc) >= self.scheduled_time


class TimezoneJobQueue:
    """Timezone-specific job queue with async worker management"""
    
    def __init__(self, timezone_name: str, max_concurrent_jobs: int = 5):
        self.timezone_name = timezone_name
        self.max_concurrent_jobs = max_concurrent_jobs
        
        # Queue state
        self.status = QueueStatus.STOPPED
        self._queue: List[QueuedJob] = []  # Priority queue
        self._queue_lock = asyncio.Lock()
        self._active_jobs: Dict[str, QueuedJob] = {}  # Currently executing jobs
        
        # Worker management
        self._workers: List[asyncio.Task] = []
        self._stop_event = asyncio.Event()
        self._worker_semaphore = asyncio.Semaphore(max_concurrent_jobs)
        
        # Logging
        self.tz_logger = TimezoneLogger.get_logger(timezone_name)
        self.system_logger = get_logger(f"TimezoneQueue.{timezone_name}")
        
        # Timezone handling
        try:
            self.timezone = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            self.system_logger.warning(f"Unknown timezone {timezone_name}, using UTC")
            self.timezone = pytz.UTC
        
        # Performance metrics
        self._total_jobs_processed = 0
        self._successful_jobs = 0
        self._failed_jobs = 0
        self._total_execution_time = 0.0
        self._queue_start_time = None
        
        self.system_logger.info(f"Timezone queue initialized: {timezone_name}, max concurrent: {max_concurrent_jobs}")
    
    async def start(self, worker_count: int = 2):
        """Start the queue workers"""
        if self.status == QueueStatus.RUNNING:
            self.system_logger.warning("Queue is already running")
            return
        
        self.status = QueueStatus.STARTING
        self._stop_event.clear()
        self._queue_start_time = datetime.now(dt_timezone.utc)
        
        # Start worker tasks
        for i in range(worker_count):
            worker_task = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker_task)
        
        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitor_loop())
        self._workers.append(monitor_task)
        
        self.status = QueueStatus.RUNNING
        self.system_logger.info(f"Queue started with {worker_count} workers")
        self.tz_logger.log_queue_status(len(self._queue), len(self._active_jobs), 0.0)
    
    async def stop(self):
        """Stop the queue workers"""
        if self.status == QueueStatus.STOPPED:
            return
        
        self.status = QueueStatus.STOPPING
        self._stop_event.set()
        
        # Wait for all workers to complete
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
            self._workers.clear()
        
        # Wait for active jobs to complete (with timeout)
        timeout = 30  # 30 seconds timeout
        start_time = time.time()
        while self._active_jobs and (time.time() - start_time) < timeout:
            await asyncio.sleep(1)
        
        if self._active_jobs:
            self.system_logger.warning(f"Stopped queue with {len(self._active_jobs)} jobs still active")
        
        self.status = QueueStatus.STOPPED
        self.system_logger.info("Queue stopped")
    
    async def add_job(self, job: JobDefinition, scheduled_time: Optional[datetime] = None, priority: int = 0):
        """Add a job to the queue"""
        if scheduled_time is None:
            scheduled_time = datetime.now(dt_timezone.utc)
        
        # Convert to timezone-aware datetime if needed
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=dt_timezone.utc)
        
        queued_job = QueuedJob(
            job=job,
            scheduled_time=scheduled_time,
            priority=priority
        )
        
        async with self._queue_lock:
            heapq.heappush(self._queue, queued_job)
        
        # Log job queued
        self.tz_logger.log_job_queued(
            job.job_id,
            job.job_name,
            scheduled_time,
            priority
        )
        
        self.system_logger.info(f"Job queued: {job.job_name} ({job.job_id}) for {scheduled_time}")
    
    async def get_next_ready_job(self) -> Optional[QueuedJob]:
        """Get the next job ready for execution"""
        async with self._queue_lock:
            ready_jobs = []
            remaining_jobs = []
            
            # Separate ready and not-ready jobs
            while self._queue:
                job = heapq.heappop(self._queue)
                if job.is_ready_to_execute():
                    ready_jobs.append(job)
                else:
                    remaining_jobs.append(job)
            
            # Put not-ready jobs back in queue
            for job in remaining_jobs:
                heapq.heappush(self._queue, job)
            
            # Return highest priority ready job
            if ready_jobs:
                ready_jobs.sort()  # Sort by priority and time
                return ready_jobs[0]
        
        return None
    
    async def _worker_loop(self, worker_id: int):
        """Main worker loop"""
        worker_logger = get_logger(f"TimezoneQueue.{self.timezone_name}.Worker{worker_id}")
        worker_logger.info(f"Worker {worker_id} started")
        
        while not self._stop_event.is_set():
            try:
                # Check for ready jobs
                queued_job = await self.get_next_ready_job()
                
                if queued_job is None:
                    # No ready jobs, wait a bit
                    await asyncio.sleep(1)
                    continue
                
                # Acquire semaphore to limit concurrent executions
                async with self._worker_semaphore:
                    # Add to active jobs
                    self._active_jobs[queued_job.execution_id] = queued_job
                    
                    try:
                        # Execute the job
                        await self._execute_job(queued_job, worker_id)
                    finally:
                        # Remove from active jobs
                        if queued_job.execution_id in self._active_jobs:
                            del self._active_jobs[queued_job.execution_id]
                
            except Exception as e:
                worker_logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
        
        worker_logger.info(f"Worker {worker_id} stopped")
    
    async def _execute_job(self, queued_job: QueuedJob, worker_id: int):
        """Execute a single job"""
        job = queued_job.job
        execution_id = queued_job.execution_id
        
        # Create execution context
        context = ExecutionContext(
            job_id=job.job_id,
            execution_id=execution_id,
            timezone=self.timezone_name,
            start_time=datetime.now(dt_timezone.utc)
        )
        
        # Create loggers
        job_logger = create_job_logger(job.job_id, execution_id, job.job_name, self.timezone_name)
        
        # Create execution result
        result = JobExecutionResult(
            execution_id=execution_id,
            job_id=job.job_id,
            job_name=job.job_name,
            status=JobStatus.RUNNING,
            timezone=self.timezone_name,
            start_time=context.start_time
        )
        
        try:
            # Log job start
            self.tz_logger.log_job_started(job.job_id, job.job_name, execution_id)
            job_logger.log_execution_start(job)
            
            self.system_logger.info(f"Worker {worker_id} executing job: {job.job_name} ({job.job_id})")
            
            # Execute each step
            for step_number, step_config in enumerate(job.steps, 1):
                try:
                    # Create step instance
                    step = StepFactory.create_step(step_config)
                    
                    # Execute step
                    step_result = await step.execute(context, job_logger, self.tz_logger)
                    result.add_step_result(step_result)
                    
                    # Check if step failed and should stop execution
                    if step_result.status.value in ["failed", "timeout", "cancelled"]:
                        if not step_config.continue_on_failure:
                            result.mark_completed(
                                JobStatus.FAILED,
                                f"Job failed at step {step_number}: {step_config.step_name}"
                            )
                            break
                    
                except Exception as step_error:
                    error_msg = f"Step {step_number} ({step_config.step_name}) execution error: {str(step_error)}"
                    self.system_logger.error(error_msg)
                    
                    # Create failed step result
                    failed_step = result.step_results[-1] if result.step_results else None
                    if failed_step:
                        failed_step.mark_completed("failed", error_message=error_msg)
                    
                    if not step_config.continue_on_failure:
                        result.mark_completed(JobStatus.FAILED, error_msg)
                        break
            
            # Determine final job status
            if result.status == JobStatus.RUNNING:  # Not failed yet
                successful_steps = result.get_successful_steps()
                total_steps = result.get_step_count()
                
                if successful_steps == total_steps:
                    result.mark_completed(JobStatus.SUCCESS)
                elif successful_steps > 0:
                    result.mark_completed(JobStatus.PARTIAL_SUCCESS, "Some steps completed successfully")
                else:
                    result.mark_completed(JobStatus.FAILED, "All steps failed")
            
            # Update metrics
            self._total_jobs_processed += 1
            if result.status == JobStatus.SUCCESS:
                self._successful_jobs += 1
            else:
                self._failed_jobs += 1
            
            if result.duration_seconds:
                self._total_execution_time += result.duration_seconds
            
            # Log completion
            self.tz_logger.log_job_completed(
                job.job_id,
                job.job_name,
                execution_id,
                result.status.value,
                result.duration_seconds or 0
            )
            
            job_logger.log_execution_completion(result)
            
            # Save execution result to database for history
            self._save_execution_to_database(job, execution_id, result)
            
            self.system_logger.info(
                f"Job completed: {job.job_name} ({job.job_id}) - "
                f"Status: {result.status.value}, "
                f"Duration: {result.duration_seconds:.2f}s"
            )
            
        except Exception as e:
            error_msg = f"Job execution error: {str(e)}"
            self.system_logger.error(error_msg)
            
            result.mark_completed(JobStatus.FAILED, error_msg)
            
            self.tz_logger.log_error(job.job_id, execution_id, error_msg)
            job_logger.log_execution_completion(result)
            
            self._total_jobs_processed += 1
            self._failed_jobs += 1
    
    async def _monitor_loop(self):
        """Monitor queue performance and log metrics"""
        monitor_logger = get_logger(f"TimezoneQueue.{self.timezone_name}.Monitor")
        monitor_logger.info("Queue monitor started")
        
        last_metrics_time = time.time()
        
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                
                # Log metrics every 5 minutes
                if current_time - last_metrics_time >= 300:
                    await self._log_performance_metrics()
                    last_metrics_time = current_time
                
                # Log queue status every minute
                async with self._queue_lock:
                    queue_depth = len(self._queue)
                
                active_count = len(self._active_jobs)
                avg_wait_time = self._calculate_average_wait_time()
                
                self.tz_logger.log_queue_status(queue_depth, active_count, avg_wait_time)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                monitor_logger.error(f"Monitor error: {str(e)}")
                await asyncio.sleep(60)
        
        monitor_logger.info("Queue monitor stopped")
    
    def _calculate_average_wait_time(self) -> float:
        """Calculate average wait time for jobs in queue"""
        if not self._queue:
            return 0.0
        
        total_wait_time = sum(job.get_wait_time() for job in self._queue)
        return total_wait_time / len(self._queue)
    
    async def _log_performance_metrics(self):
        """Log performance metrics"""
        if self._total_jobs_processed == 0:
            return
        
        # Calculate metrics
        success_rate = (self._successful_jobs / self._total_jobs_processed) * 100
        avg_execution_time = self._total_execution_time / self._total_jobs_processed
        
        # Calculate jobs per hour
        if self._queue_start_time:
            hours_running = (datetime.now(dt_timezone.utc) - self._queue_start_time).total_seconds() / 3600
            jobs_per_hour = self._total_jobs_processed / hours_running if hours_running > 0 else 0
        else:
            jobs_per_hour = 0
        
        # Get memory usage (approximate)
        import psutil
        process = psutil.Process()
        memory_usage = process.memory_info().rss // (1024 * 1024)  # MB
        
        self.tz_logger.log_performance_metrics(
            jobs_per_hour=jobs_per_hour,
            success_rate=success_rate,
            avg_duration=avg_execution_time,
            memory_usage=memory_usage
        )
        
        self.system_logger.info(
            f"Performance metrics - "
            f"Processed: {self._total_jobs_processed}, "
            f"Success Rate: {success_rate:.1f}%, "
            f"Avg Duration: {avg_execution_time:.2f}s, "
            f"Jobs/Hour: {jobs_per_hour:.1f}"
        )
    
    # Public interface methods
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        return {
            "timezone": self.timezone_name,
            "status": self.status.value,
            "queue_size": len(self._queue),
            "active_executions": len(self._active_jobs),
            "worker_count": len([w for w in self._workers if not w.done()]),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "total_processed": self._total_jobs_processed,
            "successful_jobs": self._successful_jobs,
            "failed_jobs": self._failed_jobs,
            "success_rate": (self._successful_jobs / self._total_jobs_processed * 100) if self._total_jobs_processed > 0 else 0,
            "avg_execution_time": (self._total_execution_time / self._total_jobs_processed) if self._total_jobs_processed > 0 else 0
        }
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """Get list of currently active jobs"""
        return [
            {
                "execution_id": execution_id,
                "job_id": queued_job.job.job_id,
                "job_name": queued_job.job.job_name,
                "started_time": queued_job.scheduled_time.isoformat(),
                "priority": queued_job.priority
            }
            for execution_id, queued_job in self._active_jobs.items()
        ]
    
    def get_queued_jobs(self) -> List[Dict[str, Any]]:
        """Get list of jobs waiting in queue"""
        return [
            {
                "execution_id": queued_job.execution_id,
                "job_id": queued_job.job.job_id,
                "job_name": queued_job.job.job_name,
                "scheduled_time": queued_job.scheduled_time.isoformat(),
                "priority": queued_job.priority,
                "wait_time": queued_job.get_wait_time()
            }
            for queued_job in sorted(self._queue)
        ]
    
    async def cancel_job(self, execution_id: str) -> bool:
        """Cancel a queued or active job"""
        # Check active jobs first
        if execution_id in self._active_jobs:
            # For active jobs, we can only mark them for cancellation
            # The actual cancellation depends on step implementation
            queued_job = self._active_jobs[execution_id]
            self.system_logger.warning(f"Attempted to cancel active job: {execution_id}")
            return False  # Cannot cancel active jobs in this implementation
        
        # Remove from queue
        async with self._queue_lock:
            original_queue = list(self._queue)
            self._queue = [job for job in original_queue if job.execution_id != execution_id]
            heapq.heapify(self._queue)
            
            if len(self._queue) < len(original_queue):
                self.system_logger.info(f"Cancelled queued job: {execution_id}")
                return True
        
        return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get detailed performance summary"""
        runtime = 0
        if self._queue_start_time:
            runtime = (datetime.now(dt_timezone.utc) - self._queue_start_time).total_seconds()
        
        return {
            "timezone": self.timezone_name,
            "runtime_seconds": runtime,
            "total_jobs_processed": self._total_jobs_processed,
            "successful_jobs": self._successful_jobs,
            "failed_jobs": self._failed_jobs,
            "success_rate": (self._successful_jobs / self._total_jobs_processed * 100) if self._total_jobs_processed > 0 else 0,
            "total_execution_time": self._total_execution_time,
            "average_execution_time": (self._total_execution_time / self._total_jobs_processed) if self._total_jobs_processed > 0 else 0,
            "jobs_per_hour": (self._total_jobs_processed / (runtime / 3600)) if runtime > 0 else 0,
            "current_queue_size": len(self._queue),
            "current_active_jobs": len(self._active_jobs),
            "max_concurrent_jobs": self.max_concurrent_jobs
        }
    
    def _save_execution_to_database(self, job: JobDefinition, execution_id: str, result: JobExecutionResult):
        """Save execution result to database for history tracking"""
        try:
            self.system_logger.info(f"Starting database save for execution: {execution_id}")
            from database.sqlalchemy_models import JobExecutionHistory, get_db_session
            import json
            
            # Prepare execution metadata
            metadata = {
                "timezone": job.timezone,
                "execution_id": execution_id,
                "step_count": len(job.steps),
                "successful_steps": result.get_successful_steps() if hasattr(result, 'get_successful_steps') else 0,
                "failed_steps": result.get_step_count() - result.get_successful_steps() if hasattr(result, 'get_step_count') else 0,
                "step_results": []
            }
            
            # Add step results to metadata
            if hasattr(result, 'step_results') and result.step_results:
                for step_result in result.step_results:
                    step_info = {
                        "step_id": step_result.step_id,
                        "step_name": step_result.step_name,
                        "step_type": step_result.step_type,
                        "status": step_result.status.value,
                        "duration": step_result.duration_seconds,
                        "error": step_result.error_message
                    }
                    metadata["step_results"].append(step_info)
            
            # Prepare output summary
            output_lines = []
            if hasattr(result, 'step_results') and result.step_results:
                for step_result in result.step_results:
                    if step_result.output:
                        output_lines.append(f"[{step_result.step_name}]: {step_result.output[:200]}")
            
            output_summary = "\n".join(output_lines)[:1000]  # Limit to 1000 chars
            
            # Create database record
            self.system_logger.info(f"Creating database record for: {job.job_name} ({job.job_id})")
            with get_db_session() as session:
                execution_record = JobExecutionHistory(
                    job_id=job.job_id,
                    job_name=job.job_name,
                    status=result.status.value.upper(),
                    start_time=result.start_time,
                    end_time=result.end_time,
                    duration_seconds=result.duration_seconds,
                    output=output_summary,
                    error_message=result.error_message,
                    return_code=0 if result.status.value == "success" else 1,
                    retry_count=0,  # V2 doesn't support retries at job level yet
                    max_retries=job.max_retries,
                    execution_metadata=json.dumps(metadata)
                )
                
                session.add(execution_record)
                session.commit()
                
                self.system_logger.info(f"Saved execution history to database: {execution_id}")
                
        except Exception as e:
            self.system_logger.error(f"Failed to save execution history to database: {str(e)}")
            import traceback
            self.system_logger.error(f"Database save traceback: {traceback.format_exc()}")
            # Don't raise the exception - database logging is not critical for job execution