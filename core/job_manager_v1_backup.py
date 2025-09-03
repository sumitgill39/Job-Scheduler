"""
Job Manager using SQLAlchemy for database operations
Clean implementation without connection pools
"""

import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from utils.logger import get_logger


class JobManager:
    """Manages job configurations using SQLAlchemy"""
    
    def __init__(self, db_session=None):
        self.logger = get_logger(__name__)
        self.db_session = db_session  # Will be injected by SQLAlchemy setup
        self.logger.info("[JOB_MANAGER] SQLAlchemy Job Manager initialized")
    
    def set_session(self, session):
        """Set the database session"""
        self.db_session = session
    
    def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job and store in database
        
        Args:
            job_data: Dictionary containing job configuration
            
        Returns:
            Dict with success status and job_id or error message
        """
        try:
            # Generate job ID
            job_id = str(uuid.uuid4())
            job_name = job_data.get('name', 'Unnamed Job')
            job_type = job_data.get('type', 'unknown')
            
            self.logger.info(f"[JOB_MANAGER] Creating {job_type} job '{job_name}' with ID: {job_id}")
            
            # Validate required fields
            if not job_name or job_name.strip() == '':
                return {
                    'success': False,
                    'error': 'Job name is required'
                }
            
            if job_type not in ['sql', 'powershell']:
                return {
                    'success': False,
                    'error': f'Unsupported job type: {job_type}'
                }
            
            # Import SQLAlchemy models
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            # Extract job configuration fields
            config_fields = {}
            
            # Common fields for all job types
            if 'type' in job_data:
                config_fields['type'] = job_data['type']
            
            # Add advanced fields to configuration if provided
            if 'timeout' in job_data:
                config_fields['timeout'] = job_data['timeout']
            if 'max_retries' in job_data:
                config_fields['max_retries'] = job_data['max_retries']
            if 'retry_delay' in job_data:
                config_fields['retry_delay'] = job_data['retry_delay']
            
            # SQL job specific fields
            if job_type == 'sql':
                if 'sql_query' in job_data:
                    config_fields['sql_query'] = job_data['sql_query']
                if 'connection_name' in job_data:
                    config_fields['connection_name'] = job_data['connection_name']
            
            # PowerShell job specific fields
            elif job_type == 'powershell':
                # Handle inline script content
                if 'script_content' in job_data:
                    config_fields['script_content'] = job_data['script_content']
                # Handle script file path
                if 'script_path' in job_data:
                    config_fields['script_path'] = job_data['script_path']
                # Handle other PowerShell-specific fields
                if 'execution_policy' in job_data:
                    config_fields['execution_policy'] = job_data['execution_policy']
                if 'working_directory' in job_data:
                    config_fields['working_directory'] = job_data['working_directory']
                if 'parameters' in job_data:
                    config_fields['parameters'] = job_data['parameters']
            
            # Create job configuration
            with get_db_session() as session:
                job_config = JobConfiguration(
                    job_id=job_id,
                    name=job_name,
                    job_type=job_type,
                    configuration=json.dumps(config_fields),
                    enabled=job_data.get('enabled', True),
                    created_by='system',
                    # Add schedule fields
                    schedule_enabled=job_data.get('schedule_enabled', False),
                    schedule_type=job_data.get('schedule_type'),
                    schedule_expression=job_data.get('schedule_expression'),
                    timezone=job_data.get('timezone', 'UTC'),
                    next_run_time=job_data.get('next_run_time')
                )
                
                session.add(job_config)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] Job created successfully: {job_id}")
                
                return {
                    'success': True,
                    'job_id': job_id,
                    'message': f'Job {job_name} created successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error creating job: {e}")
            return {
                'success': False,
                'error': f'Error creating job: {str(e)}'
            }
    
    def list_jobs(self, enabled_only: bool = False, limit: int = None, job_type: str = None) -> List[Dict[str, Any]]:
        """List jobs from database
        
        Args:
            enabled_only: If True, return only enabled jobs
            limit: Maximum number of jobs to return
            job_type: If provided, filter by job type
            
        Returns:
            List of job dictionaries
        """
        try:
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Listing jobs (enabled_only={enabled_only}, limit={limit}, job_type={job_type})")
            
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
                
                # Convert to dictionaries and parse JSON configuration
                result = []
                for job in jobs:
                    job_dict = job.to_dict()
                    try:
                        job_dict['configuration'] = json.loads(job_dict['configuration'] or '{}')
                    except json.JSONDecodeError:
                        job_dict['configuration'] = {}
                    result.append(job_dict)
                
                self.logger.info(f"[JOB_MANAGER] Found {len(result)} jobs")
                return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error listing jobs: {e}")
            return []
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID
        
        Args:
            job_id: Job ID to retrieve
            
        Returns:
            Job dictionary or None if not found
        """
        try:
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Getting job: {job_id}")
            
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
                    
                    self.logger.info(f"[JOB_MANAGER] Found job: {job.name}")
                    return job_dict
                else:
                    self.logger.warning(f"[JOB_MANAGER] Job not found: {job_id}")
                    return None
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting job {job_id}: {e}")
            return None
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job
        
        Args:
            job_id: Job ID to update
            job_data: Updated job data
            
        Returns:
            Dict with success status
        """
        try:
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Updating job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfiguration).filter(
                    JobConfiguration.job_id == job_id
                ).first()
                
                if not job:
                    return {
                        'success': False,
                        'error': f'Job {job_id} not found'
                    }
                
                # Update fields if provided
                if 'name' in job_data:
                    job.name = job_data['name']
                if 'enabled' in job_data:
                    job.enabled = job_data['enabled']
                
                # Update schedule fields
                if 'schedule_enabled' in job_data:
                    job.schedule_enabled = job_data['schedule_enabled']
                if 'schedule_type' in job_data:
                    job.schedule_type = job_data['schedule_type']
                if 'schedule_expression' in job_data:
                    job.schedule_expression = job_data['schedule_expression']
                if 'timezone' in job_data:
                    job.timezone = job_data['timezone']
                
                # Update other advanced fields (these would need to be stored in config if not in model)
                # For now, we'll store them in the configuration JSON
                advanced_fields = {}
                if 'timeout' in job_data:
                    advanced_fields['timeout'] = job_data['timeout']
                if 'max_retries' in job_data:
                    advanced_fields['max_retries'] = job_data['max_retries']
                if 'retry_delay' in job_data:
                    advanced_fields['retry_delay'] = job_data['retry_delay']
                
                # Update configuration fields
                config_fields = {}
                
                # Include advanced fields in configuration
                config_fields.update(advanced_fields)
                
                # Common fields for all job types
                if 'type' in job_data:
                    config_fields['type'] = job_data['type']
                
                # SQL job specific fields
                if job.job_type == 'sql':
                    if 'sql_query' in job_data:
                        config_fields['sql_query'] = job_data['sql_query']
                    if 'connection_name' in job_data:
                        config_fields['connection_name'] = job_data['connection_name']
                
                # PowerShell job specific fields
                elif job.job_type == 'powershell':
                    # Handle inline script content
                    if 'script_content' in job_data:
                        config_fields['script_content'] = job_data['script_content']
                    # Handle script file path
                    if 'script_path' in job_data:
                        config_fields['script_path'] = job_data['script_path']
                    # Handle other PowerShell-specific fields
                    if 'execution_policy' in job_data:
                        config_fields['execution_policy'] = job_data['execution_policy']
                    if 'working_directory' in job_data:
                        config_fields['working_directory'] = job_data['working_directory']
                    if 'parameters' in job_data:
                        config_fields['parameters'] = job_data['parameters']
                
                # Only update configuration if we have relevant fields
                if config_fields:
                    job.configuration = json.dumps(config_fields)
                
                # Update modified date
                job.modified_date = datetime.now()
                
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] Job updated successfully: {job_id}")
                return {
                    'success': True,
                    'message': f'Job {job.name} updated successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error updating job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating job: {str(e)}'
            }
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete a job
        
        Args:
            job_id: Job ID to delete
            
        Returns:
            Dict with success status
        """
        try:
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Deleting job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfiguration).filter(
                    JobConfiguration.job_id == job_id
                ).first()
                
                if not job:
                    return {
                        'success': False,
                        'error': f'Job {job_id} not found'
                    }
                
                job_name = job.name
                session.delete(job)
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] Job deleted successfully: {job_name}")
                return {
                    'success': True,
                    'message': f'Job {job_name} deleted successfully'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error deleting job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error deleting job: {str(e)}'
            }
    
    def get_execution_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a specific job
        
        Args:
            job_id: Job ID to get history for
            limit: Maximum number of records to return
            
        Returns:
            List of execution history dictionaries
        """
        try:
            from database.sqlalchemy_models import JobExecutionHistory, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Getting execution history for job: {job_id} (limit: {limit})")
            
            with get_db_session() as session:
                query = session.query(JobExecutionHistory).filter(
                    JobExecutionHistory.job_id == job_id
                ).order_by(JobExecutionHistory.start_time.desc()).limit(limit)
                
                executions = query.all()
                
                result = [execution.to_dict() for execution in executions]
                
                self.logger.info(f"[JOB_MANAGER] Found {len(result)} execution records for job {job_id}")
                return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting execution history for job {job_id}: {e}")
            return []
    
    def get_all_execution_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get execution history for all jobs
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of execution history dictionaries
        """
        try:
            from database.sqlalchemy_models import JobExecutionHistory, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Getting all execution history (limit: {limit})")
            
            with get_db_session() as session:
                query = session.query(JobExecutionHistory).order_by(
                    JobExecutionHistory.start_time.desc()
                ).limit(limit)
                
                executions = query.all()
                
                result = [execution.to_dict() for execution in executions]
                
                self.logger.info(f"[JOB_MANAGER] Found {len(result)} total execution records")
                return result
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error getting all execution history: {e}")
            return []
    
    def toggle_job(self, job_id: str, enabled: bool = None) -> Dict[str, Any]:
        """Toggle job enabled/disabled status
        
        Args:
            job_id: Job ID to toggle
            enabled: If provided, set to this specific state. If None, toggle current state
            
        Returns:
            Dict with success status and current enabled state
        """
        try:
            from database.sqlalchemy_models import JobConfiguration, get_db_session
            
            self.logger.info(f"[JOB_MANAGER] Toggling job: {job_id}")
            
            with get_db_session() as session:
                job = session.query(JobConfiguration).filter(
                    JobConfiguration.job_id == job_id
                ).first()
                
                if not job:
                    return {
                        'success': False,
                        'error': f'Job {job_id} not found'
                    }
                
                # Determine new enabled state
                if enabled is not None:
                    new_enabled = enabled
                else:
                    new_enabled = not job.enabled
                
                old_state = 'enabled' if job.enabled else 'disabled'
                new_state = 'enabled' if new_enabled else 'disabled'
                
                job.enabled = new_enabled
                job.modified_date = datetime.now()
                
                session.commit()
                
                self.logger.info(f"[JOB_MANAGER] Job {job.name} toggled from {old_state} to {new_state}")
                return {
                    'success': True,
                    'message': f'Job {job.name} {new_state} successfully',
                    'enabled': new_enabled
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error toggling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error toggling job: {str(e)}'
            }