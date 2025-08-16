"""
Mock job storage for testing when database is not available
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils.logger import get_logger


class MockJobStorage:
    """Mock job storage that works without database connectivity"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._execution_history: List[Dict[str, Any]] = []
        self.logger.info("[MOCK_STORAGE] Mock job storage initialized")
    
    def save_job(self, job_config: Dict[str, Any]) -> Dict[str, Any]:
        """Save job configuration to mock storage"""
        try:
            job_id = job_config['job_id']
            
            # Test JSON serialization to ensure special characters are handled
            json_test = json.dumps(job_config)
            
            # Store in mock storage
            self._jobs[job_id] = job_config.copy()
            
            self.logger.info(f"[MOCK_STORAGE] Successfully saved job to mock storage: {job_id}")
            self.logger.debug(f"[MOCK_STORAGE] Job type: {job_config.get('type')}, Name: {job_config.get('name')}")
            
            return {
                'success': True,
                'job_id': job_id,
                'message': 'Job saved to mock storage successfully'
            }
            
        except json.JSONEncodeError as e:
            error_msg = f"JSON serialization failed for job: {str(e)}"
            self.logger.error(f"[MOCK_STORAGE] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f"Failed to save job to mock storage: {str(e)}"
            self.logger.error(f"[MOCK_STORAGE] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job configuration from mock storage"""
        job = self._jobs.get(job_id)
        if job:
            self.logger.debug(f"[MOCK_STORAGE] Retrieved job from mock storage: {job_id}")
        else:
            self.logger.warning(f"[MOCK_STORAGE] Job not found in mock storage: {job_id}")
        return job
    
    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get all jobs from mock storage"""
        jobs = list(self._jobs.values())
        self.logger.debug(f"[MOCK_STORAGE] Retrieved {len(jobs)} jobs from mock storage")
        return jobs
    
    def delete_job(self, job_id: str) -> bool:
        """Delete job from mock storage"""
        if job_id in self._jobs:
            del self._jobs[job_id]
            self.logger.info(f"[MOCK_STORAGE] Deleted job from mock storage: {job_id}")
            return True
        else:
            self.logger.warning(f"[MOCK_STORAGE] Job not found for deletion: {job_id}")
            return False
    
    def save_execution_record(self, execution_record: Dict[str, Any]) -> bool:
        """Save execution record to mock storage"""
        try:
            # Add execution ID if not present
            if 'execution_id' not in execution_record:
                execution_record['execution_id'] = len(self._execution_history) + 1
            
            self._execution_history.append(execution_record)
            self.logger.debug(f"[MOCK_STORAGE] Saved execution record: {execution_record['execution_id']}")
            return True
        except Exception as e:
            self.logger.error(f"[MOCK_STORAGE] Failed to save execution record: {e}")
            return False
    
    def get_execution_history(self, job_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history from mock storage"""
        history = self._execution_history
        
        if job_id:
            history = [record for record in history if record.get('job_id') == job_id]
        
        # Sort by start_time (most recent first) and limit
        history = sorted(history, key=lambda x: x.get('start_time', ''), reverse=True)
        history = history[:limit]
        
        self.logger.debug(f"[MOCK_STORAGE] Retrieved {len(history)} execution records")
        return history
    
    def get_stats(self) -> Dict[str, Any]:
        """Get mock storage statistics"""
        return {
            'total_jobs': len(self._jobs),
            'total_executions': len(self._execution_history),
            'job_types': {
                'sql': len([j for j in self._jobs.values() if j.get('type') == 'sql']),
                'powershell': len([j for j in self._jobs.values() if j.get('type') == 'powershell'])
            },
            'storage_type': 'mock'
        }


# Global mock storage instance
_mock_storage = None

def get_mock_storage() -> MockJobStorage:
    """Get global mock storage instance"""
    global _mock_storage
    if _mock_storage is None:
        _mock_storage = MockJobStorage()
    return _mock_storage