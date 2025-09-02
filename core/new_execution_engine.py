"""
Modern Job Execution Engine
Timezone-aware, multi-step, extensible job execution system
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Type
from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
import pytz
from concurrent.futures import ThreadPoolExecutor
import threading
import queue
import time

from utils.logger import get_logger


class StepStatus(Enum):
    """Step execution status"""
    PENDING = "pending"
    RUNNING = "running" 
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_SUCCESS = "partial_success"


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
    output: str = ""
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass 
class JobExecutionResult:
    """Result of complete job execution"""
    job_id: str
    job_name: str
    status: JobStatus
    timezone: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    steps: List[StepResult] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        if self.end_time and self.start_time:
            self.duration_seconds = (self.end_time - self.start_time).total_seconds()


class ExecutionStep(ABC):
    """Abstract base class for all job execution steps"""
    
    def __init__(self, step_id: str, step_name: str, config: Dict[str, Any]):
        self.step_id = step_id
        self.step_name = step_name
        self.config = config
        self.logger = get_logger(f"Step.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def step_type(self) -> str:
        """Return the step type identifier"""
        pass
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        """Execute the step and return result"""
        pass
    
    def validate_config(self) -> List[str]:
        """Validate step configuration, return list of errors"""
        return []


class SqlStep(ExecutionStep):
    """SQL execution step"""
    
    @property
    def step_type(self) -> str:
        return "sql"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = datetime.utcnow()
        self.logger.info(f"[SQL_STEP] Executing SQL step: {self.step_name}")
        
        try:
            # Get SQL configuration
            query = self.config.get('query', '')
            connection_name = self.config.get('connection_name', 'default')
            timeout = self.config.get('timeout', 300)
            
            if not query:
                raise ValueError("SQL query is required")
            
            # Execute SQL in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, self._execute_sql, query, connection_name, timeout)
            
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                output=str(result),
                metadata={
                    'query': query[:100] + '...' if len(query) > 100 else query,
                    'connection_name': connection_name,
                    'row_count': len(result) if isinstance(result, list) else 0
                }
            )
            
        except Exception as e:
            self.logger.error(f"[SQL_STEP] Error executing SQL step {self.step_name}: {e}")
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                error_message=str(e),
                metadata={'query': self.config.get('query', ''), 'connection_name': self.config.get('connection_name', '')}
            )
    
    def _execute_sql(self, query: str, connection_name: str, timeout: int):
        """Execute SQL query synchronously"""
        # TODO: Implement actual SQL execution using connection manager
        # For now, simulate execution
        self.logger.info(f"[SQL_STEP] Executing query on {connection_name}: {query[:50]}...")
        time.sleep(0.1)  # Simulate execution time
        return [{"result": "SQL executed successfully", "timestamp": datetime.utcnow().isoformat()}]


class PowerShellStep(ExecutionStep):
    """PowerShell execution step"""
    
    @property
    def step_type(self) -> str:
        return "powershell"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = datetime.utcnow()
        self.logger.info(f"[PS_STEP] Executing PowerShell step: {self.step_name}")
        
        try:
            # Get PowerShell configuration
            script = self.config.get('script', '')
            script_path = self.config.get('script_path', '')
            parameters = self.config.get('parameters', {})
            timeout = self.config.get('timeout', 300)
            
            if not script and not script_path:
                raise ValueError("PowerShell script or script_path is required")
            
            # Execute PowerShell in thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, self._execute_powershell, script, script_path, parameters, timeout)
            
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                output=result,
                metadata={
                    'script_length': len(script) if script else 0,
                    'script_path': script_path,
                    'parameters': parameters
                }
            )
            
        except Exception as e:
            self.logger.error(f"[PS_STEP] Error executing PowerShell step {self.step_name}: {e}")
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                error_message=str(e),
                metadata={'script': script[:100], 'script_path': script_path}
            )
    
    def _execute_powershell(self, script: str, script_path: str, parameters: Dict[str, Any], timeout: int) -> str:
        """Execute PowerShell script synchronously"""
        # TODO: Implement actual PowerShell execution
        # For now, simulate execution
        self.logger.info(f"[PS_STEP] Executing PowerShell script...")
        time.sleep(0.1)  # Simulate execution time
        return "PowerShell script executed successfully"


class AzureDevOpsStep(ExecutionStep):
    """Azure DevOps pipeline execution step"""
    
    @property
    def step_type(self) -> str:
        return "azure_devops"
    
    async def execute(self, context: Dict[str, Any]) -> StepResult:
        start_time = datetime.utcnow()
        self.logger.info(f"[AZDO_STEP] Executing Azure DevOps step: {self.step_name}")
        
        try:
            # Get Azure DevOps configuration
            organization = self.config.get('organization', '')
            project = self.config.get('project', '')
            pipeline_id = self.config.get('pipeline_id', '')
            branch = self.config.get('branch', 'main')
            parameters = self.config.get('parameters', {})
            
            if not all([organization, project, pipeline_id]):
                raise ValueError("Azure DevOps organization, project, and pipeline_id are required")
            
            # Execute Azure DevOps pipeline in thread pool
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, self._execute_azure_devops, organization, project, pipeline_id, branch, parameters)
            
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.SUCCESS,
                start_time=start_time,
                end_time=end_time,
                output=result,
                metadata={
                    'organization': organization,
                    'project': project,
                    'pipeline_id': pipeline_id,
                    'branch': branch,
                    'parameters': parameters
                }
            )
            
        except Exception as e:
            self.logger.error(f"[AZDO_STEP] Error executing Azure DevOps step {self.step_name}: {e}")
            end_time = datetime.utcnow()
            
            return StepResult(
                step_id=self.step_id,
                step_name=self.step_name,
                step_type=self.step_type,
                status=StepStatus.FAILED,
                start_time=start_time,
                end_time=end_time,
                error_message=str(e),
                metadata={
                    'organization': organization,
                    'project': project,
                    'pipeline_id': pipeline_id
                }
            )
    
    def _execute_azure_devops(self, organization: str, project: str, pipeline_id: str, branch: str, parameters: Dict[str, Any]) -> str:
        """Execute Azure DevOps pipeline synchronously"""
        # TODO: Implement actual Azure DevOps API calls
        # For now, simulate execution
        self.logger.info(f"[AZDO_STEP] Triggering pipeline {pipeline_id} in {organization}/{project}")
        time.sleep(0.2)  # Simulate API call time
        return f"Azure DevOps pipeline {pipeline_id} triggered successfully on {branch}"


class StepFactory:
    """Factory for creating execution steps"""
    
    _step_types: Dict[str, Type[ExecutionStep]] = {
        'sql': SqlStep,
        'powershell': PowerShellStep,
        'azure_devops': AzureDevOpsStep
    }
    
    @classmethod
    def register_step_type(cls, step_type: str, step_class: Type[ExecutionStep]):
        """Register a new step type"""
        cls._step_types[step_type] = step_class
    
    @classmethod
    def create_step(cls, step_type: str, step_id: str, step_name: str, config: Dict[str, Any]) -> ExecutionStep:
        """Create a step instance"""
        if step_type not in cls._step_types:
            raise ValueError(f"Unknown step type: {step_type}")
        
        step_class = cls._step_types[step_type]
        return step_class(step_id, step_name, config)
    
    @classmethod
    def get_available_step_types(cls) -> List[str]:
        """Get list of available step types"""
        return list(cls._step_types.keys())


@dataclass
class JobDefinition:
    """Definition of a job with multiple steps"""
    job_id: str
    job_name: str
    description: str
    timezone: str
    steps: List[Dict[str, Any]]
    schedule: Optional[Dict[str, Any]] = None
    enabled: bool = True
    max_retries: int = 0
    timeout_seconds: int = 3600
    metadata: Dict[str, Any] = field(default_factory=dict)


class TimezoneJobQueue:
    """Job queue for a specific timezone"""
    
    def __init__(self, timezone_name: str):
        self.timezone_name = timezone_name
        self.timezone = pytz.timezone(timezone_name)
        self.job_queue = queue.PriorityQueue()
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.logger = get_logger(f"TZQueue.{timezone_name}")
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    def add_job(self, job: JobDefinition, scheduled_time: datetime, priority: int = 0):
        """Add job to queue with priority"""
        # Convert scheduled time to this timezone
        if scheduled_time.tzinfo is None:
            scheduled_time = self.timezone.localize(scheduled_time)
        else:
            scheduled_time = scheduled_time.astimezone(self.timezone)
        
        # Priority queue: lower numbers = higher priority
        # Use negative timestamp so earlier times have higher priority
        priority_value = (-scheduled_time.timestamp(), priority, job.job_id)
        
        self.job_queue.put((priority_value, scheduled_time, job))
        self.logger.info(f"[TZ_QUEUE] Job {job.job_name} scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    
    async def start(self):
        """Start the queue worker"""
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        self.logger.info(f"[TZ_QUEUE] Started worker for timezone {self.timezone_name}")
    
    async def stop(self):
        """Stop the queue worker"""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        # Cancel active executions
        for execution_id, task in self.active_executions.items():
            task.cancel()
        
        self.logger.info(f"[TZ_QUEUE] Stopped worker for timezone {self.timezone_name}")
    
    async def _worker(self):
        """Worker that processes jobs in the queue"""
        while self._running:
            try:
                # Get next job (blocking with timeout)
                try:
                    priority_value, scheduled_time, job = self.job_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                # Check if it's time to execute
                current_time = datetime.now(self.timezone)
                if current_time < scheduled_time:
                    # Put job back and wait
                    self.job_queue.put((priority_value, scheduled_time, job))
                    await asyncio.sleep(1.0)
                    continue
                
                # Execute job
                execution_task = asyncio.create_task(self._execute_job(job))
                self.active_executions[job.job_id] = execution_task
                
                # Don't await here - let it run in background
                # Clean up completed tasks
                self._cleanup_completed_tasks()
                
            except Exception as e:
                self.logger.error(f"[TZ_QUEUE] Error in worker: {e}")
                await asyncio.sleep(1.0)
    
    def _cleanup_completed_tasks(self):
        """Clean up completed execution tasks"""
        completed = [job_id for job_id, task in self.active_executions.items() if task.done()]
        for job_id in completed:
            del self.active_executions[job_id]
    
    async def _execute_job(self, job: JobDefinition) -> JobExecutionResult:
        """Execute a job with all its steps"""
        execution_start = datetime.utcnow()
        self.logger.info(f"[TZ_QUEUE] Starting execution of job {job.job_name} ({job.job_id})")
        
        result = JobExecutionResult(
            job_id=job.job_id,
            job_name=job.job_name,
            status=JobStatus.RUNNING,
            timezone=self.timezone_name,
            start_time=execution_start
        )
        
        context = {'job': job, 'timezone': self.timezone_name}
        success_count = 0
        
        try:
            # Execute each step
            for step_config in job.steps:
                step_type = step_config.get('type', '')
                step_id = step_config.get('id', str(uuid.uuid4()))
                step_name = step_config.get('name', f'{step_type}_step')
                
                try:
                    # Create and execute step
                    step = StepFactory.create_step(step_type, step_id, step_name, step_config)
                    step_result = await step.execute(context)
                    result.steps.append(step_result)
                    
                    if step_result.status == StepStatus.SUCCESS:
                        success_count += 1
                    elif step_result.status == StepStatus.FAILED and not step_config.get('continue_on_failure', False):
                        # Stop execution if step failed and continue_on_failure is False
                        break
                        
                except Exception as e:
                    # Create failed step result
                    step_result = StepResult(
                        step_id=step_id,
                        step_name=step_name,
                        step_type=step_type,
                        status=StepStatus.FAILED,
                        start_time=datetime.utcnow(),
                        end_time=datetime.utcnow(),
                        error_message=str(e)
                    )
                    result.steps.append(step_result)
                    
                    if not step_config.get('continue_on_failure', False):
                        break
            
            # Determine final job status
            total_steps = len(job.steps)
            failed_steps = len([s for s in result.steps if s.status == StepStatus.FAILED])
            
            if failed_steps == 0:
                result.status = JobStatus.SUCCESS
            elif success_count > 0:
                result.status = JobStatus.PARTIAL_SUCCESS
            else:
                result.status = JobStatus.FAILED
                
        except Exception as e:
            self.logger.error(f"[TZ_QUEUE] Unexpected error executing job {job.job_name}: {e}")
            result.status = JobStatus.FAILED
            result.metadata['error'] = str(e)
        
        finally:
            result.end_time = datetime.utcnow()
            self.logger.info(f"[TZ_QUEUE] Job {job.job_name} completed with status {result.status.value} in {result.duration_seconds:.2f}s")
            
            # Clean up from active executions
            self.active_executions.pop(job.job_id, None)
        
        return result


class NewExecutionEngine:
    """Modern execution engine with timezone-based queues"""
    
    def __init__(self):
        self.timezone_queues: Dict[str, TimezoneJobQueue] = {}
        self.logger = get_logger("NewExecutionEngine")
        self._running = False
    
    async def start(self):
        """Start the execution engine"""
        self._running = True
        self.logger.info("[EXECUTION_ENGINE] Starting new execution engine")
        
        # Start all timezone queues
        for queue in self.timezone_queues.values():
            await queue.start()
    
    async def stop(self):
        """Stop the execution engine"""
        self._running = False
        self.logger.info("[EXECUTION_ENGINE] Stopping execution engine")
        
        # Stop all timezone queues
        for queue in self.timezone_queues.values():
            await queue.stop()
    
    def add_timezone_queue(self, timezone_name: str):
        """Add a timezone queue"""
        if timezone_name not in self.timezone_queues:
            self.timezone_queues[timezone_name] = TimezoneJobQueue(timezone_name)
            self.logger.info(f"[EXECUTION_ENGINE] Added timezone queue: {timezone_name}")
    
    async def schedule_job(self, job: JobDefinition, scheduled_time: datetime, priority: int = 0):
        """Schedule a job for execution"""
        # Ensure timezone queue exists
        if job.timezone not in self.timezone_queues:
            self.add_timezone_queue(job.timezone)
            if self._running:
                await self.timezone_queues[job.timezone].start()
        
        # Add job to appropriate timezone queue
        queue = self.timezone_queues[job.timezone]
        queue.add_job(job, scheduled_time, priority)
        
        self.logger.info(f"[EXECUTION_ENGINE] Scheduled job {job.job_name} in timezone {job.timezone}")
    
    async def execute_job_now(self, job: JobDefinition) -> JobExecutionResult:
        """Execute a job immediately"""
        # Create temporary queue for immediate execution
        temp_queue = TimezoneJobQueue(job.timezone or 'UTC')
        result = await temp_queue._execute_job(job)
        return result
    
    def get_queue_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all queues"""
        status = {}
        for tz_name, queue in self.timezone_queues.items():
            status[tz_name] = {
                'timezone': tz_name,
                'queue_size': queue.job_queue.qsize(),
                'active_executions': len(queue.active_executions),
                'running': queue._running
            }
        return status


