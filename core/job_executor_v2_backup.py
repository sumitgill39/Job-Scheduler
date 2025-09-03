"""
Job Executor V2 using YAML-based job definitions
Direct, simplified execution without complex V2 execution engine dependencies
"""

import yaml
import uuid
import asyncio
import subprocess
import tempfile
import os
import time
import json
import psutil
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from utils.logger import get_logger
from .job_manager import JobManager


class JobExecutorV2:
    """Simplified job executor for YAML-based job definitions"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.job_manager = JobManager()
        self.logger.info("[JOB_EXECUTOR_V2] YAML-based Job Executor initialized")
    
    async def execute_job(self, job_id: str, execution_mode: str = 'manual', executed_by: str = 'system') -> Dict[str, Any]:
        """
        Execute a V2 job by ID
        
        Args:
            job_id: Job ID to execute
            execution_mode: 'manual', 'scheduled', or 'api'
            executed_by: User or system that triggered execution
            
        Returns:
            Dict with execution result
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        self.logger.info(f"[JOB_EXECUTOR_V2] Starting execution of job: {job_id} (execution_id: {execution_id})")
        
        # Initialize execution data
        execution_data = {
            'execution_id': execution_id,
            'job_id': job_id,
            'status': 'running',
            'start_time': start_time,
            'execution_mode': execution_mode,
            'executed_by': executed_by,
            'execution_timezone': 'UTC'
        }
        
        try:
            # Get job configuration
            job_config = self.job_manager.get_job(job_id)
            if not job_config:
                raise Exception(f"Job {job_id} not found")
            
            if not job_config['enabled']:
                raise Exception(f"Job {job_id} is disabled")
            
            execution_data['job_name'] = job_config['name']
            parsed_config = job_config['parsed_config']
            
            self.logger.info(f"[JOB_EXECUTOR_V2] Executing job '{job_config['name']}' of type '{parsed_config.get('type')}'")
            
            # Execute based on job type
            job_type = parsed_config.get('type', '').lower()
            
            if job_type == 'powershell':
                result = await self._execute_powershell_job(parsed_config, execution_data)
            elif job_type == 'sql':
                result = await self._execute_sql_job(parsed_config, execution_data)
            else:
                raise Exception(f"Unsupported job type: {job_type}")
            
            # Update execution data with results
            execution_data.update(result)
            execution_data['status'] = 'success' if result.get('success', False) else 'failed'
            
        except Exception as e:
            self.logger.error(f"[JOB_EXECUTOR_V2] Job execution failed: {e}")
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
            self.job_manager.record_execution(execution_data)
            
            self.logger.info(f"[JOB_EXECUTOR_V2] Job execution completed: {execution_id} (status: {execution_data['status']}, duration: {duration:.2f}s)")
        
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
            'return_code': execution_data.get('return_code', 0)
        }
    
    async def _execute_powershell_job(self, config: Dict[str, Any], execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a PowerShell job"""
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
                
                self.logger.info(f"[JOB_EXECUTOR_V2] Executing PowerShell command: {' '.join(ps_command[:4])} ...")
                
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
                        output_parts.append(f"STDOUT:\n{stdout_text}")
                    if stderr_text:
                        output_parts.append(f"STDERR:\n{stderr_text}")
                    
                    output_log = '\n'.join(output_parts) if output_parts else 'PowerShell script executed with no output'
                    
                    success = process.returncode == 0
                    if not success and not stderr_text:
                        output_log += f"\nProcess exited with code: {process.returncode}"
                    
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
    
    async def _execute_sql_job(self, config: Dict[str, Any], execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SQL job"""
        try:
            query = config.get('query', '').strip()
            if not query:
                raise Exception("SQL query is empty")
            
            connection_name = config.get('connection', 'default')
            timeout = config.get('timeout', 300)
            
            # Import database modules
            import pyodbc
            from database.sqlalchemy_models import get_db_session
            
            self.logger.info(f"[JOB_EXECUTOR_V2] Executing SQL query on connection: {connection_name}")
            
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
                        output_log = f"Query returned {len(rows)} rows:\n"
                        
                        # Show first few rows as sample
                        if len(data) <= 10:
                            output_log += json.dumps(data, indent=2, default=str)
                        else:
                            output_log += json.dumps(data[:10], indent=2, default=str)
                            output_log += f"\n... and {len(data) - 10} more rows"
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
    
    def execute_job_sync(self, job_id: str, execution_mode: str = 'manual', executed_by: str = 'system') -> Dict[str, Any]:
        """
        Synchronous wrapper for job execution
        """
        try:
            # Run the async execution
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            self.execute_job(job_id, execution_mode, executed_by)
        )
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a job"""
        return self.job_manager.get_execution_history(job_id, limit)
    
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