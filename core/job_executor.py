"""
Job Execution Engine for Windows Job Scheduler
Handles job execution with database logging
"""

import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
from utils.logger import get_logger
from .job_base import JobResult, JobStatus

# Import database and job manager with error handling
try:
    from database.simple_connection_manager import get_database_manager
    from .job_manager import JobManager
    HAS_DATABASE = True
except ImportError as e:
    HAS_DATABASE = False
    get_database_manager = None
    JobManager = None

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
    """Executes jobs and logs results to database"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        
        if not HAS_DATABASE:
            self.logger.error("[JOB_EXECUTOR] Database dependencies not available - JobExecutor will not function properly")
            self.db_manager = None
            self.job_manager = None
            return
        
        self.db_manager = get_database_manager()
        self.job_manager = JobManager()
        self.logger.info("[JOB_EXECUTOR] Job executor initialized")
    
    def execute_job(self, job_id: str) -> Dict[str, Any]:
        """
        Execute a job by ID and log results to database
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            Dict with execution result information
        """
        self.logger.info(f"[JOB_EXECUTOR] Starting execution of job: {job_id}")
        
        if not HAS_DATABASE or not self.job_manager:
            error_msg = "Database dependencies not available - cannot execute jobs"
            self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Get job configuration from database
        job_config = self.job_manager.get_job(job_id)
        if not job_config:
            error_msg = f"Job {job_id} not found in database"
            self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Debug: Log the job configuration to understand what we're getting
        self.logger.info(f"[JOB_EXECUTOR] Retrieved job config for {job_id}: {job_config}")
        self.logger.info(f"[JOB_EXECUTOR] Job config keys: {list(job_config.keys())}")
        self.logger.info(f"[JOB_EXECUTOR] Job type from config: '{job_config.get('job_type', 'MISSING')}'")
        self.logger.info(f"[JOB_EXECUTOR] Job configuration: {job_config.get('configuration', {})}")
        
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
                # Handle both old and new field naming for backward compatibility  
                job_type = job_config.get('job_type', '') or job_config.get('type', '') or 'unknown'
                error_msg = f"Failed to create job instance for job {job_id} (type: {job_type})"
                
                self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
            
            # Log execution start
            execution_id = self._log_execution_start(job_config)
            self.logger.info(f"[JOB_EXECUTOR] Started execution {execution_id} for job {job_id}")
            
            # Execute the job
            start_time = datetime.now()
            result = job_instance.run()
            end_time = datetime.now()
            
            # Log execution completion
            self._log_execution_completion(execution_id, result)
            
            self.logger.info(f"[JOB_EXECUTOR] Completed execution {execution_id} with status: {result.status.value}")
            
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
            self.logger.exception(f"[JOB_EXECUTOR] {error_msg}")
            
            # Try to log the failure
            try:
                if 'execution_id' in locals():
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
            
            self.logger.info(f"[JOB_EXECUTOR] Creating job instance for type: '{job_type}'")
            self.logger.info(f"[JOB_EXECUTOR] Job config keys: {list(job_config.keys())}")
            self.logger.info(f"[JOB_EXECUTOR] Configuration keys: {list(configuration.keys())}")
            
            # Additional debugging for job type detection
            self.logger.info(f"[JOB_EXECUTOR] Raw job_type field: '{job_config.get('job_type', 'NOT_FOUND')}'")
            self.logger.info(f"[JOB_EXECUTOR] Raw type field: '{job_config.get('type', 'NOT_FOUND')}'")
            self.logger.info(f"[JOB_EXECUTOR] Final determined job_type: '{job_type}'")
            
            if job_type == 'sql':
                sql_config = configuration.get('sql', {})
                basic_config = configuration.get('basic', {})
                
                if not HAS_SQL_JOB:
                    self.logger.warning("[JOB_EXECUTOR] Using MOCK SQL job - pyodbc dependencies not available")
                else:
                    self.logger.debug(f"[JOB_EXECUTOR] Creating SQL job with query: {sql_config.get('query', 'NO_QUERY')[:50]}...")
                
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
                else:
                    self.logger.debug(f"[JOB_EXECUTOR] Creating PowerShell job with script content length: {len(ps_config.get('script_content', ''))}")
                
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
            self.logger.exception(f"[JOB_EXECUTOR] Full exception details:")
            return None
    
    def _log_execution_start(self, job_config: Dict[str, Any]) -> Optional[int]:
        """Log job execution start to database"""
        try:
            system_connection = self.db_manager.get_connection()
            if not system_connection:
                self.logger.error("[JOB_EXECUTOR] Cannot log execution: system database not available")
                return None
            
            cursor = system_connection.cursor()
            
            # Insert execution record
            cursor.execute("""
                INSERT INTO job_execution_history 
                (job_id, job_name, status, start_time, retry_count, max_retries, metadata)
                VALUES (?, ?, ?, GETDATE(), 0, ?, ?)
            """, (
                job_config['job_id'],
                job_config['name'],
                JobStatus.RUNNING.value,
                job_config.get('configuration', {}).get('basic', {}).get('max_retries', 3),
                json.dumps({
                    'job_type': job_config.get('type'),
                    'execution_started_by': 'manual',
                    'configuration_snapshot': job_config.get('configuration', {})
                })
            ))
            
            # Get the execution ID
            cursor.execute("SELECT @@IDENTITY")
            execution_id = cursor.fetchone()[0]
            
            system_connection.commit()
            cursor.close()
            self.db_manager.return_connection(system_connection)
            
            self.logger.debug(f"[JOB_EXECUTOR] Logged execution start with ID: {execution_id}")
            return execution_id
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error logging execution start: {e}")
            try:
                system_connection.rollback()
            except:
                pass
            return None
    
    def _log_execution_completion(self, execution_id: int, result: JobResult):
        """Log job execution completion to database"""
        try:
            system_connection = self.db_manager.get_connection()
            if not system_connection:
                self.logger.error("[JOB_EXECUTOR] Cannot log completion: system database not available")
                return
            
            cursor = system_connection.cursor()
            
            # Update execution record
            cursor.execute("""
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
            """, (
                result.status.value,
                result.duration_seconds,
                result.output,
                result.error_message,
                result.return_code,
                result.retry_count,
                json.dumps({
                    **result.metadata,
                    'execution_completed': True,
                    'completion_time': datetime.now().isoformat()
                }),
                execution_id
            ))
            
            system_connection.commit()
            cursor.close()
            self.db_manager.return_connection(system_connection)
            
            self.logger.debug(f"[JOB_EXECUTOR] Logged execution completion for ID: {execution_id}")
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error logging execution completion: {e}")
            try:
                system_connection.rollback()
            except:
                pass
    
    def _log_execution_failure(self, execution_id: int, error_message: str):
        """Log job execution failure to database"""
        try:
            system_connection = self.db_manager.get_connection()
            if not system_connection:
                return
            
            cursor = system_connection.cursor()
            
            cursor.execute("""
                UPDATE job_execution_history 
                SET status = ?, 
                    end_time = GETDATE(), 
                    error_message = ?,
                    metadata = ?
                WHERE execution_id = ?
            """, (
                JobStatus.FAILED.value,
                error_message,
                json.dumps({
                    'execution_failed': True,
                    'failure_time': datetime.now().isoformat(),
                    'failure_reason': 'executor_error'
                }),
                execution_id
            ))
            
            system_connection.commit()
            cursor.close()
            self.db_manager.return_connection(system_connection)
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error logging execution failure: {e}")
    
    def get_execution_history(self, job_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job execution history from database"""
        try:
            system_connection = self.db_manager.get_connection()
            if not system_connection:
                return []
            
            cursor = system_connection.cursor()
            
            if job_id:
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    WHERE job_id = ?
                    ORDER BY start_time DESC
                """
                cursor.execute(query, (limit, job_id))
            else:
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    ORDER BY start_time DESC
                """
                cursor.execute(query, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            self.db_manager.return_connection(system_connection)
            
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
            
            self.logger.debug(f"[JOB_EXECUTOR] Retrieved {len(history)} execution records")
            return history
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error getting execution history: {e}")
            return []

    def get_execution_history_incremental(self, job_id: str, since_timestamp: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job execution history from database since a specific timestamp"""
        try:
            system_connection = self.db_manager.get_connection()
            if not system_connection:
                return []
            
            cursor = system_connection.cursor()
            
            if since_timestamp:
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    WHERE job_id = ? AND start_time > ?
                    ORDER BY start_time DESC
                """
                cursor.execute(query, (limit, job_id, since_timestamp))
            else:
                # Fall back to regular query if no timestamp provided
                query = """
                    SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time, 
                           duration_seconds, output, error_message, return_code, retry_count, max_retries, metadata
                    FROM job_execution_history 
                    WHERE job_id = ?
                    ORDER BY start_time DESC
                """
                cursor.execute(query, (limit, job_id))
            
            rows = cursor.fetchall()
            cursor.close()
            self.db_manager.return_connection(system_connection)
            
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
            
            self.logger.debug(f"[JOB_EXECUTOR] Retrieved {len(history)} incremental execution records since {since_timestamp}")
            return history
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error getting incremental execution history: {e}")
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
                'job_type': job_config['job_type'],  # Changed from 'type' to 'job_type' for consistency
                'enabled': job_config['enabled'],
                'last_execution': last_execution,
                'is_running': last_execution and last_execution['status'] == JobStatus.RUNNING.value if last_execution else False
            }
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error getting job status: {e}")
            return {
                'success': False,
                'error': str(e)
            }