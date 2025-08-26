"""
Job Storage Manager for Windows Job Scheduler
Supports both YAML file storage and SQL Server database storage
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from dataclasses import asdict
import threading

from utils.logger import get_logger
from .sqlalchemy_models import get_db_session, JobConfiguration, JobExecutionHistory


class JobStorage:
    """Manages job configuration and execution history storage"""
    
    def __init__(self, storage_type: str = "yaml", storage_config: Dict[str, Any] = None):
        """
        Initialize job storage
        
        Args:
            storage_type: "yaml" or "database"
            storage_config: Storage-specific configuration
        """
        self.storage_type = storage_type.lower()
        self.storage_config = storage_config or {}
        self.logger = get_logger(__name__)
        self._lock = threading.Lock()
        
        # Initialize storage backend
        if self.storage_type == "yaml":
            self._init_yaml_storage()
        elif self.storage_type == "database":
            self._init_database_storage()
        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")
        
        self.logger.info(f"Job storage initialized with {self.storage_type} backend")
    
    def _init_yaml_storage(self):
        """Initialize YAML file storage"""
        self.yaml_file = self.storage_config.get('yaml_file', 'config/jobs.yaml')
        self.history_file = self.storage_config.get('history_file', 'config/job_history.yaml')
        
        # Ensure directories exist
        for file_path in [self.yaml_file, self.history_file]:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize files if they don't exist
        if not os.path.exists(self.yaml_file):
            self._save_yaml_data({})
        
        if not os.path.exists(self.history_file):
            self._save_yaml_data({}, self.history_file)
    
    def _init_database_storage(self):
        """Initialize database storage"""
        self.db_manager = get_database_manager()
        self.connection_name = self.storage_config.get('connection_name', 'default')
        
        # Create tables if they don't exist
        self._create_database_tables()
    
    def _create_database_tables(self):
        """Create database tables for job storage"""
        create_jobs_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='job_configurations' AND xtype='U')
        CREATE TABLE job_configurations (
            job_id NVARCHAR(50) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            job_type NVARCHAR(50) NOT NULL,
            configuration NTEXT NOT NULL,
            enabled BIT DEFAULT 1,
            created_date DATETIME DEFAULT GETDATE(),
            modified_date DATETIME DEFAULT GETDATE(),
            created_by NVARCHAR(255),
            INDEX IX_job_configurations_name (name),
            INDEX IX_job_configurations_type (job_type)
        )
        """
        
        create_history_table = """
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='job_execution_history' AND xtype='U')
        CREATE TABLE job_execution_history (
            execution_id BIGINT IDENTITY(1,1) PRIMARY KEY,
            job_id NVARCHAR(50) NOT NULL,
            job_name NVARCHAR(255) NOT NULL,
            status NVARCHAR(50) NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            duration_seconds FLOAT,
            output NTEXT,
            error_message NTEXT,
            return_code INT,
            retry_count INT DEFAULT 0,
            max_retries INT DEFAULT 0,
            metadata NTEXT,
            INDEX IX_job_history_job_id (job_id),
            INDEX IX_job_history_start_time (start_time),
            INDEX IX_job_history_status (status)
        )
        """
        
        try:
            connection = self.db_manager.get_connection(self.connection_name)
            if connection:
                cursor = connection.cursor()
                cursor.execute(create_jobs_table)
                cursor.execute(create_history_table)
                connection.commit()
                cursor.close()
                connection.close()
                self.logger.info("Database tables created/verified successfully")
            else:
                self.logger.error("Could not establish database connection for table creation")
        except Exception as e:
            self.logger.error(f"Failed to create database tables: {e}")
    
    # Job Configuration Methods
    
    def save_job(self, job_config: Dict[str, Any]) -> bool:
        """Save job configuration"""
        try:
            with self._lock:
                if self.storage_type == "yaml":
                    return self._save_job_yaml(job_config)
                elif self.storage_type == "database":
                    return self._save_job_database(job_config)
            return False
        except Exception as e:
            self.logger.error(f"Failed to save job {job_config.get('job_id', 'unknown')}: {e}")
            return False
    
    def _save_job_yaml(self, job_config: Dict[str, Any]) -> bool:
        """Save job to YAML file"""
        jobs = self._load_yaml_data(self.yaml_file)
        job_id = job_config.get('job_id')
        
        if not job_id:
            self.logger.error("Job configuration missing job_id")
            return False
        
        # Add timestamps
        current_time = datetime.now().isoformat()
        if job_id not in jobs:
            job_config['created_date'] = current_time
        job_config['modified_date'] = current_time
        
        jobs[job_id] = job_config
        return self._save_yaml_data(jobs, self.yaml_file)
    
    def _save_job_database(self, job_config: Dict[str, Any]) -> bool:
        """Save job to database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            job_id = job_config.get('job_id')
            
            # Check if job exists
            cursor.execute("SELECT COUNT(*) FROM job_configurations WHERE job_id = ?", job_id)
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Update existing job
                cursor.execute("""
                    UPDATE job_configurations 
                    SET name = ?, job_type = ?, configuration = ?, enabled = ?, modified_date = GETDATE()
                    WHERE job_id = ?
                """, (
                    job_config.get('name'),
                    job_config.get('job_type'),
                    json.dumps(job_config),
                    job_config.get('enabled', True),
                    job_id
                ))
            else:
                # Insert new job
                cursor.execute("""
                    INSERT INTO job_configurations (job_id, name, job_type, configuration, enabled, created_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    job_id,
                    job_config.get('name'),
                    job_config.get('job_type'),
                    json.dumps(job_config),
                    job_config.get('enabled', True),
                    os.getenv('USERNAME', 'System')
                ))
            
            connection.commit()
            cursor.close()
            connection.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Database error saving job: {e}")
            try:
                connection.rollback()
                connection.close()
            except:
                pass
            return False
    
    def load_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job configuration by ID"""
        try:
            if self.storage_type == "yaml":
                return self._load_job_yaml(job_id)
            elif self.storage_type == "database":
                return self._load_job_database(job_id)
            return None
        except Exception as e:
            self.logger.error(f"Failed to load job {job_id}: {e}")
            return None
    
    def _load_job_yaml(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job from YAML file"""
        jobs = self._load_yaml_data(self.yaml_file)
        return jobs.get(job_id)
    
    def _load_job_database(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Load job from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return None
        
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT configuration FROM job_configurations WHERE job_id = ?", job_id)
            row = cursor.fetchone()
            cursor.close()
            connection.close()
            
            if row:
                return json.loads(row[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Database error loading job: {e}")
            try:
                connection.close()
            except:
                pass
            return None
    
    def load_all_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Load all job configurations"""
        try:
            if self.storage_type == "yaml":
                return self._load_yaml_data(self.yaml_file)
            elif self.storage_type == "database":
                return self._load_all_jobs_database()
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load all jobs: {e}")
            return {}
    
    def _load_all_jobs_database(self) -> Dict[str, Dict[str, Any]]:
        """Load all jobs from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return {}
        
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT job_id, configuration FROM job_configurations")
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            jobs = {}
            for row in rows:
                job_id, config_json = row
                jobs[job_id] = json.loads(config_json)
            
            return jobs
            
        except Exception as e:
            self.logger.error(f"Database error loading all jobs: {e}")
            try:
                connection.close()
            except:
                pass
            return {}
    
    def delete_job(self, job_id: str) -> bool:
        """Delete job configuration"""
        try:
            with self._lock:
                if self.storage_type == "yaml":
                    return self._delete_job_yaml(job_id)
                elif self.storage_type == "database":
                    return self._delete_job_database(job_id)
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete job {job_id}: {e}")
            return False
    
    def _delete_job_yaml(self, job_id: str) -> bool:
        """Delete job from YAML file"""
        jobs = self._load_yaml_data(self.yaml_file)
        if job_id in jobs:
            del jobs[job_id]
            return self._save_yaml_data(jobs, self.yaml_file)
        return True  # Job doesn't exist, consider it deleted
    
    def _delete_job_database(self, job_id: str) -> bool:
        """Delete job from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM job_configurations WHERE job_id = ?", job_id)
            connection.commit()
            cursor.close()
            connection.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Database error deleting job: {e}")
            try:
                connection.rollback()
                connection.close()
            except:
                pass
            return False
    
    # Job Execution History Methods
    
    def save_execution_result(self, job_result) -> bool:
        """Save job execution result"""
        try:
            if self.storage_type == "yaml":
                return self._save_execution_yaml(job_result)
            elif self.storage_type == "database":
                return self._save_execution_database(job_result)
            return False
        except Exception as e:
            self.logger.error(f"Failed to save execution result for job {job_result.job_id}: {e}")
            return False
    
    def _save_execution_yaml(self, job_result) -> bool:
        """Save execution result to YAML file"""
        history = self._load_yaml_data(self.history_file)
        
        # Convert job result to dictionary
        result_dict = job_result.to_dict() if hasattr(job_result, 'to_dict') else asdict(job_result)
        
        # Add execution ID (timestamp-based)
        execution_id = f"{job_result.job_id}_{int(datetime.now().timestamp() * 1000)}"
        result_dict['execution_id'] = execution_id
        
        # Store under job ID
        if job_result.job_id not in history:
            history[job_result.job_id] = []
        
        history[job_result.job_id].append(result_dict)
        
        # Keep only last 100 executions per job
        if len(history[job_result.job_id]) > 100:
            history[job_result.job_id] = history[job_result.job_id][-100:]
        
        return self._save_yaml_data(history, self.history_file)
    
    def _save_execution_database(self, job_result) -> bool:
        """Save execution result to database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO job_execution_history 
                (job_id, job_name, status, start_time, end_time, duration_seconds,
                 output, error_message, return_code, retry_count, max_retries, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_result.job_id,
                job_result.job_name,
                job_result.status.value if hasattr(job_result.status, 'value') else str(job_result.status),
                job_result.start_time,
                job_result.end_time,
                job_result.duration_seconds,
                job_result.output,
                job_result.error_message,
                job_result.return_code,
                job_result.retry_count,
                job_result.max_retries,
                json.dumps(job_result.metadata) if job_result.metadata else None
            ))
            
            connection.commit()
            cursor.close()
            connection.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Database error saving execution result: {e}")
            try:
                connection.rollback()
                connection.close()
            except:
                pass
            return False
    
    def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history for a job"""
        try:
            if self.storage_type == "yaml":
                return self._get_job_history_yaml(job_id, limit)
            elif self.storage_type == "database":
                return self._get_job_history_database(job_id, limit)
            return []
        except Exception as e:
            self.logger.error(f"Failed to get job history for {job_id}: {e}")
            return []
    
    def _get_job_history_yaml(self, job_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get job history from YAML file"""
        history = self._load_yaml_data(self.history_file)
        job_history = history.get(job_id, [])
        return job_history[-limit:] if job_history else []
    
    def _get_job_history_database(self, job_id: str, limit: int) -> List[Dict[str, Any]]:
        """Get job history from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return []
        
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT TOP (?) execution_id, job_id, job_name, status, start_time, end_time,
                       duration_seconds, output, error_message, return_code, retry_count,
                       max_retries, metadata
                FROM job_execution_history 
                WHERE job_id = ? 
                ORDER BY start_time DESC
            """, limit, job_id)
            
            rows = cursor.fetchall()
            cursor.close()
            connection.close()
            
            history = []
            for row in rows:
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
                    'metadata': json.loads(row[12]) if row[12] else {}
                })
            
            return history
            
        except Exception as e:
            self.logger.error(f"Database error getting job history: {e}")
            try:
                connection.close()
            except:
                pass
            return []
    
    # Utility Methods
    
    def _load_yaml_data(self, file_path: str) -> Dict[str, Any]:
        """Load data from YAML file"""
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data if data is not None else {}
        except Exception as e:
            self.logger.error(f"Failed to load YAML file {file_path}: {e}")
            return {}
    
    def _save_yaml_data(self, data: Dict[str, Any], file_path: str = None) -> bool:
        """Save data to YAML file"""
        if file_path is None:
            file_path = self.yaml_file
        
        try:
            # Ensure directory exists
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, indent=2, allow_unicode=True)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save YAML file {file_path}: {e}")
            return False
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage backend information"""
        info = {
            'storage_type': self.storage_type,
            'storage_config': self.storage_config
        }
        
        if self.storage_type == "yaml":
            info.update({
                'yaml_file': self.yaml_file,
                'history_file': self.history_file,
                'yaml_file_exists': os.path.exists(self.yaml_file),
                'history_file_exists': os.path.exists(self.history_file)
            })
            
            # Get file sizes
            try:
                if os.path.exists(self.yaml_file):
                    info['yaml_file_size'] = os.path.getsize(self.yaml_file)
                if os.path.exists(self.history_file):
                    info['history_file_size'] = os.path.getsize(self.history_file)
            except Exception as e:
                info['file_size_error'] = str(e)
                
        elif self.storage_type == "database":
            info.update({
                'connection_name': self.connection_name,
                'database_info': self.db_manager.get_connection_info(self.connection_name)
            })
            
            # Test database connection
            test_result = self.db_manager.test_connection(self.connection_name)
            info['connection_test'] = test_result
        
        return info
    
    def get_job_statistics(self) -> Dict[str, Any]:
        """Get job storage statistics"""
        stats = {
            'total_jobs': 0,
            'enabled_jobs': 0,
            'disabled_jobs': 0,
            'job_types': {},
            'total_executions': 0
        }
        
        try:
            # Get job statistics
            all_jobs = self.load_all_jobs()
            stats['total_jobs'] = len(all_jobs)
            
            for job_config in all_jobs.values():
                if job_config.get('enabled', True):
                    stats['enabled_jobs'] += 1
                else:
                    stats['disabled_jobs'] += 1
                
                job_type = job_config.get('job_type', 'unknown')
                stats['job_types'][job_type] = stats['job_types'].get(job_type, 0) + 1
            
            # Get execution statistics
            if self.storage_type == "database":
                stats.update(self._get_database_execution_stats())
            else:
                stats.update(self._get_yaml_execution_stats())
            
        except Exception as e:
            self.logger.error(f"Failed to get job statistics: {e}")
            stats['error'] = str(e)
        
        return stats
    
    def _get_database_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return {'execution_stats_error': 'No database connection'}
        
        try:
            cursor = connection.cursor()
            
            # Total executions
            cursor.execute("SELECT COUNT(*) FROM job_execution_history")
            total_executions = cursor.fetchone()[0]
            
            # Executions by status
            cursor.execute("""
                SELECT status, COUNT(*) 
                FROM job_execution_history 
                GROUP BY status
            """)
            status_counts = dict(cursor.fetchall())
            
            # Recent executions (last 24 hours)
            cursor.execute("""
                SELECT COUNT(*) 
                FROM job_execution_history 
                WHERE start_time >= DATEADD(hour, -24, GETDATE())
            """)
            recent_executions = cursor.fetchone()[0]
            
            cursor.close()
            connection.close()
            
            return {
                'total_executions': total_executions,
                'executions_by_status': status_counts,
                'recent_executions_24h': recent_executions
            }
            
        except Exception as e:
            try:
                connection.close()
            except:
                pass
            return {'execution_stats_error': str(e)}
    
    def _get_yaml_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics from YAML files"""
        try:
            history = self._load_yaml_data(self.history_file)
            total_executions = 0
            status_counts = {}
            recent_executions = 0
            
            # Count executions
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for job_history in history.values():
                for execution in job_history:
                    total_executions += 1
                    
                    status = execution.get('status', 'unknown')
                    status_counts[status] = status_counts.get(status, 0) + 1
                    
                    # Check if recent
                    start_time_str = execution.get('start_time')
                    if start_time_str:
                        try:
                            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                            if start_time > cutoff_time:
                                recent_executions += 1
                        except:
                            pass
            
            return {
                'total_executions': total_executions,
                'executions_by_status': status_counts,
                'recent_executions_24h': recent_executions
            }
            
        except Exception as e:
            return {'execution_stats_error': str(e)}
    
    def cleanup_old_history(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """Clean up old execution history"""
        if self.storage_type == "database":
            return self._cleanup_database_history(days_to_keep)
        else:
            return self._cleanup_yaml_history(days_to_keep)
    
    def _cleanup_database_history(self, days_to_keep: int) -> Dict[str, Any]:
        """Clean up old execution history from database"""
        connection = self.db_manager.get_connection(self.connection_name)
        if not connection:
            return {'success': False, 'error': 'No database connection'}
        
        try:
            cursor = connection.cursor()
            
            # Count records to be deleted
            cursor.execute("""
                SELECT COUNT(*) 
                FROM job_execution_history 
                WHERE start_time < DATEADD(day, -?, GETDATE())
            """, days_to_keep)
            records_to_delete = cursor.fetchone()[0]
            
            # Delete old records
            cursor.execute("""
                DELETE FROM job_execution_history 
                WHERE start_time < DATEADD(day, -?, GETDATE())
            """, days_to_keep)
            
            connection.commit()
            cursor.close()
            connection.close()
            
            return {
                'success': True,
                'records_deleted': records_to_delete,
                'days_kept': days_to_keep
            }
            
        except Exception as e:
            try:
                connection.rollback()
                connection.close()
            except:
                pass
            return {'success': False, 'error': str(e)}
    
    def _cleanup_yaml_history(self, days_to_keep: int) -> Dict[str, Any]:
        """Clean up old execution history from YAML files"""
        try:
            history = self._load_yaml_data(self.history_file)
            records_deleted = 0
            
            from datetime import datetime, timedelta
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            
            for job_id in list(history.keys()):
                job_history = history[job_id]
                original_count = len(job_history)
                
                # Filter out old records
                filtered_history = []
                for execution in job_history:
                    start_time_str = execution.get('start_time')
                    if start_time_str:
                        try:
                            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
                            if start_time > cutoff_time:
                                filtered_history.append(execution)
                            else:
                                records_deleted += 1
                        except:
                            # Keep records with invalid timestamps
                            filtered_history.append(execution)
                    else:
                        # Keep records without timestamps
                        filtered_history.append(execution)
                
                history[job_id] = filtered_history
                
                # Remove empty job histories
                if not filtered_history:
                    del history[job_id]
            
            # Save cleaned history
            success = self._save_yaml_data(history, self.history_file)
            
            return {
                'success': success,
                'records_deleted': records_deleted,
                'days_kept': days_to_keep
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    # Test job storage
    print("=== Testing YAML Storage ===")
    yaml_storage = JobStorage("yaml", {"yaml_file": "test_jobs.yaml", "history_file": "test_history.yaml"})
    
    # Test job configuration
    test_job_config = {
        'job_id': 'test-job-001',
        'name': 'Test Job',
        'job_type': 'sql',
        'enabled': True,
        'sql_query': 'SELECT 1',
        'connection_name': 'default'
    }
    
    # Save job
    print("Saving test job...")
    success = yaml_storage.save_job(test_job_config)
    print(f"Save success: {success}")
    
    # Load job
    print("Loading test job...")
    loaded_job = yaml_storage.load_job('test-job-001')
    print(f"Loaded job: {loaded_job}")
    
    # Load all jobs
    print("Loading all jobs...")
    all_jobs = yaml_storage.load_all_jobs()
    print(f"All jobs: {list(all_jobs.keys())}")
    
    # Storage info
    print("Storage info:")
    info = yaml_storage.get_storage_info()
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    # Statistics
    print("Job statistics:")
    stats = yaml_storage.get_job_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Clean up test files
    import os
    try:
        os.unlink("test_jobs.yaml")
        os.unlink("test_history.yaml")
        print("Cleaned up test files")
    except:
        pass