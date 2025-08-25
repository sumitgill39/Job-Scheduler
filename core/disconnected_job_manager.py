"""
Job Manager using Disconnected Data Access Pattern
Eliminates connection pooling issues by working with data in memory (ADO.NET style)
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional

from database.disconnected_data_manager import DisconnectedDataManager, DataSet
from core.job_base import JobStatus
from utils.logger import get_logger


class DisconnectedJobManager:
    """
    Job Manager using disconnected data access pattern
    Similar to ADO.NET DataSet/DataAdapter pattern - no connection pooling issues
    """
    
    def __init__(self, db_manager: DisconnectedDataManager):
        self.db = db_manager
        self.logger = get_logger("job_manager.disconnected")
        
        # Cached datasets
        self.job_dataset: Optional[DataSet] = None
        self.last_refresh: Optional[datetime] = None
        self.cache_ttl = 300  # 5 minutes
        
        # Table configurations for updates
        self.table_configs = {
            'job_configurations': {
                'exclude_on_insert': ['created_date'],  # Let DB handle timestamp
                'exclude_on_update': ['job_id', 'created_date', 'created_by']
            },
            'job_execution_history': {
                'exclude_on_insert': ['execution_id'],  # Auto-increment
                'exclude_on_update': ['execution_id', 'job_id']
            }
        }
        
        self.logger.info("[DISCONNECTED_JOB_MANAGER] Initialized with disconnected data access")
    
    def _ensure_job_dataset(self, force_refresh: bool = False):
        """Ensure job dataset is loaded and fresh"""
        if not force_refresh and self.job_dataset and self.last_refresh:
            # Check if data is still fresh
            age_seconds = (datetime.now() - self.last_refresh).total_seconds()
            if age_seconds < self.cache_ttl:
                return
        
        self._refresh_job_dataset()
    
    def _refresh_job_dataset(self):
        """Refresh job dataset from database (like DataAdapter.Fill)"""
        self.logger.debug("[DISCONNECTED_JOB_MANAGER] Refreshing job dataset from database...")
        
        queries = {
            'jobs': """
                SELECT job_id, name, job_type, configuration, enabled, 
                       created_date, modified_date, created_by
                FROM job_configurations
                ORDER BY created_date DESC
            """,
            'execution_history': """
                SELECT TOP (2000) execution_id, job_id, job_name, status, 
                       start_time, end_time, duration_seconds, output, 
                       error_message, return_code, retry_count, max_retries, metadata
                FROM job_execution_history
                ORDER BY start_time DESC
            """,
            'job_stats': """
                SELECT 
                    job_id,
                    COUNT(*) as total_executions,
                    SUM(CASE WHEN status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_executions,
                    SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_executions,
                    AVG(CAST(duration_seconds AS FLOAT)) as avg_duration,
                    MAX(start_time) as last_execution
                FROM job_execution_history
                WHERE start_time >= DATEADD(day, -30, GETDATE())
                GROUP BY job_id
            """
        }
        
        self.job_dataset = self.db.fill_dataset(
            queries, 
            dataset_name="JobDataSet",
            cache_key="job_data",
            cache_ttl=self.cache_ttl
        )
        self.last_refresh = datetime.now()
        
        jobs_count = self.job_dataset.get_table('jobs').count() if self.job_dataset.get_table('jobs') else 0
        history_count = self.job_dataset.get_table('execution_history').count() if self.job_dataset.get_table('execution_history') else 0
        
        self.logger.info(f"[DISCONNECTED_JOB_MANAGER] Dataset refreshed: {jobs_count} jobs, {history_count} history records")
    
    def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new job using disconnected pattern"""
        try:
            # Ensure we have fresh data
            self._ensure_job_dataset()
            
            # Generate job ID if not provided
            job_id = job_data.get('job_id', str(uuid.uuid4()))
            
            # Prepare job configuration
            job_config = {
                'job_id': job_id,
                'name': job_data['name'],
                'job_type': job_data['job_type'],
                'configuration': json.dumps(job_data.get('configuration', {})),
                'enabled': job_data.get('enabled', True),
                'created_by': 'SYSTEM_USER'
            }
            
            # Add to in-memory dataset
            jobs_table = self.job_dataset.get_table('jobs')
            if jobs_table:
                jobs_table.add_row(job_config)
                
                # Persist changes immediately
                success = self._persist_changes()
                
                if success:
                    self.logger.info(f"[DISCONNECTED_JOB_MANAGER] Created job '{job_data['name']}' with ID: {job_id}")
                    return {
                        'success': True,
                        'job_id': job_id,
                        'message': 'Job created successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to persist job to database'
                    }
            else:
                return {
                    'success': False,
                    'error': 'Jobs table not available in dataset'
                }
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error creating job: {e}")
            return {
                'success': False,
                'error': f'Error creating job: {str(e)}'
            }
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID from in-memory dataset"""
        try:
            self._ensure_job_dataset()
            
            jobs_table = self.job_dataset.get_table('jobs')
            if not jobs_table:
                return None
            
            job_row = jobs_table.find(job_id)
            if job_row:
                # Parse configuration JSON
                if job_row.get('configuration'):
                    try:
                        job_row['configuration'] = json.loads(job_row['configuration'])
                    except json.JSONDecodeError:
                        job_row['configuration'] = {}
                
                self.logger.debug(f"[DISCONNECTED_JOB_MANAGER] Retrieved job: {job_id}")
                return job_row
            
            return None
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error retrieving job {job_id}: {e}")
            return None
    
    def list_jobs(self, job_type: str = None, enabled_only: bool = False, limit: int = None) -> List[Dict[str, Any]]:
        """List jobs from in-memory dataset with filtering"""
        try:
            self._ensure_job_dataset()
            
            jobs_table = self.job_dataset.get_table('jobs')
            if not jobs_table:
                return []
            
            # Define filter function
            def filter_func(row):
                if job_type and row.get('job_type') != job_type:
                    return False
                if enabled_only and not row.get('enabled'):
                    return False
                return True
            
            # Apply filter and get results
            filtered_jobs = jobs_table.select(
                filter_func if (job_type or enabled_only) else None,
                order_by='-created_date',  # Descending order
                limit=limit
            )
            
            # Parse configuration JSON for each job
            for job in filtered_jobs:
                if job.get('configuration'):
                    try:
                        job['configuration'] = json.loads(job['configuration'])
                    except json.JSONDecodeError:
                        job['configuration'] = {}
            
            self.logger.debug(f"[DISCONNECTED_JOB_MANAGER] Listed {len(filtered_jobs)} jobs")
            return filtered_jobs
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error listing jobs: {e}")
            return []
    
    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update job using disconnected pattern"""
        try:
            self._ensure_job_dataset()
            
            jobs_table = self.job_dataset.get_table('jobs')
            if not jobs_table:
                return {
                    'success': False,
                    'error': 'Jobs table not available'
                }
            
            # Prepare updates
            updates = {}
            if 'name' in job_data:
                updates['name'] = job_data['name']
            if 'configuration' in job_data:
                updates['configuration'] = json.dumps(job_data['configuration'])
            if 'enabled' in job_data:
                updates['enabled'] = job_data['enabled']
            
            # Update in memory
            if jobs_table.update_row(job_id, updates):
                # Persist changes
                success = self._persist_changes()
                
                if success:
                    self.logger.info(f"[DISCONNECTED_JOB_MANAGER] Updated job: {job_id}")
                    return {
                        'success': True,
                        'message': 'Job updated successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to persist changes to database'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error updating job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error updating job: {str(e)}'
            }
    
    def delete_job(self, job_id: str) -> Dict[str, Any]:
        """Delete job using disconnected pattern"""
        try:
            self._ensure_job_dataset()
            
            jobs_table = self.job_dataset.get_table('jobs')
            if not jobs_table:
                return {
                    'success': False,
                    'error': 'Jobs table not available'
                }
            
            # Delete from memory
            if jobs_table.delete_row(job_id):
                # Persist changes
                success = self._persist_changes()
                
                if success:
                    self.logger.info(f"[DISCONNECTED_JOB_MANAGER] Deleted job: {job_id}")
                    return {
                        'success': True,
                        'message': 'Job deleted successfully'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to persist deletion to database'
                    }
            else:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error deleting job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error deleting job: {str(e)}'
            }
    
    def toggle_job(self, job_id: str, enabled: bool = None) -> Dict[str, Any]:
        """Toggle job enabled status"""
        try:
            # Get current job
            job = self.get_job(job_id)
            if not job:
                return {
                    'success': False,
                    'error': f'Job not found: {job_id}'
                }
            
            # Determine new enabled state
            if enabled is None:
                new_enabled = not job['enabled']
            else:
                new_enabled = bool(enabled)
            
            # Update job
            return self.update_job(job_id, {'enabled': new_enabled})
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error toggling job {job_id}: {e}")
            return {
                'success': False,
                'error': f'Error toggling job: {str(e)}'
            }
    
    def get_all_execution_history(self, limit: int = 1000, job_id: str = None) -> List[Dict[str, Any]]:
        """Get execution history from in-memory dataset"""
        try:
            self._ensure_job_dataset()
            
            history_table = self.job_dataset.get_table('execution_history')
            if not history_table:
                return []
            
            # Define filter function for job_id if specified
            def filter_func(row):
                if job_id and row.get('job_id') != job_id:
                    return False
                return True
            
            # Get filtered results
            history = history_table.select(
                filter_func if job_id else None,
                order_by='-start_time',  # Most recent first
                limit=limit
            )
            
            # Parse metadata JSON
            for record in history:
                if record.get('metadata'):
                    try:
                        record['metadata'] = json.loads(record['metadata'])
                    except json.JSONDecodeError:
                        record['metadata'] = {}
            
            self.logger.debug(f"[DISCONNECTED_JOB_MANAGER] Retrieved {len(history)} execution history records")
            return history
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error retrieving execution history: {e}")
            return []
    
    def add_execution_record(self, execution_data: Dict[str, Any]) -> Optional[str]:
        """Add execution record to in-memory dataset"""
        try:
            self._ensure_job_dataset()
            
            history_table = self.job_dataset.get_table('execution_history')
            if not history_table:
                self.logger.error("[DISCONNECTED_JOB_MANAGER] Execution history table not available")
                return None
            
            # Prepare execution record
            execution_record = {
                'job_id': execution_data['job_id'],
                'job_name': execution_data['job_name'],
                'status': execution_data.get('status', JobStatus.RUNNING.value),
                'start_time': execution_data.get('start_time', datetime.now()),
                'end_time': execution_data.get('end_time'),
                'duration_seconds': execution_data.get('duration_seconds'),
                'output': execution_data.get('output'),
                'error_message': execution_data.get('error_message'),
                'return_code': execution_data.get('return_code'),
                'retry_count': execution_data.get('retry_count', 0),
                'max_retries': execution_data.get('max_retries', 3),
                'metadata': json.dumps(execution_data.get('metadata', {}))
            }
            
            # Add to dataset
            temp_key = history_table.add_row(execution_record)
            
            # Persist immediately for execution records
            success = self._persist_changes()
            
            if success:
                self.logger.debug(f"[DISCONNECTED_JOB_MANAGER] Added execution record for job: {execution_data['job_id']}")
                return temp_key
            else:
                self.logger.error("[DISCONNECTED_JOB_MANAGER] Failed to persist execution record")
                return None
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error adding execution record: {e}")
            return None
    
    def get_job_statistics(self, job_id: str = None) -> Dict[str, Any]:
        """Get job statistics from cached stats table"""
        try:
            self._ensure_job_dataset()
            
            stats_table = self.job_dataset.get_table('job_stats')
            if not stats_table:
                return {}
            
            if job_id:
                # Get stats for specific job
                stats_row = stats_table.find(job_id)
                return stats_row if stats_row else {}
            else:
                # Get all job stats
                return {
                    'all_jobs': stats_table.rows,
                    'total_jobs': len(self.job_dataset.get_table('jobs').rows) if self.job_dataset.get_table('jobs') else 0,
                    'total_executions': sum(row.get('total_executions', 0) for row in stats_table.rows)
                }
                
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error getting job statistics: {e}")
            return {}
    
    def _persist_changes(self) -> bool:
        """Persist all dataset changes to database"""
        try:
            if not self.job_dataset or not self.job_dataset.has_changes():
                return True
            
            results = self.db.update_dataset(self.job_dataset, self.table_configs)
            success = all(results.values())
            
            if success:
                self.logger.debug("[DISCONNECTED_JOB_MANAGER] All changes persisted successfully")
            else:
                failed_tables = [table for table, result in results.items() if not result]
                self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Failed to persist changes for tables: {failed_tables}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"[DISCONNECTED_JOB_MANAGER] Error persisting changes: {e}")
            return False
    
    def refresh_data(self, force: bool = False):
        """Force refresh of job dataset"""
        if force:
            self.db.clear_cache("job_data")
        self._refresh_job_dataset()
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information for monitoring"""
        cache_info = self.db.get_cache_info()
        
        if self.job_dataset:
            cache_info.update({
                'job_dataset_tables': list(self.job_dataset.tables.keys()),
                'job_dataset_row_counts': {
                    name: table.count() for name, table in self.job_dataset.tables.items()
                },
                'job_dataset_has_changes': self.job_dataset.has_changes(),
                'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None
            })
        
        return cache_info