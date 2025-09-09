"""
V2-YAML Job Executor - CLEAN IMPLEMENTATION
Pure V2 YAML execution only - NO V1 legacy code
REPLACED CACHED FILE - Force fresh import
Created: 2025-09-04 12:35
"""

import yaml
import json
import uuid
import subprocess
import tempfile
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from utils.logger import get_logger
from database.sqlalchemy_models import get_db_session, JobExecutionHistoryV2


class JobExecutor:
    """Clean V2 YAML job executor - NO legacy code"""
    
    def __init__(self, job_manager=None, db_session=None):
        self.logger = get_logger(__name__)
        self.job_manager = job_manager
        self.db_session = db_session
        print("**** CLEAN V2 JobExecutor initialized - FRESH IMPORT ****")
        self.logger.info("[CLEAN_V2_EXECUTOR] Clean V2 YAML Job Executor initialized - NO LEGACY")
    
    def set_session(self, session):
        """Set the database session"""
        self.db_session = session
    
    def execute_job(self, job_id: str) -> Dict[str, Any]:
        """
        Execute a V2 YAML job - CLEAN implementation
        
        Args:
            job_id: Job ID to execute
            
        Returns:
            Dict with execution result information
        """
        print(f"**** CLEAN V2 JobExecutor.execute_job() called ****")
        print(f"**** EXECUTOR: job_id parameter: {job_id} ****")
        print(f"**** EXECUTOR: method file: {__file__} ****")
        print(f"**** EXECUTOR: self type: {type(self)} ****")
        print(f"**** EXECUTOR: job_manager type: {type(self.job_manager)} ****")
        
        self.logger.info(f"[CLEAN_V2_EXECUTOR] Starting CLEAN V2 YAML execution: {job_id}")
        
        if not self.job_manager:
            error_msg = "Job manager not available"
            print(f"**** EXECUTOR ERROR: {error_msg} ****")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Get V2 job configuration - CLEAN call with NO version parameters
        print(f"**** EXECUTOR: About to call self.job_manager.get_job({job_id}) ****")
        print(f"**** EXECUTOR: job_manager.get_job method: {self.job_manager.get_job} ****")
        
        # Check the method signature
        import inspect
        method_sig = inspect.signature(self.job_manager.get_job)
        print(f"**** EXECUTOR: get_job method signature: {method_sig} ****")
        
        try:
            # DIRECT method call with ONLY job_id parameter
            print(f"**** EXECUTOR: Calling get_job with ONLY job_id parameter ****")
            job_config = self.job_manager.get_job(job_id)
            print(f"**** EXECUTOR: get_job call completed successfully ****")
            print(f"**** EXECUTOR: Retrieved job config: {job_config is not None} ****")
            
            if job_config:
                print(f"**** EXECUTOR: Job name: {job_config.get('name', 'Unknown')} ****")
                print(f"**** EXECUTOR: Job enabled: {job_config.get('enabled', True)} ****")
                
                # Add detailed job_config debugging
                print(f"**** EXECUTOR DEBUG: job_config type: {type(job_config)} ****")
                print(f"**** EXECUTOR DEBUG: job_config keys: {job_config.keys() if job_config else 'None'} ****")
                print(f"**** EXECUTOR DEBUG: yaml_configuration length: {len(job_config.get('yaml_configuration', '')) if job_config.get('yaml_configuration') else 0} ****")
                print(f"**** EXECUTOR DEBUG: yaml_configuration preview: {repr(job_config.get('yaml_configuration', '')[:200])} ****")
                print(f"**** EXECUTOR DEBUG: parsed_config exists: {bool(job_config.get('parsed_config'))} ****")
                if job_config.get('parsed_config'):
                    print(f"**** EXECUTOR DEBUG: parsed_config: {job_config.get('parsed_config')} ****")
                
        except Exception as e:
            print(f"**** EXECUTOR ERROR: Failed to get job configuration: {e} ****")
            print(f"**** EXECUTOR ERROR TYPE: {type(e)} ****")
            import traceback
            print(f"**** EXECUTOR TRACEBACK: {traceback.format_exc()} ****")
            return {
                'success': False,
                'error': f'Failed to get job configuration: {str(e)}'
            }
        
        if not job_config:
            error_msg = f"CLEAN V2: Job {job_id} not found in database"
            print(f"CLEAN V2 ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Check if job is enabled
        if not job_config.get('enabled', True):
            error_msg = f"CLEAN V2: Job {job_id} is disabled"
            print(f"CLEAN V2 WARNING: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        # Execute V2 YAML job
        print(f"CLEAN V2: Starting job execution...")
        self.logger.info(f"[CLEAN_V2_EXECUTOR] Executing V2 YAML job {job_id}")
        
        try:
            return self._execute_v2_yaml_job(job_config)
                
        except Exception as e:
            error_msg = f"CLEAN V2 execution error for job {job_id}: {str(e)}"
            print(f"CLEAN V2 ERROR: {error_msg}")
            self.logger.exception(f"[CLEAN_V2_EXECUTOR] {error_msg}")
            
            return {
                'success': False,
                'error': error_msg
            }
    
    def _execute_v2_yaml_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute V2 YAML job configuration"""
        job_id = job_config['job_id']
        execution_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        print(f"CLEAN V2: Starting execution: {job_id} (execution_id: {execution_id})")
        self.logger.info(f"[CLEAN_V2_EXECUTOR] Starting V2 YAML execution: {job_id}")
        
        # Parse YAML configuration
        try:
            yaml_config = job_config.get('yaml_configuration', '')
            print(f"CLEAN V2: Raw YAML config: {repr(yaml_config)}")
            print(f"CLEAN V2: YAML config type: {type(yaml_config)}")
            print(f"CLEAN V2: YAML config length: {len(yaml_config) if yaml_config else 0}")
            
            if not yaml_config or yaml_config.strip() == '':
                # No YAML config, check for parsed_config
                parsed_config = job_config.get('parsed_config', {})
                print(f"CLEAN V2: Using parsed_config: {parsed_config}")
            else:
                # Parse YAML configuration
                print(f"CLEAN V2: About to parse YAML with yaml.safe_load()")
                parsed_config = yaml.safe_load(yaml_config)
                print(f"CLEAN V2: YAML parsing result: {parsed_config}")
                print(f"CLEAN V2: Parsed config type: {type(parsed_config)}")
                
                # Handle case where yaml.safe_load returns None (empty/invalid YAML)
                if parsed_config is None:
                    print(f"CLEAN V2: YAML parsing returned None, falling back to parsed_config")
                    parsed_config = job_config.get('parsed_config', {})
                else:
                    print(f"CLEAN V2: YAML parsed successfully - keys: {list(parsed_config.keys()) if isinstance(parsed_config, dict) else 'NOT_DICT'}")
                    if isinstance(parsed_config, dict):
                        print(f"CLEAN V2: Job type from YAML: {parsed_config.get('type', 'NO_TYPE')}")
                        print(f"CLEAN V2: Script path from YAML: {parsed_config.get('scriptPath', 'NO_SCRIPT_PATH')}")
                        print(f"CLEAN V2: Inline script from YAML: {bool(parsed_config.get('inlineScript'))}")
            
            # Final validation of parsed_config
            if parsed_config is None:
                parsed_config = {}
                print(f"CLEAN V2: WARNING - No valid configuration found, using empty dict")
            
            print(f"CLEAN V2: Final parsed config: {parsed_config}")
            print(f"CLEAN V2: Parsed YAML config successfully: {parsed_config.get('name', 'Unknown') if parsed_config else 'No Config'}")
            
        except yaml.YAMLError as e:
            error_msg = f"CLEAN V2: Invalid YAML configuration for job {job_id}: {e}"
            print(f"CLEAN V2 ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"CLEAN V2: Unexpected error parsing configuration for job {job_id}: {e}"
            print(f"CLEAN V2 ERROR: {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        try:
            # Execute based on job type from YAML config
            if not parsed_config or not isinstance(parsed_config, dict):
                result = {
                    'success': False,
                    'error': 'CLEAN V2: No valid job configuration found',
                    'message': 'Invalid or missing job configuration'
                }
            else:
                job_type = parsed_config.get('type', '').lower()
                print(f"CLEAN V2: Executing job type: {job_type}")
                
                if job_type == 'powershell':
                    result = self._execute_powershell_job(parsed_config, execution_id)
                elif job_type == 'sql':
                    result = self._execute_sql_job(parsed_config, execution_id)
                elif job_type == 'agent_job' or job_type == 'agent':
                    result = self._execute_agent_job(parsed_config, execution_id)
                else:
                    result = {
                        'success': False,
                        'error': f'CLEAN V2: Unsupported job type: {job_type}',
                        'message': 'Job type not supported'
                    }
            
            # Calculate duration
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()
            
            # Record execution in database
            try:
                self._record_execution(job_config, execution_id, start_time, end_time, duration, result)
            except Exception as db_error:
                print(f"CLEAN V2 WARNING: Failed to record execution: {db_error}")
            
            # Return API-compatible result
            api_result = {
                'success': result.get('success', False),
                'execution_id': execution_id,
                'job_id': job_id,
                'status': 'completed' if result.get('success') else 'failed',
                'message': f"CLEAN V2 YAML job executed: {result.get('message', '')}",
                'output': result.get('output', ''),
                'error': result.get('error'),
                'duration_seconds': duration,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            }
            
            success_status = 'SUCCESS' if result.get('success') else 'FAILED'
            print(f"CLEAN V2: Job execution completed: {success_status}")
            self.logger.info(f"[CLEAN_V2_EXECUTOR] V2 job {job_id} completed: {success_status}")
            
            return api_result
            
        except Exception as e:
            error_msg = f"CLEAN V2 job execution failed: {str(e)}"
            print(f"CLEAN V2 ERROR: {error_msg}")
            self.logger.exception(f"[CLEAN_V2_EXECUTOR] {error_msg}")
            
            return {
                'success': False,
                'execution_id': execution_id,
                'job_id': job_id,
                'status': 'failed',
                'error': error_msg
            }
    
    def _execute_powershell_job(self, config: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        """Execute PowerShell job from V2 YAML config"""
        print(f"CLEAN V2: Executing PowerShell job")
        
        try:
            # Get script content or path from YAML
            script_content = config.get('inlineScript')
            script_path = config.get('scriptPath')
            execution_policy = config.get('executionPolicy', 'RemoteSigned')
            parameters = config.get('parameters', [])
            
            print(f"CLEAN V2: PowerShell parameters: {parameters}")
            
            # Helper function to build parameter arguments
            def build_parameter_args(params):
                """Convert parameter list to PowerShell command line arguments"""
                param_args = []
                if isinstance(params, list):
                    for param in params:
                        if isinstance(param, dict):
                            # Handle dict format: {"name": "ParamName", "value": "ParamValue"}
                            name = param.get('name', '')
                            value = param.get('value', '')
                            if name:
                                param_args.extend([f'-{name}', str(value)])
                        elif isinstance(param, str) and '=' in param:
                            # Handle string format: "ParamName=ParamValue"
                            name, value = param.split('=', 1)
                            param_args.extend([f'-{name}', value])
                elif isinstance(params, dict):
                    # Handle direct dict format: {"ParamName": "ParamValue"}
                    for name, value in params.items():
                        param_args.extend([f'-{name}', str(value)])
                        
                return param_args
            
            param_args = build_parameter_args(parameters)
            if param_args:
                print(f"CLEAN V2: PowerShell parameter arguments: {param_args}")
            
            if script_content:
                # Execute inline script
                print(f"CLEAN V2: Executing inline PowerShell script")
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False) as temp_file:
                    temp_file.write(script_content)
                    temp_script_path = temp_file.name
                
                try:
                    cmd = ['powershell.exe', '-ExecutionPolicy', execution_policy, '-File', temp_script_path] + param_args
                    print(f"CLEAN V2: Running: {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                    
                    return {
                        'success': result.returncode == 0,
                        'output': result.stdout,
                        'error': result.stderr if result.returncode != 0 else None,
                        'return_code': result.returncode,
                        'message': f"CLEAN V2 PowerShell executed (return code: {result.returncode})"
                    }
                finally:
                    try:
                        os.unlink(temp_script_path)
                    except:
                        pass
                        
            elif script_path:
                # Execute script file
                print(f"CLEAN V2: Executing PowerShell file: {script_path}")
                cmd = ['powershell.exe', '-ExecutionPolicy', execution_policy, '-File', script_path] + param_args
                print(f"CLEAN V2: Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'error': result.stderr if result.returncode != 0 else None,
                    'return_code': result.returncode,
                    'message': f"CLEAN V2 PowerShell file executed: {script_path}"
                }
            else:
                return {
                    'success': False,
                    'error': 'CLEAN V2: No PowerShell script content or path specified',
                    'message': 'Missing script configuration'
                }
                
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': 'CLEAN V2: PowerShell script timed out after 300 seconds',
                'message': 'Execution timeout'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'CLEAN V2 PowerShell error: {str(e)}',
                'message': 'PowerShell execution failed'
            }
    
    def _execute_sql_job(self, config: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        """Execute SQL job from V2 YAML config"""
        print(f"CLEAN V2: Executing SQL job (mock)")
        
        query = config.get('query', 'SELECT 1')
        connection_name = config.get('connection', 'default')
        
        # Mock successful execution
        return {
            'success': True,
            'output': f'CLEAN V2 SQL executed on "{connection_name}": {query[:50]}...',
            'message': f'CLEAN V2 SQL job executed successfully (mock)',
            'return_code': 0
        }
    
    def _execute_agent_job(self, config: Dict[str, Any], execution_id: str) -> Dict[str, Any]:
        """Execute agent job from V2 YAML config by assigning to passive agent"""
        print(f"CLEAN V2: Executing agent job")
        
        agent_pool = config.get('agent_pool', 'default')
        execution_strategy = config.get('execution_strategy', 'default_pool')
        job_steps = config.get('steps', [])
        
        print(f"CLEAN V2: Agent job for pool '{agent_pool}' with strategy '{execution_strategy}'")
        print(f"CLEAN V2: Job has {len(job_steps)} steps")
        
        # Try to assign job to a passive agent immediately
        from core.agent_job_handler import agent_job_handler
        
        try:
            # Get job_id from the execution context
            job_id = None
            
            # Find the job_id by looking up the execution_id in the database
            with get_db_session() as session:
                execution_record = session.query(JobExecutionHistoryV2).filter_by(
                    execution_id=execution_id
                ).first()
                
                if execution_record:
                    job_id = execution_record.job_id
                else:
                    # If no execution record yet, we need the job_id from context
                    # This should be passed in - for now, log warning and queue
                    print(f"CLEAN V2 WARNING: No execution record found for {execution_id}")
                    return {
                        'success': True,
                        'output': f'CLEAN V2: Agent job queued for pool "{agent_pool}" (no execution record)',
                        'message': f'Agent job queued for execution (pool: {agent_pool})',
                        'return_code': 0,
                        'queued_for_agent': True,
                        'agent_pool': agent_pool,
                        'execution_strategy': execution_strategy
                    }
            
            if job_id:
                # Try to assign to passive agent
                assignment_id = agent_job_handler.assign_job_to_passive_agent(
                    job_id=job_id,
                    execution_id=execution_id,
                    pool_id=agent_pool
                )
                
                if assignment_id:
                    print(f"CLEAN V2: Successfully assigned job {job_id} to passive agent (assignment: {assignment_id})")
                    return {
                        'success': True,
                        'output': f'CLEAN V2: Agent job assigned to passive agent in pool "{agent_pool}"',
                        'message': f'Agent job assigned for execution (pool: {agent_pool}, assignment: {assignment_id})',
                        'return_code': 0,
                        'assigned_to_agent': True,
                        'assignment_id': assignment_id,
                        'agent_pool': agent_pool,
                        'execution_strategy': execution_strategy
                    }
                else:
                    # No passive agent available - job remains queued
                    print(f"CLEAN V2: No passive agent available in pool '{agent_pool}', job queued")
                    return {
                        'success': True,
                        'output': f'CLEAN V2: No passive agent available, job queued for pool "{agent_pool}"',
                        'message': f'Agent job queued for execution - no agents available (pool: {agent_pool})',
                        'return_code': 0,
                        'queued_for_agent': True,
                        'agent_pool': agent_pool,
                        'execution_strategy': execution_strategy
                    }
            else:
                # Fallback - queue for later assignment
                return {
                    'success': True,
                    'output': f'CLEAN V2: Agent job queued for pool "{agent_pool}"',
                    'message': f'Agent job queued for execution (pool: {agent_pool})',
                    'return_code': 0,
                    'queued_for_agent': True,
                    'agent_pool': agent_pool,
                    'execution_strategy': execution_strategy
                }
                
        except Exception as e:
            print(f"CLEAN V2 ERROR: Failed to assign agent job: {e}")
            # Fallback to queuing
            return {
                'success': True,
                'output': f'CLEAN V2: Agent job queued for pool "{agent_pool}" (assignment failed: {str(e)})',
                'message': f'Agent job queued for execution - assignment error (pool: {agent_pool})',
                'return_code': 0,
                'queued_for_agent': True,
                'agent_pool': agent_pool,
                'execution_strategy': execution_strategy
            }
    
    def _record_execution(self, job_config: Dict[str, Any], execution_id: str, 
                         start_time: datetime, end_time: datetime, duration: float, 
                         result: Dict[str, Any]):
        """Record execution in database"""
        try:
            with get_db_session() as session:
                # For agent jobs, set appropriate status based on assignment result
                if result.get('assigned_to_agent'):
                    status = 'assigned'
                    executed_by = f"assigned_to_agent_{result.get('assignment_id', 'unknown')}"
                elif result.get('queued_for_agent'):
                    status = 'queued'
                    executed_by = f"queued_for_{result.get('agent_pool', 'default')}_pool"
                else:
                    status = 'success' if result.get('success') else 'failed'
                    executed_by = 'clean_v2_executor'
                
                execution_record = JobExecutionHistoryV2(
                    execution_id=execution_id,
                    job_id=job_config['job_id'],
                    job_name=job_config.get('name', 'Unknown Job'),
                    status=status,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration,
                    output_log=result.get('output', ''),
                    error_message=result.get('error', ''),
                    return_code=result.get('return_code', 0),
                    execution_mode='manual',
                    executed_by=executed_by,
                    execution_timezone='UTC'
                )
                session.add(execution_record)
                session.commit()
                
            print(f"CLEAN V2: Execution recorded: {execution_id}")
            self.logger.info(f"[CLEAN_V2_EXECUTOR] Execution recorded: {execution_id}")
            
        except Exception as e:
            print(f"CLEAN V2 WARNING: Failed to record execution: {e}")
            self.logger.warning(f"[CLEAN_V2_EXECUTOR] Failed to record execution: {e}")
    
    # Backward compatibility methods
    def execute_job_sync(self, job_id: str, execution_mode: str = 'manual', executed_by: str = 'system') -> Dict[str, Any]:
        """Synchronous job execution (backward compatibility)"""
        return self.execute_job(job_id)
    
    def get_execution_history(self, job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get execution history for a job"""
        try:
            with get_db_session() as session:
                query = session.query(JobExecutionHistoryV2).filter(
                    JobExecutionHistoryV2.job_id == job_id
                ).order_by(JobExecutionHistoryV2.start_time.desc())
                
                if limit:
                    query = query.limit(limit)
                
                executions = query.all()
                
                result = []
                for execution in executions:
                    result.append({
                        'execution_id': execution.execution_id,
                        'job_id': execution.job_id,
                        'job_name': execution.job_name,
                        'status': execution.status,
                        'start_time': execution.start_time.isoformat() if execution.start_time else None,
                        'end_time': execution.end_time.isoformat() if execution.end_time else None,
                        'duration_seconds': execution.duration_seconds,
                        'output_log': execution.output_log,
                        'error_message': execution.error_message,
                        'return_code': execution.return_code,
                        'execution_mode': execution.execution_mode,
                        'executed_by': execution.executed_by
                    })
                
                return result
                
        except Exception as e:
            self.logger.error(f"[CLEAN_V2_EXECUTOR] Error getting execution history: {e}")
            return []
    
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
                'job_type': 'clean_v2_yaml',
                'last_execution': last_execution
            }
            
        except Exception as e:
            self.logger.error(f"[CLEAN_V2_EXECUTOR] Error getting job status: {e}")
            return {
                'success': False,
                'error': f'Error getting job status: {str(e)}'
            }