# Job Scheduler V2 - Function Specifications and Interfaces

## Overview

This document defines the detailed function specifications, interfaces, and method signatures for all components in the Job Scheduler V2 system. It serves as the definitive reference for implementation.

## Core Data Structures

### JobDefinition Class

```python
@dataclass
class JobDefinition:
    """Complete job definition with metadata and steps"""
    job_id: str
    job_name: str
    description: str = ""
    timezone: str = "UTC"
    steps: List[Dict[str, Any]] = field(default_factory=list)
    enabled: bool = True
    max_retries: int = 0
    timeout_seconds: int = 3600
    schedule_config: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def validate(self) -> bool:
        """Validate job definition completeness and correctness"""
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobDefinition':
        """Create from dictionary (API requests, database)"""
```

### JobExecutionResult Class

```python
@dataclass
class JobExecutionResult:
    """Result of job execution with step details"""
    execution_id: str
    job_id: str
    job_name: str
    status: JobStatus
    timezone: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    steps: List['StepExecutionResult'] = field(default_factory=list)
    error_message: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if execution was successful"""
        
    def add_step_result(self, step_result: 'StepExecutionResult') -> None:
        """Add step execution result"""
        
    def get_failed_steps(self) -> List['StepExecutionResult']:
        """Get list of failed step results"""
```

### StepExecutionResult Class

```python
@dataclass
class StepExecutionResult:
    """Result of individual step execution"""
    step_id: str
    step_name: str
    step_type: str
    status: StepStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    output: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success(self) -> bool:
        """Check if step execution was successful"""
```

## Enums and Constants

### JobStatus Enum

```python
class JobStatus(Enum):
    """Job execution status states"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    RETRYING = "retrying"
```

### StepStatus Enum

```python
class StepStatus(Enum):
    """Step execution status states"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
```

## NewExecutionEngine Class

### Constructor and Lifecycle

```python
class NewExecutionEngine:
    """Modern async job execution engine with timezone support"""
    
    def __init__(self, max_workers: int = 10, default_timeout: int = 3600):
        """
        Initialize execution engine
        
        Args:
            max_workers: Maximum concurrent job executions
            default_timeout: Default job timeout in seconds
        """
        
    async def start(self) -> None:
        """Start the execution engine and all timezone queues"""
        
    async def stop(self, wait_for_jobs: bool = True) -> None:
        """
        Stop the execution engine
        
        Args:
            wait_for_jobs: Wait for running jobs to complete
        """
        
    async def health_check(self) -> Dict[str, Any]:
        """Get engine health status"""
```

### Job Execution Methods

```python
async def execute_job_now(self, job: JobDefinition) -> JobExecutionResult:
    """
    Execute job immediately, bypassing queue
    
    Args:
        job: Job definition to execute
        
    Returns:
        Complete execution result
        
    Raises:
        ExecutionEngineError: If execution fails
    """
    
async def schedule_job(self, job: JobDefinition, scheduled_time: datetime) -> str:
    """
    Schedule job for future execution
    
    Args:
        job: Job definition to schedule  
        scheduled_time: When to execute (timezone-aware)
        
    Returns:
        Execution ID for tracking
        
    Raises:
        SchedulingError: If scheduling fails
    """
    
async def cancel_job(self, execution_id: str) -> bool:
    """
    Cancel a scheduled or running job
    
    Args:
        execution_id: ID of execution to cancel
        
    Returns:
        True if cancelled, False if not found/already completed
    """
```

### Status and Monitoring Methods

```python
def get_queue_status(self) -> Dict[str, Dict[str, Any]]:
    """
    Get status of all timezone queues
    
    Returns:
        Dictionary mapping timezone -> queue status
    """
    
def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
    """
    Get status of specific execution
    
    Args:
        execution_id: Execution to check
        
    Returns:
        Status dictionary or None if not found
    """
    
def get_active_executions(self) -> List[Dict[str, Any]]:
    """Get list of currently running executions"""
```

## TimezoneJobQueue Class

### Constructor and Management

```python
class TimezoneJobQueue:
    """Timezone-specific job execution queue"""
    
    def __init__(self, timezone: str, max_concurrent: int = 5):
        """
        Initialize timezone queue
        
        Args:
            timezone: IANA timezone identifier
            max_concurrent: Maximum concurrent executions
        """
        
    async def start(self) -> None:
        """Start queue processing"""
        
    async def stop(self, wait_for_jobs: bool = True) -> None:
        """
        Stop queue processing
        
        Args:
            wait_for_jobs: Wait for running jobs to complete
        """
```

