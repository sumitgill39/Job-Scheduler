"""
Core Data Models for Job Scheduler V2
Defines job definitions, execution results, and status enums
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
import json


class StepStatus(Enum):
    """Step execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"
    TIMEOUT = "timeout"


@dataclass
class ExecutionContext:
    """Execution context shared between steps"""
    job_id: str
    execution_id: str
    timezone: str
    start_time: datetime
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def set_variable(self, key: str, value: Any):
        """Set a context variable available to subsequent steps"""
        self.variables[key] = value
    
    def get_variable(self, key: str, default: Any = None) -> Any:
        """Get a context variable"""
        return self.variables.get(key, default)
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to execution context"""
        self.metadata[key] = value


@dataclass
class StepConfiguration:
    """Configuration for a single job step"""
    step_id: str
    step_name: str
    step_type: str
    config: Dict[str, Any]
    timeout: Optional[int] = None
    continue_on_failure: bool = False
    retry_count: int = 0
    retry_delay: int = 5
    
    def validate(self) -> List[str]:
        """Validate step configuration"""
        errors = []
        
        if not self.step_id or not isinstance(self.step_id, str):
            errors.append("step_id is required and must be a string")
        
        if not self.step_name or not isinstance(self.step_name, str):
            errors.append("step_name is required and must be a string")
        
        if not self.step_type or not isinstance(self.step_type, str):
            errors.append("step_type is required and must be a string")
        
        if not isinstance(self.config, dict):
            errors.append("config must be a dictionary")
        
        if self.timeout is not None and (not isinstance(self.timeout, int) or self.timeout <= 0):
            errors.append("timeout must be a positive integer")
        
        if not isinstance(self.continue_on_failure, bool):
            errors.append("continue_on_failure must be a boolean")
        
        if not isinstance(self.retry_count, int) or self.retry_count < 0:
            errors.append("retry_count must be a non-negative integer")
        
        if not isinstance(self.retry_delay, int) or self.retry_delay <= 0:
            errors.append("retry_delay must be a positive integer")
        
        return errors


@dataclass
class JobDefinition:
    """Complete job definition with steps and metadata"""
    job_id: str
    job_name: str
    description: str
    timezone: str
    steps: List[StepConfiguration]
    enabled: bool = True
    max_retries: int = 0
    timeout_seconds: int = 3600
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    schedule: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None
    
    def __post_init__(self):
        """Validate job definition after initialization"""
        if not self.job_id:
            self.job_id = str(uuid.uuid4())
    
    def validate(self) -> List[str]:
        """Validate complete job definition"""
        errors = []
        
        if not self.job_name or not isinstance(self.job_name, str):
            errors.append("job_name is required and must be a string")
        
        if not self.description or not isinstance(self.description, str):
            errors.append("description is required and must be a string")
        
        if not self.timezone or not isinstance(self.timezone, str):
            errors.append("timezone is required and must be a string")
        
        if not self.steps or not isinstance(self.steps, list):
            errors.append("steps is required and must be a list")
        elif len(self.steps) == 0:
            errors.append("at least one step is required")
        
        # Validate each step
        step_ids = set()
        for i, step in enumerate(self.steps):
            if not isinstance(step, StepConfiguration):
                errors.append(f"Step {i} must be a StepConfiguration instance")
                continue
            
            step_errors = step.validate()
            errors.extend([f"Step {i} ({step.step_id}): {error}" for error in step_errors])
            
            # Check for duplicate step IDs
            if step.step_id in step_ids:
                errors.append(f"Duplicate step_id: {step.step_id}")
            step_ids.add(step.step_id)
        
        # Validate other fields
        if not isinstance(self.enabled, bool):
            errors.append("enabled must be a boolean")
        
        if not isinstance(self.max_retries, int) or self.max_retries < 0:
            errors.append("max_retries must be a non-negative integer")
        
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds <= 0:
            errors.append("timeout_seconds must be a positive integer")
        
        if not isinstance(self.priority, int):
            errors.append("priority must be an integer")
        
        if not isinstance(self.tags, list):
            errors.append("tags must be a list")
        
        if not isinstance(self.metadata, dict):
            errors.append("metadata must be a dictionary")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "job_id": self.job_id,
            "job_name": self.job_name,
            "description": self.description,
            "timezone": self.timezone,
            "steps": [
                {
                    "step_id": step.step_id,
                    "step_name": step.step_name,
                    "step_type": step.step_type,
                    "config": step.config,
                    "timeout": step.timeout,
                    "continue_on_failure": step.continue_on_failure,
                    "retry_count": step.retry_count,
                    "retry_delay": step.retry_delay
                }
                for step in self.steps
            ],
            "enabled": self.enabled,
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "priority": self.priority,
            "tags": self.tags,
            "metadata": self.metadata,
            "schedule": self.schedule,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobDefinition":
        """Create from dictionary"""
        steps = [
            StepConfiguration(
                step_id=step_data["step_id"],
                step_name=step_data["step_name"],
                step_type=step_data["step_type"],
                config=step_data["config"],
                timeout=step_data.get("timeout"),
                continue_on_failure=step_data.get("continue_on_failure", False),
                retry_count=step_data.get("retry_count", 0),
                retry_delay=step_data.get("retry_delay", 5)
            )
            for step_data in data["steps"]
        ]
        
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        elif not isinstance(created_at, datetime):
            created_at = datetime.now(timezone.utc)
        
        return cls(
            job_id=data["job_id"],
            job_name=data["job_name"],
            description=data["description"],
            timezone=data["timezone"],
            steps=steps,
            enabled=data.get("enabled", True),
            max_retries=data.get("max_retries", 0),
            timeout_seconds=data.get("timeout_seconds", 3600),
            priority=data.get("priority", 0),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            schedule=data.get("schedule"),
            created_at=created_at,
            created_by=data.get("created_by")
        )


@dataclass
class StepResult:
    """Result of a single step execution"""
    step_id: str
    step_name: str
    step_type: str
    status: StepStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    output: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate duration if end_time is set"""
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def mark_completed(self, status: StepStatus, output: Optional[str] = None, error_message: Optional[str] = None):
        """Mark step as completed with final status"""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.output = output
        self.error_message = error_message
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to step result"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "step_id": self.step_id,
            "step_name": self.step_name,
            "step_type": self.step_type,
            "status": self.status.value,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }


