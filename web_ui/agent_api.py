"""
Agent REST API for Job Scheduler
Implements RESTful HTTP API with JSON payloads for agent communication
"""

from flask import Blueprint, request, jsonify, current_app
from functools import wraps
from datetime import datetime, timedelta
import jwt
import hashlib
import secrets
import json
import uuid
from typing import Dict, Any, List, Optional
from database.agent_models import (
    AgentManager, AgentRegistry, AgentJobAssignment,
    AgentPool, get_agent_session
)
from database.sqlalchemy_models import JobConfigurationV2, JobExecutionHistoryV2, get_db_session
from utils.logger import get_logger
from utils.agent_logger import agent_logger
import yaml

# Create blueprint for agent API
agent_api = Blueprint('agent_api', __name__, url_prefix='/api/agent')
logger = get_logger("AgentAPI")

# JWT Configuration
JWT_SECRET = 'your-secret-key-change-in-production'  # Should be in environment variable
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 4


def generate_jwt_token(agent_id: str) -> str:
    """Generate JWT token for agent authentication"""
    payload = {
        'agent_id': agent_id,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow(),
        'type': 'agent_auth'
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'agent_auth':
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {e}")
        return None


def require_agent_auth(f):
    """Decorator to require agent authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid authorization header'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_jwt_token(token)
        
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        # Add agent_id to kwargs for use in the endpoint
        kwargs['agent_id'] = payload['agent_id']
        return f(*args, **kwargs)
    
    return decorated_function


# =============================================
# Agent Registration and Authentication
# =============================================

@agent_api.route('/register', methods=['POST'])
def register_agent():
    """
    Register a new agent with the job scheduler
    
    Expected JSON payload:
    {
        "agent_id": "unique-agent-id",
        "agent_name": "Display Name",
        "hostname": "server-hostname",
        "ip_address": "192.168.1.100",
        "capabilities": ["python", "docker", "powershell"],
        "max_parallel_jobs": 3,
        "agent_pool": "default",
        "agent_version": "1.0.0",
        "system_info": {
            "os": "Windows Server 2022",
            "cpu_cores": 8,
            "memory_gb": 16,
            "disk_space_gb": 500
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['agent_id', 'agent_name', 'hostname', 'ip_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Process system info if provided
        system_info = data.get('system_info', {})
        if system_info:
            data['os_info'] = system_info.get('os')
            data['cpu_cores'] = system_info.get('cpu_cores')
            data['memory_gb'] = system_info.get('memory_gb')
            data['disk_space_gb'] = system_info.get('disk_space_gb')
        
        # Convert capabilities list to JSON string
        if 'capabilities' in data and isinstance(data['capabilities'], list):
            data['capabilities'] = json.dumps(data['capabilities'])
        
        # Register the agent
        result = AgentManager.register_agent(data)
        
        if result['status'] in ['created', 'updated']:
            # Generate JWT token for the agent
            token = generate_jwt_token(data['agent_id'])
            
            # Log the registration event
            agent_logger.log_agent_registration(
                agent_id=data['agent_id'],
                agent_data=data,
                status=result['status'],
                jwt_token=token
            )
            
            return jsonify({
                'success': True,
                'status': result['status'],
                'agent_id': data['agent_id'],
                'jwt_token': token,
                'token_expires_in': JWT_EXPIRATION_HOURS * 3600,
                'message': f"Agent {result['status']} successfully"
            }), 201 if result['status'] == 'created' else 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('message', 'Registration failed')
            }), 500
            
    except Exception as e:
        logger.error(f"Agent registration error: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/heartbeat', methods=['POST'])
@require_agent_auth
def agent_heartbeat(agent_id: str):
    """
    Update agent heartbeat and status
    
    Expected JSON payload:
    {
        "status": "online",
        "current_jobs": 2,
        "resource_usage": {
            "cpu_percent": 45.2,
            "memory_percent": 67.8,
            "disk_percent": 23.1
        },
        "timestamp": "2025-01-27T10:30:00Z"
    }
    """
    try:
        data = request.get_json()
        
        # Prepare heartbeat data
        heartbeat_data = {
            'status': data.get('status', 'online'),
            'current_jobs': data.get('current_jobs', 0)
        }
        
        # Add resource usage if provided
        resource_usage = data.get('resource_usage', {})
        if resource_usage:
            heartbeat_data['cpu_percent'] = resource_usage.get('cpu_percent')
            heartbeat_data['memory_percent'] = resource_usage.get('memory_percent')
        
        # Update heartbeat
        success = AgentManager.update_heartbeat(agent_id, heartbeat_data)
        
        if success:
            # Log heartbeat event
            agent_logger.log_agent_heartbeat(
                agent_id=agent_id,
                status=heartbeat_data['status'],
                current_jobs=heartbeat_data['current_jobs'],
                resource_usage=data.get('resource_usage')
            )
            
            return jsonify({
                'success': True,
                'message': 'Heartbeat updated',
                'server_time': datetime.utcnow().isoformat()
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Agent not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Heartbeat update error for agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================
# Job Assignment and Polling
# =============================================

@agent_api.route('/jobs/poll', methods=['GET'])
@require_agent_auth
def poll_jobs(agent_id: str):
    """
    Poll for assigned jobs
    
    Query parameters:
    - max_jobs: Maximum number of jobs to retrieve (default: 1)
    """
    try:
        max_jobs = int(request.args.get('max_jobs', 1))
        
        session = get_db_session()
        try:
            # Get pending assignments for this agent
            assignments = session.query(AgentJobAssignment).filter(
                AgentJobAssignment.agent_id == agent_id,
                AgentJobAssignment.assignment_status == 'assigned'
            ).limit(max_jobs).all()
            
            jobs = []
            for assignment in assignments:
                # Get job configuration
                job_config = session.query(JobConfigurationV2).filter_by(
                    job_id=assignment.job_id
                ).first()
                
                if job_config:
                    # Mark assignment as accepted
                    assignment.update_status('accepted')
                    
                    jobs.append({
                        'job_id': job_config.job_id,
                        'job_name': job_config.name,
                        'execution_id': assignment.execution_id,
                        'assignment_id': assignment.assignment_id,
                        'priority': assignment.priority,
                        'timeout_minutes': assignment.timeout_minutes,
                        'yaml_configuration': job_config.yaml_configuration,
                        'assigned_at': assignment.assigned_at.isoformat()
                    })
            
            session.commit()
            
            # Log polling event
            agent_logger.log_job_polling(agent_id=agent_id, jobs_found=len(jobs))
            
            # If jobs were found, log the assignments
            for job in jobs:
                agent_logger.log_job_assignment(
                    job_id=job['job_id'],
                    execution_id=job['execution_id'],
                    agent_id=agent_id,
                    assignment_id=job['assignment_id'],
                    pool_id="default"  # We'll enhance this later
                )
            
            return jsonify({
                'success': True,
                'jobs': jobs,
                'poll_interval_seconds': 30 if not jobs else 60
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Job polling error for agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/jobs/<execution_id>/status', methods=['POST'])
@require_agent_auth
def update_job_status(agent_id: str, execution_id: str):
    """
    Update job execution status
    
    Expected JSON payload:
    {
        "status": "running",
        "progress_percent": 45,
        "current_step": "build_application",
        "message": "Compiling source code...",
        "start_time": "2025-01-27T10:35:30Z"
    }
    """
    try:
        data = request.get_json()
        status = data.get('status', 'running')
        
        session = get_db_session()
        try:
            # Find the assignment
            assignment = session.query(AgentJobAssignment).filter(
                AgentJobAssignment.execution_id == execution_id,
                AgentJobAssignment.agent_id == agent_id
            ).first()
            
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            # Update assignment status
            if status == 'running' and assignment.assignment_status != 'running':
                assignment.update_status('running')
            
            # Update execution history
            execution = session.query(JobExecutionHistoryV2).filter_by(
                execution_id=execution_id
            ).first()
            
            if execution:
                execution.status = status
                if status == 'running' and not execution.start_time:
                    execution.start_time = datetime.utcnow()
                
                # Add status message to output log
                message = data.get('message', '')
                if message:
                    if execution.output_log:
                        execution.output_log += f"\n[{datetime.utcnow().isoformat()}] {message}"
                    else:
                        execution.output_log = f"[{datetime.utcnow().isoformat()}] {message}"
            
            session.commit()
            
            # Log status update
            agent_logger.log_job_status_update(
                execution_id=execution_id,
                agent_id=agent_id,
                status=status,
                message=data.get('message')
            )
            
            return jsonify({
                'success': True,
                'message': 'Status updated'
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Status update error for job {execution_id}: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/jobs/<execution_id>/complete', methods=['POST'])
@require_agent_auth
def complete_job(agent_id: str, execution_id: str):
    """
    Mark job as completed with results
    
    Expected JSON payload:
    {
        "status": "success",
        "return_code": 0,
        "start_time": "2025-01-27T10:35:30Z",
        "end_time": "2025-01-27T10:45:15Z",
        "duration_seconds": 585,
        "output_log": "Job completed successfully...",
        "error_message": null,
        "step_results": [...]
    }
    """
    try:
        data = request.get_json()
        status = data.get('status', 'success')
        
        session = get_db_session()
        try:
            # Find the assignment
            assignment = session.query(AgentJobAssignment).filter(
                AgentJobAssignment.execution_id == execution_id,
                AgentJobAssignment.agent_id == agent_id
            ).first()
            
            if not assignment:
                return jsonify({'error': 'Assignment not found'}), 404
            
            # Update assignment
            assignment.update_status(
                'completed' if status == 'success' else 'failed',
                return_code=data.get('return_code'),
                output_summary=data.get('output_log', '')[:500] if data.get('output_log') else None
            )
            
            # Update execution history
            execution = session.query(JobExecutionHistoryV2).filter_by(
                execution_id=execution_id
            ).first()
            
            if execution:
                execution.status = status
                execution.end_time = datetime.utcnow()
                execution.duration_seconds = data.get('duration_seconds')
                execution.output_log = data.get('output_log')
                execution.error_message = data.get('error_message')
                execution.return_code = data.get('return_code')
                execution.executed_on_agent = agent_id
                
                if data.get('step_results'):
                    execution.step_results = json.dumps(data['step_results'])
            
            # Update job configuration stats
            job_config = session.query(JobConfigurationV2).filter_by(
                job_id=assignment.job_id
            ).first()
            
            if job_config:
                job_config.last_execution_id = execution_id
                job_config.last_execution_status = status
                job_config.last_execution_time = datetime.utcnow()
                job_config.total_executions = (job_config.total_executions or 0) + 1
                
                if status == 'success':
                    job_config.successful_executions = (job_config.successful_executions or 0) + 1
                else:
                    job_config.failed_executions = (job_config.failed_executions or 0) + 1
            
            # Update agent job count
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            if agent:
                agent.current_jobs = max(0, agent.current_jobs - 1)
                agent.last_job_completed = datetime.utcnow()
            
            session.commit()
            
            # Log job completion
            agent_logger.log_job_completion(
                execution_id=execution_id,
                agent_id=agent_id,
                status=status,
                duration_seconds=data.get('duration_seconds'),
                return_code=data.get('return_code')
            )
            
            return jsonify({
                'success': True,
                'message': 'Job completion recorded'
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Job completion error for {execution_id}: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================
# Administrative Endpoints
# =============================================

@agent_api.route('/list', methods=['GET'])
def list_agents():
    """List all registered agents"""
    try:
        session = get_agent_session()
        try:
            agents = session.query(AgentRegistry).all()
            agent_list = [agent.to_dict() for agent in agents]
            
            return jsonify({
                'success': True,
                'agents': agent_list,
                'total': len(agent_list)
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/<agent_id>/approve', methods=['POST'])
def approve_agent(agent_id: str):
    """Approve an agent for job execution"""
    try:
        session = get_agent_session()
        try:
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404
            
            agent.is_approved = True
            session.commit()
            
            # Log approval event
            agent_logger.log_agent_approval(agent_id=agent_id, approved_by="admin")
            
            return jsonify({
                'success': True,
                'message': 'Agent approved'
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error approving agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/pools', methods=['GET'])
def list_pools():
    """List all agent pools"""
    try:
        session = get_agent_session()
        try:
            pools = session.query(AgentPool).filter_by(is_active=True).all()
            pool_list = [pool.to_dict() for pool in pools]
            
            # Add agent count for each pool
            for pool_dict in pool_list:
                agent_count = session.query(AgentRegistry).filter_by(
                    agent_pool=pool_dict['pool_id'],
                    is_active=True
                ).count()
                pool_dict['agent_count'] = agent_count
            
            return jsonify({
                'success': True,
                'pools': pool_list,
                'total': len(pool_list)
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error listing pools: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================
# Agent Management Endpoints
# =============================================

@agent_api.route('/<agent_id>/remove', methods=['POST'])
def remove_agent(agent_id):
    """
    Remove an agent from the system
    
    This will:
    1. Mark the agent as inactive
    2. Cancel any running jobs
    3. Remove from database (optional)
    """
    try:
        data = request.get_json() or {}
        permanent_delete = data.get('permanent_delete', False)
        
        session = get_db_session()
        try:
            # Find the agent
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404
            
            # Check if agent has active jobs
            active_assignments = session.query(AgentJobAssignment).filter(
                AgentJobAssignment.agent_id == agent_id,
                AgentJobAssignment.assignment_status.in_(['assigned', 'running'])
            ).all()
            
            if active_assignments:
                # Cancel active jobs
                for assignment in active_assignments:
                    assignment.assignment_status = 'cancelled'
                    assignment.completed_at = datetime.utcnow()
                    
                    # Update execution history
                    execution = session.query(JobExecutionHistoryV2).filter_by(
                        execution_id=assignment.execution_id
                    ).first()
                    if execution:
                        execution.status = 'cancelled'
                        execution.end_time = datetime.utcnow()
                        execution.output_log = (execution.output_log or '') + f"\n[{datetime.utcnow().isoformat()}] Job cancelled due to agent removal"
            
            if permanent_delete:
                # Permanent deletion
                session.delete(agent)
                action = 'deleted permanently'
            else:
                # Soft deletion - mark as inactive
                agent.is_active = False
                agent.status = 'removed'
                agent.last_heartbeat = None
                action = 'deactivated'
            
            session.commit()
            
            # Log the removal
            logger.info(f"Agent {agent_id} {action} by user request")
            
            return jsonify({
                'success': True,
                'message': f'Agent {agent_id} has been {action}',
                'cancelled_jobs': len(active_assignments) if active_assignments else 0
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error removing agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/<agent_id>/deactivate', methods=['POST'])
def deactivate_agent(agent_id):
    """
    Temporarily deactivate an agent without removing it
    """
    try:
        session = get_db_session()
        try:
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404
            
            agent.is_active = False
            agent.status = 'inactive'
            session.commit()
            
            logger.info(f"Agent {agent_id} deactivated")
            
            return jsonify({
                'success': True,
                'message': f'Agent {agent_id} has been deactivated'
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error deactivating agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


@agent_api.route('/<agent_id>/activate', methods=['POST'])
def activate_agent(agent_id):
    """
    Reactivate a previously deactivated agent
    """
    try:
        session = get_db_session()
        try:
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            
            if not agent:
                return jsonify({'error': 'Agent not found'}), 404
            
            agent.is_active = True
            agent.status = 'offline'  # Will be updated to online when agent sends heartbeat
            session.commit()
            
            logger.info(f"Agent {agent_id} reactivated")
            
            return jsonify({
                'success': True,
                'message': f'Agent {agent_id} has been reactivated'
            }), 200
            
        finally:
            session.close()
            
    except Exception as e:
        logger.error(f"Error activating agent {agent_id}: {e}")
        return jsonify({'error': str(e)}), 500


# =============================================
# Health Check Endpoint
# =============================================

@agent_api.route('/health', methods=['GET'])
def health_check():
    """Agent API health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'agent-api',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat()
    }), 200