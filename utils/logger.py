"""
Windows-optimized logging utilities for Job Scheduler
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler, NTEventLogHandler
from pathlib import Path
import yaml
from typing import Optional


class WindowsLogger:
    """Windows-specific logger with Event Log support"""
    
    def __init__(self, name: str = "JobScheduler"):
        self.name = name
        self.logger = None
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load logging configuration from config file"""
        config_path = Path("config/config.yaml")
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('logging', {})
            except Exception:
                pass
        
        # Default configuration
        return {
            'log_file': 'logs\\scheduler.log',
            'max_file_size': '10MB',
            'backup_count': 5,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            'level': 'INFO'
        }
    
    def setup_logger(self, log_level: str = None) -> logging.Logger:
        """Setup logger with file and console handlers"""
        if self.logger:
            return self.logger
        
        # Create logger
        self.logger = logging.getLogger(self.name)
        log_level = log_level or self.config.get('level', 'INFO')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Create formatter
        formatter = logging.Formatter(self.config.get('format'))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_file = self.config.get('log_file', 'logs\\scheduler.log')
        self._ensure_log_directory(log_file)
        
        try:
            max_bytes = self._parse_size(self.config.get('max_file_size', '10MB'))
            backup_count = int(self.config.get('backup_count', 5))
            
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            self.logger.warning(f"Could not setup file handler: {e}")
        
        # Windows Event Log handler (optional)
        try:
            if sys.platform == "win32":
                event_handler = NTEventLogHandler(
                    appname=self.name,
                    logtype="Application"
                )
                event_handler.setLevel(logging.ERROR)
                event_handler.setFormatter(formatter)
                self.logger.addHandler(event_handler)
        except Exception as e:
            self.logger.debug(f"Could not setup Windows Event Log handler: {e}")
        
        # Prevent duplicate logs
        self.logger.propagate = False
        
        self.logger.info(f"Logger initialized for {self.name}")
        return self.logger
    
    def _ensure_log_directory(self, log_file: str):
        """Ensure log directory exists"""
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Could not create log directory {log_dir}: {e}")
    
    def _parse_size(self, size_str: str) -> int:
        """Parse size string like '10MB' to bytes"""
        size_str = size_str.upper().strip()
        if size_str.endswith('KB'):
            return int(size_str[:-2]) * 1024
        elif size_str.endswith('MB'):
            return int(size_str[:-2]) * 1024 * 1024
        elif size_str.endswith('GB'):
            return int(size_str[:-2]) * 1024 * 1024 * 1024
        else:
            return int(size_str)


# Global logger instance
_logger_instance = None


def setup_logger(name: str = "JobScheduler", log_level: str = None) -> logging.Logger:
    """Setup and return logger instance"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = WindowsLogger(name)
    return _logger_instance.setup_logger(log_level)


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    if name:
        return logging.getLogger(name)
    
    global _logger_instance
    if _logger_instance and _logger_instance.logger:
        return _logger_instance.logger
    
    # If no logger setup yet, create default
    return setup_logger()


class JobLogger:
    """Specialized logger for individual jobs"""
    
    def __init__(self, job_name: str, job_id: str):
        self.job_name = job_name
        self.job_id = job_id
        self.base_logger = get_logger()
    
    def info(self, message: str):
        self.base_logger.info(f"[{self.job_name}:{self.job_id}] {message}")
    
    def error(self, message: str):
        self.base_logger.error(f"[{self.job_name}:{self.job_id}] {message}")
    
    def warning(self, message: str):
        self.base_logger.warning(f"[{self.job_name}:{self.job_id}] {message}")
    
    def debug(self, message: str):
        self.base_logger.debug(f"[{self.job_name}:{self.job_id}] {message}")
    
    def exception(self, message: str):
        self.base_logger.exception(f"[{self.job_name}:{self.job_id}] {message}")


if __name__ == "__main__":
    # Test the logger
    logger = setup_logger("TestLogger", "DEBUG")
    logger.info("Logger test - INFO level")
    logger.debug("Logger test - DEBUG level")
    logger.warning("Logger test - WARNING level")
    logger.error("Logger test - ERROR level")