"""
Complete Scheduler Manager for Windows Job Scheduler
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from threading import Lock
import threading
import signal
import sys

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from .job_base import JobBase, JobStatus, JobResult
from .sql_job import SqlJob
from .powershell_job import PowerShellJob
from database.job_storage import JobStorage
from utils.logger import get_logger, JobLogger


class SchedulerManager:
    """Main scheduler manager for Windows Job Scheduler"""
    
    def __init__(self, storage_type: str = "yaml", storage_config: Dict[str, Any] = None):
        self.logger = get_logger(__name__)
        self.storage = JobStorage(storage_type, storage_config or {})
        self._lock = Lock()
        self._shutdown_event = threading.Event()
        
        # Job registry
        self.jobs: Dict[str, JobBase] = {}
        self.job_schedules: Dict[str, Dict[str, Any]] = {}
        
        # Initialize APScheduler
        self._init_scheduler()
        
        # Load existing jobs
        self._load_jobs_from_storage()
        
        self.logger.info("Scheduler Manager initialized successfully")
    
    def _init_scheduler(self):
        """Initialize APScheduler"""
        jobstores = {'default': MemoryJobStore()}
        executors = {'default': ThreadPoolExecutor(max_workers=20)}
        job_defaults = {'coalesce': False, 'max_instances': 3}
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)
        
        self.logger.info("APScheduler initialized")
    
    def start(self):
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("Scheduler started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            raise
    
    def stop(self, wait: bool = True):
        """Stop the scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=wait)
                self.logger.info("Scheduler stopped successfully")
            self._shutdown_event.set()
        except Exception as e:
            self.logger.error(f"Error stopping scheduler: {e}")
    
    def get_all_jobs(self) -> Dict[str, JobBase]:
        """Get all jobs"""
        return self.jobs.copy()
    
    def get_job(self, job_id: str) -> Optional[JobBase]:
        """Get job by ID"""
        return self.jobs.get(job_id)
    
    def add_job(self, job: JobBase, schedule: Dict[str, Any] = None, start_immediately: bool = False) -> bool:
        """Add a job to the scheduler"""
        try:
            with self._lock:
                if not job.job_id or not job.name:
                    self.logger.error("Job must have valid job_id and name")
                    return False
                
                self.jobs[job.job_id] = job
                job_config = job.to_dict()
                
                if not self.storage.save_job(job_config):
                    self.logger.error(f"Failed to save job configuration: {job.job_id}")
                    return False
                
                if schedule:
                    self.schedule_job(job.job_id, schedule)
                
                if start_immediately:
                    self.run_job_once(job.job_id)
                
                self.logger.info(f"Added job: {job.name} ({job.job_id})")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to add job {job.job_id}: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler"""
        try:
            with self._lock:
                if self.scheduler.get_job(job_id):
                    self.scheduler.remove_job(job_id)
                
                if job_id in self.jobs:
                    del self.jobs[job_id]
                
                if job_id in self.job_schedules:
                    del self.job_schedules[job_id]
                
                self.storage.delete_job(job_id)
                self.logger.info(f"Removed job: {job_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to remove job {job_id}: {e}")
            return False
    
    def schedule_job(self, job_id: str, schedule_config: Dict[str, Any]) -> bool:
        """Schedule a job"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                self.logger.error(f"Job not found for scheduling: {job_id}")
                return False
            
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            trigger = self._create_trigger(schedule_config)
            if not trigger:
                return False
            
            self.scheduler.add_job(
                func=self._execute_job_wrapper,
                args=[job_id],
                trigger=trigger,
                id=job_id,
                name=job.name,
                replace_existing=True
            )
            
            self.job_schedules[job_id] = schedule_config
            
            scheduler_job = self.scheduler.get_job(job_id)
            if scheduler_job:
                job.next_run_time = scheduler_job.next_run_time
            
            self.logger.info(f"Scheduled job: {job.name} ({job_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to schedule job {job_id}: {e}")
            return False
    
    def _create_trigger(self, schedule_config: Dict[str, Any]):
        """Create APScheduler trigger from configuration with timezone support"""
        trigger_type = schedule_config.get('type', 'cron').lower()
        timezone = schedule_config.get('timezone', 'UTC')
        
        try:
            # Import timezone handling
            from pytz import timezone as pytz_timezone
            tz = pytz_timezone(timezone) if timezone != 'UTC' else None
            
            if trigger_type == 'cron':
                cron_expr = schedule_config.get('cron')
                if cron_expr:
                    parts = cron_expr.split()
                    if len(parts) == 6:
                        trigger_kwargs = {
                            'second': parts[0], 
                            'minute': parts[1], 
                            'hour': parts[2],
                            'day': parts[3], 
                            'month': parts[4], 
                            'day_of_week': parts[5]
                        }
                        if tz:
                            trigger_kwargs['timezone'] = tz
                        return CronTrigger(**trigger_kwargs)
            
            elif trigger_type == 'interval':
                interval_config = schedule_config.get('interval', {})
                trigger_kwargs = {
                    'weeks': interval_config.get('weeks', 0),
                    'days': interval_config.get('days', 0),
                    'hours': interval_config.get('hours', 0),
                    'minutes': interval_config.get('minutes', 0),
                    'seconds': interval_config.get('seconds', 0)
                }
                if tz:
                    trigger_kwargs['timezone'] = tz
                return IntervalTrigger(**trigger_kwargs)
            
            elif trigger_type == 'date':
                run_date = schedule_config.get('run_date')
                if isinstance(run_date, str):
                    # Parse as UTC datetime since frontend converts to UTC
                    run_date = datetime.fromisoformat(run_date.replace('Z', '+00:00'))
                trigger_kwargs = {'run_date': run_date}
                if tz:
                    trigger_kwargs['timezone'] = tz
                return DateTrigger(**trigger_kwargs)
            
        except Exception as e:
            self.logger.error(f"Failed to create trigger with timezone {timezone}: {e}")
            # Fallback to UTC if timezone handling fails
            try:
                if trigger_type == 'cron':
                    cron_expr = schedule_config.get('cron')
                    if cron_expr:
                        parts = cron_expr.split()
                        if len(parts) == 6:
                            return CronTrigger(
                                second=parts[0], minute=parts[1], hour=parts[2],
                                day=parts[3], month=parts[4], day_of_week=parts[5]
                            )
                elif trigger_type == 'interval':
                    interval_config = schedule_config.get('interval', {})
                    return IntervalTrigger(
                        weeks=interval_config.get('weeks', 0),
                        days=interval_config.get('days', 0),
                        hours=interval_config.get('hours', 0),
                        minutes=interval_config.get('minutes', 0),
                        seconds=interval_config.get('seconds', 0)
                    )
                elif trigger_type == 'date':
                    run_date = schedule_config.get('run_date')
                    if isinstance(run_date, str):
                        run_date = datetime.fromisoformat(run_date.replace('Z', '+00:00'))
                    return DateTrigger(run_date=run_date)
            except Exception as fallback_error:
                self.logger.error(f"Fallback trigger creation also failed: {fallback_error}")
        
        return None
    
    def run_job_once(self, job_id: str) -> Optional[JobResult]:
        """Run job immediately once"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                self.logger.error(f"Job not found: {job_id}")
                return None
            
            self.logger.info(f"Running job once: {job.name} ({job_id})")
            result = job.run()
            self.storage.save_execution_result(result)
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to run job {job_id}: {e}")
            return None
    
    def _execute_job_wrapper(self, job_id: str):
        """Wrapper function for job execution in scheduler"""
        try:
            job = self.jobs.get(job_id)
            if not job:
                self.logger.error(f"Job not found during execution: {job_id}")
                return
            
            result = job.run()
            self.storage.save_execution_result(result)
            
            if result.status == JobStatus.RETRY:
                self._schedule_retry(job_id, job.retry_delay)
            
        except Exception as e:
            self.logger.error(f"Error in job execution wrapper for {job_id}: {e}")
    
    def _schedule_retry(self, job_id: str, delay_seconds: int):
        """Schedule job retry"""
        try:
            retry_time = datetime.now() + timedelta(seconds=delay_seconds)
            
            self.scheduler.add_job(
                func=self._execute_job_wrapper,
                args=[job_id],
                trigger=DateTrigger(run_date=retry_time),
                id=f"{job_id}_retry_{int(retry_time.timestamp())}",
                replace_existing=True
            )
            
            self.logger.info(f"Scheduled retry for job {job_id} at {retry_time}")
            
        except Exception as e:
            self.logger.error(f"Failed to schedule retry for job {job_id}: {e}")
    
    def _on_job_executed(self, event):
        """Handle job execution completion"""
        self.logger.debug(f"Job executed: {event.job_id}")
    
    def _on_job_error(self, event):
        """Handle job execution error"""
        self.logger.error(f"Job error {event.job_id}: {event.exception}")
    
    def _on_job_missed(self, event):
        """Handle missed job execution"""
        self.logger.warning(f"Job missed: {event.job_id}")
    
    def _load_jobs_from_storage(self):
        """Load jobs from storage on startup"""
        try:
            job_configs = self.storage.load_all_jobs()
            
            for job_id, job_config in job_configs.items():
                try:
                    job = self._create_job_from_config(job_config)
                    if job:
                        self.jobs[job_id] = job
                        
                        schedule_config = job_config.get('schedule')
                        if schedule_config and job.enabled:
                            self.schedule_job(job_id, schedule_config)
                        
                        self.logger.info(f"Loaded job: {job.name} ({job_id})")
                    
                except Exception as e:
                    self.logger.error(f"Failed to load job {job_id}: {e}")
            
            self.logger.info(f"Loaded {len(self.jobs)} jobs from storage")
            
        except Exception as e:
            self.logger.error(f"Failed to load jobs from storage: {e}")
    
    def _create_job_from_config(self, job_config: Dict[str, Any]) -> Optional[JobBase]:
        """Create job instance from configuration"""
        job_type = job_config.get('job_type')
        
        try:
            if job_type == 'sql':
                return SqlJob.from_dict(job_config)
            elif job_type == 'powershell':
                return PowerShellJob.from_dict(job_config)
            else:
                self.logger.error(f"Unknown job type: {job_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to create job from config: {e}")
            return None
    
    def create_sql_job(self, name: str, sql_query: str, connection_name: str = "default",
                       schedule: Dict[str, Any] = None, **kwargs) -> Optional[str]:
        """Create a new SQL job"""
        try:
            job = SqlJob(
                name=name,
                sql_query=sql_query,
                connection_name=connection_name,
                **kwargs
            )
            
            if schedule:
                job_config = job.to_dict()
                job_config['schedule'] = schedule
                self.storage.save_job(job_config)
            
            success = self.add_job(job, schedule)
            
            if success:
                self.logger.info(f"Created SQL job: {name} ({job.job_id})")
                return job.job_id
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to create SQL job {name}: {e}")
            return None
    
    def create_powershell_job(self, name: str, script_path: str = None, 
                             script_content: str = None, parameters: List[str] = None,
                             schedule: Dict[str, Any] = None, **kwargs) -> Optional[str]:
        """Create a new PowerShell job"""
        try:
            job = PowerShellJob(
                name=name,
                script_path=script_path,
                script_content=script_content,
                parameters=parameters or [],
                **kwargs
            )
            
            if schedule:
                job_config = job.to_dict()
                job_config['schedule'] = schedule
                self.storage.save_job(job_config)
            
            success = self.add_job(job, schedule)
            
            if success:
                self.logger.info(f"Created PowerShell job: {name} ({job.job_id})")
                return job.job_id
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to create PowerShell job {name}: {e}")
            return None
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status information"""
        try:
            scheduled_jobs = self.scheduler.get_jobs()
            
            return {
                'running': self.scheduler.running,
                'total_jobs': len(self.jobs),
                'scheduled_jobs': len(scheduled_jobs),
                'enabled_jobs': len([j for j in self.jobs.values() if j.enabled]),
                'disabled_jobs': len([j for j in self.jobs.values() if not j.enabled]),
                'job_types': self._get_job_type_counts(),
                'next_run_times': self._get_next_run_times(),
                'uptime': "Available in future version"
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get scheduler status: {e}")
            return {'error': str(e)}
    
    def _get_job_type_counts(self) -> Dict[str, int]:
        """Get count of jobs by type"""
        counts = {}
        for job in self.jobs.values():
            counts[job.job_type] = counts.get(job.job_type, 0) + 1
        return counts
    
    def _get_next_run_times(self) -> List[Dict[str, Any]]:
        """Get next run times for scheduled jobs"""
        next_runs = []
        
        for scheduled_job in self.scheduler.get_jobs():
            job = self.jobs.get(scheduled_job.id)
            if job and scheduled_job.next_run_time:
                next_runs.append({
                    'job_id': scheduled_job.id,
                    'job_name': job.name,
                    'next_run_time': scheduled_job.next_run_time.isoformat(),
                    'job_type': job.job_type
                })
        
        next_runs.sort(key=lambda x: x['next_run_time'])
        return next_runs[:10]
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status for a specific job"""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        scheduled_job = self.scheduler.get_job(job_id)
        
        return {
            'job_id': job_id,
            'name': job.name,
            'job_type': job.job_type,
            'enabled': job.enabled,
            'current_status': job.current_status.value,
            'is_running': job.is_running,
            'last_run_time': job.last_run_time.isoformat() if job.last_run_time else None,
            'next_run_time': scheduled_job.next_run_time.isoformat() if scheduled_job and scheduled_job.next_run_time else None,
            'retry_count': job.retry_count,
            'max_retries': job.max_retries,
            'execution_history_count': len(job.execution_history),
            'last_result': job.get_last_result().to_dict() if job.get_last_result() else None,
            'schedule': self.job_schedules.get(job_id)
        }
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a job"""
        try:
            history = self.storage.get_job_history(job_id, limit)
            
            job = self.jobs.get(job_id)
            if job and not history:
                history = [result.to_dict() for result in job.get_execution_history(limit)]
            
            return history
            
        except Exception as e:
            self.logger.error(f"Failed to get execution history for {job_id}: {e}")
            return []
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a job"""
        try:
            job = self.jobs.get(job_id)
            if job:
                job.enabled = False
                
                if self.scheduler.get_job(job_id):
                    self.scheduler.pause_job(job_id)
                
                job_config = job.to_dict()
                self.storage.save_job(job_config)
                
                self.logger.info(f"Paused job: {job_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to pause job {job_id}: {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        try:
            job = self.jobs.get(job_id)
            if job:
                job.enabled = True
                
                if self.scheduler.get_job(job_id):
                    self.scheduler.resume_job(job_id)
                else:
                    schedule = self.job_schedules.get(job_id)
                    if schedule:
                        self.schedule_job(job_id, schedule)
                
                job_config = job.to_dict()
                self.storage.save_job(job_config)
                
                self.logger.info(f"Resumed job: {job_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to resume job {job_id}: {e}")
            return False