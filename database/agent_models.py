"""
SQLAlchemy models for Agent-Based Job Execution System
Compatible with existing Job Scheduler database models
"""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Integer, 
    Float, ForeignKey, Index
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.sqlalchemy_models import Base, database_engine
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class AgentRegistry(Base):
    """Agent registration and status tracking"""
    __tablename__ = 'agent_registry'
    
    # Primary identification
    agent_id = Column(String(50), primary_key=True)
    agent_name = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(50), nullable=False)
    
    # Agent capabilities and pool assignment
    agent_pool = Column(String(100), default='default')
    capabilities = Column(Text)  # JSON array of capabilities
    max_parallel_jobs = Column(Integer, default=1)
    agent_version = Column(String(20))
    
    # System information
    os_info = Column(String(255))
    cpu_cores = Column(Integer)
    memory_gb = Column(Integer)
    disk_space_gb = Column(Integer)
    
    # Status and health
    status = Column(String(20), default='offline')  # online, offline, maintenance, error
    last_heartbeat = Column(DateTime)
    last_job_completed = Column(DateTime)
    
    # Resource utilization
    current_jobs = Column(Integer, default=0)
    cpu_percent = Column(Float)
    memory_percent = Column(Float)
    disk_percent = Column(Float)
    
    # Authentication
    api_key_hash = Column(String(255))
    jwt_secret = Column(String(500))
    
    # Metadata
    registered_date = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    is_approved = Column(Boolean, default=False)
    
    # Relationships
    job_assignments = relationship("AgentJobAssignment", back_populates="agent")
    
    # Indexes
    __table_args__ = (
        Index('ix_agent_registry_pool', 'agent_pool'),
        Index('ix_agent_registry_status', 'status'),
        Index('ix_agent_registry_heartbeat', 'last_heartbeat'),
        Index('ix_agent_registry_active', 'is_active'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'agent_id': self.agent_id,
            'agent_name': self.agent_name,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'agent_pool': self.agent_pool,
            'capabilities': json.loads(self.capabilities) if self.capabilities else [],
            'max_parallel_jobs': self.max_parallel_jobs,
            'agent_version': self.agent_version,
            'os_info': self.os_info,
            'cpu_cores': self.cpu_cores,
            'memory_gb': self.memory_gb,
            'disk_space_gb': self.disk_space_gb,
            'status': self.status,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'last_job_completed': self.last_job_completed.isoformat() if self.last_job_completed else None,
            'current_jobs': self.current_jobs,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_percent': self.disk_percent,
            'registered_date': self.registered_date.isoformat() if self.registered_date else None,
            'is_active': self.is_active,
            'is_approved': self.is_approved,
            'is_online': self.is_online()
        }
    
    def is_online(self) -> bool:
        """Check if agent is currently online based on heartbeat"""
        if not self.last_heartbeat:
            return False
        # Consider online if heartbeat within last 5 minutes
        time_diff = datetime.utcnow() - self.last_heartbeat
        return time_diff.total_seconds() < 300 and self.status == 'online'
    
    def can_accept_job(self) -> bool:
        """Check if agent can accept a new job"""
        return (
            self.is_active and 
            self.is_approved and 
            self.is_online() and 
            self.current_jobs < self.max_parallel_jobs
        )
    
    def update_heartbeat(self, status: str = 'online', 
                        current_jobs: int = 0,
                        cpu_percent: float = None,
                        memory_percent: float = None) -> None:
        """Update agent heartbeat information"""
        self.last_heartbeat = datetime.utcnow()
        self.status = status
        self.current_jobs = current_jobs
        if cpu_percent is not None:
            self.cpu_percent = cpu_percent
        if memory_percent is not None:
            self.memory_percent = memory_percent
        self.last_updated = datetime.utcnow()


class AgentJobAssignment(Base):
    """Job to agent assignment tracking"""
    __tablename__ = 'agent_job_assignments'
    
    # Assignment identification
    assignment_id = Column(String(36), primary_key=True)
    execution_id = Column(String(36), nullable=False)
    job_id = Column(String(36), nullable=False)
    agent_id = Column(String(50), ForeignKey('agent_registry.agent_id', ondelete='SET NULL'))
    
    # Assignment details
    assignment_type = Column(String(20), default='local')  # local, agent
    assignment_strategy = Column(String(50))  # default_pool, specific_agent
    
    # Assignment status
    assignment_status = Column(String(20), default='assigned')
    assigned_at = Column(DateTime, default=func.now())
    accepted_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Resource allocation
    priority = Column(Integer, default=5)
    timeout_minutes = Column(Integer, default=60)
    max_retries = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    
    # Results
    return_code = Column(Integer)
    output_summary = Column(String(500))
    
    # Relationships
    agent = relationship("AgentRegistry", back_populates="job_assignments")
    
    # Indexes
    __table_args__ = (
        Index('ix_agent_assignments_execution', 'execution_id'),
        Index('ix_agent_assignments_job', 'job_id'),
        Index('ix_agent_assignments_agent', 'agent_id'),
        Index('ix_agent_assignments_status', 'assignment_status'),
        Index('ix_agent_assignments_assigned', 'assigned_at'),
        Index('ix_agent_assignments_type', 'assignment_type'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'assignment_id': self.assignment_id,
            'execution_id': self.execution_id,
            'job_id': self.job_id,
            'agent_id': self.agent_id,
            'assignment_type': self.assignment_type,
            'assignment_strategy': self.assignment_strategy,
            'assignment_status': self.assignment_status,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'priority': self.priority,
            'timeout_minutes': self.timeout_minutes,
            'max_retries': self.max_retries,
            'retry_count': self.retry_count,
            'return_code': self.return_code,
            'output_summary': self.output_summary,
            'agent_info': self.agent.to_dict() if self.agent else None
        }
    
    def update_status(self, status: str, **kwargs) -> None:
        """Update assignment status with timestamps"""
        self.assignment_status = status
        
        if status == 'accepted' and not self.accepted_at:
            self.accepted_at = datetime.utcnow()
        elif status == 'running' and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in ['completed', 'failed', 'timeout'] and not self.completed_at:
            self.completed_at = datetime.utcnow()
            if 'return_code' in kwargs:
                self.return_code = kwargs['return_code']
            if 'output_summary' in kwargs:
                self.output_summary = kwargs['output_summary']


class AgentPool(Base):
    """Agent pool configuration"""
    __tablename__ = 'agent_pools'
    
    # Pool identification
    pool_id = Column(String(100), primary_key=True)
    pool_name = Column(String(255), nullable=False)
    description = Column(Text)
    
    # Pool configuration
    max_agents = Column(Integer, default=10)
    load_balancing_strategy = Column(String(50), default='round_robin')
    
    # Pool status
    is_active = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())
    created_by = Column(String(255), default='system')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'pool_id': self.pool_id,
            'pool_name': self.pool_name,
            'description': self.description,
            'max_agents': self.max_agents,
            'load_balancing_strategy': self.load_balancing_strategy,
            'is_active': self.is_active,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'created_by': self.created_by
        }


