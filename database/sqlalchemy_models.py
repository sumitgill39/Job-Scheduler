"""
SQLAlchemy models for Windows Job Scheduler
Clean database model definitions without connection pools
"""

from sqlalchemy import (
    Column, String, Text, Boolean, DateTime, Integer, 
    Float, create_engine, JSON, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

Base = declarative_base()


class JobConfiguration(Base):
    """Job configuration table"""
    __tablename__ = 'job_configurations'
    
    job_id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False)
    job_type = Column(String(50), nullable=False)  # 'sql', 'powershell'
    configuration = Column(Text)  # JSON string
    enabled = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())
    modified_date = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), default='system')
    
    # Enhanced scheduling fields
    schedule_enabled = Column(Boolean, default=False)
    schedule_type = Column(String(50))  # 'once', 'recurring', 'cron'
    schedule_expression = Column(String(255))  # cron expression or schedule details
    timezone = Column(String(50), default='UTC')  # timezone for execution
    next_run_time = Column(DateTime)  # calculated next execution time
    last_run_time = Column(DateTime)  # last execution time
    
    # Indexes
    __table_args__ = (
        Index('ix_job_configurations_enabled', 'enabled'),
        Index('ix_job_configurations_job_type', 'job_type'),
        Index('ix_job_configurations_created_date', 'created_date'),
        Index('ix_job_configurations_schedule_enabled', 'schedule_enabled'),
        Index('ix_job_configurations_next_run_time', 'next_run_time'),
        Index('ix_job_configurations_timezone', 'timezone'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'job_type': self.job_type,
            'configuration': self.configuration,
            'enabled': self.enabled,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'created_by': self.created_by,
            'schedule_enabled': self.schedule_enabled,
            'schedule_type': self.schedule_type,
            'schedule_expression': self.schedule_expression,
            'timezone': self.timezone,
            'next_run_time': self.next_run_time.isoformat() if self.next_run_time else None,
            'last_run_time': self.last_run_time.isoformat() if self.last_run_time else None
        }


class JobExecutionHistory(Base):
    """Job execution history table"""
    __tablename__ = 'job_execution_history'
    
    execution_id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(36), nullable=False)
    job_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # 'RUNNING', 'COMPLETED', 'FAILED', etc.
    start_time = Column(DateTime, default=func.now())
    end_time = Column(DateTime)
    duration_seconds = Column(Float)
    output = Column(Text)
    error_message = Column(Text)
    return_code = Column(Integer)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    execution_metadata = Column('metadata', Text)  # JSON string for additional data
    
    # Indexes
    __table_args__ = (
        Index('ix_job_execution_history_job_id', 'job_id'),
        Index('ix_job_execution_history_status', 'status'),
        Index('ix_job_execution_history_start_time', 'start_time'),
        Index('ix_job_execution_history_job_id_start_time', 'job_id', 'start_time'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'execution_id': self.execution_id,
            'job_id': self.job_id,
            'job_name': self.job_name,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'output': self.output,
            'error_message': self.error_message,
            'return_code': self.return_code,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'execution_metadata': self.execution_metadata
        }


class DatabaseEngine:
    """SQLAlchemy database engine and session management"""
    
    def __init__(self):
        self.engine = None
        self.Session = None
        self._setup_engine()
    
    def _setup_engine(self):
        """Setup SQLAlchemy engine from environment variables"""
        # Get database configuration from environment - defaults for local SQL Express
        db_driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        db_server = os.getenv('DB_SERVER', 'DESKTOP-4ADGDVE\\SQLEXPRESS')
        db_port = os.getenv('DB_PORT', '1433')
        db_database = os.getenv('DB_DATABASE', 'sreutil')
        db_username = os.getenv('DB_USERNAME', '')
        db_password = os.getenv('DB_PASSWORD', '')
        db_trusted_connection = os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true'
        db_encrypt = os.getenv('DB_ENCRYPT', 'false').lower() == 'true'
        db_trust_server_certificate = os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'true').lower() == 'true'
        
        # Build connection string for SQL Server Express (named pipes)
        if db_trusted_connection:
            # Windows Authentication with named pipes for SQL Server Express
            connection_string = (
                f"mssql+pyodbc://@{db_server}/{db_database}"
                f"?driver={db_driver.replace(' ', '+')}"
                f"&trusted_connection=yes"
            )
        else:
            # SQL Server Authentication
            connection_string = (
                f"mssql+pyodbc://{db_username}:{db_password}@{db_server}/{db_database}"
                f"?driver={db_driver.replace(' ', '+')}"
            )
        
        # Add encryption settings
        if db_encrypt:
            connection_string += "&encrypt=yes"
        if db_trust_server_certificate:
            connection_string += "&TrustServerCertificate=yes"
        
        # Create engine with optimized settings
        self.engine = create_engine(
            connection_string,
            # Connection pool settings - but using SQLAlchemy's efficient pooling
            pool_size=5,  # Small pool size
            max_overflow=10,  # Allow temporary expansion
            pool_timeout=30,  # Connection timeout
            pool_recycle=3600,  # Recycle connections every hour
            pool_pre_ping=True,  # Test connections before use
            # SQL Server specific settings
            echo=False,  # Set to True for SQL debugging
            future=True  # Use SQLAlchemy 2.0 style
        )
        
        # Create session factory
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        """Get a new database session"""
        return self.Session()
    
    def create_tables(self):
        """Create all tables"""
        Base.metadata.create_all(self.engine)
    
    def test_connection(self):
        """Test database connection"""
        try:
            with self.get_session() as session:
                # Simple test query
                from sqlalchemy import text
                session.execute(text('SELECT 1 as test_value'))
                return {
                    'success': True,
                    'message': 'Database connection successful'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }


