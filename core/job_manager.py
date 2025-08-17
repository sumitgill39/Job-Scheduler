"""
Job Manager for storing and retrieving job configurations from database
"""

import json
import uuid
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from database.connection_pool import get_connection_pool
from utils.logger import get_logger


class JobManager:
    """Manages job configurations in database"""
    
    def __init__(self):
        self.connection_pool = get_connection_pool()
        self.logger = get_logger(__name__)
        self.logger.info("[JOB_MANAGER] Job Manager initialized with connection pooling")
    
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
            
            # Validate job-specific requirements
            if job_type == 'sql':
                if not job_data.get('sql_query'):
                    return {
                        'success': False,
                        'error': 'SQL query is required for SQL jobs'
                    }
                if not job_data.get('connection_name'):
                    return {
                        'success': False,
                        'error': 'Database connection is required for SQL jobs'
                    }
                
                # Validate connection exists
                if not self._validate_connection(job_data.get('connection_name')):
                    return {
                        'success': False,
                        'error': f'Database connection "{job_data.get("connection_name")}" not found'
                    }
            
            elif job_type == 'powershell':
                if not job_data.get('script_content') and not job_data.get('script_path'):
                    return {
                        'success': False,
                        'error': 'PowerShell script content or path is required'
                    }
            
            # Prepare job configuration for storage
            job_config = {
                'job_id': job_id,
                'name': job_name.strip(),
                'job_type': job_type,  # Changed from 'type' to 'job_type' for consistency
                'description': job_data.get('description', ''),
                'enabled': job_data.get('enabled', True),
                'created_date': datetime.now().isoformat(),
                'configuration': {
                    'basic': {
                        'timeout': job_data.get('timeout', 300),
                        'max_retries': job_data.get('max_retries', 3),
                        'retry_delay': job_data.get('retry_delay', 60),
                        'run_as': job_data.get('run_as', '')
                    }
                }
            }
            
            # Add job-specific configuration
            if job_type == 'sql':
                sql_query = job_data.get('sql_query')
                connection_name = job_data.get('connection_name')
                
                self.logger.info(f"[JOB_MANAGER] SQL query from job_data: '{sql_query}'")
                self.logger.info(f"[JOB_MANAGER] Connection name from job_data: '{connection_name}'")
                
                job_config['configuration']['sql'] = {
                    'connection_name': connection_name,
                    'query': sql_query,
                    'query_timeout': job_data.get('query_timeout', 300),
                    'max_rows': job_data.get('max_rows', 1000)
                }
                
                self.logger.info(f"[JOB_MANAGER] SQL config created: {job_config['configuration']['sql']}")
            
            elif job_type == 'powershell':
                job_config['configuration']['powershell'] = {
                    'script_content': job_data.get('script_content', ''),
                    'script_path': job_data.get('script_path', ''),
                    'execution_policy': job_data.get('execution_policy', 'RemoteSigned'),
                    'working_directory': job_data.get('working_directory', ''),
                    'parameters': job_data.get('parameters', [])
                }
            
            # Add schedule configuration if provided
            if job_data.get('schedule'):
                job_config['configuration']['schedule'] = job_data['schedule']
            
            # Save to database
            if self._save_job_to_database(job_config):
                self.logger.info(f"[JOB_MANAGER] Successfully created job '{job_name}' with ID: {job_id}")
                return {
                    'success': True,
                    'job_id': job_id,
                    'message': f'Job "{job_name}" created successfully'
                }
            else:
                self.logger.error(f"[JOB_MANAGER] Failed to save job '{job_name}' to database")
                return {
                    'success': False,
                    'error': 'Failed to save job to database'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error creating job: {e}")
            return {
                'success': False,
                'error': f'Error creating job: {str(e)}'
            }
    
    def _validate_connection(self, connection_name: str) -> bool:
        """Validate that a database connection exists"""
        try:
            connections = self.connection_pool.db_manager.list_connections()
            return connection_name in connections
        except Exception as e:
            self.logger.warning(f"[JOB_MANAGER] Could not validate connection '{connection_name}': {e}")
            return False
    
    def _save_job_to_database(self, job_config: Dict[str, Any]) -> bool:
        """Save job configuration to database"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                self.logger.error("[JOB_MANAGER] CRITICAL: System database connection failed - PowerShell jobs cannot be saved")
                self.logger.error("[JOB_MANAGER] Check database configuration in config/database_config.yaml")
                self.logger.error("[JOB_MANAGER] Ensure SQL Server is accessible and pyodbc is installed")
                return False
            
            cursor = system_connection.cursor()
            
            # Convert configuration to JSON
            config_json = json.dumps(job_config['configuration'], indent=2)
            
            self.logger.info(f"[JOB_MANAGER] Configuration JSON being saved to database:")
            self.logger.info(f"[JOB_MANAGER] {config_json}")
            
            # Insert job record
            cursor.execute("""
                INSERT INTO job_configurations 
                (job_id, name, job_type, configuration, enabled, created_date, created_by)
                VALUES (?, ?, ?, ?, ?, GETDATE(), SYSTEM_USER)
            """, (
                job_config['job_id'],
                job_config['name'],
                job_config['job_type'],  # Changed from 'type' to 'job_type' for consistency
                config_json,
                job_config['enabled']
            ))
            
            system_connection.commit()
            cursor.close()
            # Don't close connection - let pool manage it
            
            self.logger.info(f"[JOB_MANAGER] Saved job '{job_config['name']}' to database")
            return True
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error saving job to database: {e}")
            try:
                system_connection.rollback()
            except:
                pass
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve job configuration by ID from database"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                self.logger.error("[JOB_MANAGER] Cannot retrieve job - database connection failed")
                return None
            
            cursor = system_connection.cursor()
            cursor.execute("""
                SELECT job_id, name, job_type, configuration, enabled, created_date, modified_date, created_by
                FROM job_configurations 
                WHERE job_id = ?
            """, job_id)
            
            row = cursor.fetchone()
            cursor.close()
            # Don't close connection - let pool manage it
            
            if not row:
                return None
            
            # Parse configuration JSON
            try:
                configuration = json.loads(row[3])
            except:
                configuration = {}
            
            # Handle legacy jobs that might have empty job_type
            job_type = row[2]
            if not job_type:
                # Try to infer job type from configuration
                if 'sql' in configuration:
                    job_type = 'sql'
                elif 'powershell' in configuration:
                    job_type = 'powershell'
                else:
                    job_type = 'unknown'
                
                # Update the database with the inferred job type
                try:
                    update_cursor = system_connection.cursor()
                    update_cursor.execute("UPDATE job_configurations SET job_type = ? WHERE job_id = ?", (job_type, row[0]))
                    system_connection.commit()
                    update_cursor.close()
                    self.logger.info(f"[JOB_MANAGER] Updated job {row[0]} with inferred job_type: {job_type}")
                except Exception as e:
                    self.logger.warning(f"[JOB_MANAGER] Could not update job_type for job {row[0]}: {e}")
            
            return {
                'job_id': row[0],
                'name': row[1],
                'job_type': job_type,  # Now guaranteed to have a value
                'configuration': configuration,
                'enabled': bool(row[4]),
                'created_date': row[5],
                'modified_date': row[6],
                'created_by': row[7]
            }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error retrieving job {job_id}: {e}")
            return None
    
    def list_jobs(self, job_type: str = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all jobs with optional filtering from database"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                self.logger.error("[JOB_MANAGER] Cannot list jobs - database connection failed")
                return []
            
            cursor = system_connection.cursor()
            
            # Build query with filters
            query = "SELECT job_id, name, job_type, enabled, created_date, modified_date FROM job_configurations WHERE 1=1"
            params = []
            
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            
            if enabled_only:
                query += " AND enabled = 1"
            
            query += " ORDER BY created_date DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            # Don't close connection - let pool manage it
            
            jobs = []
            for row in rows:
                jobs.append({
                    'job_id': row[0],
                    'name': row[1],
                    'job_type': row[2],  # Changed from 'type' to 'job_type' for consistency
                    'enabled': bool(row[3]),
                    'created_date': row[4],
                    'modified_date': row[5]
                })
            
            self.logger.debug(f"[JOB_MANAGER] Retrieved {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error listing jobs: {e}")
            return []
    
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete job configuration"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                return {
                    'success': False,
                    'error': 'System database not available'
                }
            
            cursor = system_connection.cursor()
            cursor.execute("DELETE FROM job_configurations WHERE job_id = ?", job_id)
            rows_affected = cursor.rowcount
            
            system_connection.commit()
            cursor.close()
            # Don't close connection - let pool manage it
            
            if rows_affected > 0:
                self.logger.info(f"[JOB_MANAGER] Deleted job {job_id}")
                return {
                    'success': True,
                    'message': 'Job deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': f'Job with ID {job_id} not found'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error deleting job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error deleting job: {str(e)}'
            }
    
    def toggle_job(self, job_id: str, enabled: bool = None) -> Dict[str, Any]:
        """Toggle job enabled/disabled state or set specific state"""
        try:
            # First get the current job state
            job = self.get_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job with ID {job_id} not found'
                }
            
            # Determine new enabled state
            if enabled is None:
                new_enabled = not job['enabled']
            else:
                new_enabled = bool(enabled)
            
            # Update the job enabled state
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                return {
                    'success': False,
                    'error': 'System database not available'
                }
            
            cursor = system_connection.cursor()
            cursor.execute("""
                UPDATE job_configurations 
                SET enabled = ?, modified_date = GETDATE()
                WHERE job_id = ?
            """, (new_enabled, job_id))
            
            rows_affected = cursor.rowcount
            system_connection.commit()
            cursor.close()
            # Don't close connection - let pool manage it
            
            if rows_affected > 0:
                action = 'enabled' if new_enabled else 'disabled'
                self.logger.info(f"[JOB_MANAGER] Job {job_id} {action}")
                return {
                    'success': True,
                    'message': f'Job {action} successfully',
                    'enabled': new_enabled
                }
            else:
                return {
                    'success': False,
                    'error': f'Failed to update job {job_id}'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error toggling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error toggling job: {str(e)}'
            }
    
    def get_all_execution_history(self, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get complete execution history from database"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                self.logger.error("[JOB_MANAGER] Cannot retrieve execution history - database connection failed")
                return []
            
            cursor = system_connection.cursor()
            
            # Query execution history with job details (SQL Server syntax)
            cursor.execute("""
                SELECT TOP (?)
                    jeh.execution_id,
                    jeh.job_id,
                    jeh.job_name,
                    jeh.status,
                    jeh.start_time,
                    jeh.end_time,
                    jeh.duration_seconds,
                    jeh.output,
                    jeh.error_message,
                    jeh.return_code,
                    jeh.retry_count,
                    jeh.max_retries,
                    jeh.metadata,
                    jc.job_type
                FROM job_execution_history jeh
                LEFT JOIN job_configurations jc ON jeh.job_id = jc.job_id
                ORDER BY jeh.start_time DESC
            """, (limit,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            history = []
            for row in rows:
                execution = {
                    'execution_id': row[0],
                    'job_id': row[1],
                    'job_name': row[2],
                    'status': row[3],
                    'start_time': row[4],
                    'end_time': row[5],
                    'duration_seconds': row[6],
                    'output': row[7],
                    'error_message': row[8],
                    'return_code': row[9],
                    'retry_count': row[10],
                    'max_retries': row[11],
                    'metadata': row[12],
                    'job_type': row[13] if row[13] else 'unknown'
                }
                
                # Parse metadata if it exists
                if execution['metadata']:
                    try:
                        metadata_dict = json.loads(execution['metadata'])
                        # Add job_type to metadata if not present
                        if 'job_type' not in metadata_dict and execution['job_type']:
                            metadata_dict['job_type'] = execution['job_type']
                        execution['metadata'] = json.dumps(metadata_dict)
                    except:
                        pass
                
                history.append(execution)
            
            self.logger.info(f"[JOB_MANAGER] Retrieved {len(history)} execution history records")
            return history
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error retrieving execution history: {e}")
            return []
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing job configuration"""
        try:
            self.logger.info(f"[JOB_MANAGER] Updating job {job_id}")
            
            # First, check if job exists
            existing_job = self.get_job(job_id)
            if not existing_job:
                return {
                    'success': False,
                    'error': f'Job {job_id} not found'
                }
            
            # Validate required fields
            job_name = job_data.get('name', '').strip()
            if not job_name:
                return {
                    'success': False,
                    'error': 'Job name is required'
                }
            
            job_type = existing_job.get('job_type')  # Keep original job type
            
            # Validate job-specific requirements
            if job_type == 'sql':
                if not job_data.get('sql_query'):
                    return {
                        'success': False,
                        'error': 'SQL query is required for SQL jobs'
                    }
                if not job_data.get('connection_name'):
                    return {
                        'success': False,
                        'error': 'Database connection is required for SQL jobs'
                    }
                
                # Validate connection exists
                if not self._validate_connection(job_data.get('connection_name')):
                    return {
                        'success': False,
                        'error': f'Database connection "{job_data.get("connection_name")}" not found'
                    }
            
            elif job_type == 'powershell':
                if not job_data.get('script_content') and not job_data.get('script_path'):
                    return {
                        'success': False,
                        'error': 'PowerShell script content or path is required'
                    }
            
            # Prepare updated job configuration
            job_config = {
                'job_id': job_id,
                'name': job_name,
                'job_type': job_type,  # Changed from 'type' to 'job_type' for consistency
                'description': job_data.get('description', ''),
                'enabled': job_data.get('enabled', True),
                'modified_date': datetime.now().isoformat(),
                'configuration': {
                    'basic': {
                        'timeout': job_data.get('timeout', 300),
                        'max_retries': job_data.get('max_retries', 3),
                        'retry_delay': job_data.get('retry_delay', 60),
                        'run_as': job_data.get('run_as', '')
                    }
                }
            }
            
            # Add job-specific configuration
            if job_type == 'sql':
                job_config['configuration']['sql'] = {
                    'connection_name': job_data.get('connection_name'),
                    'query': job_data.get('sql_query'),
                    'query_timeout': job_data.get('query_timeout', 300),
                    'max_rows': job_data.get('max_rows', 1000)
                }
            
            elif job_type == 'powershell':
                job_config['configuration']['powershell'] = {
                    'script_content': job_data.get('script_content', ''),
                    'script_path': job_data.get('script_path', ''),
                    'execution_policy': job_data.get('execution_policy', 'RemoteSigned'),
                    'working_directory': job_data.get('working_directory', ''),
                    'parameters': job_data.get('parameters', [])
                }
            
            # Add schedule configuration if provided
            if job_data.get('schedule'):
                job_config['configuration']['schedule'] = job_data['schedule']
            
            # Update in database
            if self._update_job_in_database(job_config):
                self.logger.info(f"[JOB_MANAGER] Successfully updated job '{job_name}' with ID: {job_id}")
                return {
                    'success': True,
                    'job_id': job_id,
                    'message': f'Job "{job_name}" updated successfully'
                }
            else:
                self.logger.error(f"[JOB_MANAGER] Failed to update job '{job_name}' in database")
                return {
                    'success': False,
                    'error': 'Failed to update job in database'
                }
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error updating job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating job: {str(e)}'
            }
    
    def _update_job_in_database(self, job_config: Dict[str, Any]) -> bool:
        """Update job configuration in database"""
        try:
            system_connection = self.connection_pool.get_connection("system")
            if not system_connection:
                self.logger.error("[JOB_MANAGER] Cannot update job - database connection failed")
                return False
            
            cursor = system_connection.cursor()
            
            # Convert configuration to JSON
            config_json = json.dumps(job_config['configuration'], indent=2)
            
            self.logger.info(f"[JOB_MANAGER] Updating job configuration in database:")
            self.logger.info(f"[JOB_MANAGER] {config_json}")
            
            # Update job record
            cursor.execute("""
                UPDATE job_configurations 
                SET name = ?, 
                    configuration = ?, 
                    enabled = ?, 
                    modified_date = GETDATE()
                WHERE job_id = ?
            """, (
                job_config['name'],
                config_json,
                job_config['enabled'],
                job_config['job_id']
            ))
            
            rows_affected = cursor.rowcount
            system_connection.commit()
            cursor.close()
            
            if rows_affected > 0:
                self.logger.info(f"[JOB_MANAGER] Updated job '{job_config['name']}' in database")
                return True
            else:
                self.logger.warning(f"[JOB_MANAGER] No rows affected when updating job {job_config['job_id']}")
                return False
            
        except Exception as e:
            self.logger.error(f"[JOB_MANAGER] Error updating job in database: {e}")
            try:
                system_connection.rollback()
            except:
                pass
            return False