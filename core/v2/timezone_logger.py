"""
Timezone-aware logging system for Job Scheduler V2
Creates separate log files per timezone with structured logging
"""

import os
import logging
import threading
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Optional, Any
from pathlib import Path
import pytz
from logging.handlers import TimedRotatingFileHandler

from utils.logger import get_logger


class TimezoneAwareFormatter(logging.Formatter):
    """Formatter that includes timezone information"""
    
    def __init__(self, timezone_name: str, fmt: Optional[str] = None):
        self.timezone_name = timezone_name
        if not fmt:
            fmt = '[%(asctime)s][{tz}][%(levelname)s][%(name)s] %(message)s'.format(tz=timezone_name)
        super().__init__(fmt)
        
        # Set timezone for formatting
        try:
            self.tz = pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            self.tz = pytz.UTC
    
    def formatTime(self, record, datefmt=None):
        """Format time with timezone awareness"""
        dt = datetime.fromtimestamp(record.created, tz=dt_timezone.utc)
        dt = dt.astimezone(self.tz)
        
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # microseconds to milliseconds


class TimezoneFileHandler(TimedRotatingFileHandler):
    """File handler that creates timezone-specific log files"""
    
    def __init__(self, timezone_name: str, base_dir: str = "logs/timezones"):
        self.timezone_name = timezone_name
        self.base_dir = Path(base_dir)
        
        # Create timezone directory
        self.timezone_dir = self.base_dir / timezone_name.replace('/', '_').replace('\\', '_')
        self.timezone_dir.mkdir(parents=True, exist_ok=True)
        
        # Create daily log file
        log_filename = self.timezone_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        
        super().__init__(
            filename=str(log_filename),
            when='midnight',
            interval=1,
            backupCount=90,  # Keep 90 days of logs
            encoding='utf-8'
        )
        
        # Set formatter
        formatter = TimezoneAwareFormatter(timezone_name)
        self.setFormatter(formatter)
    
    def doRollover(self):
        """Override rollover to use timezone-aware naming"""
        super().doRollover()
        
        # Update filename for new day
        new_filename = self.timezone_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        self.baseFilename = str(new_filename)