class JobConfigurationV2(Base):
    """New V2 Job configuration table with YAML format"""
    __tablename__ = 'job_configurations_v2'
    
    # Primary key and basic info
    job_id = Column(String(36), primary_key=True)  # UUID
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(String(20), default='2.0')
    
    # Job configuration in YAML format
    yaml_configuration = Column(Text, nullable=False)  # YAML string
    
    # Metadata
    enabled = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())
    modified_date = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), default='system')
    
    # Execution tracking
    last_execution_id = Column(String(36))  # Last execution UUID
    last_execution_status = Column(String(50))  # success, failed, running
    last_execution_time = Column(DateTime)
    next_scheduled_time = Column(DateTime)
    
    # Performance metrics
    total_executions = Column(Integer, default=0)
    successful_executions = Column(Integer, default=0)
    failed_executions = Column(Integer, default=0)
    average_duration_seconds = Column(Float)
    
    # Indexes for performance
    __table_args__ = (
        Index('ix_job_configurations_v2_enabled', 'enabled'),
        Index('ix_job_configurations_v2_name', 'name'),
        Index('ix_job_configurations_v2_created_date', 'created_date'),
        Index('ix_job_configurations_v2_last_execution_status', 'last_execution_status'),
        Index('ix_job_configurations_v2_next_scheduled_time', 'next_scheduled_time'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'yaml_configuration': self.yaml_configuration,
            'enabled': self.enabled,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'created_by': self.created_by,
            'last_execution_id': self.last_execution_id,
            'last_execution_status': self.last_execution_status,
            'last_execution_time': self.last_execution_time.isoformat() if self.last_execution_time else None,
            'next_scheduled_time': self.next_scheduled_time.isoformat() if self.next_scheduled_time else None,
            'total_executions': self.total_executions,
            'successful_executions': self.successful_executions,
            'failed_executions': self.failed_executions,
            'average_duration_seconds': self.average_duration_seconds,
            'success_rate': (self.successful_executions / self.total_executions * 100) if self.total_executions > 0 else 0
        }


class JobExecutionHistoryV2(Base):
    """Enhanced execution history for V2 jobs"""
    __tablename__ = 'job_execution_history_v2'
    
    # Primary key
    execution_id = Column(String(36), primary_key=True)  # UUID
    job_id = Column(String(36), nullable=False)  # Foreign key to job_configurations_v2
    
    # Execution details
    job_name = Column(String(255))
    status = Column(String(50), nullable=False)  # pending, running, success, failed, timeout
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Float)
    
    # Results and logging
    output_log = Column(Text)  # Execution output/logs
    error_message = Column(Text)
    return_code = Column(Integer)
    
    # Step-by-step execution details (JSON format)
    step_results = Column(Text)  # JSON array of step results
    
    # Execution context
    execution_mode = Column(String(50))  # scheduled, manual, api
    executed_by = Column(String(255), default='system')
    execution_timezone = Column(String(50))
    server_info = Column(Text)  # JSON with server/system info
    
    # Performance metrics
    memory_usage_mb = Column(Float)
    cpu_time_seconds = Column(Float)
    
    # Retry information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=0)
    is_retry = Column(Boolean, default=False)
    parent_execution_id = Column(String(36))  # Original execution if this is a retry
    
    # Indexes
    __table_args__ = (
        Index('ix_job_execution_history_v2_job_id', 'job_id'),
        Index('ix_job_execution_history_v2_status', 'status'),
        Index('ix_job_execution_history_v2_start_time', 'start_time'),
        Index('ix_job_execution_history_v2_execution_mode', 'execution_mode'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'execution_id': self.execution_id,
            'job_id': self.job_id,
            'job_name': self.job_name,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration_seconds,
            'output_log': self.output_log,
            'error_message': self.error_message,
            'return_code': self.return_code,
            'step_results': self.step_results,
            'execution_mode': self.execution_mode,
            'executed_by': self.executed_by,
            'execution_timezone': self.execution_timezone,
            'server_info': self.server_info,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_time_seconds': self.cpu_time_seconds,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'is_retry': self.is_retry,
            'parent_execution_id': self.parent_execution_id
        }


# Global database engine instance
database_engine = DatabaseEngine()


def get_db_session():
    """Get a database session - use this in your code"""
    return database_engine.get_session()


def init_database():
    """Initialize database tables"""
    database_engine.create_tables()
    return {'success': True, 'message': 'Database initialized successfully'}