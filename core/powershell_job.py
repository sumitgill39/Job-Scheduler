"""
PowerShell Job implementation for Windows Job Scheduler
"""

import os
import sys
import tempfile
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from .job_base import JobBase, JobResult, JobStatus

# Import WindowsUtils with error handling
try:
    from utils.windows_utils import WindowsUtils
    HAS_WINDOWS_UTILS = True
except ImportError:
    HAS_WINDOWS_UTILS = False
    WindowsUtils = None


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
        
        # Initialize Windows utilities with error handling
        if HAS_WINDOWS_UTILS:
            self.windows_utils = WindowsUtils()
        else:
            self.windows_utils = None
        
        # Detect PowerShell availability
        self.powershell_available = self._detect_powershell()
        
        # Validate initialization
        self._validate_initialization()
        
        script_info = self.script_path or "inline script"
        self.job_logger.info(f"Initialized PowerShell job with script: {script_info}")
    
    def _detect_powershell(self) -> bool:
        """Detect if PowerShell is available on the system"""
        try:
            # Try different PowerShell commands based on platform
            commands_to_try = []
            
            if platform.system().lower() == 'windows':
                commands_to_try = ['powershell', 'pwsh']
            else:
                # On non-Windows, try PowerShell Core
                commands_to_try = ['pwsh', 'powershell']
            
            for cmd in commands_to_try:
                try:
                    result = subprocess.run(
                        [cmd, '-Command', 'Write-Host "PowerShell Available"'],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0:
                        self.powershell_path = cmd
                        self.job_logger.info(f"PowerShell detected: {cmd}")
                        return True
                except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.SubprocessError):
                    continue
            
            self.job_logger.warning("PowerShell not detected on this system")
            return False
            
        except Exception as e:
            self.job_logger.warning(f"Error detecting PowerShell: {e}")
            return False
    
    def _validate_initialization(self):
        """Validate job initialization"""
        if not self.script_path and not self.script_content:
            raise ValueError("Either script_path or script_content must be provided")
        
        if self.script_path and self.script_content:
            self.job_logger.warning("Both script_path and script_content provided. script_path will be used.")
        
        if self.script_path and not os.path.exists(self.script_path):
            raise FileNotFoundError(f"PowerShell script file not found: {self.script_path}")
    
    def execute(self, execution_logger=None) -> JobResult:
        """Execute PowerShell script - following SQL job pattern"""
        start_time = datetime.now()
        
        if execution_logger:
            execution_logger.info("Starting PowerShell script execution", "POWERSHELL_JOB", {
                'script_type': 'file' if self.script_path else 'inline',
                'script_path': self.script_path if self.script_path else None,
                'script_length': len(self.script_content) if self.script_content else 0,
                'execution_policy': self.execution_policy,
                'parameters_count': len(self.parameters),
                'powershell_available': self.powershell_available,
                'platform': platform.system()
            })
        
        # Check PowerShell availability (like SQL job checks pyodbc)
        if not self.powershell_available:
            if execution_logger:
                execution_logger.error("PowerShell not available on this system", "POWERSHELL_JOB")
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message="PowerShell not available on this system"
            )
        
        try:
            if execution_logger:
                execution_logger.info(f"Executing PowerShell script using: {self.powershell_path or 'powershell'}", "POWERSHELL_JOB")
            self.job_logger.info("Starting PowerShell script execution")
            
            # Execute using direct subprocess approach (like SQL job uses pyodbc directly)
            if self.script_path:
                result = self._execute_script_file_direct(execution_logger)
            else:
                result = self._execute_script_content_direct(execution_logger)
            
            # Update result timing
            result.start_time = start_time
            result.end_time = datetime.now()
            
            # Log execution result
            if result.status == JobStatus.SUCCESS:
                if execution_logger:
                    execution_logger.info(f"PowerShell script completed successfully in {result.duration_seconds:.2f} seconds", "POWERSHELL_JOB")
                self.job_logger.info(f"PowerShell script completed successfully in {result.duration_seconds:.2f} seconds")
            else:
                if execution_logger:
                    execution_logger.error(f"PowerShell script failed: {result.error_message}", "POWERSHELL_JOB")
                self.job_logger.error(f"PowerShell script failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error in PowerShell job: {str(e)}"
            self.job_logger.exception(error_msg)
            
            if execution_logger:
                execution_logger.error(error_msg, "POWERSHELL_JOB")
            
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
    
    def _execute_script_file_direct(self, execution_logger=None) -> JobResult:
        """Execute PowerShell script from file using direct subprocess approach"""
        try:
            # Build PowerShell command (like SQL job builds connection string)
            command = self._build_powershell_command(self.script_path, execution_logger)
            
            # Change working directory if specified
            original_cwd = None
            if self.working_directory:
                original_cwd = os.getcwd()
                os.chdir(self.working_directory)
                if execution_logger:
                    execution_logger.debug(f"Changed working directory to: {self.working_directory}", "POWERSHELL_JOB")
                self.job_logger.debug(f"Changed working directory to: {self.working_directory}")
            
            try:
                # Execute command (like SQL job executes query)
                if execution_logger:
                    execution_logger.debug(f"Executing command: {' '.join(command[:3])}...", "POWERSHELL_JOB")
                
                start_exec = datetime.now()
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.shell_timeout,
                    cwd=self.working_directory
                )
                exec_time = (datetime.now() - start_exec).total_seconds()
                
                if execution_logger:
                    execution_logger.info(f"PowerShell execution completed in {exec_time:.2f} seconds", "POWERSHELL_JOB")
                
                return self._create_job_result_from_subprocess(result, self.script_path, exec_time)
                
            finally:
                # Restore working directory
                if original_cwd:
                    os.chdir(original_cwd)
                    if execution_logger:
                        execution_logger.debug(f"Restored working directory to: {original_cwd}", "POWERSHELL_JOB")
                    self.job_logger.debug(f"Restored working directory to: {original_cwd}")
        
        except subprocess.TimeoutExpired as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"PowerShell script timed out after {self.shell_timeout} seconds",
                metadata={
                    'script_path': self.script_path,
                    'parameters': self.parameters,
                    'timeout': self.shell_timeout
                }
            )
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
    
    def _execute_script_content_direct(self, execution_logger=None) -> JobResult:
        """Execute inline PowerShell script content using direct approach"""
        temp_script_path = None
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_file:
                temp_file.write(self.script_content)
                temp_script_path = temp_file.name
            
            if execution_logger:
                execution_logger.debug(f"Created temporary script file: {temp_script_path}", "POWERSHELL_JOB")
            self.job_logger.debug(f"Created temporary script file: {temp_script_path}")
            
            try:
                # Execute temporary script using direct approach
                command = self._build_powershell_command(temp_script_path, execution_logger)
                
                if execution_logger:
                    execution_logger.debug(f"Executing inline script via temp file", "POWERSHELL_JOB")
                
                start_exec = datetime.now()
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=self.shell_timeout,
                    cwd=self.working_directory
                )
                exec_time = (datetime.now() - start_exec).total_seconds()
                
                if execution_logger:
                    execution_logger.info(f"Inline script execution completed in {exec_time:.2f} seconds", "POWERSHELL_JOB")
                
                return self._create_job_result_from_subprocess(result, "inline_script", exec_time)
                
            finally:
                # Clean up temporary file
                if temp_script_path:
                    try:
                        os.unlink(temp_script_path)
                        if execution_logger:
                            execution_logger.debug(f"Cleaned up temporary script file: {temp_script_path}", "POWERSHELL_JOB")
                        self.job_logger.debug(f"Cleaned up temporary script file: {temp_script_path}")
                    except Exception as e:
                        if execution_logger:
                            execution_logger.warning(f"Could not clean up temporary file: {e}", "POWERSHELL_JOB")
                        self.job_logger.warning(f"Could not clean up temporary file {temp_script_path}: {e}")
        
        except subprocess.TimeoutExpired as e:
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=datetime.now(),
                end_time=datetime.now(),
                error_message=f"Inline PowerShell script timed out after {self.shell_timeout} seconds",
                metadata={
                    'script_content_length': len(self.script_content) if self.script_content else 0,
                    'parameters': self.parameters,
                    'timeout': self.shell_timeout
                }
            )
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
    
    def _build_powershell_command(self, script_path: str, execution_logger=None) -> List[str]:
        """Build PowerShell command (like SQL job builds connection string)"""
        # Use detected PowerShell path or fallback
        ps_command = self.powershell_path if self.powershell_path else 'powershell'
        command = [ps_command]
        
        # Add execution policy
        if self.execution_policy:
            command.extend(['-ExecutionPolicy', self.execution_policy])
        
        # Add file parameter
        command.extend(['-File', script_path])
        
        # Add script parameters
        if self.parameters:
            command.extend(self.parameters)
        
        if execution_logger:
            command_preview = ' '.join(command[:5]) + ('...' if len(command) > 5 else '')
            execution_logger.debug(f"Built PowerShell command: {command_preview}", "POWERSHELL_JOB")
        
        self.job_logger.debug(f"PowerShell command: {command}")
        return command
    
    def _create_job_result_from_subprocess(self, subprocess_result, script_identifier: str, exec_time: float) -> JobResult:
        """Create JobResult from subprocess result (like SQL job creates result from query)"""
        status = JobStatus.SUCCESS if subprocess_result.returncode == 0 else JobStatus.FAILED
        
        # Prepare output (like SQL job formats query results)
        output_parts = []
        if subprocess_result.stdout:
            output_parts.append(f"STDOUT:\n{subprocess_result.stdout.strip()}")
        if subprocess_result.stderr and subprocess_result.returncode != 0:
            output_parts.append(f"STDERR:\n{subprocess_result.stderr.strip()}")
        
        output = "\n\n".join(output_parts) if output_parts else "No output"
        
        # Create metadata (like SQL job creates metadata)
        metadata = {
            'script_identifier': script_identifier,
            'return_code': subprocess_result.returncode,
            'execution_time_seconds': exec_time,
            'parameters': self.parameters,
            'execution_policy': self.execution_policy,
            'working_directory': self.working_directory,
            'powershell_path': self.powershell_path or 'powershell',
            'stdout_length': len(subprocess_result.stdout) if subprocess_result.stdout else 0,
            'stderr_length': len(subprocess_result.stderr) if subprocess_result.stderr else 0,
            'platform': platform.system()
        }
        
        return JobResult(
            job_id=self.job_id,
            job_name=self.name,
            status=status,
            start_time=datetime.now(),  # Will be updated by caller
            end_time=datetime.now(),    # Will be updated by caller
            output=output,
            error_message=subprocess_result.stderr.strip() if subprocess_result.stderr and subprocess_result.returncode != 0 else '',
            return_code=subprocess_result.returncode,
            metadata=metadata
        )
    
    def test_powershell_availability(self) -> Dict[str, Any]:
        """Test PowerShell availability (like SQL job test_connection)"""
        try:
            if not self.powershell_available:
                return {
                    'success': False,
                    'message': 'PowerShell not available on this system',
                    'details': f'Platform: {platform.system()}, Tried commands: powershell, pwsh'
                }
            
            # Test basic PowerShell command
            command = [self.powershell_path or 'powershell', '-Command', 'Write-Host "PowerShell test successful"']
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'message': 'PowerShell is available and working',
                    'details': result.stdout.strip(),
                    'powershell_path': self.powershell_path or 'powershell',
                    'platform': platform.system()
                }
            else:
                return {
                    'success': False,
                    'message': 'PowerShell test failed',
                    'details': result.stderr.strip() or result.stdout.strip(),
                    'return_code': result.returncode
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'PowerShell test failed: {str(e)}',
                'details': str(e)
            }
    
    def test_script(self) -> Dict[str, Any]:
        """Test PowerShell script syntax"""
        try:
            if not self.powershell_available:
                return {
                    'success': False,
                    'message': 'PowerShell not available for script testing',
                    'details': 'PowerShell not detected on this system'
                }
            
            # Create test command to validate syntax
            if self.script_path:
                test_command = [
                    self.powershell_path or 'powershell',
                    '-ExecutionPolicy', self.execution_policy,
                    '-Command', f'$null = Get-Content "{self.script_path}" -ErrorAction Stop; Write-Host "Syntax OK"'
                ]
            else:
                # Create temporary file for testing
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as temp_file:
                    temp_file.write(self.script_content)
                    temp_script_path = temp_file.name
                
                test_command = [
                    self.powershell_path or 'powershell',
                    '-ExecutionPolicy', self.execution_policy,
                    '-Command', f'$null = Get-Content "{temp_script_path}" -ErrorAction Stop; Write-Host "Syntax OK"'
                ]
            
            # Execute syntax test
            result = subprocess.run(
                test_command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up temp file if created
            if not self.script_path and 'temp_script_path' in locals():
                try:
                    os.unlink(temp_script_path)
                except:
                    pass
            
            return {
                'success': result.returncode == 0,
                'message': 'Script syntax is valid' if result.returncode == 0 else 'Script syntax error',
                'details': result.stdout.strip() or result.stderr.strip(),
                'return_code': result.returncode
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
            'powershell_path': self.powershell_path or 'powershell',
            'powershell_available': self.powershell_available,
            'platform': platform.system()
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