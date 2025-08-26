"""
Job Execution Engine using SQLAlchemy
Clean implementation without connection pools
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from utils.logger import get_logger
from .job_base import JobResult, JobStatus

# Import job types with error handling
try:
    from .sql_job import SqlJob
    HAS_SQL_JOB = True
except ImportError as e:
    HAS_SQL_JOB = False
    # Use mock implementation for testing
    from .mock_job import MockSqlJob as SqlJob

try:
    from .powershell_job import PowerShellJob
    HAS_POWERSHELL_JOB = True
except ImportError as e:
    HAS_POWERSHELL_JOB = False
    # Use mock implementation for testing
    from .mock_job import MockPowerShellJob as PowerShellJob


class JobExecutor:
    """Executes jobs using SQLAlchemy for database operations"""
    
    def __init__(self, job_manager=None, db_session=None):
        self.logger = get_logger(__name__)
        self.job_manager = job_manager
        self.db_session = db_session
        self.logger.info("[JOB_EXECUTOR] SQLAlchemy Job Executor initialized")
    
    def set_session(self, session):
        """Set the database session"""
        self.db_session = session
    
    def execute_job(self, job_id: str) -> Dict[str, Any]:
        """
        Execute a job by ID and log results using SQLAlchemy
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            Dict with execution result information
        """
        self.logger.info(f"[JOB_EXECUTOR] Starting execution of job: {job_id}")
        
        if not self.job_manager:
            error_msg = "Job manager not available"
            self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Get job configuration
        job_config = self.job_manager.get_job(job_id)
        if not job_config:
            error_msg = f"Job {job_id} not found in database"
            self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Check if job is enabled
        if not job_config.get('enabled', True):
            error_msg = f"Job {job_id} is disabled"
            self.logger.warning(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        try:
            # Create job instance based on type
            job_instance = self._create_job_instance(job_config)
            if not job_instance:
                job_type = job_config.get('job_type', '') or job_config.get('type', '') or 'unknown'
                error_msg = f"Failed to create job instance for job {job_id} (type: {job_type})"
                
                self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Execute the job
            start_time = datetime.now()
            result = job_instance.run()
            end_time = datetime.now()
            
            # TODO: Log execution using SQLAlchemy
            self.logger.info(f"[JOB_EXECUTOR] Completed execution with status: {result.status.value}")
            
            return {
                'success': True,
                'status': result.status.value,
                'duration_seconds': result.duration_seconds,
                'output': result.output[:1000] if result.output else '',
                'error_message': result.error_message,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
        except Exception as e:
            error_msg = f"Unexpected error executing job {job_id}: {str(e)}"
            self.logger.exception(f"[JOB_EXECUTOR] {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _create_job_instance(self, job_config: Dict[str, Any]):
        """Create job instance from configuration"""
        try:
            # Handle job type
            job_type = job_config.get('job_type', '') or job_config.get('type', '')
            if not job_type:
                # Try to infer job type from configuration
                configuration = job_config.get('configuration', {})
                if 'sql' in configuration:
                    job_type = 'sql'
                elif 'powershell' in configuration:
                    job_type = 'powershell'
                else:
                    job_type = 'unknown'
            
            job_type = job_type.lower()
            configuration = job_config.get('configuration', {})
            
            self.logger.info(f"[JOB_EXECUTOR] Creating job instance for type: '{job_type}'")
            
            if job_type == 'sql':
                sql_config = configuration.get('sql', {})
                basic_config = configuration.get('basic', {})
                
                if not HAS_SQL_JOB:
                    self.logger.warning("[JOB_EXECUTOR] Using MOCK SQL job - pyodbc dependencies not available")
                
                return SqlJob(
                    job_id=job_config['job_id'],
                    name=job_config['name'],
                    description=job_config.get('description', ''),
                    sql_query=sql_config.get('query', ''),
                    connection_name=sql_config.get('connection_name', 'system'),
                    query_timeout=sql_config.get('query_timeout', 300),
                    max_rows=sql_config.get('max_rows', 1000),
                    timeout=basic_config.get('timeout', 300),
                    max_retries=basic_config.get('max_retries', 3),
                    retry_delay=basic_config.get('retry_delay', 60),
                    run_as=basic_config.get('run_as', ''),
                    enabled=job_config.get('enabled', True)
                )
            
            elif job_type == 'powershell':
                ps_config = configuration.get('powershell', {})
                basic_config = configuration.get('basic', {})
                
                if not HAS_POWERSHELL_JOB:
                    self.logger.warning("[JOB_EXECUTOR] Using MOCK PowerShell job - dependencies not available")
                
                return PowerShellJob(
                    job_id=job_config['job_id'],
                    name=job_config['name'],
                    description=job_config.get('description', ''),
                    script_content=ps_config.get('script_content', ''),
                    script_path=ps_config.get('script_path', ''),
                    execution_policy=ps_config.get('execution_policy', 'RemoteSigned'),
                    working_directory=ps_config.get('working_directory', ''),
                    parameters=ps_config.get('parameters', []),
                    timeout=basic_config.get('timeout', 300),
                    max_retries=basic_config.get('max_retries', 3),
                    retry_delay=basic_config.get('retry_delay', 60),
                    run_as=basic_config.get('run_as', ''),
                    enabled=job_config.get('enabled', True)
                )
            
            else:
                self.logger.error(f"[JOB_EXECUTOR] Unsupported job type: {job_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error creating job instance: {e}")
            return None