@dataclass
class JobExecutionResult:
    """Result of complete job execution"""
    execution_id: str
    job_id: str
    job_name: str
    status: JobStatus
    timezone: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    step_results: List[StepResult] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Generate execution_id if not provided"""
        if not self.execution_id:
            timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
            self.execution_id = f"exec_{timestamp}_{str(uuid.uuid4())[:8]}"
        
        # Calculate duration if end_time is set
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def add_step_result(self, step_result: StepResult):
        """Add a step result"""
        self.step_results.append(step_result)
    
    def mark_completed(self, status: JobStatus, error_message: Optional[str] = None):
        """Mark job as completed"""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
        self.error_message = error_message
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()
    
    def get_step_count(self) -> int:
        """Get total number of steps"""
        return len(self.step_results)
    
    def get_successful_steps(self) -> int:
        """Get number of successful steps"""
        return len([step for step in self.step_results if step.status == StepStatus.SUCCESS])
    
    def get_failed_steps(self) -> int:
        """Get number of failed steps"""
        return len([step for step in self.step_results if step.status == StepStatus.FAILED])
    
    def add_metadata(self, key: str, value: Any):
        """Add metadata to job result"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "success": self.status == JobStatus.SUCCESS,
            "message": f"Job {self.job_name} completed with status: {self.status.value}",
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "status": self.status.value,
            "timezone": self.timezone,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "steps": [step.to_dict() for step in self.step_results],
            "step_count": self.get_step_count(),
            "successful_steps": self.get_successful_steps(),
            "failed_steps": self.get_failed_steps(),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2, default=str)


