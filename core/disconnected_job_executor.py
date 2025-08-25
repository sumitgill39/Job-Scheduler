"""
Disconnected Job Execution Engine for Windows Job Scheduler
Handles job execution with disconnected database logging (no connection pool issues)
"""

import json
import time
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


class DisconnectedJobExecutor:
    """Executes jobs and logs results using disconnected data access (no connection pools)"""
    
    def __init__(self, job_manager, data_manager):
        self.logger = get_logger(__name__)
        
        if not job_manager or not data_manager:
            self.logger.error("[DISCONNECTED_JOB_EXECUTOR] Job manager and data manager are required")
            raise ValueError("Job manager and data manager are required")
        
        self.job_manager = job_manager
        self.data_manager = data_manager
        self.logger.info("[DISCONNECTED_JOB_EXECUTOR] Disconnected job executor initialized - no connection pool issues!")
    
    def execute_job(self, job_id: str) -> Dict[str, Any]:
        """
        Execute a job by ID and log results using disconnected data access
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            Dict with execution result information
        """
        self.logger.info(f"[DISCONNECTED_JOB_EXECUTOR] Starting execution of job: {job_id}")
        
        # Get job configuration from disconnected job manager
        job_config = self.job_manager.get_job(job_id)
        if not job_config:
            error_msg = f"Job {job_id} not found in database"
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Debug: Log the job configuration to understand what we're getting
        self.logger.info(f"[DISCONNECTED_JOB_EXECUTOR] Retrieved job config for {job_id}: {job_config}")
        
        # Check if job is enabled
        if not job_config.get('enabled', True):
            error_msg = f"Job {job_id} is disabled"
            self.logger.warning(f"[DISCONNECTED_JOB_EXECUTOR] {error_msg}")
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
                
                self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Log execution start (using disconnected data manager)
            execution_id = self._log_execution_start(job_config)
            self.logger.info(f"[DISCONNECTED_JOB_EXECUTOR] Started execution {execution_id} for job {job_id}")
            
            # Execute the job
            start_time = datetime.now()
            result = job_instance.run()
            end_time = datetime.now()
            
            # Log execution completion (using disconnected data manager)
            if execution_id:
                self._log_execution_completion(execution_id, result)
            
            self.logger.info(f"[DISCONNECTED_JOB_EXECUTOR] Completed execution {execution_id} with status: {result.status.value}")
            
            return {
                'success': True,
                'execution_id': execution_id,
                'status': result.status.value,
                'duration_seconds': result.duration_seconds,
                'output': result.output[:1000] if result.output else '',  # Limit output for API response
                'error_message': result.error_message,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
        except Exception as e:
            error_msg = f"Unexpected error executing job {job_id}: {str(e)}"
            self.logger.exception(f"[DISCONNECTED_JOB_EXECUTOR] {error_msg}")
            
            # Try to log the failure
            try:
                if 'execution_id' in locals() and execution_id:
                    self._log_execution_failure(execution_id, error_msg)
            except:
                pass
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _create_job_instance(self, job_config: Dict[str, Any]):
        """Create job instance from configuration"""
        try:
            # Handle both old and new field naming for backward compatibility
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
            
            self.logger.info(f"[DISCONNECTED_JOB_EXECUTOR] Creating job instance for type: '{job_type}'")
            
            if job_type == 'sql':
                sql_config = configuration.get('sql', {})
                basic_config = configuration.get('basic', {})
                
                if not HAS_SQL_JOB:
                    self.logger.warning("[DISCONNECTED_JOB_EXECUTOR] Using MOCK SQL job - pyodbc dependencies not available")
                
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
                    self.logger.warning("[DISCONNECTED_JOB_EXECUTOR] Using MOCK PowerShell job - dependencies not available")
                
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
                self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Unsupported job type: {job_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error creating job instance: {e}")
            self.logger.exception(f"[DISCONNECTED_JOB_EXECUTOR] Full exception details:")
            return None
    
    def _log_execution_start(self, job_config: Dict[str, Any]) -> Optional[int]:
        """Log job execution start using disconnected data manager"""
        try:
            # Use disconnected data manager for brief database operation
            insert_query = """
                INSERT INTO job_execution_history 
                (job_id, job_name, status, start_time, retry_count, max_retries, metadata)
                VALUES (?, ?, ?, GETDATE(), 0, ?, ?)
            """
            
            metadata_json = json.dumps({
                'job_type': job_config.get('job_type'),
                'execution_started_by': 'manual',
                'configuration_snapshot': job_config.get('configuration', {})
            })
            
            params = (
                job_config['job_id'],
                job_config['name'],
                JobStatus.RUNNING.value,
                job_config.get('configuration', {}).get('basic', {}).get('max_retries', 3),
                metadata_json
            )
            
            # Execute insert and get the new execution_id
            execution_id = self.data_manager.execute_insert_with_identity(insert_query, params)
            
            self.logger.debug(f"[DISCONNECTED_JOB_EXECUTOR] Logged execution start with ID: {execution_id}")
            return execution_id
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error logging execution start: {e}")
            return None
    
    def _log_execution_completion(self, execution_id: int, result: JobResult):
        """Log job execution completion using disconnected data manager"""
        try:
            update_query = """
                UPDATE job_execution_history 
                SET status = ?, 
                    end_time = GETDATE(), 
                    duration_seconds = ?, 
                    output = ?, 
                    error_message = ?, 
                    return_code = ?,
                    retry_count = ?,
                    metadata = ?
                WHERE execution_id = ?
            """
            
            metadata_json = json.dumps({
                **result.metadata,
                'execution_completed': True,
                'completion_time': datetime.now().isoformat()
            })
            
            params = (
                result.status.value,
                result.duration_seconds,
                result.output,
                result.error_message,
                result.return_code,
                result.retry_count,
                metadata_json,
                execution_id
            )
            
            # Execute update using disconnected data manager
            self.data_manager.execute_non_query(update_query, params)
            
            self.logger.debug(f"[DISCONNECTED_JOB_EXECUTOR] Logged execution completion for ID: {execution_id}")
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error logging execution completion: {e}")
    
    def _log_execution_failure(self, execution_id: int, error_message: str):
        """Log job execution failure using disconnected data manager"""
        try:
            update_query = """
                UPDATE job_execution_history 
                SET status = ?, 
                    end_time = GETDATE(), 
                    error_message = ?,
                    metadata = ?
                WHERE execution_id = ?
            """
            
            metadata_json = json.dumps({
                'execution_failed': True,
                'failure_time': datetime.now().isoformat(),
                'failure_reason': 'executor_error'
            })
            
            params = (
                JobStatus.FAILED.value,
                error_message,
                metadata_json,
                execution_id
            )
            
            # Execute update using disconnected data manager
            self.data_manager.execute_non_query(update_query, params)
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error logging execution failure: {e}")
    
    def get_execution_history(self, job_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job execution history using disconnected data manager"""
        try:
            if job_id:
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    WHERE job_id = ?
                    ORDER BY start_time DESC
                """
                params = (limit, job_id)
            else:
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    ORDER BY start_time DESC
                """
                params = (limit,)
            
            # Use disconnected data manager to execute query
            rows = self.data_manager.execute_query(query, params)
            
            history = []
            for row in rows:
                # Parse metadata JSON
                try:
                    metadata = json.loads(row[12]) if row[12] else {}
                except:
                    metadata = {}
                
                history.append({
                    'execution_id': row[0],
                    'job_id': row[1],
                    'job_name': row[2],
                    'status': row[3],
                    'start_time': row[4].isoformat() if row[4] else None,
                    'end_time': row[5].isoformat() if row[5] else None,
                    'duration_seconds': row[6],
                    'output': row[7],
                    'error_message': row[8],
                    'return_code': row[9],
                    'retry_count': row[10],
                    'max_retries': row[11],
                    'metadata': metadata
                })
            
            self.logger.debug(f"[DISCONNECTED_JOB_EXECUTOR] Retrieved {len(history)} execution records")
            return history
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error getting execution history: {e}")
            return []
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get current status of a job including last execution"""
        try:
            # Get job configuration
            job_config = self.job_manager.get_job(job_id)
            if not job_config:
                return {
                    'success': False,
                    'error': 'Job not found'
                }
            
            # Get latest execution
            history = self.get_execution_history(job_id, limit=1)
            last_execution = history[0] if history else None
            
            return {
                'success': True,
                'job_id': job_id,
                'name': job_config['name'],
                'job_type': job_config['job_type'],
                'enabled': job_config['enabled'],
                'last_execution': last_execution,
                'is_running': last_execution and last_execution['status'] == JobStatus.RUNNING.value if last_execution else False
            }
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_EXECUTOR] Error getting job status: {e}")
            return {
                'success': False,
                'error': str(e)
            }