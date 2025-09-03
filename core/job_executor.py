"""
Unified Job Executor - Consolidated V1 and V2 execution functionality
Handles both JSON (V1) and YAML (V2) job execution in a single executor
"""

import yaml
import json
import uuid
import asyncio
import subprocess
import tempfile
import os
import time
import psutil
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from utils.logger import get_logger
from .job_manager import JobManager
from .job_base import JobResult, JobStatus

# Import job types with error handling
try:
    from .sql_job import SqlJob
    HAS_SQL_JOB = True
except ImportError as e:
    HAS_SQL_JOB = False
    # Use mock implementation for testing
    try:
        from .mock_job import MockSqlJob as SqlJob
    except ImportError:
        SqlJob = None

try:
    from .powershell_job import PowerShellJob
    HAS_POWERSHELL_JOB = True
except ImportError as e:
    HAS_POWERSHELL_JOB = False
    # Use mock implementation for testing
    try:
        from .mock_job import MockPowerShellJob as PowerShellJob
    except ImportError:
        PowerShellJob = None


class JobExecutor:
    """Unified job executor supporting both V1 (JSON) and V2 (YAML) formats"""
    
    def __init__(self, job_manager=None, db_session=None):
        self.logger = get_logger(__name__)
        self.job_manager = job_manager or JobManager()
        self.db_session = db_session
        self.logger.info("[JOB_EXECUTOR] Unified Job Executor initialized (V1 + V2 support)")
    
    def set_session(self, session):
        """Set the database session"""
        self.db_session = session
    
    def execute_job(self, job_id: str) -> Dict[str, Any]:
        """
        Execute a job by ID (automatically detects V1 or V2 format)
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            Dict with execution result information
        """
        print(f"**** JobExecutor.execute_job() called with job_id: {job_id} ****")
        self.logger.info(f"[JOB_EXECUTOR] Starting execution of job: {job_id}")
        
        if not self.job_manager:
            error_msg = "Job manager not available"
            self.logger.error(f"[JOB_EXECUTOR] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Get job configuration with auto-detection
        job_config = self.job_manager.get_job(job_id, version='auto')
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
        
        # Determine job version and execute accordingly
        job_version = job_config.get('_version', 'v1')
        self.logger.info(f"[JOB_EXECUTOR] Job {job_id} detected as version: {job_version}")
        
        try:
            if job_version == 'v2':
                self.logger.info(f"[JOB_EXECUTOR] Executing job {job_id} via V2 path")
                return self._execute_v2_job(job_config)
            else:
                self.logger.info(f"[JOB_EXECUTOR] Executing job {job_id} via V1 path")
                return self._execute_v1_job(job_config)
                
        except Exception as e:
            error_msg = f"Unexpected error executing job {job_id}: {str(e)}"
            self.logger.exception(f"[JOB_EXECUTOR] {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _execute_v1_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute V1 job using traditional job classes"""
        job_id = job_config['job_id']
        
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
            
            self.logger.info(f"[JOB_EXECUTOR] V1 job completed with status: {result.status.value}")
            
            # Generate execution_id for API compatibility (use UUID to avoid database truncation)
            import uuid
            execution_id = str(uuid.uuid4())
            
            # Record execution in database for V1 jobs
            try:
                execution_data = {
                    'execution_id': execution_id,
                    'job_id': job_id,
                    'job_name': job_config.get('name', 'Unknown Job'),
                    'status': 'SUCCESS' if result.status == JobStatus.SUCCESS else 'FAILED',
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_seconds': result.duration_seconds,
                    'output_log': result.output if result.output else '',
                    'error_message': result.error_message if result.error_message else None,
                    'return_code': 0 if result.status == JobStatus.SUCCESS else 1,
                    'execution_mode': 'manual',
                    'executed_by': 'api',
                    'execution_timezone': 'UTC'
                }
                
                self.job_manager.record_execution(execution_data)
                self.logger.info(f"[JOB_EXECUTOR] V1 execution recorded to database: {execution_id}")
            except Exception as e:
                self.logger.warning(f"[JOB_EXECUTOR] Failed to record V1 execution: {e}")
            
            return {
                'success': result.status == JobStatus.SUCCESS,
                'status': result.status.value,
                'duration_seconds': result.duration_seconds,
                'output': result.output[:1000] if result.output else '',
                'error_message': result.error_message,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'execution_id': execution_id,
                '_version': 'v1'
            }
            
        except Exception as e:
            error_msg = f"Error executing V1 job {job_id}: {str(e)}"
            self.logger.exception(f"[JOB_EXECUTOR] {error_msg}")
            
            # Record failed execution for V1 jobs
            try:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds() if 'start_time' in locals() else 0
                execution_id = f"{job_id}_{int(time.time() * 1000)}"
                
                execution_data = {
                    'execution_id': execution_id,
                    'job_id': job_id,
                    'job_name': job_config.get('name', 'Unknown Job'),
                    'status': 'FAILED',
                    'start_time': locals().get('start_time', datetime.now()),
                    'end_time': end_time,
                    'duration_seconds': duration,
                    'output_log': '',
                    'error_message': error_msg,
                    'return_code': -1,
                    'execution_mode': 'manual',
                    'executed_by': 'api',
                    'execution_timezone': 'UTC'
                }
                
                self.job_manager.record_execution(execution_data)
                self.logger.info(f"[JOB_EXECUTOR] V1 failed execution recorded to database: {execution_id}")
            except Exception as db_error:
                self.logger.warning(f"[JOB_EXECUTOR] Failed to record V1 failed execution: {db_error}")
            
            return {
                'success': False,
                'error': error_msg,
                '_version': 'v1'
            }
    
    def _execute_v2_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute V2 job using YAML-based async execution"""
        job_id = job_config['job_id']
        
        try:
            # Run async execution synchronously - handle existing event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in an async context, we need to use a different approach
                import threading
                import concurrent.futures
                
                def run_async():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(
                            self._execute_v2_job_async(job_config, 'manual', 'system')
                        )
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_async)
                    return future.result()
                    
            except RuntimeError:
                # No event loop running, safe to create new one
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                
                return loop.run_until_complete(
                    self._execute_v2_job_async(job_config, 'manual', 'system')
                )
            
        except Exception as e:
            error_msg = f"Error executing V2 job {job_id}: {str(e)}"
            self.logger.exception(f"[JOB_EXECUTOR] {error_msg}")
            
            return {
                'success': False,
                'status': 'failed',
                'error': error_msg,
                'error_message': error_msg,
                'duration_seconds': 0,
                'output': '',
                'return_code': -1,
                '_version': 'v2'
            }
    
    async def _execute_v2_job_async(self, job_config: Dict[str, Any], execution_mode: str = 'manual', executed_by: str = 'system') -> Dict[str, Any]:
        """Execute V2 job asynchronously"""
        job_id = job_config['job_id']
        execution_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        self.logger.info(f"[JOB_EXECUTOR] Starting V2 execution of job: {job_id} (execution_id: {execution_id})")
        
        # Initialize execution data
        execution_data = {
            'execution_id': execution_id,
            'job_id': job_id,
            'job_name': job_config['name'],
            'status': 'running',
            'start_time': start_time,
            'execution_mode': execution_mode,
            'executed_by': executed_by,
            'execution_timezone': 'UTC'
        }
        
        try:
            # Get parsed config
            parsed_config = job_config.get('parsed_config', {})
            if not parsed_config:
                # Try to parse YAML if not already parsed
                yaml_config = job_config.get('yaml_configuration', '')
                if yaml_config:
                    parsed_config = yaml.safe_load(yaml_config)
                else:
                    raise Exception("No YAML configuration available")
            
            self.logger.info(f"[JOB_EXECUTOR] Executing V2 job '{job_config['name']}' of type '{parsed_config.get('type')}'")
            
            # Execute based on job type
            job_type = parsed_config.get('type', '').lower()
            
            if job_type == 'powershell':
                result = await self._execute_powershell_job_v2(parsed_config, execution_data)
            elif job_type == 'sql':
                result = await self._execute_sql_job_v2(parsed_config, execution_data)
            else:
                raise Exception(f"Unsupported V2 job type: {job_type}")
            
            # Update execution data with results
            execution_data.update(result)
            execution_data['status'] = 'success' if result.get('success', False) else 'failed'
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] V2 job execution failed: {e}")
            execution_data.update({
                'status': 'failed',
                'error_message': str(e),
                'output_log': f"Execution failed: {str(e)}"
            })
        
        finally:
            # Finalize execution data
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            execution_data.update({
                'end_time': end_time,
                'duration_seconds': duration
            })
            
            # Record execution in database
            try:
                self.job_manager.record_execution(execution_data)
            except Exception as e:
                self.logger.warning(f"[JOB_EXECUTOR] Failed to record execution: {e}")
            
            self.logger.info(f"[JOB_EXECUTOR] V2 job execution completed: {execution_id} (status: {execution_data['status']}, duration: {duration:.2f}s)")
        
        return {
            'success': execution_data['status'] == 'success',
            'execution_id': execution_id,
            'job_id': job_id,
            'status': execution_data['status'],
            'duration_seconds': execution_data.get('duration_seconds', 0),
            'start_time': start_time.isoformat(),
            'end_time': execution_data.get('end_time', end_time).isoformat(),
            'output': execution_data.get('output_log', ''),
            'error': execution_data.get('error_message', ''),
            'return_code': execution_data.get('return_code', 0),
            '_version': 'v2'
        }
    
    async def _execute_powershell_job_v2(self, config: Dict[str, Any], execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a V2 PowerShell job"""
        try:
            execution_mode = config.get('executionMode', 'inline')
            timeout = config.get('timeout', 300)
            
            # Get script content
            if execution_mode == 'inline':
                script_content = config.get('inlineScript', '')
                if not script_content.strip():
                    raise Exception("Inline script content is empty")
            elif execution_mode == 'script':
                script_path = config.get('scriptPath', '')
                if not script_path or not os.path.exists(script_path):
                    raise Exception(f"Script file not found: {script_path}")
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            else:
                raise Exception(f"Invalid execution mode: {execution_mode}")
            
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(script_content)
                temp_script_path = temp_file.name
            
            try:
                # Prepare PowerShell command
                ps_command = [
                    'powershell.exe',
                    '-ExecutionPolicy', 'Bypass',
                    '-NoProfile',
                    '-NonInteractive',
                    '-File', temp_script_path
                ]
                
                # Add parameters if specified
                parameters = config.get('parameters', [])
                for param in parameters:
                    if isinstance(param, dict) and 'name' in param and 'value' in param:
                        ps_command.extend(['-' + param['name'], str(param['value'])])
                
                self.logger.info(f"[JOB_EXECUTOR] Executing V2 PowerShell command: {' '.join(ps_command[:4])} ...")
                
                # Execute PowerShell script
                process = await asyncio.create_subprocess_exec(
                    *ps_command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=config.get('workingDirectory', os.getcwd())
                )
                
                try:
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), 
                        timeout=timeout
                    )
                    
                    stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ''
                    stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ''
                    
                    # Prepare output
                    output_parts = []
                    if stdout_text:
                        output_parts.append(f"STDOUT:\\n{stdout_text}")
                    if stderr_text:
                        output_parts.append(f"STDERR:\\n{stderr_text}")
                    
                    output_log = '\\n'.join(output_parts) if output_parts else 'PowerShell script executed with no output'
                    
                    success = process.returncode == 0
                    if not success and not stderr_text:
                        output_log += f"\\nProcess exited with code: {process.returncode}"
                    
                    return {
                        'success': success,
                        'output_log': output_log,
                        'return_code': process.returncode,
                        'error_message': stderr_text if stderr_text and not success else None
                    }
                    
                except asyncio.TimeoutError:
                    # Kill the process if it times out
                    try:
                        process.kill()
                        await process.wait()
                    except:
                        pass
                    
                    raise Exception(f"PowerShell script timed out after {timeout} seconds")
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_script_path)
                except:
                    pass
        
        except Exception as e:
            return {
                'success': False,
                'output_log': f"PowerShell execution error: {str(e)}",
                'error_message': str(e),
                'return_code': -1
            }
    
    async def _execute_sql_job_v2(self, config: Dict[str, Any], execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a V2 SQL job"""
        try:
            query = config.get('query', '').strip()
            if not query:
                raise Exception("SQL query is empty")
            
            connection_name = config.get('connection', 'default')
            timeout = config.get('timeout', 300)
            
            # Import database modules
            try:
                import pyodbc
                from database.sqlalchemy_models import get_db_session
            except ImportError as e:
                raise Exception(f"Database dependencies not available: {e}")
            
            self.logger.info(f"[JOB_EXECUTOR] Executing V2 SQL query on connection: {connection_name}")
            
            # Execute SQL query
            with get_db_session() as session:
                # Execute query with timeout
                result = session.execute(query)
                
                # Check if query returns data
                if result.returns_rows:
                    # SELECT query - fetch results
                    rows = result.fetchall()
                    columns = list(result.keys()) if hasattr(result, 'keys') else []
                    
                    # Convert to list of dictionaries
                    if rows and columns:
                        data = [dict(zip(columns, row)) for row in rows]
                        output_log = f"Query returned {len(rows)} rows:\\n"
                        
                        # Show first few rows as sample
                        if len(data) <= 10:
                            output_log += json.dumps(data, indent=2, default=str)
                        else:
                            output_log += json.dumps(data[:10], indent=2, default=str)
                            output_log += f"\\n... and {len(data) - 10} more rows"
                    else:
                        output_log = "Query executed successfully but returned no data"
                else:
                    # INSERT/UPDATE/DELETE query
                    rows_affected = result.rowcount if hasattr(result, 'rowcount') else 0
                    output_log = f"Query executed successfully. {rows_affected} rows affected."
                
                # Commit transaction
                session.commit()
                
                return {
                    'success': True,
                    'output_log': output_log,
                    'return_code': 0
                }
        
        except Exception as e:
            return {
                'success': False,
                'output_log': f"SQL execution error: {str(e)}",
                'error_message': str(e),
                'return_code': -1
            }
    
    def _create_job_instance(self, job_config: Dict[str, Any]):
        """Create job instance from V1 configuration"""
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
            
            self.logger.info(f"[JOB_EXECUTOR] Creating V1 job instance for type: '{job_type}'")
            
            if job_type == 'sql':
                if not HAS_SQL_JOB or not SqlJob:
                    self.logger.warning("[JOB_EXECUTOR] SQL job dependencies not available")
                    return None
                
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
                if not HAS_POWERSHELL_JOB or not PowerShellJob:
                    self.logger.warning("[JOB_EXECUTOR] PowerShell job dependencies not available")
                    return None
                
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
    
    def get_execution_history(self, job_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get execution history for a job or all jobs
        
        Args:
            job_id: Job ID to get history for (None for all jobs)
            limit: Maximum number of records to return
            
        Returns:
            List of execution history dictionaries
        """
        if job_id:
            return self.job_manager.get_execution_history(job_id, limit)
        else:
            return self.job_manager.get_all_execution_history(limit)
    
    def get_execution_history_incremental(self, job_id: str, since_timestamp: str = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get incremental execution history for a job"""
        # This would require additional implementation in JobManager
        # For now, return regular history
        return self.get_execution_history(job_id, limit)
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get job status information"""
        try:
            job = self.job_manager.get_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            # Get recent execution history
            history = self.get_execution_history(job_id, limit=1)
            last_execution = history[0] if history else None
            
            return {
                'success': True,
                'job_id': job_id,
                'name': job['name'],
                'enabled': job.get('enabled', True),
                'job_type': job.get('job_type', 'unknown'),
                'version': job.get('_version', 'v1'),
                'last_execution': last_execution
            }
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR] Error getting job status for {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information for execution context"""
        try:
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            
            return {
                'hostname': os.getenv('COMPUTERNAME', 'Unknown'),
                'platform': os.name,
                'cpu_count': cpu_count,
                'memory_total_mb': round(memory.total / 1024 / 1024, 2),
                'memory_available_mb': round(memory.available / 1024 / 1024, 2),
                'memory_percent': memory.percent
            }
        except:
            return {
                'hostname': 'Unknown',
                'platform': os.name
            }
    
    # Backward compatibility methods
    def execute_job_sync(self, job_id: str, execution_mode: str = 'manual', executed_by: str = 'system') -> Dict[str, Any]:
        """
        Synchronous job execution (backward compatibility for V2 APIs)
        """
        return self.execute_job(job_id)