### Job Management Methods

```python
async def add_immediate_job(self, job: JobDefinition) -> str:
    """
    Add job for immediate execution
    
    Args:
        job: Job to execute
        
    Returns:
        Execution ID
    """
    
async def schedule_job(self, job: JobDefinition, scheduled_time: datetime) -> str:
    """
    Schedule job for future execution
    
    Args:
        job: Job to schedule
        scheduled_time: Execution time (must be in queue's timezone)
        
    Returns:
        Execution ID
    """
    
async def cancel_job(self, execution_id: str) -> bool:
    """
    Cancel job in queue
    
    Args:
        execution_id: ID of job to cancel
        
    Returns:
        True if cancelled successfully
    """
```

### Status Methods

```python
def get_status(self) -> Dict[str, Any]:
    """
    Get queue status
    
    Returns:
        Dictionary with queue metrics and state
    """
    
def get_queue_depth(self) -> int:
    """Get number of jobs waiting in queue"""
    
def get_active_count(self) -> int:
    """Get number of currently executing jobs"""
```

## ExecutionStep Abstract Base Class

### Base Interface

```python
class ExecutionStep(ABC):
    """Abstract base class for all execution steps"""
    
    def __init__(self, step_config: Dict[str, Any], context: ExecutionContext):
        """
        Initialize step
        
        Args:
            step_config: Step configuration from job definition
            context: Execution context with shared data
        """
        
    @abstractmethod
    async def execute(self) -> StepExecutionResult:
        """
        Execute the step
        
        Returns:
            Step execution result
            
        Raises:
            StepExecutionError: If step execution fails
        """
        
    @abstractmethod
    def validate_config(self) -> List[str]:
        """
        Validate step configuration
        
        Returns:
            List of validation errors (empty if valid)
        """
        
    def get_step_type(self) -> str:
        """Get step type identifier"""
        
    def get_timeout(self) -> int:
        """Get step timeout in seconds"""
        
    def supports_cancel(self) -> bool:
        """Check if step supports cancellation"""
        
    async def cancel(self) -> bool:
        """
        Cancel step execution
        
        Returns:
            True if cancelled successfully
        """
```

## SqlStep Class

### Constructor and Configuration

```python
class SqlStep(ExecutionStep):
    """SQL query execution step"""
    
    def __init__(self, step_config: Dict[str, Any], context: ExecutionContext):
        """
        Initialize SQL step
        
        Required config:
            - query: SQL query to execute
            - connection_name: Database connection identifier
        Optional config:
            - timeout: Query timeout in seconds (default: 300)
            - parameters: Query parameters dictionary
            - fetch_results: Whether to fetch and return results (default: True)
        """
```

### Execution Methods

```python
async def execute(self) -> StepExecutionResult:
    """
    Execute SQL query
    
    Returns:
        Step result with query output and metadata
    """
    
def validate_config(self) -> List[str]:
    """Validate SQL step configuration"""
    
async def _execute_query(self, query: str, parameters: Dict[str, Any]) -> Tuple[Any, int]:
    """
    Execute SQL query with parameters
    
    Returns:
        Tuple of (results, affected_rows)
    """
```

## PowerShellStep Class

### Constructor and Configuration

```python
class PowerShellStep(ExecutionStep):
    """PowerShell script execution step"""
    
    def __init__(self, step_config: Dict[str, Any], context: ExecutionContext):
        """
        Initialize PowerShell step
        
        Required config (one of):
            - script: Inline PowerShell script
            - script_path: Path to PowerShell script file
        Optional config:
            - parameters: Script parameters dictionary
            - timeout: Script timeout in seconds (default: 300)
            - execution_policy: PowerShell execution policy
            - working_directory: Script working directory
        """
```

### Execution Methods

```python
async def execute(self) -> StepExecutionResult:
    """
    Execute PowerShell script
    
    Returns:
        Step result with script output and metadata
    """
    
def validate_config(self) -> List[str]:
    """Validate PowerShell step configuration"""
    
async def _run_powershell(self, script: str, parameters: Dict[str, Any]) -> Tuple[str, str, int]:
    """
    Run PowerShell script with parameters
    
    Returns:
        Tuple of (stdout, stderr, exit_code)
    """
```

## StepFactory Class

### Factory Methods