class TimezoneLogger:
    """Timezone-specific logger for job execution"""
    
    _instances: Dict[str, "TimezoneLogger"] = {}
    _lock = threading.Lock()
    
    def __init__(self, timezone_name: str):
        self.timezone_name = timezone_name
        self.logger_name = f"timezone.{timezone_name.replace('/', '_')}"
        
        # Create logger
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Add timezone file handler if not already added
        if not self.logger.handlers:
            handler = TimezoneFileHandler(timezone_name)
            handler.setLevel(logging.INFO)
            self.logger.addHandler(handler)
            self.logger.propagate = False
        
        # System logger for debug info
        self.system_logger = get_logger(f"TimezoneLogger.{timezone_name}")
        
        self.system_logger.info(f"Timezone logger initialized for {timezone_name}")
    
    @classmethod
    def get_logger(cls, timezone_name: str) -> "TimezoneLogger":
        """Get or create timezone logger (singleton per timezone)"""
        if timezone_name not in cls._instances:
            with cls._lock:
                if timezone_name not in cls._instances:
                    cls._instances[timezone_name] = cls(timezone_name)
        return cls._instances[timezone_name]
    
    def log_job_queued(self, job_id: str, job_name: str, scheduled_time: datetime, priority: int = 0):
        """Log job queued for execution"""
        self.logger.info(f"[QUEUE][{job_id}] Job '{job_name}' queued for {scheduled_time.isoformat()}, priority: {priority}")
    
    def log_job_started(self, job_id: str, job_name: str, execution_id: str):
        """Log job execution start"""
        self.logger.info(f"[START][{job_id}][{execution_id}] Starting job: {job_name}")
    
    def log_job_completed(self, job_id: str, job_name: str, execution_id: str, status: str, duration: float):
        """Log job execution completion"""
        self.logger.info(f"[COMPLETE][{job_id}][{execution_id}] Job '{job_name}' completed with status: {status}, duration: {duration:.2f}s")
    
    def log_step_started(self, job_id: str, execution_id: str, step_id: str, step_name: str, step_type: str):
        """Log step execution start"""
        self.logger.info(f"[STEP_START][{job_id}][{execution_id}][{step_id}] Executing {step_type} step: {step_name}")
    
    def log_step_completed(self, job_id: str, execution_id: str, step_id: str, step_name: str, status: str, duration: float, output: Optional[str] = None):
        """Log step execution completion"""
        output_snippet = output[:100] + "..." if output and len(output) > 100 else output
        self.logger.info(f"[STEP_{status.upper()}][{job_id}][{execution_id}][{step_id}] Step '{step_name}' completed in {duration:.2f}s" + 
                        (f", output: {output_snippet}" if output_snippet else ""))
    
    def log_error(self, job_id: str, execution_id: str, error_message: str, step_id: Optional[str] = None):
        """Log error during job execution"""
        location = f"[{step_id}]" if step_id else ""
        self.logger.error(f"[ERROR][{job_id}][{execution_id}]{location} {error_message}")
    
    def log_warning(self, job_id: str, execution_id: str, warning_message: str, step_id: Optional[str] = None):
        """Log warning during job execution"""
        location = f"[{step_id}]" if step_id else ""
        self.logger.warning(f"[WARNING][{job_id}][{execution_id}]{location} {warning_message}")
    
    def log_queue_status(self, queue_depth: int, active_jobs: int, avg_wait_time: float):
        """Log queue status metrics"""
        self.logger.info(f"[QUEUE_STATUS] Depth: {queue_depth}, Active: {active_jobs}, Avg Wait: {avg_wait_time:.2f}s")
    
    def log_performance_metrics(self, jobs_per_hour: float, success_rate: float, avg_duration: float, memory_usage: int):
        """Log performance metrics"""
        self.logger.info(f"[PERFORMANCE] Jobs/Hour: {jobs_per_hour:.1f}, Success Rate: {success_rate:.1f}%, Avg Duration: {avg_duration:.2f}s, Memory: {memory_usage}MB")
    
    def get_log_file_path(self) -> Path:
        """Get current log file path"""
        timezone_dir = Path("logs/timezones") / self.timezone_name.replace('/', '_').replace('\\', '_')
        return timezone_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    
    def get_timezone_log_dir(self) -> Path:
        """Get timezone log directory"""
        return Path("logs/timezones") / self.timezone_name.replace('/', '_').replace('\\', '_')


class PerformanceLogger:
    """Logger for system-wide performance metrics"""
    
    def __init__(self):
        self.logger_name = "performance"
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Create performance log directory
        perf_dir = Path("logs/performance")
        perf_dir.mkdir(parents=True, exist_ok=True)
        
        # Add file handler for performance logs
        if not self.logger.handlers:
            handler = TimedRotatingFileHandler(
                filename=str(perf_dir / "system_performance.log"),
                when='midnight',
                interval=1,
                backupCount=365,  # Keep 1 year of performance logs
                encoding='utf-8'
            )
            
            formatter = logging.Formatter(
                '[%(asctime)s][PERFORMANCE][%(levelname)s] %(message)s'
            )
            handler.setFormatter(formatter)
            handler.setLevel(logging.INFO)
            
            self.logger.addHandler(handler)
            self.logger.propagate = False
    
    def log_system_metrics(self, total_jobs: int, successful_jobs: int, failed_jobs: int, 
                          avg_duration: float, memory_usage: int, cpu_usage: float):
        """Log system-wide metrics"""
        success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        metrics = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "total_jobs": total_jobs,
            "successful_jobs": successful_jobs,
            "failed_jobs": failed_jobs,
            "success_rate": success_rate,
            "avg_duration": avg_duration,
            "memory_usage_mb": memory_usage,
            "cpu_usage_percent": cpu_usage
        }
        
        self.logger.info(f"PERFORMANCE_METRICS: {metrics}")
    
    def log_timezone_breakdown(self, timezone_stats: Dict[str, Dict[str, Any]]):
        """Log per-timezone performance breakdown"""
        breakdown = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "timezone_stats": timezone_stats
        }
        
        self.logger.info(f"TIMEZONE_BREAKDOWN: {breakdown}")
    
    def log_queue_performance(self, timezone: str, queue_depth: int, throughput: float, 
                            avg_wait_time: float, worker_count: int):
        """Log queue-specific performance"""
        queue_metrics = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "timezone": timezone,
            "queue_depth": queue_depth,
            "throughput": throughput,
            "avg_wait_time": avg_wait_time,
            "worker_count": worker_count
        }
        
        self.logger.info(f"QUEUE_METRICS: {queue_metrics}")


