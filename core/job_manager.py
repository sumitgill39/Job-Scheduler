"""
Unified Job Manager - Consolidated V1 and V2 functionality
Handles both JSON (V1) and YAML (V2) job configurations in a single manager
"""

import yaml
import json
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from utils.logger import get_logger
from database.sqlalchemy_models import (
    JobConfiguration, JobConfigurationV2, 
    JobExecutionHistory, JobExecutionHistoryV2, 
    get_db_session
)


class JobManager:
    """Unified job manager supporting both V1 (JSON) and V2 (YAML) formats"""
    
    def __init__(self, db_session=None):
        self.logger = get_logger(__name__)
        self.db_session = db_session  # Will be injected by SQLAlchemy setup
        self.logger.info("[JOB_MANAGER] Unified Job Manager initialized (V1 + V2 support)")
    
    def set_session(self, session):
        """Set the database session"""
        self.db_session = session
    
    def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new job using appropriate format (V1 JSON or V2 YAML)
        
        Args:
            job_data: Dictionary containing job configuration
            - For V1: Standard job fields (name, type, sql_query, etc.)
            - For V2: Must include 'yaml_config' field
            
        Returns:
            Dict with success status and job_id or error message
        """
        try:
            # Detect format based on presence of yaml_config
            is_v2_format = 'yaml_config' in job_data
            
            if is_v2_format:
                return self._create_v2_job(job_data)
            else:
                return self._create_v1_job(job_data)
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error creating job: {e}")
            return {
                'success': False,
                'error': f'Error creating job: {str(e)}'
            }
    
    def _create_v1_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create V1 job with JSON configuration"""
        # Generate job ID
        job_id = str(uuid.uuid4())
        job_name = job_data.get('name', 'Unnamed Job')
        job_type = job_data.get('type', 'unknown')
        
        self.logger.info(f"[JOB_MANAGER] Creating V1 {job_type} job '{job_name}' with ID: {job_id}")
        
        # Validate required fields
        if not job_name or job_name.strip() == '':
            return {'success': False, 'error': 'Job name is required'}
        
        if job_type not in ['sql', 'powershell']:
            return {'success': False, 'error': f'Unsupported job type: {job_type}'}
        
        # Extract job configuration fields
        config_fields = {}
        
        # Common fields for all job types
        if 'type' in job_data:
            config_fields['type'] = job_data['type']
        
        # Add advanced fields to configuration if provided
        for field in ['timeout', 'max_retries', 'retry_delay']:
            if field in job_data:
                config_fields[field] = job_data[field]
        
        # SQL job specific fields
        if job_type == 'sql':
            for field in ['sql_query', 'connection_name']:
                if field in job_data:
                    config_fields[field] = job_data[field]
        
        # PowerShell job specific fields
        elif job_type == 'powershell':
            for field in ['script_content', 'script_path', 'execution_policy', 'working_directory', 'parameters']:
                if field in job_data:
                    config_fields[field] = job_data[field]
        
        # Create job configuration
        with get_db_session() as session:
            job_config = JobConfiguration(
                job_id=job_id,
                name=job_name,
                job_type=job_type,
                configuration=json.dumps(config_fields),
                enabled=job_data.get('enabled', True),
                created_by='system',
                schedule_enabled=job_data.get('schedule_enabled', False),
                schedule_type=job_data.get('schedule_type'),
                schedule_expression=job_data.get('schedule_expression'),
                timezone=job_data.get('timezone', 'UTC'),
                next_run_time=job_data.get('next_run_time')
            )
            
            session.add(job_config)
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V1 job created successfully: {job_id}")
            
            return {
                'success': True,
                'job_id': job_id,
                'version': 'v1',
                'message': f'Job {job_name} created successfully'
            }
    
    def _create_v2_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create V2 job with YAML configuration"""
        # Generate job ID
        job_id = str(uuid.uuid4())
        job_name = job_data.get('name', 'Unnamed Job')
        description = job_data.get('description', f'V2 Job: {job_name}')
        yaml_config = job_data.get('yaml_config', '')
        
        self.logger.info(f"[JOB_MANAGER] Creating V2 job '{job_name}' with ID: {job_id}")
        
        # Validate required fields
        if not job_name or job_name.strip() == '':
            return {'success': False, 'error': 'Job name is required'}
        
        if not yaml_config or yaml_config.strip() == '':
            return {'success': False, 'error': 'YAML configuration is required'}
        
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
                enabled=job_data.get('enabled', True),
                created_by='system'
            )
            
            session.add(job_config)
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V2 job created successfully: {job_id}")
            
            return {
                'success': True,
                'job_id': job_id,
                'version': 'v2',
                'message': f'V2 Job {job_name} created successfully'
            }
    
    def list_jobs(self, enabled_only: bool = False, limit: int = None, job_type: str = None, version: str = 'all') -> List[Dict[str, Any]]:
        """
        List jobs from V1, V2, or both systems
        
        Args:
            enabled_only: If True, return only enabled jobs
            limit: Maximum number of jobs to return
            job_type: If provided, filter by job type
            version: 'v1', 'v2', or 'all' (default)
            
        Returns:
            List of job dictionaries with _version field
        """
        try:
            self.logger.info(f"[JOB_MANAGER] Listing jobs (enabled_only={enabled_only}, limit={limit}, job_type={job_type}, version={version})")
            
            result = []
            
            # Get V1 jobs
            if version in ['v1', 'all']:
                v1_jobs = self._list_v1_jobs(enabled_only, limit, job_type)
                for job in v1_jobs:
                    job['_version'] = 'v1'
                    job['_format'] = 'json'
                result.extend(v1_jobs)
            
            # Get V2 jobs
            if version in ['v2', 'all']:
                v2_jobs = self._list_v2_jobs(enabled_only, limit, job_type)
                for job in v2_jobs:
                    job['_version'] = 'v2'
                    job['_format'] = 'yaml'
                result.extend(v2_jobs)
            
            # Sort by creation date (newest first)
            result.sort(key=lambda x: x.get('created_date', ''), reverse=True)
            
            # Apply limit if specified and not already applied per version
            if limit and version == 'all':
                result = result[:limit]
            
            self.logger.info(f"[JOB_MANAGER] Found {len(result)} jobs")
            return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error listing jobs: {e}")
            return []
    
    def _list_v1_jobs(self, enabled_only: bool, limit: int, job_type: str) -> List[Dict[str, Any]]:
        """List V1 jobs from JobConfiguration table"""
        with get_db_session() as session:
            query = session.query(JobConfiguration)
            
            if enabled_only:
                query = query.filter(JobConfiguration.enabled == True)
                
            if job_type:
                query = query.filter(JobConfiguration.job_type == job_type)
            
            query = query.order_by(JobConfiguration.created_date.desc())
            
            if limit:
                query = query.limit(limit)
            
            jobs = query.all()
            
            result = []
            for job in jobs:
                job_dict = job.to_dict()
                try:
                    job_dict['configuration'] = json.loads(job_dict['configuration'] or '{}')
                except json.JSONDecodeError:
                    job_dict['configuration'] = {}
                result.append(job_dict)
            
            return result
    
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
    
    def get_job(self, job_id: str, version: str = 'auto') -> Optional[Dict[str, Any]]:
        """
        Get a job by ID from appropriate version
        
        Args:
            job_id: Job ID to retrieve
            version: 'v1', 'v2', or 'auto' (searches both)
            
        Returns:
            Job dictionary with _version field or None if not found
        """
        try:
            self.logger.info(f"[JOB_MANAGER] Getting job: {job_id} (version: {version})")
            
            if version == 'auto':
                # Try V2 first, then V1
                job = self._get_v2_job(job_id)
                if job:
                    job['_version'] = 'v2'
                    job['_format'] = 'yaml'
                    return job
                
                job = self._get_v1_job(job_id)
                if job:
                    job['_version'] = 'v1' 
                    job['_format'] = 'json'
                    return job
                
                return None
                
            elif version == 'v2':
                job = self._get_v2_job(job_id)
                if job:
                    job['_version'] = 'v2'
                    job['_format'] = 'yaml'
                return job
                
            else:  # v1
                job = self._get_v1_job(job_id)
                if job:
                    job['_version'] = 'v1'
                    job['_format'] = 'json'
                return job
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting job {job_id}: {e}")
            return None
    
    def _get_v1_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get V1 job from JobConfiguration table"""
        with get_db_session() as session:
            job = session.query(JobConfiguration).filter(
                JobConfiguration.job_id == job_id
            ).first()
            
            if job:
                job_dict = job.to_dict()
                try:
                    job_dict['configuration'] = json.loads(job_dict['configuration'] or '{}')
                except json.JSONDecodeError:
                    job_dict['configuration'] = {}
                
                self.logger.info(f"[JOB_MANAGER] Found V1 job: {job.name}")
                return job_dict
            
            return None
    
    def _get_v2_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get V2 job from JobConfigurationV2 table"""
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
                
                self.logger.info(f"[JOB_MANAGER] Found V2 job: {job.name}")
                return job_dict
            
            return None
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job (automatically detects V1 or V2)"""
        try:
            self.logger.info(f"[JOB_MANAGER] Updating job: {job_id}")
            
            # First, find which version this job is
            existing_job = self.get_job(job_id, version='auto')
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found in either V1 or V2 tables'
                }
            
            job_version = existing_job['_version']
            
            if job_version == 'v2':
                return self._update_v2_job(job_id, job_data)
            else:
                return self._update_v1_job(job_id, job_data)
                
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error updating job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating job: {str(e)}'
            }
    
    def _update_v1_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update V1 job in JobConfiguration table"""
        with get_db_session() as session:
            job = session.query(JobConfiguration).filter(
                JobConfiguration.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V1 job {job_id} not found'}
            
            # Update basic fields
            for field in ['name', 'enabled']:
                if field in job_data:
                    setattr(job, field, job_data[field])
            
            # Update schedule fields
            for field in ['schedule_enabled', 'schedule_type', 'schedule_expression', 'timezone']:
                if field in job_data:
                    setattr(job, field, job_data[field])
            
            # Update configuration fields
            config_fields = {}
            
            # Include advanced fields in configuration
            for field in ['timeout', 'max_retries', 'retry_delay', 'type']:
                if field in job_data:
                    config_fields[field] = job_data[field]
            
            # Job type specific fields
            if job.job_type == 'sql':
                for field in ['sql_query', 'connection_name']:
                    if field in job_data:
                        config_fields[field] = job_data[field]
            elif job.job_type == 'powershell':
                for field in ['script_content', 'script_path', 'execution_policy', 'working_directory', 'parameters']:
                    if field in job_data:
                        config_fields[field] = job_data[field]
            
            if config_fields:
                job.configuration = json.dumps(config_fields)
            
            job.modified_date = datetime.now()
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V1 job updated successfully: {job_id}")
            return {
                'success': True,
                'version': 'v1',
                'message': f'Job {job.name} updated successfully'
            }
    
    def _update_v2_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update V2 job in JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V2 job {job_id} not found'}
            
            # Update fields if provided
            for field in ['name', 'description', 'enabled']:
                if field in job_data:
                    setattr(job, field, job_data[field])
            
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
            
            job.modified_date = datetime.now()
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V2 job updated successfully: {job_id}")
            return {
                'success': True,
                'version': 'v2',
                'message': f'V2 job {job.name} updated successfully'
            }
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a job (automatically detects V1 or V2)"""
        try:
            self.logger.info(f"[JOB_MANAGER] Deleting job: {job_id}")
            
            # First, find which version this job is
            existing_job = self.get_job(job_id, version='auto')
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found in either V1 or V2 tables'
                }
            
            job_version = existing_job['_version']
            job_name = existing_job['name']
            
            if job_version == 'v2':
                result = self._delete_v2_job(job_id)
            else:
                result = self._delete_v1_job(job_id)
            
            if result['success']:
                result['version'] = job_version
                result['message'] = f'{job_version.upper()} job {job_name} deleted successfully'
            
            return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error deleting job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error deleting job: {str(e)}'
            }
    
    def _delete_v1_job(self, job_id: str) -> Dict[str, Any]:
        """Delete V1 job from JobConfiguration table"""
        with get_db_session() as session:
            job = session.query(JobConfiguration).filter(
                JobConfiguration.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V1 job {job_id} not found'}
            
            session.delete(job)
            session.commit()
            
            return {'success': True}
    
    def _delete_v2_job(self, job_id: str) -> Dict[str, Any]:
        """Delete V2 job from JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V2 job {job_id} not found'}
            
            session.delete(job)
            session.commit()
            
            return {'success': True}
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a job from V2 table only"""
        try:
            self.logger.info(f"[JOB_MANAGER] Getting execution history for job: {job_id} from V2 table (limit: {limit})")
            
            # Get V2 execution history only
            with get_db_session() as session:
                query = session.query(JobExecutionHistoryV2).filter(
                    JobExecutionHistoryV2.job_id == job_id
                ).order_by(JobExecutionHistoryV2.start_time.desc()).limit(limit)
                
                executions = query.all()
                v2_history = [execution.to_dict() for execution in executions]
                
                # Add version tag for consistency
                for record in v2_history:
                    record['_version'] = 'v2'
                
                self.logger.info(f"[JOB_MANAGER] Found {len(v2_history)} V2 execution records for job {job_id}")
                return v2_history
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting V2 execution history for job {job_id}: {e}")
            return []
    
    def get_all_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history for all jobs from V2 table only"""
        try:
            self.logger.info(f"[JOB_MANAGER] Getting all execution history from V2 table (limit: {limit})")
            
            # Get V2 execution history only
            with get_db_session() as session:
                query = session.query(JobExecutionHistoryV2).order_by(
                    JobExecutionHistoryV2.start_time.desc()
                ).limit(limit)
                
                executions = query.all()
                v2_history = [execution.to_dict() for execution in executions]
                
                # Add version tag for consistency
                for record in v2_history:
                    record['_version'] = 'v2'
                
                self.logger.info(f"[JOB_MANAGER] Found {len(v2_history)} execution records from V2 table")
                return v2_history
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting V2 execution history: {e}")
            return []
    
    def toggle_job(self, job_id: str, enabled: bool = None) -> Dict[str, Any]:
        """Toggle job enabled/disabled status (automatically detects V1 or V2)"""
        try:
            self.logger.info(f"[JOB_MANAGER] Toggling job: {job_id}")
            
            # First, find which version this job is
            existing_job = self.get_job(job_id, version='auto')
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found in either V1 or V2 tables'
                }
            
            job_version = existing_job['_version']
            
            # Determine new enabled state
            current_enabled = existing_job.get('enabled', False)
            if enabled is not None:
                new_enabled = enabled
            else:
                new_enabled = not current_enabled
            
            # Update the appropriate table
            if job_version == 'v2':
                result = self._toggle_v2_job(job_id, new_enabled)
            else:
                result = self._toggle_v1_job(job_id, new_enabled)
            
            if result['success']:
                result['version'] = job_version
                result['enabled'] = new_enabled
            
            return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error toggling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error toggling job: {str(e)}'
            }
    
    def _toggle_v1_job(self, job_id: str, enabled: bool) -> Dict[str, Any]:
        """Toggle V1 job in JobConfiguration table"""
        with get_db_session() as session:
            job = session.query(JobConfiguration).filter(
                JobConfiguration.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V1 job {job_id} not found'}
            
            old_state = 'enabled' if job.enabled else 'disabled'
            new_state = 'enabled' if enabled else 'disabled'
            
            job.enabled = enabled
            job.modified_date = datetime.now()
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V1 job {job.name} toggled from {old_state} to {new_state}")
            return {
                'success': True,
                'message': f'Job {job.name} {new_state} successfully'
            }
    
    def _toggle_v2_job(self, job_id: str, enabled: bool) -> Dict[str, Any]:
        """Toggle V2 job in JobConfigurationV2 table"""
        with get_db_session() as session:
            job = session.query(JobConfigurationV2).filter(
                JobConfigurationV2.job_id == job_id
            ).first()
            
            if not job:
                return {'success': False, 'error': f'V2 job {job_id} not found'}
            
            old_state = 'enabled' if job.enabled else 'disabled'
            new_state = 'enabled' if enabled else 'disabled'
            
            job.enabled = enabled
            job.modified_date = datetime.now()
            session.commit()
            
            self.logger.info(f"[JOB_MANAGER] V2 job {job.name} toggled from {old_state} to {new_state}")
            return {
                'success': True,
                'message': f'V2 job {job.name} {new_state} successfully'
            }
    
    # V2-specific methods for backward compatibility
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
                
                # Update job statistics if it's a V2 job
                try:
                    self._update_job_statistics(execution_data['job_id'], execution_data, session)
                except Exception as e:
                    self.logger.warning(f"[JOB_MANAGER] Could not update job statistics: {e}")
                
                self.logger.info(f"[JOB_MANAGER] Execution recorded: {execution_id}")
                return {
                    'success': True,
                    'execution_id': execution_id
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error recording execution: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
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
        """Update job performance statistics for V2 jobs"""
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
            self.logger.error(f"[JOB_MANAGER] Error updating job statistics: {e}")
    
    # Helper methods for V2 sample configurations
    def get_sample_configs(self) -> Dict[str, Dict[str, str]]:
        """Get sample YAML configurations for V2 jobs"""
        return {
            'powershell': {
                'name': 'Sample PowerShell Job',
                'description': 'System health check script',
                'yaml_config': create_sample_powershell_yaml()
            },
            'sql': {
                'name': 'Sample SQL Job', 
                'description': 'Database maintenance query',
                'yaml_config': create_sample_sql_yaml()
            }
        }


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