```python
class StepFactory:
    """Factory for creating execution steps"""
    
    _step_types: Dict[str, Type[ExecutionStep]] = {
        'sql': SqlStep,
        'powershell': PowerShellStep,
        # Future step types registered here
    }
    
    @classmethod
    def create_step(cls, step_config: Dict[str, Any], context: ExecutionContext) -> ExecutionStep:
        """
        Create step instance from configuration
        
        Args:
            step_config: Step configuration dictionary
            context: Execution context
            
        Returns:
            Configured step instance
            
        Raises:
            ValueError: If step type is not supported
            ConfigurationError: If step configuration is invalid
        """
        
    @classmethod
    def register_step_type(cls, step_type: str, step_class: Type[ExecutionStep]) -> None:
        """
        Register new step type
        
        Args:
            step_type: Step type identifier
            step_class: Step implementation class
        """
        
    @classmethod  
    def get_available_step_types(cls) -> List[str]:
        """Get list of available step types"""
        
    @classmethod
    def get_step_schema(cls, step_type: str) -> Dict[str, Any]:
        """
        Get JSON schema for step type configuration
        
        Args:
            step_type: Step type to get schema for
            
        Returns:
            JSON schema dictionary
        """
```

## ExecutionContext Class

### Context Management

```python
class ExecutionContext:
    """Shared execution context for job steps"""
    
    def __init__(self, job: JobDefinition, execution_id: str):
        """
        Initialize execution context
        
        Args:
            job: Job definition being executed
            execution_id: Unique execution identifier
        """
        
    def get_job_metadata(self) -> Dict[str, Any]:
        """Get job metadata"""
        
    def set_step_output(self, step_id: str, output: Any) -> None:
        """Store step output for use by subsequent steps"""
        
    def get_step_output(self, step_id: str) -> Any:
        """Get output from previous step"""
        
    def get_connection(self, connection_name: str) -> Any:
        """Get database connection by name"""
        
    def add_execution_metadata(self, key: str, value: Any) -> None:
        """Add metadata to execution result"""
        
    def is_cancelled(self) -> bool:
        """Check if execution has been cancelled"""
```

## ModernJobAPI Class

### API Interface Methods

```python
class ModernJobAPI:
    """Modern job API with timezone-based execution"""
    
    def __init__(self):
        """Initialize modern job API"""
        
    async def start(self) -> None:
        """Start the execution engine"""
        
    async def stop(self) -> None:
        """Stop the execution engine"""
```

### Job Management Methods

```python
def execute_job_immediately(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a job immediately and return the result
    
    Args:
        job_data: Job definition dictionary
        
    Returns:
        Execution result dictionary with success/error information
    """
    
def schedule_job(self, job_data: Dict[str, Any], scheduled_time: datetime) -> Dict[str, Any]:
    """
    Schedule a job for future execution
    
    Args:
        job_data: Job definition dictionary
        scheduled_time: When to execute the job
        
    Returns:
        Scheduling result dictionary
    """
    
def get_execution_status(self) -> Dict[str, Any]:
    """Get status of all timezone queues"""
    
def get_available_step_types(self) -> Dict[str, Any]:
    """Get list of available step types"""
```

### Internal Helper Methods

```python
def _parse_job_data(self, job_data: Dict[str, Any]) -> JobDefinition:
    """Parse job data from API request into JobDefinition"""
    
def _format_execution_response(self, result: JobExecutionResult) -> Dict[str, Any]:
    """Format JobExecutionResult into API response"""
    
def _ensure_loop(self) -> None:
    """Ensure we have an event loop for async operations"""
    
def _run_async(self, coro) -> Any:
    """Run async function in sync context"""
```

## Error Classes

### Exception Hierarchy

```python
class ExecutionEngineError(Exception):
    """Base exception for execution engine errors"""
    pass

class SchedulingError(ExecutionEngineError):
    """Error during job scheduling"""
    pass

class StepExecutionError(ExecutionEngineError):
    """Error during step execution"""
    
    def __init__(self, step_id: str, step_type: str, message: str):
        self.step_id = step_id
        self.step_type = step_type
        super().__init__(message)

class ConfigurationError(ExecutionEngineError):
    """Error in job or step configuration"""
    pass

class TimeoutError(ExecutionEngineError):
    """Execution timeout error"""
    pass

class CancellationError(ExecutionEngineError):
    """Job or step cancellation error"""
    pass
```

## Flask Route Functions

### V2 API Route Specifications