# Helper functions
def create_job_from_legacy(legacy_job: Dict[str, Any]) -> JobDefinition:
    """Convert legacy job format to V2 JobDefinition"""
    import json
    
    job_type = legacy_job.get('job_type', legacy_job.get('type', 'unknown'))
    
    # Parse configuration JSON if present
    config_data = {}
    configuration = legacy_job.get('configuration')
    if configuration:
        try:
            if isinstance(configuration, str):
                config_data = json.loads(configuration)
            elif isinstance(configuration, dict):
                config_data = configuration
        except json.JSONDecodeError:
            config_data = {}
    
    # Build step configuration
    step_config_dict = {
        "timeout": legacy_job.get('timeout', config_data.get('timeout', 300))
    }
    
    # Add type-specific configuration
    if job_type == "sql":
        # Handle both legacy field names for SQL query
        query = (
            legacy_job.get('sql_query') or 
            legacy_job.get('query') or 
            config_data.get('sql_query') or 
            config_data.get('query', '')
        )
        step_config_dict["query"] = query
        
        # Add connection name
        connection_name = (
            legacy_job.get('connection_name') or 
            config_data.get('connection_name', 'default')
        )
        step_config_dict["connection_name"] = connection_name
    elif job_type == "powershell":
        # Handle both legacy field names for script content
        script_content = (
            legacy_job.get('script') or 
            legacy_job.get('script_content') or 
            config_data.get('script') or 
            config_data.get('script_content', '')
        )
        if script_content:
            step_config_dict["script"] = script_content
        
        script_path = config_data.get('script_path')
        if script_path:
            step_config_dict["script_path"] = script_path
            
        step_config_dict["execution_policy"] = config_data.get('execution_policy', 'RemoteSigned')
        
        # Handle working directory and parameters
        working_directory = config_data.get('working_directory')
        if working_directory:
            step_config_dict["working_directory"] = working_directory
            
        parameters = config_data.get('parameters')
        if parameters:
            # Convert parameters list to dictionary format expected by V2 engine
            if isinstance(parameters, list):
                # Convert list of parameters to dict with keys as parameter names
                param_dict = {}
                for i, param in enumerate(parameters):
                    if isinstance(param, str) and param.startswith('-'):
                        # Handle named parameters like "-Verbose", "-Force"
                        param_name = param.lstrip('-')
                        param_dict[param_name] = True
                    else:
                        # Handle unnamed parameters
                        param_dict[f"param_{i}"] = param
                step_config_dict["parameters"] = param_dict
            elif isinstance(parameters, dict):
                step_config_dict["parameters"] = parameters
            else:
                step_config_dict["parameters"] = {"raw_parameters": str(parameters)}
    
    # Create single step from legacy job
    step_config = StepConfiguration(
        step_id="main_step",
        step_name=f"{legacy_job.get('name', 'Legacy Job')} Step",
        step_type=job_type,
        config=step_config_dict,
        timeout=legacy_job.get('timeout', config_data.get('timeout', 300))
    )
    
    return JobDefinition(
        job_id=legacy_job.get('job_id', str(uuid.uuid4())),
        job_name=legacy_job.get('name', 'Legacy Job'),
        description=legacy_job.get('description', f'Migrated {job_type} job'),
        timezone=legacy_job.get('timezone') or 'UTC',
        steps=[step_config],
        enabled=legacy_job.get('enabled', True),
        metadata={"migrated_from": "legacy", "original_type": job_type}
    )


def create_simple_sql_job(name: str, query: str, connection_name: str = "default", timezone: str = "UTC") -> JobDefinition:
    """Create a simple SQL job"""
    step = StepConfiguration(
        step_id="sql_step",
        step_name=f"{name} - SQL Execution",
        step_type="sql",
        config={
            "query": query,
            "connection_name": connection_name,
            "timeout": 300
        }
    )
    
    return JobDefinition(
        job_id=str(uuid.uuid4()),
        job_name=name,
        description=f"SQL job: {name}",
        timezone=timezone,
        steps=[step]
    )


def create_simple_powershell_job(name: str, script: str, timezone: str = "UTC") -> JobDefinition:
    """Create a simple PowerShell job"""
    step = StepConfiguration(
        step_id="powershell_step",
        step_name=f"{name} - PowerShell Execution",
        step_type="powershell",
        config={
            "script": script,
            "timeout": 300
        }
    )
    
    return JobDefinition(
        job_id=str(uuid.uuid4()),
        job_name=name,
        description=f"PowerShell job: {name}",
        timezone=timezone,
        steps=[step]
    )