def create_agent_tables():
    """Create all agent-related tables"""
    # Import Base from main models to ensure all tables are registered
    from database.sqlalchemy_models import Base, database_engine
    
    # Create only the new agent tables
    Base.metadata.create_all(
        database_engine.engine, 
        tables=[
            AgentRegistry.__table__,
            AgentJobAssignment.__table__,
            AgentPool.__table__
        ]
    )
    
    print("Agent tables created successfully")


def get_agent_session():
    """Get a database session for agent operations"""
    from database.sqlalchemy_models import database_engine
    return database_engine.get_session()


# Agent Manager class for high-level operations
class AgentManager:
    """Manager class for agent operations"""
    
    @staticmethod
    def register_agent(agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new agent or update existing"""
        session = get_agent_session()
        try:
            agent = session.query(AgentRegistry).filter_by(
                agent_id=agent_data['agent_id']
            ).first()
            
            if agent:
                # Update existing agent
                for key, value in agent_data.items():
                    if hasattr(agent, key):
                        setattr(agent, key, value)
                result = {'status': 'updated', 'agent': agent.to_dict()}
            else:
                # Create new agent
                agent = AgentRegistry(**agent_data)
                session.add(agent)
                result = {'status': 'created', 'agent': agent.to_dict()}
            
            session.commit()
            return result
            
        except Exception as e:
            session.rollback()
            return {'status': 'error', 'message': str(e)}
        finally:
            session.close()
    
    @staticmethod
    def get_available_agent(pool_id: str = 'default', 
                           required_capabilities: List[str] = None) -> Optional[AgentRegistry]:
        """Get an available agent from the specified pool"""
        session = get_agent_session()
        try:
            query = session.query(AgentRegistry).filter(
                AgentRegistry.agent_pool == pool_id,
                AgentRegistry.is_active == True,
                AgentRegistry.is_approved == True,
                AgentRegistry.status == 'online'
            )
            
            # Filter by capabilities if required
            if required_capabilities:
                for capability in required_capabilities:
                    query = query.filter(
                        AgentRegistry.capabilities.contains(capability)
                    )
            
            # Get agents that can accept jobs
            agents = query.all()
            available_agents = [a for a in agents if a.can_accept_job()]
            
            if not available_agents:
                return None
            
            # Simple round-robin: select least loaded agent
            return min(available_agents, key=lambda a: a.current_jobs)
            
        finally:
            session.close()
    
    @staticmethod
    def update_heartbeat(agent_id: str, heartbeat_data: Dict[str, Any]) -> bool:
        """Update agent heartbeat"""
        session = get_agent_session()
        try:
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            if agent:
                agent.update_heartbeat(**heartbeat_data)
                session.commit()
                return True
            return False
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()
    
    @staticmethod
    def assign_job_to_agent(job_id: str, execution_id: str, 
                           agent_id: str = None, pool_id: str = 'default') -> Optional[str]:
        """Assign a job to an agent"""
        session = get_agent_session()
        try:
            # Get available agent if not specified
            if not agent_id:
                agent = AgentManager.get_available_agent(pool_id)
                if not agent:
                    return None
                agent_id = agent.agent_id
            
            # Create assignment
            import uuid
            assignment = AgentJobAssignment(
                assignment_id=str(uuid.uuid4()),
                execution_id=execution_id,
                job_id=job_id,
                agent_id=agent_id,
                assignment_type='agent',
                assignment_strategy='default_pool'
            )
            
            # Update agent job count
            agent = session.query(AgentRegistry).filter_by(agent_id=agent_id).first()
            if agent:
                agent.current_jobs += 1
            
            session.add(assignment)
            session.commit()
            
            return assignment.assignment_id
            
        except Exception:
            session.rollback()
            return None
        finally:
            session.close()