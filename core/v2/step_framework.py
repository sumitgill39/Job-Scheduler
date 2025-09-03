"""
Step Framework for Job Scheduler V2
Abstract base class and factory for execution steps
"""

import asyncio
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable
from datetime import datetime, timezone
import json
import traceback

from .data_models import StepConfiguration, StepResult, StepStatus, ExecutionContext
from .job_logger import JobLogger
from .timezone_logger import TimezoneLogger
from utils.logger import get_logger


class StepValidationError(Exception):
    """Exception raised when step configuration is invalid"""
    pass


class StepExecutionError(Exception):
    """Exception raised during step execution"""
    pass


class StepTimeoutError(Exception):
    """Exception raised when step execution times out"""
    pass


class ExecutionStep(ABC):
    """Abstract base class for all execution steps"""
    
    def __init__(self, config: StepConfiguration):
        self.config = config
        self.logger = get_logger(f"Step.{self.step_type}.{config.step_id}")
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._current_attempt = 0
        
        # Validate configuration
        validation_errors = self.validate_config()
        if validation_errors:
            raise StepValidationError(f"Step validation failed: {', '.join(validation_errors)}")
    
    @property
    @abstractmethod
    def step_type(self) -> str:
        """Return the step type identifier"""
        pass
    
    @abstractmethod
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """
        Implement the actual step execution logic
        
        Args:
            context: Execution context with shared variables
            job_logger: Logger for detailed job execution logs
            tz_logger: Logger for timezone-specific logs
            
        Returns:
            StepResult: Result of step execution
        """
        pass
    
    def validate_config(self) -> List[str]:
        """
        Validate step configuration
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Basic validation from StepConfiguration is already done
        # Subclasses should override this to add step-specific validation
        
        return errors
    
    async def execute(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """
        Execute the step with retry logic and error handling
        
        Args:
            context: Execution context
            job_logger: Job-specific logger
            tz_logger: Timezone-specific logger
            
        Returns:
            StepResult: Execution result
        """
        self._start_time = datetime.now(timezone.utc)
        
        # Create initial step result
        step_result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.RUNNING,
            start_time=self._start_time
        )
        
        # Log step start
        job_logger.log_step_start(self.config, 1)  # Step number will be set by execution engine
        tz_logger.log_step_started(
            context.job_id, 
            context.execution_id,
            self.config.step_id,
            self.config.step_name,
            self.step_type
        )
        
        max_attempts = self.config.retry_count + 1
        last_error = None
        
        for attempt in range(max_attempts):
            self._current_attempt = attempt + 1
            
            try:
                if attempt > 0:
                    # Log retry attempt
                    job_logger.log_retry_attempt(
                        self.config.step_id, 
                        attempt + 1, 
                        max_attempts,
                        self.config.retry_delay
                    )
                    
                    tz_logger.log_warning(
                        context.job_id,
                        context.execution_id,
                        f"Retrying step {self.config.step_id}, attempt {attempt + 1}/{max_attempts}",
                        self.config.step_id
                    )
                    
                    # Wait before retry
                    await asyncio.sleep(self.config.retry_delay)
                
                # Execute with timeout if specified
                if self.config.timeout:
                    step_result = await asyncio.wait_for(
                        self.execute_impl(context, job_logger, tz_logger),
                        timeout=self.config.timeout
                    )
                else:
                    step_result = await self.execute_impl(context, job_logger, tz_logger)
                
                # If we reach here, execution was successful
                step_result.retry_count = attempt
                self._end_time = datetime.now(timezone.utc)
                
                # Log success
                duration = (self._end_time - self._start_time).total_seconds()
                job_logger.log_step_completion(step_result, 1)
                tz_logger.log_step_completed(
                    context.job_id,
                    context.execution_id,
                    self.config.step_id,
                    self.config.step_name,
                    step_result.status.value,
                    duration,
                    step_result.output
                )
                
                return step_result
                
            except asyncio.TimeoutError:
                last_error = StepTimeoutError(f"Step {self.config.step_id} timed out after {self.config.timeout} seconds")
                error_msg = str(last_error)
                
                job_logger.log_step_error(self.config.step_id, error_msg)
                tz_logger.log_error(context.job_id, context.execution_id, error_msg, self.config.step_id)
                
                if attempt == max_attempts - 1:  # Last attempt
                    break
                
            except Exception as e:
                last_error = e
                error_msg = str(e)
                traceback_info = traceback.format_exc()
                
                job_logger.log_step_error(self.config.step_id, error_msg, traceback_info)
                tz_logger.log_error(context.job_id, context.execution_id, error_msg, self.config.step_id)
                
                if attempt == max_attempts - 1:  # Last attempt
                    break
                
                # Check if this is a non-retryable error
                if self._is_non_retryable_error(e):
                    self.logger.warning(f"Non-retryable error encountered: {error_msg}")
                    break
        
        # All attempts failed
        self._end_time = datetime.now(timezone.utc)
        step_result.mark_completed(
            StepStatus.FAILED,
            error_message=str(last_error)
        )
        step_result.retry_count = max_attempts - 1
        
        return step_result
    
    def _is_non_retryable_error(self, error: Exception) -> bool:
        """
        Determine if an error should not be retried
        
        Args:
            error: The exception that occurred
            
        Returns:
            True if the error should not be retried
        """
        # Override in subclasses to define step-specific non-retryable errors
        non_retryable_types = (
            StepValidationError,
            ValueError,
            TypeError
        )
        
        return isinstance(error, non_retryable_types)
    
    def get_current_attempt(self) -> int:
        """Get the current retry attempt number"""
        return self._current_attempt
    
    def get_execution_duration(self) -> Optional[float]:
        """Get the current execution duration in seconds"""
        if self._start_time:
            end_time = self._end_time or datetime.now(timezone.utc)
            return (end_time - self._start_time).total_seconds()
        return None
    
    def log_progress(self, message: str, job_logger: JobLogger):
        """Log progress message for the step"""
        job_logger.log_step_progress(self.config.step_id, message)
        self.logger.info(f"[{self.config.step_id}] Progress: {message}")
    
    def log_output(self, output: str, job_logger: JobLogger):
        """Log output from the step"""
        job_logger.log_step_output(self.config.step_id, output)
    
    def add_context_variable(self, key: str, value: Any, context: ExecutionContext):
        """Add a variable to the execution context for use by subsequent steps"""
        context.set_variable(f"{self.config.step_id}_{key}", value)
        context.add_metadata(f"step_{self.config.step_id}_variables", {key: value})
    
    def get_context_variable(self, key: str, context: ExecutionContext, default: Any = None) -> Any:
        """Get a variable from the execution context"""
        return context.get_variable(key, default)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step_id='{self.config.step_id}', type='{self.step_type}')"


class StepFactory:
    """Factory for creating and managing execution steps"""
    
    _step_types: Dict[str, Type[ExecutionStep]] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register_step_type(cls, step_type: str, step_class: Type[ExecutionStep]):
        """
        Register a new step type
        
        Args:
            step_type: String identifier for the step type
            step_class: Class that implements ExecutionStep
        """
        with cls._lock:
            if not issubclass(step_class, ExecutionStep):
                raise ValueError(f"Step class {step_class} must inherit from ExecutionStep")
            
            cls._step_types[step_type] = step_class
            
        logger = get_logger("StepFactory")
        logger.info(f"Registered step type '{step_type}' -> {step_class.__name__}")
    
    @classmethod
    def unregister_step_type(cls, step_type: str):
        """Unregister a step type"""
        with cls._lock:
            if step_type in cls._step_types:
                del cls._step_types[step_type]
    
    @classmethod
    def get_step_types(cls) -> List[str]:
        """Get list of registered step types"""
        with cls._lock:
            return list(cls._step_types.keys())
    
    @classmethod
    def create_step(cls, config: StepConfiguration) -> ExecutionStep:
        """
        Create a step instance from configuration
        
        Args:
            config: Step configuration
            
        Returns:
            ExecutionStep instance
            
        Raises:
            ValueError: If step type is not registered
            StepValidationError: If configuration is invalid
        """
        with cls._lock:
            step_class = cls._step_types.get(config.step_type)
        
        if not step_class:
            available_types = ", ".join(cls.get_step_types())
            raise ValueError(
                f"Unknown step type '{config.step_type}'. "
                f"Available types: {available_types}"
            )
        
        try:
            step_instance = step_class(config)
            logger = get_logger("StepFactory")
            logger.info(f"Created step instance: {step_instance}")
            return step_instance
        except Exception as e:
            logger = get_logger("StepFactory")
            logger.error(f"Failed to create step instance for type '{config.step_type}': {str(e)}")
            raise
    
    @classmethod
    def validate_step_config(cls, config: StepConfiguration) -> List[str]:
        """
        Validate step configuration without creating instance
        
        Args:
            config: Step configuration to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check if step type is registered
        if config.step_type not in cls._step_types:
            available_types = ", ".join(cls.get_step_types())
            errors.append(f"Unknown step type '{config.step_type}'. Available: {available_types}")
            return errors
        
        # Try to create a temporary instance for validation
        try:
            step_class = cls._step_types[config.step_type]
            temp_step = step_class(config)
            validation_errors = temp_step.validate_config()
            errors.extend(validation_errors)
        except Exception as e:
            errors.append(f"Configuration validation failed: {str(e)}")
        
        return errors
    
    @classmethod
    def get_step_info(cls, step_type: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a step type
        
        Args:
            step_type: Step type identifier
            
        Returns:
            Dictionary with step type information, or None if not found
        """
        step_class = cls._step_types.get(step_type)
        if not step_class:
            return None
        
        return {
            "type": step_type,
            "class": step_class.__name__,
            "module": step_class.__module__,
            "doc": step_class.__doc__ or "No documentation available"
        }
    
    @classmethod
    def get_all_step_info(cls) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered step types"""
        return {
            step_type: cls.get_step_info(step_type)
            for step_type in cls.get_step_types()
        }


# Decorator for easy step registration
def register_step(step_type: str):
    """
    Decorator to register a step class
    
    Usage:
    @register_step("my_step_type")
    class MyStep(ExecutionStep):
        ...
    """
    def decorator(step_class: Type[ExecutionStep]):
        StepFactory.register_step_type(step_type, step_class)
        return step_class
    return decorator


# Helper functions
def create_step_from_dict(step_data: Dict[str, Any]) -> ExecutionStep:
    """Create a step from dictionary data"""
    config = StepConfiguration(
        step_id=step_data["step_id"],
        step_name=step_data["step_name"],
        step_type=step_data["step_type"],
        config=step_data["config"],
        timeout=step_data.get("timeout"),
        continue_on_failure=step_data.get("continue_on_failure", False),
        retry_count=step_data.get("retry_count", 0),
        retry_delay=step_data.get("retry_delay", 5)
    )
    
    return StepFactory.create_step(config)


def validate_job_steps(steps: List[Dict[str, Any]]) -> List[str]:
    """Validate a list of step definitions"""
    errors = []
    
    for i, step_data in enumerate(steps):
        try:
            config = StepConfiguration(
                step_id=step_data["step_id"],
                step_name=step_data["step_name"],
                step_type=step_data["step_type"],
                config=step_data["config"],
                timeout=step_data.get("timeout"),
                continue_on_failure=step_data.get("continue_on_failure", False),
                retry_count=step_data.get("retry_count", 0),
                retry_delay=step_data.get("retry_delay", 5)
            )
            
            # Validate basic configuration
            config_errors = config.validate()
            if config_errors:
                errors.extend([f"Step {i+1}: {error}" for error in config_errors])
            
            # Validate step-specific configuration
            step_errors = StepFactory.validate_step_config(config)
            if step_errors:
                errors.extend([f"Step {i+1}: {error}" for error in step_errors])
                
        except Exception as e:
            errors.append(f"Step {i+1}: Failed to parse step configuration: {str(e)}")
    
    return errors


class MockStep(ExecutionStep):
    """Mock step for testing purposes"""
    
    @property
    def step_type(self) -> str:
        return "mock"
    
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """Mock execution that always succeeds"""
        await asyncio.sleep(0.1)  # Simulate some work
        
        result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.SUCCESS,
            start_time=datetime.now(timezone.utc),
            output="Mock step executed successfully"
        )
        result.mark_completed(StepStatus.SUCCESS)
        
        return result


# Register the mock step for testing
StepFactory.register_step_type("mock", MockStep)