class AuditLogger:
    """Logger for audit trail and compliance"""
    
    def __init__(self):
        self.logger_name = "audit"
        self.logger = logging.getLogger(self.logger_name)
        self.logger.setLevel(logging.INFO)
        
        # Create audit log directory
        audit_dir = Path("logs/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        # Add file handler for audit logs
        if not self.logger.handlers:
            handler = TimedRotatingFileHandler(
                filename=str(audit_dir / "execution_audit.log"),
                when='midnight',
                interval=1,
                backupCount=2555,  # Keep 7 years for compliance
                encoding='utf-8'
            )
            
            formatter = logging.Formatter(
                '[%(asctime)s][AUDIT][%(levelname)s] %(message)s'
            )
            handler.setFormatter(formatter)
            handler.setLevel(logging.INFO)
            
            self.logger.addHandler(handler)
            self.logger.propagate = False
    
    def log_job_execution(self, job_id: str, job_name: str, execution_id: str, 
                         user: Optional[str], timezone: str, status: str, 
                         duration: float, steps_count: int):
        """Log job execution for audit trail"""
        audit_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": "job_execution",
            "job_id": job_id,
            "job_name": job_name,
            "execution_id": execution_id,
            "user": user or "system",
            "timezone": timezone,
            "status": status,
            "duration": duration,
            "steps_count": steps_count
        }
        
        self.logger.info(f"AUDIT_EVENT: {audit_entry}")
    
    def log_api_access(self, endpoint: str, method: str, user: Optional[str], 
                      ip_address: str, status_code: int):
        """Log API access for security audit"""
        access_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": "api_access",
            "endpoint": endpoint,
            "method": method,
            "user": user or "anonymous",
            "ip_address": ip_address,
            "status_code": status_code
        }
        
        self.logger.info(f"API_ACCESS: {access_entry}")
    
    def log_system_event(self, event_type: str, description: str, user: Optional[str] = None):
        """Log system events for audit trail"""
        system_entry = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "event_type": event_type,
            "description": description,
            "user": user or "system"
        }
        
        self.logger.info(f"SYSTEM_EVENT: {system_entry}")


# Global instances
performance_logger = PerformanceLogger()
audit_logger = AuditLogger()


def get_timezone_logger(timezone_name: str) -> TimezoneLogger:
    """Get timezone logger instance"""
    return TimezoneLogger.get_logger(timezone_name)


def get_performance_logger() -> PerformanceLogger:
    """Get performance logger instance"""
    return performance_logger


def get_audit_logger() -> AuditLogger:
    """Get audit logger instance"""
    return audit_logger


def cleanup_old_logs(retention_days: int = 90):
    """Clean up old log files based on retention policy"""
    import os
    import time
    
    logs_dir = Path("logs")
    current_time = time.time()
    cutoff_time = current_time - (retention_days * 24 * 60 * 60)
    
    deleted_count = 0
    for root, dirs, files in os.walk(logs_dir):
        for file in files:
            if file.endswith('.log'):
                file_path = Path(root) / file
                if file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                    except OSError:
                        pass  # File might be in use
    
    system_logger = get_logger("LogCleanup")
    system_logger.info(f"Cleaned up {deleted_count} old log files (retention: {retention_days} days)")
    
    return deleted_count