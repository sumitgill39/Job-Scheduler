"""
Integrated Scheduler that bridges JobManager (database) and APScheduler
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

from utils.logger import get_logger
from .job_manager import JobManager
from .job_executor import JobExecutor


class IntegratedScheduler:
    """
    Integrated scheduler that combines database job management with APScheduler
    
    This service:
    - Uses JobManager for job storage (SQL Server database)
    - Uses APScheduler for actual job scheduling
    - Provides unified API for job creation, scheduling, and execution
    """
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        # Initialize components
        self.job_manager = JobManager()
        self.job_executor = JobExecutor()
        
        # Initialize APScheduler
        self._init_scheduler()
        
        # Load existing scheduled jobs from database
        self._load_scheduled_jobs()
        
        self.logger.info("[INTEGRATED_SCHEDULER] Integrated scheduler initialized")
    
    def _init_scheduler(self):
        """Initialize APScheduler"""
        jobstores = {'default': MemoryJobStore()}
        executors = {'default': ThreadPoolExecutor(max_workers=10)}
        job_defaults = {
            'coalesce': True,  # Combine multiple pending executions
            'max_instances': 1,  # Only one instance of job can run at a time
            'misfire_grace_time': 30  # Grace period for missed jobs
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        # Add event listeners
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)
        
        self.logger.info("[INTEGRATED_SCHEDULER] APScheduler configured")
    
    def start(self):
        """Start the scheduler"""
        try:
            if not self.scheduler.running:
                self.scheduler.start()
                self.logger.info("[INTEGRATED_SCHEDULER] Scheduler started successfully")
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Failed to start scheduler: {e}")
            raise
    
    def stop(self, wait: bool = True):
        """Stop the scheduler"""
        try:
            if self.scheduler.running:
                self.scheduler.shutdown(wait=wait)
                self.logger.info("[INTEGRATED_SCHEDULER] Scheduler stopped successfully")
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error stopping scheduler: {e}")
    
    def create_job_with_schedule(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a job in database and schedule it if scheduling is enabled
        
        Args:
            job_data: Job configuration including optional schedule
            
        Returns:
            Dict with success status and job_id or error message
        """
        try:
            # Create job in database first
            result = self.job_manager.create_job(job_data)
            
            if not result['success']:
                return result
            
            job_id = result['job_id']
            
            # If job has schedule configuration, schedule it
            schedule_config = job_data.get('schedule')
            if schedule_config:
                schedule_result = self.schedule_job(job_id, schedule_config)
                if not schedule_result['success']:
                    self.logger.warning(f"[INTEGRATED_SCHEDULER] Job {job_id} created but scheduling failed: {schedule_result['error']}")
                    # Don't fail the job creation, just warn
                    result['warning'] = f"Job created but scheduling failed: {schedule_result['error']}"
                else:
                    self.logger.info(f"[INTEGRATED_SCHEDULER] Job {job_id} created and scheduled successfully")
                    result['scheduled'] = True
            
            return result
            
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error creating job with schedule: {e}")
            return {
                'success': False,
                'error': f'Error creating job: {str(e)}'
            }
    
    def schedule_job(self, job_id: str, schedule_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule an existing job using APScheduler
        
        Args:
            job_id: Job ID to schedule
            schedule_config: Schedule configuration (cron, interval, or date)
            
        Returns:
            Dict with success status
        """
        try:
            # Get job from database
            job_config = self.job_manager.get_job(job_id)
            if not job_config:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            # Only schedule enabled jobs
            if not job_config.get('enabled', True):
                return {
                    'success': False,
                    'error': f'Job {job_id} is disabled'
                }
            
            # Remove existing schedule if any
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                self.logger.debug(f"[INTEGRATED_SCHEDULER] Removed existing schedule for job {job_id}")
            
            # Create trigger from schedule configuration
            trigger = self._create_trigger(schedule_config)
            if not trigger:
                return {
                    'success': False,
                    'error': 'Invalid schedule configuration'
                }
            
            # Add job to scheduler
            self.scheduler.add_job(
                func=self._execute_scheduled_job,
                args=[job_id],
                trigger=trigger,
                id=job_id,
                name=job_config.get('name', f'Job {job_id}'),
                replace_existing=True
            )
            
            self.logger.info(f"[INTEGRATED_SCHEDULER] Scheduled job {job_id} with {schedule_config.get('type', 'unknown')} trigger")
            return {
                'success': True,
                'message': f'Job {job_id} scheduled successfully'
            }
            
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error scheduling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error scheduling job: {str(e)}'
            }
    
    def unschedule_job(self, job_id: str) -> Dict[str, Any]:
        """Remove job from scheduler (but keep in database)"""
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                self.logger.info(f"[INTEGRATED_SCHEDULER] Unscheduled job {job_id}")
                return {
                    'success': True,
                    'message': f'Job {job_id} unscheduled successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Job {job_id} is not scheduled'
                }
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error unscheduling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error unscheduling job: {str(e)}'
            }
    
    def _create_trigger(self, schedule_config: Dict[str, Any]):
        """Create APScheduler trigger from schedule configuration"""
        try:
            schedule_type = schedule_config.get('type', '').lower()
            
            if schedule_type == 'cron':
                cron_expr = schedule_config.get('cron', '')
                if cron_expr:
                    # Parse cron expression (6 parts: second minute hour day month day_of_week)
                    parts = cron_expr.split()
                    if len(parts) == 6:
                        return CronTrigger(
                            second=parts[0],
                            minute=parts[1], 
                            hour=parts[2],
                            day=parts[3],
                            month=parts[4],
                            day_of_week=parts[5]
                        )
                    else:
                        self.logger.error(f"[INTEGRATED_SCHEDULER] Invalid cron expression: {cron_expr} (expected 6 parts)")
                        return None
            
            elif schedule_type == 'interval':
                interval_config = schedule_config.get('interval', {})
                return IntervalTrigger(
                    days=interval_config.get('days', 0),
                    hours=interval_config.get('hours', 0),
                    minutes=interval_config.get('minutes', 0),
                    seconds=interval_config.get('seconds', 0)
                )
            
            elif schedule_type == 'date' or schedule_type == 'once':
                run_date = schedule_config.get('run_date')
                if isinstance(run_date, str):
                    run_date = datetime.fromisoformat(run_date)
                elif not isinstance(run_date, datetime):
                    self.logger.error(f"[INTEGRATED_SCHEDULER] Invalid run_date format: {run_date}")
                    return None
                
                return DateTrigger(run_date=run_date)
            
            else:
                self.logger.error(f"[INTEGRATED_SCHEDULER] Unknown schedule type: {schedule_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error creating trigger: {e}")
            return None
    
    def _execute_scheduled_job(self, job_id: str):
        """Execute a scheduled job using JobExecutor"""
        try:
            self.logger.info(f"[INTEGRATED_SCHEDULER] Executing scheduled job: {job_id}")
            
            # Use JobExecutor to run the job
            result = self.job_executor.execute_job(job_id)
            
            if result['success']:
                self.logger.info(f"[INTEGRATED_SCHEDULER] Scheduled job {job_id} completed with status: {result['status']}")
            else:
                self.logger.error(f"[INTEGRATED_SCHEDULER] Scheduled job {job_id} failed: {result['error']}")
                
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error executing scheduled job {job_id}: {e}")
    
    def _load_scheduled_jobs(self):
        """Load jobs with schedules from database and schedule them"""
        try:
            jobs = self.job_manager.list_jobs(enabled_only=True)
            scheduled_count = 0
            
            for job in jobs:
                job_id = job['job_id']
                
                # Get full job configuration
                job_config = self.job_manager.get_job(job_id)
                if not job_config:
                    continue
                
                # Check if job has schedule configuration
                configuration = job_config.get('configuration', {})
                schedule_config = configuration.get('schedule')
                
                if schedule_config:
                    result = self.schedule_job(job_id, schedule_config)
                    if result['success']:
                        scheduled_count += 1
                    else:
                        self.logger.warning(f"[INTEGRATED_SCHEDULER] Failed to schedule job {job_id}: {result['error']}")
            
            self.logger.info(f"[INTEGRATED_SCHEDULER] Loaded and scheduled {scheduled_count} jobs from database")
            
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error loading scheduled jobs: {e}")
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get comprehensive scheduler status"""
        try:
            # Get scheduled jobs from APScheduler
            scheduled_jobs = self.scheduler.get_jobs()
            
            # Get all jobs from database
            all_jobs = self.job_manager.list_jobs()
            enabled_jobs = [j for j in all_jobs if j.get('enabled', True)]
            
            return {
                'running': self.scheduler.running,
                'total_jobs': len(all_jobs),
                'enabled_jobs': len(enabled_jobs),
                'scheduled_jobs': len(scheduled_jobs),
                'disabled_jobs': len(all_jobs) - len(enabled_jobs),
                'job_types': self._get_job_type_counts(all_jobs),
                'next_run_times': self._get_next_run_times(scheduled_jobs),
                'status': 'running' if self.scheduler.running else 'stopped'
            }
            
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error getting scheduler status: {e}")
            return {'error': str(e)}
    
    def _get_job_type_counts(self, jobs: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get count of jobs by type"""
        counts = {}
        for job in jobs:
            job_type = job.get('job_type', 'unknown')
            counts[job_type] = counts.get(job_type, 0) + 1
        return counts
    
    def _get_next_run_times(self, scheduled_jobs) -> List[Dict[str, Any]]:
        """Get next run times for scheduled jobs"""
        next_runs = []
        
        for scheduled_job in scheduled_jobs:
            job_config = self.job_manager.get_job(scheduled_job.id)
            if job_config and scheduled_job.next_run_time:
                next_runs.append({
                    'job_id': scheduled_job.id,
                    'job_name': job_config.get('name', 'Unknown'),
                    'job_type': job_config.get('job_type', 'unknown'),
                    'next_run_time': scheduled_job.next_run_time.isoformat()
                })
        
        # Sort by next run time
        next_runs.sort(key=lambda x: x['next_run_time'])
        return next_runs[:10]  # Return top 10 next runs
    
    def run_job_now(self, job_id: str) -> Dict[str, Any]:
        """Execute job immediately (one-time execution)"""
        try:
            return self.job_executor.execute_job(job_id)
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error running job {job_id} now: {e}")
            return {
                'success': False,
                'error': f'Error running job: {str(e)}'
            }
    
    def update_job_schedule(self, job_id: str, schedule_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """Update job schedule (or remove schedule if None)"""
        try:
            if schedule_config:
                return self.schedule_job(job_id, schedule_config)
            else:
                return self.unschedule_job(job_id)
        except Exception as e:
            self.logger.error(f"[INTEGRATED_SCHEDULER] Error updating job schedule for {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating schedule: {str(e)}'
            }
    
    # Event handlers
    def _on_job_executed(self, event):
        """Handle successful job execution"""
        self.logger.debug(f"[INTEGRATED_SCHEDULER] Job executed successfully: {event.job_id}")
    
    def _on_job_error(self, event):
        """Handle job execution error"""
        self.logger.error(f"[INTEGRATED_SCHEDULER] Job execution error for {event.job_id}: {event.exception}")
    
    def _on_job_missed(self, event):
        """Handle missed job execution"""
        self.logger.warning(f"[INTEGRATED_SCHEDULER] Job missed: {event.job_id}")