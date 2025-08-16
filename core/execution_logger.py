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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value,
            'message': self.message,
            'component': self.component,
            'details': self.details
        }


class ExecutionLogger:
    """Captures detailed execution logs for job runs"""
    
    def __init__(self, job_id: str, job_name: str):
        self.job_id = job_id
        self.job_name = job_name
        self.logs: List[ExecutionLogEntry] = []
        self.start_time = datetime.now()
        
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
    
    def _add_log(self, level: LogLevel, message: str, component: str, details: Dict[str, Any]):
        """Add log entry to the list"""
        entry = ExecutionLogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            component=component,
            details=details
        )
        self.logs.append(entry)
    
    def get_logs(self, level_filter: Optional[LogLevel] = None) -> List[ExecutionLogEntry]:
        """Get all logs, optionally filtered by level"""
        if level_filter:
            return [log for log in self.logs if log.level == level_filter]
        return self.logs.copy()
    
    def get_formatted_logs(self, include_details: bool = True) -> str:
        """Get formatted logs as string"""
        lines = []
        lines.append(f"=== Execution Log for {self.job_name} ({self.job_id}) ===")
        lines.append(f"Execution started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        for log in self.logs:
            timestamp = log.timestamp.strftime('%H:%M:%S.%f')[:-3]  # Include milliseconds
            component_str = f" [{log.component}]" if log.component else ""
            lines.append(f"[{timestamp}] {log.level.value}{component_str}: {log.message}")
            
            if include_details and log.details:
                for key, value in log.details.items():
                    lines.append(f"  {key}: {value}")
        
        lines.append("")
        duration = (datetime.now() - self.start_time).total_seconds()
        lines.append(f"Total execution time: {duration:.2f} seconds")
        
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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert all logs to dictionary for JSON serialization"""
        return {
            'job_id': self.job_id,
            'job_name': self.job_name,
            'start_time': self.start_time.isoformat(),
            'logs': [log.to_dict() for log in self.logs],
            'summary': self.get_log_summary()
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