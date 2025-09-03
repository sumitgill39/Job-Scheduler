"""
Job Manager V2 using YAML configuration format
Enhanced job management with structured YAML definitions
"""

import yaml
import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from utils.logger import get_logger
from database.sqlalchemy_models import JobConfigurationV2, JobExecutionHistoryV2, get_db_session


class JobManagerV2:
    """Enhanced job manager using YAML configuration format"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("[JOB_MANAGER_V2] YAML-based Job Manager initialized")
    
    def create_job(self, job_definition: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new V2 job with YAML configuration
        
        Args:
            job_definition: Dictionary containing job definition
            Expected structure:
            {
                'name': 'Job Name',
                'description': 'Job description',
                'yaml_config': 'YAML configuration string',
                'enabled': True
            }
            
        Returns:
            Dict with success status and job_id or error message
        """
        try:
            # Generate job ID
            job_id = str(uuid.uuid4())
            job_name = job_definition.get('name', 'Unnamed Job')
            description = job_definition.get('description', f'V2 Job: {job_name}')
            yaml_config = job_definition.get('yaml_config', '')
            
            self.logger.info(f"[JOB_MANAGER_V2] Creating V2 job '{job_name}' with ID: {job_id}")
            
            # Validate required fields
            if not job_name or job_name.strip() == '':
                return {
                    'success': False,
                    'error': 'Job name is required'
                }
            
            if not yaml_config or yaml_config.strip() == '':
                return {
                    'success': False,
                    'error': 'YAML configuration is required'
                }
            
            # Validate YAML format
            try:
                parsed_yaml = yaml.safe_load(yaml_config)
                validation_result = self._validate_yaml_config(parsed_yaml)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': f'Invalid YAML configuration: {validation_result["error"]}'
                    }
            except yaml.YAMLError as e:
                return {
                    'success': False,
                    'error': f'Invalid YAML syntax: {str(e)}'
                }
            
            # Create job configuration
            with get_db_session() as session:
                job_config = JobConfigurationV2(
                    job_id=job_id,
                    name=job_name,
                    description=description,
                    yaml_configuration=yaml_config,
                    enabled=job_definition.get('enabled', True),
                    created_by='system'
                )
                
                session.add(job_config)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER_V2] V2 job created successfully: {job_id}")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'message': f'V2 Job {job_name} created successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error creating V2 job: {e}")
            return {
                'success': False,
                'error': f'Error creating V2 job: {str(e)}'
            }
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a V2 job by ID"""
        try:
            self.logger.info(f"[JOB_MANAGER_V2] Getting V2 job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfigurationV2).filter(
                    JobConfigurationV2.job_id == job_id
                ).first()
                
                if job:
                    job_dict = job.to_dict()
                    
                    # Parse YAML configuration
                    try:
                        job_dict['parsed_config'] = yaml.safe_load(job_dict['yaml_configuration'])
                    except yaml.YAMLError:
                        job_dict['parsed_config'] = {}
                    
                    self.logger.info(f"[JOB_MANAGER_V2] Found V2 job: {job.name}")
                    return job_dict
                else:
                    self.logger.warning(f"[JOB_MANAGER_V2] V2 job not found: {job_id}")
                    return None
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error getting V2 job {job_id}: {e}")
            return None
    
    def list_jobs(self, enabled_only: bool = False, limit: int = None) -> List[Dict[str, Any]]:
        """List V2 jobs from database"""
        try:
            self.logger.info(f"[JOB_MANAGER_V2] Listing V2 jobs (enabled_only={enabled_only}, limit={limit})")
            
            with get_db_session() as session:
                query = session.query(JobConfigurationV2)
                
                if enabled_only:
                    query = query.filter(JobConfigurationV2.enabled == True)
                
                query = query.order_by(JobConfigurationV2.created_date.desc())
                
                if limit:
                    query = query.limit(limit)
                
                jobs = query.all()
                
                # Convert to dictionaries and parse YAML configuration
                result = []
                for job in jobs:
                    job_dict = job.to_dict()
                    try:
                        job_dict['parsed_config'] = yaml.safe_load(job_dict['yaml_configuration'])
                    except yaml.YAMLError:
                        job_dict['parsed_config'] = {}
                    result.append(job_dict)
                
                self.logger.info(f"[JOB_MANAGER_V2] Found {len(result)} V2 jobs")
                return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error listing V2 jobs: {e}")
            return []
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a V2 job"""
        try:
            self.logger.info(f"[JOB_MANAGER_V2] Updating V2 job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfigurationV2).filter(
                    JobConfigurationV2.job_id == job_id
                ).first()
                
                if not job:
                    return {
                        'success': False,
                        'error': f'V2 job {job_id} not found'
                    }
                
                # Update fields if provided
                if 'name' in job_data:
                    job.name = job_data['name']
                if 'description' in job_data:
                    job.description = job_data['description']
                if 'enabled' in job_data:
                    job.enabled = job_data['enabled']
                
                # Update YAML configuration if provided
                if 'yaml_config' in job_data:
                    yaml_config = job_data['yaml_config']
                    
                    # Validate YAML format
                    try:
                        parsed_yaml = yaml.safe_load(yaml_config)
                        validation_result = self._validate_yaml_config(parsed_yaml)
                        if not validation_result['valid']:
                            return {
                                'success': False,
                                'error': f'Invalid YAML configuration: {validation_result["error"]}'
                            }
                        job.yaml_configuration = yaml_config
                    except yaml.YAMLError as e:
                        return {
                            'success': False,
                            'error': f'Invalid YAML syntax: {str(e)}'
                        }
                
                # Update modified date
                job.modified_date = datetime.now()
                
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER_V2] V2 job updated successfully: {job_id}")
                return {
                    'success': True,
                    'message': f'V2 job {job.name} updated successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error updating V2 job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating V2 job: {str(e)}'
            }
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a V2 job"""
        try:
            self.logger.info(f"[JOB_MANAGER_V2] Deleting V2 job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfigurationV2).filter(
                    JobConfigurationV2.job_id == job_id
                ).first()
                
                if not job:
                    return {
                        'success': False,
                        'error': f'V2 job {job_id} not found'
                    }
                
                job_name = job.name
                session.delete(job)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER_V2] V2 job deleted successfully: {job_name}")
                return {
                    'success': True,
                    'message': f'V2 job {job_name} deleted successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error deleting V2 job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error deleting V2 job: {str(e)}'
            }
    
    def record_execution(self, execution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Record job execution in V2 history table"""
        try:
            execution_id = execution_data.get('execution_id', str(uuid.uuid4()))
            
            with get_db_session() as session:
                execution_record = JobExecutionHistoryV2(
                    execution_id=execution_id,
                    job_id=execution_data['job_id'],
                    job_name=execution_data.get('job_name', 'Unknown'),
                    status=execution_data['status'],
                    start_time=execution_data.get('start_time'),
                    end_time=execution_data.get('end_time'),
                    duration_seconds=execution_data.get('duration_seconds'),
                    output_log=execution_data.get('output_log'),
                    error_message=execution_data.get('error_message'),
                    return_code=execution_data.get('return_code'),
                    step_results=execution_data.get('step_results'),
                    execution_mode=execution_data.get('execution_mode', 'manual'),
                    executed_by=execution_data.get('executed_by', 'system'),
                    execution_timezone=execution_data.get('execution_timezone', 'UTC'),
                    server_info=execution_data.get('server_info'),
                    memory_usage_mb=execution_data.get('memory_usage_mb'),
                    cpu_time_seconds=execution_data.get('cpu_time_seconds'),
                    retry_count=execution_data.get('retry_count', 0),
                    max_retries=execution_data.get('max_retries', 0),
                    is_retry=execution_data.get('is_retry', False),
                    parent_execution_id=execution_data.get('parent_execution_id')
                )
                
                session.add(execution_record)
                session.commit()
                
                # Update job statistics
                self._update_job_statistics(execution_data['job_id'], execution_data, session)
                
                self.logger.info(f"[JOB_MANAGER_V2] Execution recorded: {execution_id}")
                return {
                    'success': True,
                    'execution_id': execution_id
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error recording execution: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a V2 job"""
        try:
            with get_db_session() as session:
                query = session.query(JobExecutionHistoryV2).filter(
                    JobExecutionHistoryV2.job_id == job_id
                ).order_by(JobExecutionHistoryV2.start_time.desc()).limit(limit)
                
                executions = query.all()
                result = [execution.to_dict() for execution in executions]
                
                self.logger.info(f"[JOB_MANAGER_V2] Found {len(result)} execution records for job {job_id}")
                return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error getting execution history for job {job_id}: {e}")
            return []
    
    def _validate_yaml_config(self, parsed_yaml: Any) -> Dict[str, Any]:
        """Validate YAML configuration structure"""
        if not isinstance(parsed_yaml, dict):
            return {'valid': False, 'error': 'YAML must be a dictionary/object'}
        
        # Check required fields
        required_fields = ['id', 'name', 'type']
        for field in required_fields:
            if field not in parsed_yaml:
                return {'valid': False, 'error': f'Missing required field: {field}'}
        
        # Validate job type
        job_type = parsed_yaml.get('type', '').lower()
        if job_type not in ['powershell', 'sql']:
            return {'valid': False, 'error': f'Unsupported job type: {job_type}'}
        
        # Type-specific validation
        if job_type == 'powershell':
            execution_mode = parsed_yaml.get('executionMode', '')
            if execution_mode not in ['inline', 'script']:
                return {'valid': False, 'error': 'PowerShell jobs must specify executionMode: inline or script'}
            
            if execution_mode == 'inline' and 'inlineScript' not in parsed_yaml:
                return {'valid': False, 'error': 'PowerShell inline jobs must have inlineScript field'}
            
            if execution_mode == 'script' and 'scriptPath' not in parsed_yaml:
                return {'valid': False, 'error': 'PowerShell script jobs must have scriptPath field'}
        
        elif job_type == 'sql':
            if 'query' not in parsed_yaml:
                return {'valid': False, 'error': 'SQL jobs must have query field'}
        
        return {'valid': True}
    
    def _update_job_statistics(self, job_id: str, execution_data: Dict[str, Any], session):
        """Update job performance statistics"""
        try:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if job:
                # Update execution counts
                job.total_executions = (job.total_executions or 0) + 1
                
                if execution_data['status'] == 'success':
                    job.successful_executions = (job.successful_executions or 0) + 1
                else:
                    job.failed_executions = (job.failed_executions or 0) + 1
                
                # Update last execution info
                job.last_execution_id = execution_data.get('execution_id')
                job.last_execution_status = execution_data['status']
                job.last_execution_time = execution_data.get('end_time', execution_data.get('start_time'))
                
                # Update average duration
                if execution_data.get('duration_seconds'):
                    if job.average_duration_seconds:
                        job.average_duration_seconds = (
                            (job.average_duration_seconds * (job.total_executions - 1) + 
                             execution_data['duration_seconds']) / job.total_executions
                        )
                    else:
                        job.average_duration_seconds = execution_data['duration_seconds']
                
                session.commit()
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER_V2] Error updating job statistics: {e}")


def create_sample_powershell_yaml() -> str:
    """Create a sample PowerShell job YAML configuration"""
    sample_config = {
        'id': 'PS-001',
        'name': 'System Health Check Script',
        'type': 'PowerShell',
        'executionMode': 'inline',
        'inlineScript': '''# PowerShell inline script
Get-Process | Sort-Object CPU -Descending | Select-Object -First 10
Get-Service | Where-Object {$_.Status -eq 'Running'}
Write-Host "System check completed at $(Get-Date)"''',
        'enabled': True,
        'timeout': 300,
        'schedule': {
            'type': 'cron',
            'expression': '0 */6 * * *',  # Every 6 hours
            'timezone': 'UTC'
        },
        'retryPolicy': {
            'maxRetries': 3,
            'retryDelay': 30
        },
        'notifications': {
            'onFailure': True,
            'onSuccess': False
        }
    }
    
    return yaml.dump(sample_config, default_flow_style=False, allow_unicode=True)


def create_sample_sql_yaml() -> str:
    """Create a sample SQL job YAML configuration"""
    sample_config = {
        'id': 'SQL-001',
        'name': 'Database Maintenance Query',
        'type': 'SQL',
        'query': '''-- Database maintenance query
UPDATE STATISTICS dbo.job_configurations;
DBCC CHECKDB('sreutil') WITH NO_INFOMSGS;
SELECT 
    table_name,
    row_count,
    reserved_size_mb
FROM sys.dm_db_partition_stats 
ORDER BY reserved_size_mb DESC;''',
        'connection': 'default',
        'enabled': True,
        'timeout': 600,
        'schedule': {
            'type': 'cron',
            'expression': '0 2 * * 0',  # Sunday at 2 AM
            'timezone': 'UTC'
        },
        'retryPolicy': {
            'maxRetries': 2,
            'retryDelay': 60
        }
    }
    
    return yaml.dump(sample_config, default_flow_style=False, allow_unicode=True)