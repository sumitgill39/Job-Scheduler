"""
Mock Job implementation for testing when dependencies are missing
"""

import time
from typing import Dict, Any
from datetime import datetime
from .job_base import JobBase, JobResult, JobStatus


class MockSqlJob(JobBase):
    """Mock SQL job for testing when pyodbc is not available"""
    
    def __init__(self, sql_query: str = "", connection_name: str = "system", **kwargs):
        super().__init__(**kwargs)
        self.job_type = "sql"
        self.sql_query = sql_query
        self.connection_name = connection_name
        
        self.job_logger.info(f"Initialized MOCK SQL job (pyodbc not available)")
    
    def execute(self) -> JobResult:
        """Mock SQL execution"""
        start_time = datetime.now()
        
        # Simulate some work
        time.sleep(2)
        
        # Mock successful execution
        return JobResult(
            job_id=self.job_id,
            job_name=self.name,
            status=JobStatus.SUCCESS,
            start_time=start_time,
            end_time=datetime.now(),
            output=f"MOCK EXECUTION: SQL query '{self.sql_query[:50]}...' executed successfully on connection '{self.connection_name}'",
            metadata={
                'mock_execution': True,
                'query': self.sql_query,
                'connection_name': self.connection_name,
                'note': 'This is a mock execution - pyodbc dependencies not available'
            }
        )


class MockPowerShellJob(JobBase):
    """Mock PowerShell job for testing when dependencies are not available"""
    
    def __init__(self, script_content: str = "", script_path: str = "", **kwargs):
        super().__init__(**kwargs)
        self.job_type = "powershell"
        self.script_content = script_content
        self.script_path = script_path
        
        self.job_logger.info(f"Initialized MOCK PowerShell job")
    
    def execute(self) -> JobResult:
        """Mock PowerShell execution"""
        start_time = datetime.now()
        
        # Simulate some work
        time.sleep(1.5)
        
        script_info = self.script_path if self.script_path else f"inline script ({len(self.script_content)} chars)"
        
        # Mock successful execution
        return JobResult(
            job_id=self.job_id,
            job_name=self.name,
            status=JobStatus.SUCCESS,
            start_time=start_time,
            end_time=datetime.now(),
            output=f"MOCK EXECUTION: PowerShell script '{script_info}' executed successfully",
            metadata={
                'mock_execution': True,
                'script_content': self.script_content,
                'script_path': self.script_path,
                'note': 'This is a mock execution - actual PowerShell execution not available'
            }
        )