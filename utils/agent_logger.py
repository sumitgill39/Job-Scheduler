"""
Agent System Logger
Specialized logging for agent-based job execution system
Writes to logs/scheduler.log with agent-specific formatting
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
from utils.logger import get_logger

class AgentSystemLogger:
    """Specialized logger for agent system operations"""
    
    def __init__(self):
        """Initialize agent system logger"""
        # Use the main logger that writes to logs/scheduler.log
        self.logger = get_logger("AGENT_SYSTEM")
        self.logger.info("="*60)
        self.logger.info("AGENT SYSTEM INITIALIZED")
        self.logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
        self.logger.info("="*60)
    
    def log_agent_registration(self, agent_id: str, agent_data: Dict[str, Any], 
                              status: str, jwt_token: Optional[str] = None):
        """Log agent registration event"""
        self.logger.info(f"[AGENT_REGISTRATION] Agent: {agent_id}")
        self.logger.info(f"  - Status: {status}")
        self.logger.info(f"  - Hostname: {agent_data.get('hostname')}")
        self.logger.info(f"  - IP Address: {agent_data.get('ip_address')}")
        self.logger.info(f"  - Pool: {agent_data.get('agent_pool', 'default')}")
        self.logger.info(f"  - Capabilities: {agent_data.get('capabilities', [])}")
        self.logger.info(f"  - Max Parallel Jobs: {agent_data.get('max_parallel_jobs', 1)}")
        if jwt_token:
            self.logger.debug(f"  - JWT Token Generated: {jwt_token[:20]}...")
    
    def log_agent_heartbeat(self, agent_id: str, status: str, 
                          current_jobs: int = 0, resource_usage: Dict = None):
        """Log agent heartbeat event"""
        self.logger.debug(f"[AGENT_HEARTBEAT] Agent: {agent_id}")
        self.logger.debug(f"  - Status: {status}")
        self.logger.debug(f"  - Current Jobs: {current_jobs}")
        if resource_usage:
            self.logger.debug(f"  - CPU: {resource_usage.get('cpu_percent', 'N/A')}%")
            self.logger.debug(f"  - Memory: {resource_usage.get('memory_percent', 'N/A')}%")
    
    def log_job_assignment(self, job_id: str, execution_id: str, 
                          agent_id: str, assignment_id: str, pool_id: str):
        """Log job assignment to agent"""
        self.logger.info(f"[JOB_ASSIGNMENT] Job {job_id} assigned to agent {agent_id}")
        self.logger.info(f"  - Execution ID: {execution_id}")
        self.logger.info(f"  - Assignment ID: {assignment_id}")
        self.logger.info(f"  - Agent Pool: {pool_id}")
        self.logger.info(f"  - Timestamp: {datetime.utcnow().isoformat()}")
    
    def log_job_polling(self, agent_id: str, jobs_found: int):
        """Log agent job polling event"""
        self.logger.debug(f"[JOB_POLLING] Agent {agent_id} polled for jobs")
        self.logger.debug(f"  - Jobs Found: {jobs_found}")
    
    def log_job_status_update(self, execution_id: str, agent_id: str, 
                             status: str, message: Optional[str] = None):
        """Log job status update from agent"""
        self.logger.info(f"[JOB_STATUS] Execution {execution_id} status: {status}")
        self.logger.info(f"  - Agent: {agent_id}")
        if message:
            self.logger.info(f"  - Message: {message}")
    
    def log_job_completion(self, execution_id: str, agent_id: str, 
                          status: str, duration_seconds: Optional[float] = None,
                          return_code: Optional[int] = None):
        """Log job completion by agent"""
        self.logger.info(f"[JOB_COMPLETION] Execution {execution_id} completed")
        self.logger.info(f"  - Agent: {agent_id}")
        self.logger.info(f"  - Status: {status}")
        if duration_seconds:
            self.logger.info(f"  - Duration: {duration_seconds:.2f} seconds")
        if return_code is not None:
            self.logger.info(f"  - Return Code: {return_code}")
        self.logger.info(f"  - Timestamp: {datetime.utcnow().isoformat()}")
    
    def log_agent_approval(self, agent_id: str, approved_by: str = "system"):
        """Log agent approval event"""
        self.logger.info(f"[AGENT_APPROVAL] Agent {agent_id} approved")
        self.logger.info(f"  - Approved By: {approved_by}")
        self.logger.info(f"  - Timestamp: {datetime.utcnow().isoformat()}")
    
    def log_agent_error(self, agent_id: str, operation: str, error: str):
        """Log agent error event"""
        self.logger.error(f"[AGENT_ERROR] Agent {agent_id} - Operation: {operation}")
        self.logger.error(f"  - Error: {error}")
        self.logger.error(f"  - Timestamp: {datetime.utcnow().isoformat()}")
    
    def log_no_agent_available(self, pool_id: str, job_id: str):
        """Log when no agent is available for job"""
        self.logger.warning(f"[NO_AGENT_AVAILABLE] No agent available in pool '{pool_id}'")
        self.logger.warning(f"  - Job ID: {job_id}")
        self.logger.warning(f"  - Job queued for later assignment")
    
    def log_agent_offline(self, agent_id: str, last_heartbeat: Optional[datetime] = None):
        """Log agent going offline"""
        self.logger.warning(f"[AGENT_OFFLINE] Agent {agent_id} marked as offline")
        if last_heartbeat:
            self.logger.warning(f"  - Last Heartbeat: {last_heartbeat.isoformat()}")
    
    def log_api_request(self, endpoint: str, method: str, 
                       agent_id: Optional[str] = None, status_code: int = None):
        """Log API request for debugging"""
        self.logger.debug(f"[API_REQUEST] {method} {endpoint}")
        if agent_id:
            self.logger.debug(f"  - Agent: {agent_id}")
        if status_code:
            self.logger.debug(f"  - Response: {status_code}")
    
    def log_authentication_failure(self, reason: str, token: Optional[str] = None):
        """Log authentication failure"""
        self.logger.warning(f"[AUTH_FAILURE] Authentication failed")
        self.logger.warning(f"  - Reason: {reason}")
        if token:
            self.logger.debug(f"  - Token (first 20 chars): {token[:20]}...")
    
    def log_system_stats(self, total_agents: int, online_agents: int, 
                        total_pools: int, queued_jobs: int):
        """Log agent system statistics"""
        self.logger.info("[AGENT_SYSTEM_STATS]")
        self.logger.info(f"  - Total Agents: {total_agents}")
        self.logger.info(f"  - Online Agents: {online_agents}")
        self.logger.info(f"  - Agent Pools: {total_pools}")
        self.logger.info(f"  - Queued Jobs: {queued_jobs}")
        self.logger.info(f"  - Timestamp: {datetime.utcnow().isoformat()}")


# Global instance for agent system logging
agent_logger = AgentSystemLogger()