"""
Execution Logger for capturing detailed job execution logs
"""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class LogLevel(Enum):
    """Log levels for execution logging"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ExecutionLogEntry:
    """Single execution log entry"""
    timestamp: datetime
    level: LogLevel
    message: str
    component: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    


class ExecutionLogger:
    """Captures detailed execution logs for job runs"""
    
    def __init__(self, job_id: str, job_name: str):
        self.job_id = job_id
        self.job_name = job_name
        self.logs: List[ExecutionLogEntry] = []
        self.start_time = datetime.utcnow()  # Use UTC time
        self.utc_start_time = datetime.utcnow()  # Explicit UTC tracking
        
        # Add initial log entry
        self.info("Execution logger initialized", "LOGGER", {
            'job_id': job_id,
            'job_name': job_name
        })
    
    def debug(self, message: str, component: str = "", details: Dict[str, Any] = None):
        """Add debug log entry"""
        self._add_log(LogLevel.DEBUG, message, component, details or {})
    
    def info(self, message: str, component: str = "", details: Dict[str, Any] = None):
        """Add info log entry"""
        self._add_log(LogLevel.INFO, message, component, details or {})
    
    def warning(self, message: str, component: str = "", details: Dict[str, Any] = None):
        """Add warning log entry"""
        self._add_log(LogLevel.WARNING, message, component, details or {})
    
    def error(self, message: str, component: str = "", details: Dict[str, Any] = None):
        """Add error log entry"""
        self._add_log(LogLevel.ERROR, message, component, details or {})
    
    def critical(self, message: str, component: str = "", details: Dict[str, Any] = None):
        """Add critical log entry"""
        self._add_log(LogLevel.CRITICAL, message, component, details or {})
    
    def log_utc_timing(self, event: str, scheduled_time: Optional[datetime] = None, component: str = "UTC_TIMING"):
        """Log UTC timing information for precision analysis"""
        actual_time = datetime.utcnow()
        
        details = {
            'event': event,
            'actual_utc_time': actual_time.isoformat() + 'Z',
            'precision_microseconds': actual_time.microsecond,
        }
        
        if scheduled_time:
            scheduled_utc = scheduled_time if scheduled_time.tzinfo else scheduled_time.replace(tzinfo=None)
            delay_seconds = (actual_time - scheduled_utc).total_seconds() if scheduled_utc else None
            delay_ms = int(delay_seconds * 1000) if delay_seconds is not None else None
            
            details.update({
                'scheduled_utc_time': scheduled_utc.isoformat() + 'Z' if scheduled_utc else None,
                'delay_seconds': delay_seconds,
                'delay_milliseconds': delay_ms,
                'precision_status': 'on_time' if abs(delay_seconds or 0) <= 1.0 else 'delayed'
            })
            
            message = f"UTC {event}: {abs(delay_ms or 0)}ms {'early' if (delay_seconds or 0) < 0 else 'late'}" if delay_ms else f"UTC {event}"
        else:
            message = f"UTC {event} at {actual_time.strftime('%H:%M:%S.%f')[:-3]} UTC"
            
        self.info(message, component, details)
    
    def log_schedule_precision(self, cron_expression: str, expected_time: datetime, actual_time: datetime, component: str = "SCHEDULE_PRECISION"):
        """Log scheduling precision analysis"""
        delay = (actual_time - expected_time).total_seconds()
        delay_ms = int(delay * 1000)
        
        precision_grade = "EXCELLENT" if abs(delay) <= 1.0 else "GOOD" if abs(delay) <= 5.0 else "POOR"
        
        details = {
            'cron_expression': cron_expression,
            'expected_utc': expected_time.isoformat() + 'Z',
            'actual_utc': actual_time.isoformat() + 'Z',
            'delay_seconds': delay,
            'delay_milliseconds': delay_ms,
            'precision_grade': precision_grade,
            'within_1s': abs(delay) <= 1.0,
            'within_5s': abs(delay) <= 5.0
        }
        
        level = LogLevel.INFO if abs(delay) <= 5.0 else LogLevel.WARNING
        message = f"Schedule precision: {delay_ms}ms {'early' if delay < 0 else 'late'} ({precision_grade})"
        
        self._add_log(level, message, component, details)
    
    def _add_log(self, level: LogLevel, message: str, component: str, details: Dict[str, Any]):
        """Add log entry to the list with UTC timestamp"""
        # Always use UTC for consistent timing
        utc_timestamp = datetime.utcnow()
        
        # Add UTC timing information to details
        enhanced_details = details.copy()
        enhanced_details.update({
            'utc_timestamp': utc_timestamp.isoformat() + 'Z',
            'milliseconds_since_start': int((utc_timestamp - self.utc_start_time).total_seconds() * 1000)
        })
        
        entry = ExecutionLogEntry(
            timestamp=utc_timestamp,
            level=level,
            message=message,
            component=component,
            details=enhanced_details
        )
        self.logs.append(entry)
    
    def get_logs(self, level_filter: Optional[LogLevel] = None) -> List[ExecutionLogEntry]:
        """Get all logs, optionally filtered by level"""
        if level_filter:
            return [log for log in self.logs if log.level == level_filter]
        return self.logs.copy()
    
    def get_formatted_logs(self, include_details: bool = True) -> str:
        """Get formatted logs as string with UTC timestamps"""
        lines = []
        lines.append(f"=== UTC Execution Log for {self.job_name} ({self.job_id}) ===")
        lines.append(f"Execution started (UTC): {self.utc_start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
        lines.append("")
        
        for log in self.logs:
            # Format timestamp with UTC indicator and milliseconds
            timestamp = log.timestamp.strftime('%H:%M:%S.%f')[:-3] + ' UTC'
            component_str = f" [{log.component}]" if log.component else ""
            lines.append(f"[{timestamp}] {log.level.value}{component_str}: {log.message}")
            
            if include_details and log.details:
                # Sort details to show UTC timing information first
                sorted_details = sorted(log.details.items(), 
                    key=lambda x: (
                        0 if 'utc' in x[0].lower() else 
                        1 if 'time' in x[0].lower() else 
                        2 if 'delay' in x[0].lower() or 'precision' in x[0].lower() else 3
                    ))
                
                for key, value in sorted_details:
                    if key not in ['utc_timestamp', 'milliseconds_since_start']:  # Avoid duplicate timestamps
                        lines.append(f"  {key}: {value}")
        
        lines.append("")
        current_utc = datetime.utcnow()
        duration = (current_utc - self.utc_start_time).total_seconds()
        lines.append(f"Total execution time: {duration:.3f} seconds (UTC)")
        lines.append(f"Execution completed (UTC): {current_utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} UTC")
        
        return "\n".join(lines)
    
    def get_log_summary(self) -> Dict[str, Any]:
        """Get summary of logs by level"""
        summary = {level.value: 0 for level in LogLevel}
        for log in self.logs:
            summary[log.level.value] += 1
        
        return {
            'total_entries': len(self.logs),
            'by_level': summary,
            'start_time': self.start_time.isoformat(),
            'duration_seconds': (datetime.now() - self.start_time).total_seconds(),
            'has_errors': any(log.level in [LogLevel.ERROR, LogLevel.CRITICAL] for log in self.logs),
            'has_warnings': any(log.level == LogLevel.WARNING for log in self.logs)
        }
    


class ExecutionLoggerContext:
    """Context manager for execution logging"""
    
    def __init__(self, job_id: str, job_name: str):
        self.logger = ExecutionLogger(job_id, job_name)
    
    def __enter__(self) -> ExecutionLogger:
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"Execution failed with exception: {exc_type.__name__}: {exc_val}", "CONTEXT")
        else:
            self.logger.info("Execution completed successfully", "CONTEXT")


# Global execution logger registry for tracking active executions
_active_loggers: Dict[str, ExecutionLogger] = {}


def get_execution_logger(execution_id: str) -> Optional[ExecutionLogger]:
    """Get execution logger by execution ID"""
    return _active_loggers.get(execution_id)


def register_execution_logger(execution_id: str, logger: ExecutionLogger):
    """Register execution logger for an execution ID"""
    _active_loggers[execution_id] = logger


def unregister_execution_logger(execution_id: str):
    """Unregister execution logger"""
    _active_loggers.pop(execution_id, None)


def get_active_executions() -> Dict[str, str]:
    """Get list of active execution IDs and their job names"""
    return {exec_id: logger.job_name for exec_id, logger in _active_loggers.items()}