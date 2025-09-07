"""
Agent Job Handler for Job Scheduler
Handles job assignment to agents and execution tracking
"""

import uuid
import json
import yaml
from datetime import datetime
from typing import Dict, Any, Optional, List
from database.agent_models import AgentManager, get_agent_session
from database.sqlalchemy_models import (
    JobConfigurationV2, JobExecutionHistoryV2, 
    get_db_session
)
from utils.logger import get_logger
from utils.agent_logger import agent_logger

logger = get_logger("AgentJobHandler")


class AgentJobHandler:
    """Handler for agent-based job execution"""
    
    def __init__(self):
        """Initialize the agent job handler"""
        self.logger = logger
        agent_logger.logger.info("[AGENT_JOB_HANDLER] Initialized agent job handler")
        agent_logger.logger.info("  - Ready to handle agent job assignment and execution tracking")
    
    def parse_job_configuration(self, yaml_config: str) -> Dict[str, Any]:
        """Parse YAML configuration to determine if job should run on agent"""
        try:
            config = yaml.safe_load(yaml_config)
            
            # Check if this is an agent job
            job_type = config.get('job_type', 'local')
            execution_type = config.get('execution_type', 'local')
            
            # Determine if job should run on agent
            is_agent_job = (
                job_type == 'agent_job' or 
                execution_type == 'agent' or
                'agent_pool' in config
            )
            
            return {
                'is_agent_job': is_agent_job,
                'agent_pool': config.get('agent_pool', 'default'),
                'job_type': job_type,
                'config': config
            }
        except Exception as e:
            logger.error(f"Error parsing job configuration: {e}")
            return {
                'is_agent_job': False,
                'agent_pool': 'default',
                'job_type': 'local',
                'config': {}
            }
    
    def should_execute_on_agent(self, job_id: str) -> bool:
        """Check if a job should be executed on an agent"""
        session = get_db_session()
        try:
            job = session.query(JobConfigurationV2).filter_by(job_id=job_id).first()
            if not job:
                return False
            
            # Check execution_type column first
            if hasattr(job, 'execution_type') and job.execution_type == 'agent':
                return True
            
            # Parse YAML configuration
            parsed = self.parse_job_configuration(job.yaml_configuration)
            return parsed['is_agent_job']
            
        except Exception as e:
            logger.error(f"Error checking job {job_id} for agent execution: {e}")
            return False
        finally:
            session.close()
    
    def assign_job_to_agent(self, job_id: str, execution_id: str, 
                           pool_id: str = None) -> Optional[str]:
        """
        Assign a job to an available agent
        Returns assignment_id if successful, None otherwise
        """
        session = get_db_session()
        try:
            # Get job configuration
            job = session.query(JobConfigurationV2).filter_by(job_id=job_id).first()
            if not job:
                logger.error(f"Job {job_id} not found")
                return None
            
            # Parse configuration
            parsed = self.parse_job_configuration(job.yaml_configuration)
            config = parsed['config']
            
            # Determine agent pool
            if not pool_id:
                pool_id = parsed['agent_pool']
                # Check if job has preferred agent pool
                if hasattr(job, 'preferred_agent_pool') and job.preferred_agent_pool:
                    pool_id = job.preferred_agent_pool
            
            # Get required capabilities from config
            agent_requirements = config.get('agent_requirements', {})
            required_capabilities = agent_requirements.get('capabilities', [])
            
            # Find available agent
            agent = AgentManager.get_available_agent(pool_id, required_capabilities)
            if not agent:
                self.logger.warning(f"No available agent in pool '{pool_id}' for job {job_id}")
                agent_logger.log_no_agent_available(pool_id=pool_id, job_id=job_id)
                return None
            
            # Create assignment
            assignment_id = AgentManager.assign_job_to_agent(
                job_id=job_id,
                execution_id=execution_id,
                agent_id=agent.agent_id,
                pool_id=pool_id
            )
            
            if assignment_id:
                # Update execution history with agent info
                execution = session.query(JobExecutionHistoryV2).filter_by(
                    execution_id=execution_id
                ).first()
                
                if execution:
                    execution.executed_on_agent = agent.agent_id
                    execution.assignment_id = assignment_id
                    session.commit()
                
                # Log successful assignment
                agent_logger.log_job_assignment(
                    job_id=job_id,
                    execution_id=execution_id,
                    agent_id=agent.agent_id,
                    assignment_id=assignment_id,
                    pool_id=pool_id
                )
                return assignment_id
            else:
                self.logger.error(f"Failed to create assignment for job {job_id}")
                agent_logger.log_agent_error(
                    agent_id=agent.agent_id,
                    operation="job_assignment",
                    error="Failed to create assignment record"
                )
                return None
                
        except Exception as e:
            self.logger.error(f"Error assigning job {job_id} to agent: {e}")
            agent_logger.log_agent_error(
                agent_id="unknown",
                operation="job_assignment",
                error=str(e)
            )
            session.rollback()
            return None
        finally:
            session.close()
    
    def create_agent_execution(self, job_id: str, execution_mode: str = 'manual',
                             executed_by: str = 'system') -> Optional[Dict[str, Any]]:
        """
        Create an execution record for an agent job
        Returns execution details if successful
        """
        session = get_db_session()
        try:
            # Get job configuration
            job = session.query(JobConfigurationV2).filter_by(job_id=job_id).first()
            if not job:
                return None
            
            # Parse configuration
            parsed = self.parse_job_configuration(job.yaml_configuration)
            
            if not parsed['is_agent_job']:
                logger.warning(f"Job {job_id} is not configured for agent execution")
                return None
            
            # Create execution record
            execution_id = str(uuid.uuid4())
            execution = JobExecutionHistoryV2(
                execution_id=execution_id,
                job_id=job_id,
                job_name=job.name,
                status='pending',
                execution_mode=execution_mode,
                executed_by=executed_by,
                execution_timezone='UTC'
            )
            session.add(execution)
            session.commit()
            
            # Assign to agent
            assignment_id = self.assign_job_to_agent(
                job_id=job_id,
                execution_id=execution_id,
                pool_id=parsed['agent_pool']
            )
            
            if assignment_id:
                # Update status to assigned
                execution.status = 'assigned'
                session.commit()
                
                return {
                    'success': True,
                    'execution_id': execution_id,
                    'assignment_id': assignment_id,
                    'status': 'assigned',
                    'agent_pool': parsed['agent_pool']
                }
            else:
                # No agent available - mark as queued
                execution.status = 'queued'
                session.commit()
                
                return {
                    'success': False,
                    'execution_id': execution_id,
                    'status': 'queued',
                    'message': 'No agent available, job queued'
                }
                
        except Exception as e:
            logger.error(f"Error creating agent execution for job {job_id}: {e}")
            session.rollback()
            return None
        finally:
            session.close()
    
    def get_agent_job_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of an agent job execution"""
        session = get_db_session()
        try:
            execution = session.query(JobExecutionHistoryV2).filter_by(
                execution_id=execution_id
            ).first()
            
            if not execution:
                return None
            
            result = {
                'execution_id': execution_id,
                'job_id': execution.job_id,
                'job_name': execution.job_name,
                'status': execution.status,
                'start_time': execution.start_time.isoformat() if execution.start_time else None,
                'end_time': execution.end_time.isoformat() if execution.end_time else None,
                'duration_seconds': execution.duration_seconds,
                'executed_on_agent': execution.executed_on_agent,
                'assignment_id': execution.assignment_id
            }
            
            # Get assignment details if available
            if execution.assignment_id:
                from database.agent_models import AgentJobAssignment
                assignment = session.query(AgentJobAssignment).filter_by(
                    assignment_id=execution.assignment_id
                ).first()
                
                if assignment:
                    result['assignment_status'] = assignment.assignment_status
                    result['agent_id'] = assignment.agent_id
                    result['assigned_at'] = assignment.assigned_at.isoformat() if assignment.assigned_at else None
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting status for execution {execution_id}: {e}")
            return None
        finally:
            session.close()
    
    def retry_queued_jobs(self) -> int:
        """
        Retry assignment of queued jobs to available agents
        Returns number of jobs assigned
        """
        session = get_db_session()
        assigned_count = 0
        
        try:
            # Find queued executions
            queued = session.query(JobExecutionHistoryV2).filter_by(
                status='queued'
            ).all()
            
            for execution in queued:
                # Try to assign to agent
                job = session.query(JobConfigurationV2).filter_by(
                    job_id=execution.job_id
                ).first()
                
                if job:
                    parsed = self.parse_job_configuration(job.yaml_configuration)
                    
                    if parsed['is_agent_job']:
                        assignment_id = self.assign_job_to_agent(
                            job_id=execution.job_id,
                            execution_id=execution.execution_id,
                            pool_id=parsed['agent_pool']
                        )
                        
                        if assignment_id:
                            execution.status = 'assigned'
                            execution.assignment_id = assignment_id
                            assigned_count += 1
                            self.logger.info(f"Queued job {execution.job_id} assigned to agent")
                            # Detailed logging is handled by assign_job_to_agent method
            
            if assigned_count > 0:
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Error retrying queued jobs: {e}")
            agent_logger.log_agent_error(
                agent_id="system",
                operation="retry_queued_jobs",
                error=str(e)
            )
            session.rollback()
        finally:
            session.close()
        
        return assigned_count


# Global instance
agent_job_handler = AgentJobHandler()