```python
def create_modern_job_routes(app) -> ModernJobAPI:
    """
    Create modern job execution routes
    
    Args:
        app: Flask application instance
        
    Returns:
        ModernJobAPI instance for direct access
    """

@app.route('/api/v2/jobs/execute', methods=['POST'])
def api_v2_execute_job():
    """
    Execute a job immediately using the new engine
    
    Request Body:
        Job definition JSON with steps array
        
    Response:
        Execution result with step details
        
    Status Codes:
        200: Success
        400: Invalid request or execution failure
        500: Server error
    """

@app.route('/api/v2/jobs/schedule', methods=['POST']) 
def api_v2_schedule_job():
    """
    Schedule a job for future execution
    
    Request Body:
        {
            "job": {...},           // Job definition
            "scheduled_time": "..."  // ISO 8601 timestamp
        }
        
    Response:
        Scheduling confirmation with job ID
        
    Status Codes:
        200: Success
        400: Invalid request or scheduling failure
        500: Server error
    """

@app.route('/api/v2/execution/status', methods=['GET'])
def api_v2_execution_status():
    """
    Get execution engine status
    
    Response:
        Engine status with timezone queue information
        
    Status Codes:
        200: Success
        500: Server error
    """

@app.route('/api/v2/steps/types', methods=['GET'])
def api_v2_step_types():
    """
    Get available step types
    
    Response:
        List of step types with configuration schemas
        
    Status Codes:
        200: Success
        500: Server error
    """
```

## Database Model Specifications

### V2 SQLAlchemy Models

```python
class JobExecutionV2(Base):
    """Job execution record for V2 system"""
    __tablename__ = 'job_executions_v2'
    
    execution_id: str = Column(String(100), primary_key=True)
    job_id: str = Column(String(100), nullable=False, index=True)
    job_name: str = Column(String(255), nullable=False)
    status: str = Column(String(50), nullable=False, index=True)
    timezone: str = Column(String(50), nullable=False)
    start_time: datetime = Column(DateTime, nullable=True)
    end_time: datetime = Column(DateTime, nullable=True)
    duration_seconds: float = Column(Float, default=0.0)
    error_message: str = Column(Text, nullable=True)
    retry_count: int = Column(Integer, default=0)
    metadata_json: str = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
class StepExecutionV2(Base):
    """Step execution record for V2 system"""
    __tablename__ = 'step_executions_v2'
    
    step_execution_id: str = Column(String(100), primary_key=True)
    execution_id: str = Column(String(100), ForeignKey('job_executions_v2.execution_id'))
    step_id: str = Column(String(100), nullable=False)
    step_name: str = Column(String(255), nullable=False)
    step_type: str = Column(String(50), nullable=False, index=True)
    status: str = Column(String(50), nullable=False, index=True)
    start_time: datetime = Column(DateTime, nullable=True)
    end_time: datetime = Column(DateTime, nullable=True)
    duration_seconds: float = Column(Float, default=0.0)
    output_text: str = Column(Text, nullable=True)
    error_message: str = Column(Text, nullable=True)
    metadata_json: str = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
```

## Configuration Specifications

### Environment Configuration

```python
# Environment variables for V2 system
V2_MAX_WORKERS = int(os.getenv('V2_MAX_WORKERS', '10'))
V2_DEFAULT_TIMEOUT = int(os.getenv('V2_DEFAULT_TIMEOUT', '3600'))
V2_QUEUE_MAX_CONCURRENT = int(os.getenv('V2_QUEUE_MAX_CONCURRENT', '5'))
V2_ENABLE_STEP_CACHING = os.getenv('V2_ENABLE_STEP_CACHING', 'true').lower() == 'true'
V2_LOG_LEVEL = os.getenv('V2_LOG_LEVEL', 'INFO')
```

### Step Type Schemas

```python
SQL_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {"type": "string"},
        "connection_name": {"type": "string"},
        "timeout": {"type": "integer", "default": 300},
        "parameters": {"type": "object", "default": {}},
        "fetch_results": {"type": "boolean", "default": True}
    },
    "required": ["query", "connection_name"]
}

POWERSHELL_STEP_SCHEMA = {
    "type": "object", 
    "properties": {
        "script": {"type": "string"},
        "script_path": {"type": "string"},
        "parameters": {"type": "object", "default": {}},
        "timeout": {"type": "integer", "default": 300},
        "execution_policy": {"type": "string", "default": "RemoteSigned"},
        "working_directory": {"type": "string"}
    },
    "anyOf": [
        {"required": ["script"]},
        {"required": ["script_path"]}
    ]
}
```

This specification document provides the complete interface definitions needed to implement the Job Scheduler V2 system. Each method signature includes detailed parameters, return types, and error conditions to ensure consistent implementation across all components.