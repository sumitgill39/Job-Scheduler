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
    description = Column(Text)
    configuration = Column(Text)  # JSON string
    enabled = Column(Boolean, default=True)
    created_date = Column(DateTime, default=func.now())
    modified_date = Column(DateTime, default=func.now(), onupdate=func.now())
    created_by = Column(String(255), default='system')
    
    # Indexes
    __table_args__ = (
        Index('ix_job_configurations_enabled', 'enabled'),
        Index('ix_job_configurations_job_type', 'job_type'),
        Index('ix_job_configurations_created_date', 'created_date'),
    )
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'job_id': self.job_id,
            'name': self.name,
            'job_type': self.job_type,
            'description': self.description,
            'configuration': self.configuration,
            'enabled': self.enabled,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'modified_date': self.modified_date.isoformat() if self.modified_date else None,
            'created_by': self.created_by
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
    execution_metadata = Column(Text)  # JSON string for additional data
    
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


# Global database engine instance
database_engine = DatabaseEngine()


def get_db_session():
    """Get a database session - use this in your code"""
    return database_engine.get_session()


def init_database():
    """Initialize database tables"""
    database_engine.create_tables()
    return {'success': True, 'message': 'Database initialized successfully'}