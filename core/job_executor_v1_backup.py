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
            
            # Generate execution_id for API compatibility
            execution_id = f"{job_id}_{int(start_time.timestamp() * 1000)}"
            
            return {
                'success': True,
                'status': result.status.value,
                'duration_seconds': result.duration_seconds,
                'output': result.output[:1000] if result.output else '',
                'error_message': result.error_message,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'execution_id': execution_id
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
                if not HAS_SQL_JOB:
                    self.logger.warning("[JOB_EXECUTOR] Using MOCK SQL job - pyodbc dependencies not available")
                
                # Extract SQL configuration from the flat configuration format
                return SqlJob(
                    job_id=job_config['job_id'],
                    name=job_config['name'],
                    description=job_config.get('description', ''),
                    sql_query=configuration.get('sql_query', ''),
                    connection_name=configuration.get('connection_name', 'default'),
                    query_timeout=configuration.get('query_timeout', 300),
                    max_rows=configuration.get('max_rows', 1000),
                    timeout=configuration.get('timeout', 300),
                    max_retries=configuration.get('max_retries', 3),
                    retry_delay=configuration.get('retry_delay', 60),
                    run_as=configuration.get('run_as', ''),
                    enabled=job_config.get('enabled', True)
                )
            
            elif job_type == 'powershell':
                if not HAS_POWERSHELL_JOB:
                    self.logger.warning("[JOB_EXECUTOR] Using MOCK PowerShell job - dependencies not available")
                
                # Extract PowerShell configuration from the flat configuration format
                script_content = configuration.get('script_content', '')
                script_path = configuration.get('script_path', '')
                
                # If neither script_content nor script_path is provided, provide a default
                if not script_content and not script_path:
                    self.logger.warning(f"[JOB_EXECUTOR] PowerShell job {job_config['job_id']} has no script_content or script_path. Using default.")
                    script_content = "Write-Host 'No script content provided for this PowerShell job'"
                
                return PowerShellJob(
                    job_id=job_config['job_id'],
                    name=job_config['name'],
                    description=job_config.get('description', ''),
                    script_content=script_content,
                    script_path=script_path,
                    execution_policy=configuration.get('execution_policy', 'RemoteSigned'),
                    working_directory=configuration.get('working_directory', ''),
                    parameters=configuration.get('parameters', []),
                    timeout=configuration.get('timeout', 300),
                    max_retries=configuration.get('max_retries', 3),
                    retry_delay=configuration.get('retry_delay', 60),
                    run_as=configuration.get('run_as', ''),
                    enabled=job_config.get('enabled', True)
                )
            
            else:
                self.logger.error(f"[JOB_EXECUTOR] Unsupported job type: {job_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error creating job instance: {e}")
            return None