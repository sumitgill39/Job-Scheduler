"""
Unified Job Manager - PURE V2 YAML ONLY
Handles ONLY V2 YAML-based job configurations
NO V1 LEGACY CODE - Clean implementation
Created: 2025-09-04 12:25
"""

import yaml
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from utils.logger import get_logger
from database.sqlalchemy_models import (
    get_db_session, 
    JobConfigurationV2, 
    JobExecutionHistoryV2
)


class JobManager:
    """Pure V2 YAML job manager - NO V1 legacy code"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("[JOB_MANAGER] Unified Job Manager initialized (V2 YAML support only)")
    
    def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new V2 YAML job"""
        try:
            self.logger.info("[JOB_MANAGER] Creating V2 YAML job")
            
            # All jobs are V2 YAML now
            return self._create_v2_job(job_data)
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error creating job: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_v2_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create V2 job with YAML configuration"""
        # Generate job ID
        job_id = str(uuid.uuid4())
        job_name = job_data.get('name', f'V2_Job_{job_id[:8]}')
        
        try:
            with get_db_session() as session:
                # Create new V2 job record
                job_config = JobConfigurationV2(
                    job_id=job_id,
                    name=job_name,
                    description=job_data.get('description', ''),
                    version='2.0',  # Always V2
                    yaml_configuration=job_data.get('yaml_config', job_data.get('yaml_configuration', '')),
                    enabled=job_data.get('enabled', True),
                    created_by=job_data.get('created_by', 'system')
                )
                
                session.add(job_config)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] V2 job created successfully: {job_name} ({job_id})")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'version': 'v2',
                    'message': f'V2 Job {job_name} created successfully'
                }
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error creating V2 job: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def list_jobs(self, enabled_only: bool = False, limit: int = None, job_type: str = None) -> List[Dict[str, Any]]:
        """
        List V2 YAML jobs only
        
        Args:
            enabled_only: If True, return only enabled jobs
            limit: Maximum number of jobs to return
            job_type: If provided, filter by job type
            
        Returns:
            List of V2 job dictionaries
        """
        try:
            self.logger.info(f"[JOB_MANAGER] Listing jobs (enabled_only={enabled_only}, limit={limit}, job_type={job_type})")
            
            # Get V2 jobs only
            v2_jobs = self._list_v2_jobs(enabled_only, limit, job_type)
            for job in v2_jobs:
                job['_version'] = 'v2'
                job['_format'] = 'yaml'
            
            self.logger.info(f"[JOB_MANAGER] Found {len(v2_jobs)} jobs")
            return v2_jobs
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error listing jobs: {e}")
            return []
    
    def _list_v2_jobs(self, enabled_only: bool, limit: int, job_type: str) -> List[Dict[str, Any]]:
        """List V2 jobs from JobConfigurationV2 table"""
        with get_db_session() as session:
            query = session.query(JobConfigurationV2)
            
            if enabled_only:
                query = query.filter(JobConfigurationV2.enabled == True)
            
            query = query.order_by(JobConfigurationV2.created_date.desc())
            
            if limit:
                query = query.limit(limit)
            
            jobs = query.all()
            
            result = []
            for job in jobs:
                job_dict = job.to_dict()
                try:
                    parsed_config = yaml.safe_load(job_dict['yaml_configuration'])
                    job_dict['parsed_config'] = parsed_config
                    
                    # Filter by job type if specified
                    if job_type:
                        config_type = parsed_config.get('type', '').lower()
                        if config_type != job_type.lower():
                            continue
                            
                except yaml.YAMLError:
                    job_dict['parsed_config'] = {}
                
                result.append(job_dict)
            
            return result
    
    def get_job(self, job_id: str, job_version: str = None, version: str = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Get a V2 job by ID
        
        Args:
            job_id: Job ID to retrieve
            job_version: Ignored - compatibility parameter
            version: Ignored - compatibility parameter  
            **kwargs: Ignored - compatibility parameters
            
        Returns:
            Job dictionary with _version field or None if not found
        """
        try:
            print(f"**** JOB_MANAGER: get_job() called with parameters: ****")
            print(f"**** JOB_MANAGER: job_id={job_id} ****")
            print(f"**** JOB_MANAGER: job_version={job_version} ****")  
            print(f"**** JOB_MANAGER: version={version} ****")
            print(f"**** JOB_MANAGER: kwargs={kwargs} ****")
            print(f"**** JOB_MANAGER: method file: {__file__} ****")
            
            self.logger.info(f"[JOB_MANAGER] Getting V2 job: {job_id}")
            if version is not None:
                print(f"**** JOB_MANAGER: WARNING - version parameter passed: {version} ****")
                self.logger.warning(f"[JOB_MANAGER] LEGACY: Received deprecated 'version' parameter: {version}")
            if kwargs:
                print(f"**** JOB_MANAGER: WARNING - extra kwargs passed: {kwargs} ****") 
                self.logger.warning(f"[JOB_MANAGER] EXTRA: Received additional parameters: {kwargs}")
            
            # Only V2 jobs supported now
            job = self._get_v2_job(job_id)
            if job:
                job['_version'] = 'v2'
                job['_format'] = 'yaml'
                return job
                
            return None
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting job {job_id}: {e}")
            return None
    
    def _get_v2_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get V2 job from JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if job:
                job_dict = job.to_dict()
                
                # Add debugging for job data from database
                print(f"**** JOB_MANAGER DEBUG: Raw job from DB - name: {job.name} ****")
                print(f"**** JOB_MANAGER DEBUG: yaml_configuration length: {len(job.yaml_configuration) if job.yaml_configuration else 0} ****")
                print(f"**** JOB_MANAGER DEBUG: yaml_configuration preview: {repr(job.yaml_configuration[:200]) if job.yaml_configuration else 'None'} ****")
                print(f"**** JOB_MANAGER DEBUG: job_dict keys: {job_dict.keys()} ****")
                
                # Parse YAML configuration
                try:
                    if job_dict['yaml_configuration']:
                        parsed_result = yaml.safe_load(job_dict['yaml_configuration'])
                        job_dict['parsed_config'] = parsed_result
                        print(f"**** JOB_MANAGER DEBUG: YAML parsed successfully: {parsed_result} ****")
                    else:
                        job_dict['parsed_config'] = {}
                        print(f"**** JOB_MANAGER DEBUG: No YAML configuration, using empty dict ****")
                except yaml.YAMLError as e:
                    job_dict['parsed_config'] = {}
                    print(f"**** JOB_MANAGER DEBUG: YAML parsing error: {e} ****")
                
                print(f"**** JOB_MANAGER DEBUG: Final job_dict keys: {job_dict.keys()} ****")
                print(f"**** JOB_MANAGER DEBUG: parsed_config: {job_dict.get('parsed_config')} ****")
                
                # Extract fields from YAML for template compatibility - CLEAN VERSION
                parsed_config = job_dict.get('parsed_config', {})
                
                if isinstance(parsed_config, dict) and parsed_config:
                    # Extract job type - handle both cases (Powershell and powershell)
                    job_type = parsed_config.get('type', 'unknown').lower()
                    job_dict['job_type'] = job_type
                    
                    # Extract all PowerShell fields
                    job_dict['script_content'] = parsed_config.get('inlineScript', '')
                    job_dict['script_path'] = parsed_config.get('scriptPath', '')
                    job_dict['execution_policy'] = parsed_config.get('executionPolicy', 'RemoteSigned')
                    job_dict['parameters'] = parsed_config.get('parameters', [])
                    
                    # Extract SQL fields
                    job_dict['sql_query'] = parsed_config.get('query', '')
                    job_dict['connection_name'] = parsed_config.get('connection', '')
                    
                    # Additional fields
                    job_dict['working_directory'] = parsed_config.get('workingDirectory', '')
                    job_dict['timeout'] = parsed_config.get('timeout', 300)
                    
                    # Extract schedule configuration
                    schedule_config = parsed_config.get('schedule', {})
                    if schedule_config and isinstance(schedule_config, dict):
                        # Schedule is present
                        job_dict['schedule_enabled'] = True
                        job_dict['schedule_type'] = schedule_config.get('type', 'cron')
                        
                        # Handle different schedule types
                        if schedule_config.get('type') == 'cron':
                            # Look for both 'cron' and 'expression' fields
                            job_dict['cron_expression'] = schedule_config.get('cron', schedule_config.get('expression', '0 0 * * *'))
                        elif schedule_config.get('type') == 'interval':
                            interval_data = schedule_config.get('interval', {})
                            job_dict['interval_days'] = interval_data.get('days', 0)
                            job_dict['interval_hours'] = interval_data.get('hours', 0)
                            job_dict['interval_minutes'] = interval_data.get('minutes', 0)
                            job_dict['interval_seconds'] = interval_data.get('seconds', 0)
                        elif schedule_config.get('type') == 'date':
                            job_dict['run_date_time'] = schedule_config.get('run_date', '')
                        
                        # Timezone
                        job_dict['schedule_timezone'] = schedule_config.get('timezone', 'UTC')
                        
                        self.logger.info(f"[JOB_MANAGER] Schedule extracted - type: {job_dict['schedule_type']}, timezone: {job_dict['schedule_timezone']}")
                    else:
                        # No schedule configured
                        job_dict['schedule_enabled'] = False
                        job_dict['schedule_type'] = 'cron'
                        job_dict['cron_expression'] = '0 0 * * *'
                        job_dict['schedule_timezone'] = 'UTC'
                    
                    # Log what we extracted for debugging
                    self.logger.info(f"[JOB_MANAGER] Extracted job_type: {job_type}")
                    self.logger.info(f"[JOB_MANAGER] Has script_content: {bool(job_dict['script_content'])}")
                    self.logger.info(f"[JOB_MANAGER] Has script_path: {bool(job_dict['script_path'])}")
                    self.logger.info(f"[JOB_MANAGER] Has sql_query: {bool(job_dict['sql_query'])}")
                    
                    # Create nested configuration object for backward compatibility
                    job_dict['configuration'] = {
                        'script_content': job_dict['script_content'],
                        'script_path': job_dict['script_path'],
                        'execution_policy': job_dict['execution_policy'],
                        'parameters': job_dict['parameters'],
                        'sql_query': job_dict['sql_query'],
                        'connection_name': job_dict['connection_name'],
                        'working_directory': job_dict['working_directory'],
                        'schedule': schedule_config if schedule_config else {}
                    }
                else:
                    # Empty or invalid YAML - provide defaults
                    job_dict['job_type'] = 'unknown'
                    job_dict['script_content'] = ''
                    job_dict['script_path'] = ''
                    job_dict['execution_policy'] = 'RemoteSigned'
                    job_dict['parameters'] = []
                    job_dict['sql_query'] = ''
                    job_dict['connection_name'] = ''
                    job_dict['working_directory'] = ''
                    job_dict['timeout'] = 300
                    job_dict['timezone'] = 'UTC'
                    
                    job_dict['configuration'] = {
                        'script_content': '',
                        'script_path': '',
                        'execution_policy': 'RemoteSigned',
                        'parameters': [],
                        'sql_query': '',
                        'connection_name': '',
                        'working_directory': ''
                    }
                    
                    self.logger.warning(f"[JOB_MANAGER] No valid YAML configuration found for job")
                
                print(f"**** JOB_MANAGER DEBUG: Enhanced job_dict with job_type: {job_dict['job_type']} ****")
                
                self.logger.info(f"[JOB_MANAGER] Found V2 job: {job.name}")
                return job_dict
            
            return None
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a V2 job"""
        try:
            self.logger.info(f"[JOB_MANAGER] Updating job: {job_id}")
            
            # All jobs are V2 now
            existing_job = self.get_job(job_id)
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            return self._update_v2_job(job_id, job_data)
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error updating job {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_v2_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update V2 job - CLEAN REWRITE"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if not job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            self.logger.info(f"[JOB_MANAGER] Updating V2 job: {job.name}")
            self.logger.info(f"[JOB_MANAGER] Update data keys: {list(job_data.keys())}")
            
            # Update basic fields
            if 'name' in job_data:
                job.name = job_data['name']
            if 'description' in job_data:
                job.description = job_data['description']
            if 'enabled' in job_data:
                job.enabled = job_data['enabled']
            
            # Handle YAML configuration update
            yaml_updated = False
            
            # Method 1: Direct YAML provided (from API or direct calls)
            if 'yaml_config' in job_data:
                job.yaml_configuration = job_data['yaml_config']
                yaml_updated = True
                self.logger.info(f"[JOB_MANAGER] Updated with direct yaml_config")
            elif 'yaml_configuration' in job_data:
                job.yaml_configuration = job_data['yaml_configuration']
                yaml_updated = True
                self.logger.info(f"[JOB_MANAGER] Updated with direct yaml_configuration")
            
            # Method 2: Build YAML from individual form fields (from edit page)
            elif any(key in job_data for key in ['job_type', 'type', 'script_content', 'script_path', 'execution_policy', 'parameters', 'sql_query', 'connection_name']):
                # Create new YAML configuration from form data
                yaml_config = {}
                
                # Get job type
                job_type = job_data.get('job_type', job_data.get('type', 'powershell'))
                yaml_config['name'] = job_data.get('name', job.name)
                yaml_config['type'] = job_type
                
                # PowerShell specific fields
                if job_type == 'powershell':
                    if job_data.get('script_content'):
                        yaml_config['inlineScript'] = job_data['script_content']
                    if job_data.get('script_path'):
                        yaml_config['scriptPath'] = job_data['script_path']
                    if job_data.get('execution_policy'):
                        yaml_config['executionPolicy'] = job_data['execution_policy']
                    if job_data.get('parameters'):
                        yaml_config['parameters'] = job_data['parameters']
                
                # SQL specific fields  
                elif job_type == 'sql':
                    if job_data.get('sql_query'):
                        yaml_config['query'] = job_data['sql_query']
                    if job_data.get('connection_name'):
                        yaml_config['connection'] = job_data['connection_name']
                
                # Handle schedule configuration
                schedule_enabled = job_data.get('enable_schedule', False) or job_data.get('schedule_enabled', False)
                schedule_timezone = job_data.get('schedule_timezone', 'UTC')  # Renamed to avoid shadowing timezone module
                
                if schedule_enabled:
                    schedule_config = {}
                    schedule_type = job_data.get('schedule_type', 'cron')
                    
                    if schedule_type == 'cron':
                        schedule_config = {
                            'type': 'cron',
                            'expression': job_data.get('cron_expression', '0 0 * * *'),
                            'timezone': schedule_timezone
                        }
                    elif schedule_type == 'interval':
                        # Handle interval scheduling
                        days = int(job_data.get('interval_days', 0))
                        hours = int(job_data.get('interval_hours', 0))
                        minutes = int(job_data.get('interval_minutes', 0))
                        seconds = int(job_data.get('interval_seconds', 0))
                        
                        schedule_config = {
                            'type': 'interval',
                            'interval': {
                                'days': days,
                                'hours': hours,
                                'minutes': minutes,
                                'seconds': seconds
                            },
                            'timezone': schedule_timezone
                        }
                    elif schedule_type == 'once':
                        # Handle one-time scheduling
                        run_date = job_data.get('run_date', '')
                        run_time = job_data.get('run_time', '')
                        if run_date and run_time:
                            run_datetime = f"{run_date}T{run_time}:00"
                            schedule_config = {
                                'type': 'date',
                                'run_date': run_datetime,
                                'timezone': schedule_timezone
                            }
                    
                    if schedule_config:
                        yaml_config['schedule'] = schedule_config
                        self.logger.info(f"[JOB_MANAGER] Added schedule configuration: {schedule_config}")
                
                # Also handle legacy schedule format if it exists
                if job_data.get('schedule'):
                    schedule_data = job_data.get('schedule')
                    if isinstance(schedule_data, dict):
                        yaml_config['schedule'] = schedule_data
                        self.logger.info(f"[JOB_MANAGER] Added legacy schedule configuration: {schedule_data}")
                
                # Convert to YAML string
                job.yaml_configuration = yaml.dump(yaml_config, default_flow_style=False, allow_unicode=True)
                yaml_updated = True
                self.logger.info(f"[JOB_MANAGER] Built new YAML from form fields: {yaml_config}")
            
            if yaml_updated:
                self.logger.info(f"[JOB_MANAGER] YAML configuration updated successfully")
            else:
                self.logger.info(f"[JOB_MANAGER] No YAML update needed")
            
            # Save changes
            job.modified_date = datetime.now(timezone.utc)
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V2 job updated successfully: {job.name}")
            
            return {
                'success': True,
                'job_id': job_id,
                'version': 'v2',
                'message': f'Job {job.name} updated successfully'
            }
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a V2 job"""
        try:
            self.logger.info(f"[JOB_MANAGER] Deleting job: {job_id}")
            
            # Check if job exists
            existing_job = self.get_job(job_id)
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            job_name = existing_job['name']
            
            # Delete V2 job
            result = self._delete_v2_job(job_id)
            
            if result['success']:
                self.logger.info(f"[JOB_MANAGER] Job {job_name} deleted successfully")
            
            return result
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error deleting job {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _delete_v2_job(self, job_id: str) -> Dict[str, Any]:
        """Delete V2 job from JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if job:
                job_name = job.name
                session.delete(job)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] V2 job deleted: {job_name}")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'message': f'V2 Job {job_name} deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'V2 Job {job_id} not found'
                }
    
    def toggle_job(self, job_id: str, enabled: bool = None) -> Dict[str, Any]:
        """Toggle job enabled/disabled state or set to specific state"""
        try:
            self.logger.info(f"[JOB_MANAGER] Toggling job: {job_id}")
            
            # Check if job exists
            existing_job = self.get_job(job_id)
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            # Determine new enabled state
            current_enabled = existing_job.get('enabled', True)
            
            if enabled is not None:
                # Set to specific state
                new_enabled = enabled
                self.logger.info(f"[JOB_MANAGER] Setting job {job_id} enabled state to {new_enabled}")
            else:
                # Toggle current state
                new_enabled = not current_enabled
                self.logger.info(f"[JOB_MANAGER] Toggling job {job_id} from {current_enabled} to {new_enabled}")
            
            # Update V2 job
            result = self._toggle_v2_job(job_id, new_enabled)
            
            return result
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error toggling job {job_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _toggle_v2_job(self, job_id: str, enabled: bool) -> Dict[str, Any]:
        """Toggle V2 job in JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if job:
                job.enabled = enabled
                job.modified_date = datetime.now(timezone.utc)
                session.commit()
                
                status = "enabled" if enabled else "disabled"
                self.logger.info(f"[JOB_MANAGER] V2 job {status}: {job.name}")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'enabled': enabled,
                    'message': f'V2 Job {job.name} {status} successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'V2 Job {job_id} not found'
                }
    
    # Execution history methods
    def get_all_execution_history(self, limit: int = 50, job_id: str = None, status: str = None) -> List[Dict[str, Any]]:
        """Get execution history for all jobs or specific job"""
        try:
            with get_db_session() as session:
                query = session.query(JobExecutionHistoryV2)
                
                if job_id:
                    query = query.filter(JobExecutionHistoryV2.job_id == job_id)
                
                if status:
                    query = query.filter(JobExecutionHistoryV2.status == status)
                
                query = query.order_by(JobExecutionHistoryV2.start_time.desc())
                
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
                        'executed_by': execution.executed_by,
                        '_version': 'v2'  # All executions are V2 now
                    })
                
                return result
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting execution history: {e}")
            return []
    
    def get_job_execution_history(self, job_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get execution history for a specific job"""
        return self.get_all_execution_history(limit=limit, job_id=job_id)