"""
PowerShell Job implementation for Windows Job Scheduler
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from .job_base import JobBase, JobResult, JobStatus
from utils.windows_utils import WindowsUtils


class PowerShellJob(JobBase):
    """PowerShell job implementation for Windows"""
    
    def __init__(self, script_path: str = None, script_content: str = None,
                 parameters: List[str] = None, execution_policy: str = "RemoteSigned",
                 working_directory: str = None, **kwargs):
        """
        Initialize PowerShell job
        
        Args:
            script_path: Path to PowerShell script file (.ps1)
            script_content: Inline PowerShell script content
            parameters: List of parameters to pass to script
            execution_policy: PowerShell execution policy
            working_directory: Working directory for script execution
            **kwargs: Base job parameters
        """
        super().__init__(**kwargs)
        self.job_type = "powershell"
        self.script_path = script_path
        self.script_content = script_content
        self.parameters = parameters or []
        self.execution_policy = execution_policy
        self.working_directory = working_directory
        
        # PowerShell-specific settings
        self.powershell_path = kwargs.get('powershell_path')
        self.capture_output = kwargs.get('capture_output', True)
        self.shell_timeout = kwargs.get('shell_timeout', self.timeout)
        
        # Initialize Windows utilities
        self.windows_utils = WindowsUtils()
        
        # Validate initialization
        self._validate_initialization()
        
        script_info = self.script_path or "inline script"
        self.job_logger.info(f"Initialized PowerShell job with script: {script_info}")
    
    def _validate_initialization(self):
        """Validate job initialization"""
        if not self.script_path and not self.script_content:
            raise ValueError("Either script_path or script_content must be provided")
        
        if self.script_path and self.script_content:
            self.job_logger.warning("Both script_path and script_content provided. script_path will be used.")
        
        if self.script_path and not os.path.exists(self.script_path):
            raise FileNotFoundError(f"PowerShell script file not found: {self.script_path}")
    
    def execute(self) -> JobResult:
        """Execute PowerShell script"""
        start_time = datetime.now()
        
        try:
            self.job_logger.info("Starting PowerShell script execution")
            
            # Determine script to execute
            if self.script_path:
                result = self._execute_script_file()
            else:
                result = self._execute_script_content()
            
            # Update result timing
            result.start_time = start_time
            result.end_time = datetime.now()
            
            # Log execution result
            if result.status == JobStatus.SUCCESS:
                self.job_logger.info(f"PowerShell script completed successfully in {result.duration_seconds:.2f} seconds")
            else:
                self.job_logger.error(f"PowerShell script failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error in PowerShell job: {str(e)}"
            self.job_logger.exception(error_msg)
            
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=error_msg,
                metadata={
                    'script_path': self.script_path,
                    'has_script_content': bool(self.script_content),
                    'parameters': self.parameters
                }
            )
    
    def _execute_script_file(self) -> JobResult:
        """Execute PowerShell script from file"""
        try:
            # Normalize script path for Windows
            script_path = self.windows_utils.normalize_windows_path(self.script_path)
            
            # Change working directory if specified
            original_cwd = None
            if self.working_directory:
                original_cwd = os.getcwd()
                os.chdir(self.working_directory)
                self.job_logger.debug(f"Changed working directory to: {self.working_directory}")
            
            try:
                # Execute script
                execution_result = self.windows_utils.execute_powershell_script(
                    script_path=script_path,
                    parameters=self.parameters,
                    execution_policy=self.execution_policy,
                    timeout=self.shell_timeout,
                    run_as_user=self.run_as
                )
                
                return self._create_job_result_from_execution(execution_result, script_path)
                
            finally:
                # Restore working directory
                if original_cwd:
                    os.chdir(original_cwd)
                    self.job_logger.debug(f"Restored working directory to: {original_cwd}")
        
        except Exception as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"Failed to execute PowerShell script file: {str(e)}",
                metadata={
                    'script_path': self.script_path,
                    'parameters': self.parameters,
                    'execution_policy': self.execution_policy
                }
            )
    
    def _execute_script_content(self) -> JobResult:
        """Execute inline PowerShell script content"""
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(self.script_content)
                temp_script_path = temp_file.name
            
            self.job_logger.debug(f"Created temporary script file: {temp_script_path}")
            
            try:
                # Execute temporary script
                execution_result = self.windows_utils.execute_powershell_script(
                    script_path=temp_script_path,
                    parameters=self.parameters,
                    execution_policy=self.execution_policy,
                    timeout=self.shell_timeout,
                    run_as_user=self.run_as
                )
                
                return self._create_job_result_from_execution(execution_result, "inline_script")
                
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_script_path)
                    self.job_logger.debug(f"Cleaned up temporary script file: {temp_script_path}")
                except Exception as e:
                    self.job_logger.warning(f"Could not clean up temporary file {temp_script_path}: {e}")
        
        except Exception as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"Failed to execute inline PowerShell script: {str(e)}",
                metadata={
                    'script_content_length': len(self.script_content) if self.script_content else 0,
                    'parameters': self.parameters,
                    'execution_policy': self.execution_policy
                }
            )
    
    def _create_job_result_from_execution(self, execution_result: Dict[str, Any], script_identifier: str) -> JobResult:
        """Create JobResult from PowerShell execution result"""
        status = JobStatus.SUCCESS if execution_result['success'] else JobStatus.FAILED
        
        # Prepare output
        output_parts = []
        if execution_result.get('stdout'):
            output_parts.append(f"STDOUT:\n{execution_result['stdout']}")
        if execution_result.get('stderr') and not execution_result['success']:
            output_parts.append(f"STDERR:\n{execution_result['stderr']}")
        
        output = "\n\n".join(output_parts) if output_parts else "No output"
        
        return JobResult(
            job_id=self.job_id,
            job_name=self.name,
            status=status,
            start_time=datetime.now(),  # Will be updated by caller
            end_time=datetime.now(),    # Will be updated by caller
            output=output,
            error_message=execution_result.get('stderr', '') if not execution_result['success'] else '',
            return_code=execution_result.get('return_code'),
            metadata={
                'script_identifier': script_identifier,
                'command': execution_result.get('command', ''),
                'parameters': self.parameters,
                'execution_policy': self.execution_policy,
                'working_directory': self.working_directory,
                'powershell_path': self.windows_utils.get_powershell_path(),
                'stdout_length': len(execution_result.get('stdout', '')),
                'stderr_length': len(execution_result.get('stderr', ''))
            }
        )
    
    def test_script(self) -> Dict[str, Any]:
        """Test PowerShell script syntax"""
        try:
            if self.script_path:
                # Test script file
                test_command = f"Get-Command -Syntax (Get-Content '{self.script_path}' -Raw)"
            else:
                # Test inline script
                # Create temporary file for testing
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(self.script_content)
                    temp_script_path = temp_file.name
                
                test_command = f"Get-Command -Syntax (Get-Content '{temp_script_path}' -Raw)"
            
            # Execute syntax test
            result = self.windows_utils.execute_powershell_command(
                command=test_command,
                execution_policy=self.execution_policy,
                timeout=30
            )
            
            # Clean up temp file if created
            if not self.script_path and 'temp_script_path' in locals():
                try:
                    os.unlink(temp_script_path)
                except:
                    pass
            
            return {
                'success': result['success'],
                'message': 'Script syntax is valid' if result['success'] else 'Script syntax error',
                'details': result.get('stdout') or result.get('stderr', ''),
                'return_code': result.get('return_code')
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Script test failed: {str(e)}',
                'details': str(e)
            }
    
    def get_script_info(self) -> Dict[str, Any]:
        """Get information about the PowerShell script"""
        info = {
            'job_type': self.job_type,
            'execution_policy': self.execution_policy,
            'parameters': self.parameters,
            'working_directory': self.working_directory,
            'powershell_path': self.windows_utils.get_powershell_path()
        }
        
        if self.script_path:
            try:
                script_path = Path(self.script_path)
                info.update({
                    'script_type': 'file',
                    'script_path': str(script_path.resolve()),
                    'script_exists': script_path.exists(),
                    'script_size_bytes': script_path.stat().st_size if script_path.exists() else 0,
                    'script_modified': script_path.stat().st_mtime if script_path.exists() else None
                })
            except Exception as e:
                info.update({
                    'script_type': 'file',
                    'script_path': self.script_path,
                    'script_error': str(e)
                })
        else:
            info.update({
                'script_type': 'inline',
                'script_content_length': len(self.script_content) if self.script_content else 0,
                'script_lines': len(self.script_content.split('\n')) if self.script_content else 0
            })
        
        return info
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert PowerShell job to dictionary"""
        base_dict = super().to_dict()
        base_dict.update({
            'script_path': self.script_path,
            'script_content': self.script_content,
            'parameters': self.parameters,
            'execution_policy': self.execution_policy,
            'working_directory': self.working_directory,
            'powershell_path': self.powershell_path,
            'capture_output': self.capture_output,
            'shell_timeout': self.shell_timeout
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PowerShellJob':
        """Create PowerShell job from dictionary"""
        # Extract PowerShell-specific parameters
        ps_params = {
            'script_path': data.get('script_path'),
            'script_content': data.get('script_content'),
            'parameters': data.get('parameters', []),
            'execution_policy': data.get('execution_policy', 'RemoteSigned'),
            'working_directory': data.get('working_directory'),
            'powershell_path': data.get('powershell_path'),
            'capture_output': data.get('capture_output', True),
            'shell_timeout': data.get('shell_timeout')
        }
        
        # Extract base job parameters
        base_params = {
            'job_id': data.get('job_id'),
            'name': data.get('name', ''),
            'description': data.get('description', ''),
            'timeout': data.get('timeout', 300),
            'max_retries': data.get('max_retries', 3),
            'retry_delay': data.get('retry_delay', 60),
            'run_as': data.get('run_as'),
            'enabled': data.get('enabled', True),
            'metadata': data.get('metadata', {})
        }
        
        # Combine parameters
        all_params = {**base_params, **ps_params}
        
        return cls(**all_params)
    
    def clone(self, new_name: str = None) -> 'PowerShellJob':
        """Create a copy of this PowerShell job"""
        job_dict = self.to_dict()
        job_dict['job_id'] = None  # Will generate new ID
        if new_name:
            job_dict['name'] = new_name
        return self.from_dict(job_dict)


if __name__ == "__main__":
    # Test PowerShell job with inline script
    inline_script = """
    Write-Host "Hello from PowerShell!"
    Write-Host "Current date: $(Get-Date)"
    Write-Host "Computer name: $env:COMPUTERNAME"
    Write-Host "Username: $env:USERNAME"
    
    # Test parameters
    param(
        [string]$Message = "Default message"
    )
    Write-Host "Parameter message: $Message"
    """
    
    job = PowerShellJob(
        name="Test PowerShell Job",
        description="A test PowerShell job with inline script",
        script_content=inline_script,
        parameters=["-Message", "Hello from Python!"],
        execution_policy="RemoteSigned",
        timeout=60
    )
    
    print(f"Created PowerShell job: {job}")
    print(f"Job info: {job.get_script_info()}")
    
    # Test script syntax
    syntax_test = job.test_script()
    print(f"Syntax test: {syntax_test}")
    
    # Execute job
    result = job.run()
    print(f"Execution result: {result.status.value}")
    print(f"Return code: {result.return_code}")
    print(f"Output:\n{result.output}")
    
    if result.metadata:
        print(f"Metadata: {result.metadata}")
    
    # Test with script file
    print("\n" + "="*50)
    print("Testing with script file...")
    
    # Create a test script file
    test_script_path = "test_script.ps1"
    with open(test_script_path, 'w', encoding='utf-8') as f:
        f.write("""
        # Test PowerShell Script
        Write-Host "This is a test script file"
        Write-Host "PowerShell version: $($PSVersionTable.PSVersion)"
        Get-Date
        """)
    
    try:
        file_job = PowerShellJob(
            name="Test PowerShell File Job",
            script_path=test_script_path,
            timeout=30
        )
        
        file_result = file_job.run()
        print(f"File job result: {file_result.status.value}")
        print(f"File job output:\n{file_result.output}")
        
    finally:
        # Clean up test file
        try:
            os.unlink(test_script_path)
        except:
            pass