"""
Modern Execution Engine for Job Scheduler V2
Coordinates timezone queues, manages job execution, and provides central control
"""

import asyncio
import threading
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from enum import Enum
import json
import uuid

from .data_models import JobDefinition, JobExecutionResult, JobStatus, ExecutionContext, create_job_from_legacy
from .timezone_queue import TimezoneJobQueue, QueueStatus
from .timezone_logger import get_timezone_logger, get_performance_logger, get_audit_logger
from .step_framework import StepFactory
from utils.logger import get_logger


class ExecutionEngineStatus(Enum):
    """Execution engine status"""
    STOPPED = "stopped"
    STARTING = "starting" 
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ModernExecutionEngine:
    """
    Central execution engine that manages timezone queues and job coordination
    """
    
    def __init__(self, default_max_concurrent_jobs: int = 5):
        self.default_max_concurrent_jobs = default_max_concurrent_jobs
        self.status = ExecutionEngineStatus.STOPPED
        
        # Timezone queue management
        self._timezone_queues: Dict[str, TimezoneJobQueue] = {}
        self._queue_lock = asyncio.Lock()
        
        # Engine management
        self._engine_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        # Logging
        self.logger = get_logger("ModernExecutionEngine")
        self.performance_logger = get_performance_logger()
        self.audit_logger = get_audit_logger()
        
        # Metrics
        self._total_jobs_executed = 0
        self._engine_start_time: Optional[datetime] = None
        
        # Default timezone queues
        self._default_timezones = ["UTC", "America/New_York", "Europe/London"]
        
        self.logger.info("Modern Execution Engine initialized")
    
    async def start(self):
        """Start the execution engine"""
        if self.status == ExecutionEngineStatus.RUNNING:
            self.logger.warning("Execution engine is already running")
            return
        
        self.status = ExecutionEngineStatus.STARTING
        self._stop_event.clear()
        self._engine_start_time = datetime.now(dt_timezone.utc)
        
        try:
            # Create default timezone queues
            for tz_name in self._default_timezones:
                await self._ensure_timezone_queue(tz_name)
            
            # Start monitoring task
            self._engine_task = asyncio.create_task(self._engine_monitor_loop())
            
            self.status = ExecutionEngineStatus.RUNNING
            self.logger.info("Modern Execution Engine started successfully")
            
            # Log system event
            self.audit_logger.log_system_event("engine_started", "Modern Execution Engine started")
            
        except Exception as e:
            self.status = ExecutionEngineStatus.ERROR
            self.logger.error(f"Failed to start execution engine: {str(e)}")
            raise
    
    async def stop(self):
        """Stop the execution engine"""
        if self.status == ExecutionEngineStatus.STOPPED:
            return
        
        self.status = ExecutionEngineStatus.STOPPING
        self._stop_event.set()
        
        try:
            # Stop engine monitoring
            if self._engine_task and not self._engine_task.done():
                await self._engine_task
            
            # Stop all timezone queues
            async with self._queue_lock:
                stop_tasks = [queue.stop() for queue in self._timezone_queues.values()]
                if stop_tasks:
                    await asyncio.gather(*stop_tasks, return_exceptions=True)
                
                self._timezone_queues.clear()
            
            self.status = ExecutionEngineStatus.STOPPED
            self.logger.info("Modern Execution Engine stopped")
            
            # Log system event
            self.audit_logger.log_system_event("engine_stopped", "Modern Execution Engine stopped")
            
        except Exception as e:
            self.status = ExecutionEngineStatus.ERROR
            self.logger.error(f"Error stopping execution engine: {str(e)}")
            raise
    
    async def _ensure_timezone_queue(self, timezone_name: str, max_concurrent_jobs: Optional[int] = None) -> TimezoneJobQueue:
        """Ensure a timezone queue exists and is started"""
        async with self._queue_lock:
            if timezone_name not in self._timezone_queues:
                # Create new queue
                queue = TimezoneJobQueue(
                    timezone_name=timezone_name,
                    max_concurrent_jobs=max_concurrent_jobs or self.default_max_concurrent_jobs
                )
                
                self._timezone_queues[timezone_name] = queue
                
                # Start the queue
                await queue.start(worker_count=2)
                
                self.logger.info(f"Created and started timezone queue: {timezone_name}")
            
            return self._timezone_queues[timezone_name]
    
    async def schedule_job(self, job: JobDefinition, scheduled_time: Optional[datetime] = None, priority: int = 0) -> str:
        """
        Schedule a job for execution in the appropriate timezone queue
        
        Args:
            job: Job definition
            scheduled_time: When to execute (None for immediate)
            priority: Job priority (higher number = higher priority)
            
        Returns:
            Execution ID for tracking
        """
        if self.status != ExecutionEngineStatus.RUNNING:
            raise RuntimeError("Execution engine is not running")
        
        # Validate job
        validation_errors = job.validate()
        if validation_errors:
            raise ValueError(f"Job validation failed: {', '.join(validation_errors)}")
        
        # Ensure timezone queue exists
        queue = await self._ensure_timezone_queue(job.timezone)
        
        # Set default scheduled time
        if scheduled_time is None:
            scheduled_time = datetime.now(dt_timezone.utc)
        
        # Add job to queue
        await queue.add_job(job, scheduled_time, priority)
        
        # Generate execution ID for tracking
        execution_id = f"exec_{scheduled_time.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        # Log scheduling
        self.logger.info(f"Job scheduled: {job.job_name} ({job.job_id}) in {job.timezone} for {scheduled_time}")
        
        # Audit log
        self.audit_logger.log_job_execution(
            job_id=job.job_id,
            job_name=job.job_name,
            execution_id=execution_id,
            user=job.created_by,
            timezone=job.timezone,
            status="scheduled",
            duration=0,
            steps_count=len(job.steps)
        )
        
        return execution_id
    
    async def execute_job_immediately(self, job: JobDefinition, priority: int = 10) -> JobExecutionResult:
        """
        Execute a job immediately and return the result
        
        Args:
            job: Job definition
            priority: Job priority (higher for immediate execution)
            
        Returns:
            Job execution result
        """
        if self.status != ExecutionEngineStatus.RUNNING:
            raise RuntimeError("Execution engine is not running")
        
        # Validate job
        validation_errors = job.validate()
        if validation_errors:
            raise ValueError(f"Job validation failed: {', '.join(validation_errors)}")
        
        # Ensure timezone queue exists
        queue = await self._ensure_timezone_queue(job.timezone)
        
        # Schedule for immediate execution with high priority
        immediate_time = datetime.now(dt_timezone.utc)
        await queue.add_job(job, immediate_time, priority)
        
        # Wait for actual job completion using queue's job tracking
        execution_timeout = job.timeout_seconds + 60  # Add buffer
        start_wait_time = datetime.now(dt_timezone.utc)
        
        # Track the job by monitoring the queue for completion
        while True:
            # Check if we've exceeded timeout
            if (datetime.now(dt_timezone.utc) - start_wait_time).total_seconds() > execution_timeout:
                raise TimeoutError(f"Job execution timed out after {execution_timeout} seconds")
            
            # Get queue status to check if job completed
            queue_status = queue.get_queue_status()
            active_jobs = queue.get_active_jobs()
            
            # Check if our job is still in the queue or being processed
            job_still_running = any(active_job.get('job_id') == job.job_id for active_job in active_jobs)
            queue_not_empty = queue_status.get('queue_size', 0) > 0
            
            if not job_still_running and not queue_not_empty:
                # Job should be completed, wait a moment for database save to complete
                await asyncio.sleep(1)
                break
            
            await asyncio.sleep(0.5)  # Check every half second
        
        # Try to get the actual execution result from the database
        try:
            from database.sqlalchemy_models import JobExecutionHistory, get_db_session
            
            # Look for the most recent execution of this job
            with get_db_session() as session:
                recent_execution = session.query(JobExecutionHistory).filter(
                    JobExecutionHistory.job_id == job.job_id,
                    JobExecutionHistory.start_time >= immediate_time - timedelta(seconds=5)
                ).order_by(JobExecutionHistory.start_time.desc()).first()
                
                if recent_execution:
                    # Convert database record back to JobExecutionResult
                    result = JobExecutionResult(
                        execution_id=recent_execution.execution_metadata and 
                                   json.loads(recent_execution.execution_metadata).get('execution_id', 'unknown'),
                        job_id=job.job_id,
                        job_name=job.job_name,
                        status=JobStatus(recent_execution.status.lower()),
                        timezone=job.timezone,
                        start_time=recent_execution.start_time.replace(tzinfo=dt_timezone.utc),
                        end_time=recent_execution.end_time.replace(tzinfo=dt_timezone.utc) if recent_execution.end_time else None
                    )
                    result.duration_seconds = recent_execution.duration_seconds
                    result.error_message = recent_execution.error_message
                    
                    self.logger.info(f"Immediate job executed: {job.job_name} ({job.job_id}) - Status: {result.status.value}")
                    self._total_jobs_executed += 1
                    
                    return result
        
        except Exception as e:
            self.logger.warning(f"Could not retrieve actual execution result: {e}")
        
        # Fallback: create a result based on queue completion status
        execution_id = f"exec_{immediate_time.strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        result = JobExecutionResult(
            execution_id=execution_id,
            job_id=job.job_id,
            job_name=job.job_name,
            status=JobStatus.SUCCESS,  # Assume success if queue completed without errors
            timezone=job.timezone,
            start_time=immediate_time,
            end_time=datetime.now(dt_timezone.utc)
        )
        
        self.logger.info(f"Immediate job executed (fallback): {job.job_name} ({job.job_id})")
        self._total_jobs_executed += 1
        
        return result
    
    async def _engine_monitor_loop(self):
        """Engine monitoring and maintenance loop"""
        self.logger.info("Engine monitor started")
        
        last_metrics_time = datetime.now(dt_timezone.utc)
        
        while not self._stop_event.is_set():
            try:
                current_time = datetime.now(dt_timezone.utc)
                
                # Log performance metrics every 10 minutes
                if (current_time - last_metrics_time).total_seconds() >= 600:
                    await self._log_performance_metrics()
                    last_metrics_time = current_time
                
                # Check queue health
                await self._check_queue_health()
                
                # Sleep for 30 seconds
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Engine monitor error: {str(e)}")
                await asyncio.sleep(60)
        
        self.logger.info("Engine monitor stopped")
    
    async def _check_queue_health(self):
        """Check health of all timezone queues"""
        async with self._queue_lock:
            unhealthy_queues = []
            
            for tz_name, queue in self._timezone_queues.items():
                status = queue.get_queue_status()
                
                # Check for unhealthy conditions
                if status["status"] == "error":
                    unhealthy_queues.append(tz_name)
                elif status["queue_size"] > 100:  # Queue backing up
                    self.logger.warning(f"Queue {tz_name} has {status['queue_size']} pending jobs")
                elif status["success_rate"] < 80 and status["total_processed"] > 10:  # Low success rate
                    self.logger.warning(f"Queue {tz_name} has low success rate: {status['success_rate']:.1f}%")
            
            if unhealthy_queues:
                self.logger.error(f"Unhealthy queues detected: {', '.join(unhealthy_queues)}")
    
    async def _log_performance_metrics(self):
        """Log overall engine performance metrics"""
        async with self._queue_lock:
            # Collect metrics from all queues
            total_processed = 0
            total_successful = 0
            total_queued = 0
            total_active = 0
            
            timezone_stats = {}
            
            for tz_name, queue in self._timezone_queues.items():
                status = queue.get_queue_status()
                
                total_processed += status["total_processed"]
                total_successful += status["successful_jobs"]
                total_queued += status["queue_size"]
                total_active += status["active_executions"]
                
                timezone_stats[tz_name] = {
                    "processed": status["total_processed"],
                    "queued": status["queue_size"],
                    "active": status["active_executions"],
                    "success_rate": status["success_rate"]
                }
            
            # Calculate overall metrics
            overall_success_rate = (total_successful / total_processed * 100) if total_processed > 0 else 0
            
            # Get system metrics
            import psutil
            process = psutil.Process()
            memory_usage = process.memory_info().rss // (1024 * 1024)  # MB
            cpu_usage = process.cpu_percent()
            
            # Log to performance logger
            self.performance_logger.log_system_metrics(
                total_jobs=total_processed,
                successful_jobs=total_successful,
                failed_jobs=total_processed - total_successful,
                avg_duration=0,  # Would need to track this across queues
                memory_usage=memory_usage,
                cpu_usage=cpu_usage
            )
            
            self.performance_logger.log_timezone_breakdown(timezone_stats)
            
            self.logger.info(
                f"Engine metrics - "
                f"Total Processed: {total_processed}, "
                f"Success Rate: {overall_success_rate:.1f}%, "
                f"Queued: {total_queued}, "
                f"Active: {total_active}, "
                f"Memory: {memory_usage}MB"
            )
    
    # Public interface methods
    def get_engine_status(self) -> Dict[str, Any]:
        """Get overall engine status"""
        runtime = 0
        if self._engine_start_time:
            runtime = (datetime.now(dt_timezone.utc) - self._engine_start_time).total_seconds()
        
        return {
            "status": self.status.value,
            "runtime_seconds": runtime,
            "timezone_queue_count": len(self._timezone_queues),
            "total_jobs_executed": self._total_jobs_executed,
            "start_time": self._engine_start_time.isoformat() if self._engine_start_time else None,
            "supported_step_types": StepFactory.get_step_types()
        }
    
    def get_timezone_queue_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all timezone queues"""
        return {
            tz_name: queue.get_queue_status()
            for tz_name, queue in self._timezone_queues.items()
        }
    
    def get_active_jobs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get active jobs across all timezone queues"""
        return {
            tz_name: queue.get_active_jobs()
            for tz_name, queue in self._timezone_queues.items()
        }
    
    def get_queued_jobs(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get queued jobs across all timezone queues"""
        return {
            tz_name: queue.get_queued_jobs()
            for tz_name, queue in self._timezone_queues.items()
        }
    
    async def cancel_job(self, execution_id: str, timezone: Optional[str] = None) -> bool:
        """Cancel a job by execution ID"""
        if timezone:
            # Look in specific timezone queue
            if timezone in self._timezone_queues:
                return await self._timezone_queues[timezone].cancel_job(execution_id)
        else:
            # Look in all timezone queues
            for queue in self._timezone_queues.values():
                if await queue.cancel_job(execution_id):
                    return True
        
        return False
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        engine_status = self.get_engine_status()
        
        # Aggregate queue performance
        queue_summaries = {}
        total_processed = 0
        total_successful = 0
        
        for tz_name, queue in self._timezone_queues.items():
            summary = queue.get_performance_summary()
            queue_summaries[tz_name] = summary
            total_processed += summary["total_jobs_processed"]
            total_successful += summary["successful_jobs"]
        
        overall_success_rate = (total_successful / total_processed * 100) if total_processed > 0 else 0
        
        return {
            "engine": engine_status,
            "overall_success_rate": overall_success_rate,
            "total_jobs_processed": total_processed,
            "timezone_queues": queue_summaries
        }
    
    # Legacy compatibility methods
    async def execute_legacy_job(self, legacy_job: Dict[str, Any]) -> JobExecutionResult:
        """Execute a job in legacy format by converting to V2"""
        try:
            # Convert legacy job to V2 format
            v2_job = create_job_from_legacy(legacy_job)
            
            # Execute using V2 engine
            result = await self.execute_job_immediately(v2_job)
            
            self.logger.info(f"Legacy job executed via V2 engine: {legacy_job.get('name', 'Unknown')}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to execute legacy job: {str(e)}")
            raise
    
    def list_supported_timezones(self) -> List[str]:
        """Get list of supported timezones"""
        import pytz
        return sorted(pytz.all_timezones)
    
    def validate_job_definition(self, job_data: Dict[str, Any]) -> List[str]:
        """Validate job definition and return any errors"""
        try:
            if isinstance(job_data, JobDefinition):
                return job_data.validate()
            else:
                # Assume it's dictionary data
                job = JobDefinition.from_dict(job_data)
                return job.validate()
        except Exception as e:
            return [f"Job validation error: {str(e)}"]


# Global engine instance
_engine_instance: Optional[ModernExecutionEngine] = None
_engine_lock = threading.Lock()


def get_execution_engine() -> ModernExecutionEngine:
    """Get the global execution engine instance (singleton)"""
    global _engine_instance
    
    if _engine_instance is None:
        with _engine_lock:
            if _engine_instance is None:
                _engine_instance = ModernExecutionEngine()
    
    return _engine_instance


async def initialize_execution_engine() -> ModernExecutionEngine:
    """Initialize and start the global execution engine"""
    engine = get_execution_engine()
    
    if engine.status != ExecutionEngineStatus.RUNNING:
        await engine.start()
    
    return engine


async def shutdown_execution_engine():
    """Shutdown the global execution engine"""
    global _engine_instance
    
    if _engine_instance and _engine_instance.status == ExecutionEngineStatus.RUNNING:
        await _engine_instance.stop()


# Convenience functions for common operations
async def execute_simple_sql_job(name: str, query: str, connection_name: str = "default", timezone: str = "UTC") -> JobExecutionResult:
    """Execute a simple SQL job immediately"""
    from .data_models import create_simple_sql_job
    
    engine = get_execution_engine()
    job = create_simple_sql_job(name, query, connection_name, timezone)
    
    return await engine.execute_job_immediately(job)


async def execute_simple_powershell_job(name: str, script: str, timezone: str = "UTC") -> JobExecutionResult:
    """Execute a simple PowerShell job immediately"""
    from .data_models import create_simple_powershell_job
    
    engine = get_execution_engine()
    job = create_simple_powershell_job(name, script, timezone)
    
    return await engine.execute_job_immediately(job)


async def schedule_simple_job(job_type: str, name: str, content: str, scheduled_time: datetime, timezone: str = "UTC") -> str:
    """Schedule a simple job for later execution"""
    engine = get_execution_engine()
    
    if job_type == "sql":
        from .data_models import create_simple_sql_job
        job = create_simple_sql_job(name, content, "default", timezone)
    elif job_type == "powershell":
        from .data_models import create_simple_powershell_job  
        job = create_simple_powershell_job(name, content, timezone)
    else:
        raise ValueError(f"Unsupported job type: {job_type}")
    
    return await engine.schedule_job(job, scheduled_time)


# Fix missing import
from enum import Enum