# Example usage and testing
if __name__ == "__main__":
    async def test_execution_engine():
        """Test the new execution engine"""
        engine = NewExecutionEngine()
        
        # Create a test job with multiple steps
        test_job = JobDefinition(
            job_id="test-job-001",
            job_name="Multi-Step Test Job", 
            description="Test job with SQL, PowerShell, and Azure DevOps steps",
            timezone="UTC",
            steps=[
                {
                    'id': 'step1',
                    'name': 'Database Query',
                    'type': 'sql',
                    'query': 'SELECT COUNT(*) FROM users',
                    'connection_name': 'main_db'
                },
                {
                    'id': 'step2', 
                    'name': 'System Check',
                    'type': 'powershell',
                    'script': 'Get-Process | Select-Object -First 5',
                    'continue_on_failure': True
                },
                {
                    'id': 'step3',
                    'name': 'Deploy Pipeline',
                    'type': 'azure_devops',
                    'organization': 'myorg',
                    'project': 'myproject', 
                    'pipeline_id': '123',
                    'branch': 'main'
                }
            ]
        )
        
        # Test immediate execution
        print("Testing immediate execution...")
        result = await engine.execute_job_now(test_job)
        
        print(f"Job Status: {result.status.value}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Steps executed: {len(result.steps)}")
        
        for step in result.steps:
            print(f"  - {step.step_name}: {step.status.value} ({step.duration_seconds:.2f}s)")
    
    # Run the test
    asyncio.run(test_execution_engine())