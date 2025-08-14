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
        self.logger.info("[JOB_MANAGER] Job Manager initialized")
    
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
                        'error': f'Database connection \"{job_data.get(\"connection_name\")}\" not found'
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
                'type': job_type,
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
                job_config['configuration']['sql'] = {\n                    'connection_name': job_data.get('connection_name'),\n                    'query': job_data.get('sql_query'),\n                    'query_timeout': job_data.get('query_timeout', 300),\n                    'max_rows': job_data.get('max_rows', 1000)\n                }\n            \n            elif job_type == 'powershell':\n                job_config['configuration']['powershell'] = {\n                    'script_content': job_data.get('script_content', ''),\n                    'script_path': job_data.get('script_path', ''),\n                    'execution_policy': job_data.get('execution_policy', 'RemoteSigned'),\n                    'working_directory': job_data.get('working_directory', ''),\n                    'parameters': job_data.get('parameters', [])\n                }\n            \n            # Add schedule configuration if provided\n            if job_data.get('schedule'):\n                job_config['configuration']['schedule'] = job_data['schedule']\n            \n            # Save to database\n            if self._save_job_to_database(job_config):\n                self.logger.info(f\"[JOB_MANAGER] Successfully created job '{job_name}' with ID: {job_id}\")\n                return {\n                    'success': True,\n                    'job_id': job_id,\n                    'message': f'Job \"{job_name}\" created successfully'\n                }\n            else:\n                self.logger.error(f\"[JOB_MANAGER] Failed to save job '{job_name}' to database\")\n                return {\n                    'success': False,\n                    'error': 'Failed to save job to database'\n                }\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error creating job: {e}\")\n            return {\n                'success': False,\n                'error': f'Error creating job: {str(e)}'\n            }\n    \n    def _validate_connection(self, connection_name: str) -> bool:\n        \"\"\"Validate that a database connection exists\"\"\"\n        try:\n            connections = self.db_manager.list_connections()\n            return connection_name in connections\n        except Exception as e:\n            self.logger.warning(f\"[JOB_MANAGER] Could not validate connection '{connection_name}': {e}\")\n            return False\n    \n    def _save_job_to_database(self, job_config: Dict[str, Any]) -> bool:\n        \"\"\"Save job configuration to database\"\"\"\n        try:\n            system_connection = self.db_manager.get_connection(\"system\")\n            if not system_connection:\n                self.logger.error(\"[JOB_MANAGER] Cannot save job: system database not available\")\n                return False\n            \n            cursor = system_connection.cursor()\n            \n            # Convert configuration to JSON\n            config_json = json.dumps(job_config['configuration'], indent=2)\n            \n            # Insert job record\n            cursor.execute(\"\"\"\n                INSERT INTO job_configurations \n                (job_id, name, job_type, configuration, enabled, created_date, created_by)\n                VALUES (?, ?, ?, ?, ?, GETDATE(), SYSTEM_USER)\n            \"\"\", (\n                job_config['job_id'],\n                job_config['name'],\n                job_config['type'],\n                config_json,\n                job_config['enabled']\n            ))\n            \n            system_connection.commit()\n            cursor.close()\n            system_connection.close()\n            \n            self.logger.info(f\"[JOB_MANAGER] Saved job '{job_config['name']}' to database\")\n            return True\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error saving job to database: {e}\")\n            try:\n                system_connection.rollback()\n                system_connection.close()\n            except:\n                pass\n            return False\n    \n    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:\n        \"\"\"Retrieve job configuration by ID\"\"\"\n        try:\n            system_connection = self.db_manager.get_connection(\"system\")\n            if not system_connection:\n                return None\n            \n            cursor = system_connection.cursor()\n            cursor.execute(\"\"\"\n                SELECT job_id, name, job_type, configuration, enabled, created_date, modified_date, created_by\n                FROM job_configurations \n                WHERE job_id = ?\n            \"\"\", job_id)\n            \n            row = cursor.fetchone()\n            cursor.close()\n            system_connection.close()\n            \n            if not row:\n                return None\n            \n            # Parse configuration JSON\n            try:\n                configuration = json.loads(row[3])\n            except:\n                configuration = {}\n            \n            return {\n                'job_id': row[0],\n                'name': row[1],\n                'type': row[2],\n                'configuration': configuration,\n                'enabled': bool(row[4]),\n                'created_date': row[5],\n                'modified_date': row[6],\n                'created_by': row[7]\n            }\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error retrieving job {job_id}: {e}\")\n            return None\n    \n    def list_jobs(self, job_type: str = None, enabled_only: bool = False) -> List[Dict[str, Any]]:\n        \"\"\"List all jobs with optional filtering\"\"\"\n        try:\n            system_connection = self.db_manager.get_connection(\"system\")\n            if not system_connection:\n                return []\n            \n            cursor = system_connection.cursor()\n            \n            # Build query with filters\n            query = \"SELECT job_id, name, job_type, enabled, created_date, modified_date FROM job_configurations WHERE 1=1\"\n            params = []\n            \n            if job_type:\n                query += \" AND job_type = ?\"\n                params.append(job_type)\n            \n            if enabled_only:\n                query += \" AND enabled = 1\"\n            \n            query += \" ORDER BY created_date DESC\"\n            \n            cursor.execute(query, params)\n            rows = cursor.fetchall()\n            cursor.close()\n            system_connection.close()\n            \n            jobs = []\n            for row in rows:\n                jobs.append({\n                    'job_id': row[0],\n                    'name': row[1],\n                    'type': row[2],\n                    'enabled': bool(row[3]),\n                    'created_date': row[4],\n                    'modified_date': row[5]\n                })\n            \n            self.logger.debug(f\"[JOB_MANAGER] Retrieved {len(jobs)} jobs\")\n            return jobs\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error listing jobs: {e}\")\n            return []\n    \n    def update_job(self, job_id: str, job_data: Dict[str, Any]) -> Dict[str, Any]:\n        \"\"\"Update existing job configuration\"\"\"\n        try:\n            # First check if job exists\n            existing_job = self.get_job(job_id)\n            if not existing_job:\n                return {\n                    'success': False,\n                    'error': f'Job with ID {job_id} not found'\n                }\n            \n            system_connection = self.db_manager.get_connection(\"system\")\n            if not system_connection:\n                return {\n                    'success': False,\n                    'error': 'System database not available'\n                }\n            \n            cursor = system_connection.cursor()\n            \n            # Update job record\n            cursor.execute(\"\"\"\n                UPDATE job_configurations \n                SET name = ?, configuration = ?, enabled = ?, modified_date = GETDATE()\n                WHERE job_id = ?\n            \"\"\", (\n                job_data.get('name', existing_job['name']),\n                json.dumps(job_data.get('configuration', existing_job['configuration'])),\n                job_data.get('enabled', existing_job['enabled']),\n                job_id\n            ))\n            \n            system_connection.commit()\n            cursor.close()\n            system_connection.close()\n            \n            self.logger.info(f\"[JOB_MANAGER] Updated job {job_id}\")\n            return {\n                'success': True,\n                'message': 'Job updated successfully'\n            }\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error updating job {job_id}: {e}\")\n            return {\n                'success': False,\n                'error': f'Error updating job: {str(e)}'\n            }\n    \n    def delete_job(self, job_id: str) -> Dict[str, Any]:\n        \"\"\"Delete job configuration\"\"\"\n        try:\n            system_connection = self.db_manager.get_connection(\"system\")\n            if not system_connection:\n                return {\n                    'success': False,\n                    'error': 'System database not available'\n                }\n            \n            cursor = system_connection.cursor()\n            cursor.execute(\"DELETE FROM job_configurations WHERE job_id = ?\", job_id)\n            rows_affected = cursor.rowcount\n            \n            system_connection.commit()\n            cursor.close()\n            system_connection.close()\n            \n            if rows_affected > 0:\n                self.logger.info(f\"[JOB_MANAGER] Deleted job {job_id}\")\n                return {\n                    'success': True,\n                    'message': 'Job deleted successfully'\n                }\n            else:\n                return {\n                    'success': False,\n                    'error': f'Job with ID {job_id} not found'\n                }\n            \n        except Exception as e:\n            self.logger.error(f\"[JOB_MANAGER] Error deleting job {job_id}: {e}\")\n            return {\n                'success': False,\n                'error': f'Error deleting job: {str(e)}'\n            }