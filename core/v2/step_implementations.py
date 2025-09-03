"""
Step Implementations for Job Scheduler V2
SQL, PowerShell, and Azure DevOps step implementations
"""

import asyncio
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone
import pyodbc
import json
import psutil

from .step_framework import ExecutionStep, register_step, StepValidationError, StepExecutionError
from .data_models import StepResult, StepStatus, ExecutionContext, StepConfiguration
from .job_logger import JobLogger
from .timezone_logger import TimezoneLogger
from database.sqlalchemy_models import get_db_session
from utils.logger import get_logger
from utils.windows_utils import windows_utils


@register_step("sql")
class SqlStep(ExecutionStep):
    """SQL execution step with connection management"""
    
    @property
    def step_type(self) -> str:
        return "sql"
    
    def validate_config(self) -> List[str]:
        """Validate SQL step configuration"""
        errors = super().validate_config()
        
        required_fields = ["query"]
        for field in required_fields:
            if field not in self.config.config:
                errors.append(f"Missing required field: {field}")
        
        # Validate query
        query = self.config.config.get("query", "").strip()
        if not query:
            errors.append("Query cannot be empty")
        
        # Basic SQL injection prevention (simple checks)
        dangerous_patterns = [
            "xp_cmdshell", "sp_oacreate", "sp_oamethod", "openrowset", "opendatasource"
        ]
        query_lower = query.lower()
        for pattern in dangerous_patterns:
            if pattern in query_lower:
                errors.append(f"Potentially dangerous SQL pattern detected: {pattern}")
        
        # Validate connection name
        connection_name = self.config.config.get("connection_name", "default")
        if not isinstance(connection_name, str) or not connection_name.strip():
            errors.append("connection_name must be a non-empty string")
        
        # Validate timeout
        timeout = self.config.config.get("timeout", 300)
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append("timeout must be a positive integer")
        
        # Validate max_rows
        max_rows = self.config.config.get("max_rows")
        if max_rows is not None and (not isinstance(max_rows, int) or max_rows <= 0):
            errors.append("max_rows must be a positive integer")
        
        return errors
    
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """Execute SQL query"""
        query = self.config.config["query"]
        connection_name = self.config.config.get("connection_name", "default")
        timeout = self.config.config.get("timeout", 300)
        max_rows = self.config.config.get("max_rows")
        parameters = self.config.config.get("parameters", {})
        
        start_time = datetime.now(timezone.utc)
        
        # Create result object
        result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.RUNNING,
            start_time=start_time
        )
        
        try:
            # Log progress
            self.log_progress(f"Connecting to database (connection: {connection_name})", job_logger)
            
            # Execute in thread pool to avoid blocking async loop
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                sql_result = await loop.run_in_executor(
                    executor, 
                    self._execute_sql_sync, 
                    query, 
                    connection_name, 
                    timeout, 
                    max_rows,
                    parameters,
                    job_logger
                )
            
            # Process results
            rows_affected, rows_returned, output_data = sql_result
            
            # Format output
            if rows_returned:
                output = f"Query executed successfully. {rows_returned} rows returned."
                if len(output_data) > 1000:  # Truncate large outputs
                    output += f" Output truncated. First 1000 characters: {str(output_data)[:1000]}..."
                else:
                    output += f" Data: {output_data}"
            else:
                output = f"Query executed successfully. {rows_affected} rows affected."
            
            # Add metadata
            result.add_metadata("connection_name", connection_name)
            result.add_metadata("query", query[:500] + "..." if len(query) > 500 else query)
            result.add_metadata("rows_affected", rows_affected)
            result.add_metadata("rows_returned", rows_returned)
            result.add_metadata("execution_time", (datetime.now(timezone.utc) - start_time).total_seconds())
            
            if parameters:
                result.add_metadata("parameters", parameters)
            
            # Log completion
            self.log_output(output, job_logger)
            result.mark_completed(StepStatus.SUCCESS, output)
            
            # Add context variables for subsequent steps
            self.add_context_variable("rows_affected", rows_affected, context)
            self.add_context_variable("rows_returned", rows_returned, context)
            if rows_returned and output_data:
                self.add_context_variable("query_result", output_data, context)
            
            return result
            
        except Exception as e:
            error_message = f"SQL execution failed: {str(e)}"
            self.logger.error(f"SQL step error: {error_message}")
            
            result.mark_completed(StepStatus.FAILED, error_message=error_message)
            result.add_metadata("error_type", type(e).__name__)
            result.add_metadata("connection_name", connection_name)
            
            return result
    
    def _execute_sql_sync(self, query: str, connection_name: str, timeout: int, 
                         max_rows: Optional[int], parameters: Dict[str, Any],
                         job_logger: JobLogger) -> tuple:
        """Execute SQL query synchronously (runs in thread pool)"""
        
        # Get database connection using environment variables
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        # Build connection string
        driver = os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server')
        server = os.getenv('DB_SERVER', 'localhost')
        database = os.getenv('DB_DATABASE', 'master')
        trusted_connection = os.getenv('DB_TRUSTED_CONNECTION', 'true').lower() == 'true'
        
        if trusted_connection:
            conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        else:
            username = os.getenv('DB_USERNAME', '')
            password = os.getenv('DB_PASSWORD', '')
            conn_str = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={username};PWD={password};"
        
        self.log_progress(f"Connecting with: {conn_str.replace('PWD=' + os.getenv('DB_PASSWORD', ''), 'PWD=***')}", job_logger)
        
        connection = None
        cursor = None
        rows_affected = 0
        rows_returned = 0
        output_data = None
        
        try:
            # Connect to database
            connection = pyodbc.connect(conn_str, timeout=timeout)
            cursor = connection.cursor()
            
            self.log_progress("Connected to database successfully", job_logger)
            
            # Set query timeout
            cursor.timeout = timeout
            
            # Execute query with parameters
            if parameters:
                self.log_progress(f"Executing query with parameters: {parameters}", job_logger)
                cursor.execute(query, parameters)
            else:
                self.log_progress("Executing query", job_logger)
                cursor.execute(query)
            
            # Check if query returns data
            if cursor.description:
                # SELECT query - fetch results
                if max_rows:
                    rows = cursor.fetchmany(max_rows)
                    if len(rows) == max_rows:
                        self.log_progress(f"Retrieved {len(rows)} rows (limited by max_rows={max_rows})", job_logger)
                    else:
                        self.log_progress(f"Retrieved {len(rows)} rows", job_logger)
                else:
                    rows = cursor.fetchall()
                    self.log_progress(f"Retrieved {len(rows)} rows", job_logger)
                
                rows_returned = len(rows)
                
                # Convert to list of dictionaries
                if rows:
                    columns = [column[0] for column in cursor.description]
                    output_data = [dict(zip(columns, row)) for row in rows]
                else:
                    output_data = []
                
            else:
                # INSERT/UPDATE/DELETE query
                rows_affected = cursor.rowcount
                self.log_progress(f"Query affected {rows_affected} rows", job_logger)
            
            # Commit transaction
            connection.commit()
            self.log_progress("Transaction committed successfully", job_logger)
            
            return rows_affected, rows_returned, output_data
            
        except pyodbc.Error as e:
            if connection:
                connection.rollback()
            raise StepExecutionError(f"Database error: {str(e)}")
        
        except Exception as e:
            if connection:
                connection.rollback()
            raise StepExecutionError(f"Unexpected error: {str(e)}")
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
            self.log_progress("Database connection closed", job_logger)


@register_step("powershell")
class PowerShellStep(ExecutionStep):
    """PowerShell script execution step"""
    
    @property
    def step_type(self) -> str:
        return "powershell"
    
    def validate_config(self) -> List[str]:
        """Validate PowerShell step configuration"""
        errors = super().validate_config()
        
        # Must have either script or script_path
        script = self.config.config.get("script")
        script_path = self.config.config.get("script_path")
        
        if not script and not script_path:
            errors.append("Either 'script' (inline) or 'script_path' must be provided")
        
        if script and script_path:
            errors.append("Cannot specify both 'script' and 'script_path'")
        
        # Validate script_path if provided
        if script_path:
            if not isinstance(script_path, str):
                errors.append("script_path must be a string")
            elif not os.path.isabs(script_path) and not script_path.startswith('./'):
                errors.append("script_path should be absolute or start with './'")
        
        # Validate script content if provided
        if script:
            if not isinstance(script, str):
                errors.append("script must be a string")
            elif not script.strip():
                errors.append("script cannot be empty")
        
        # Validate parameters
        parameters = self.config.config.get("parameters", {})
        if not isinstance(parameters, dict):
            errors.append("parameters must be a dictionary")
        
        # Validate execution_policy
        execution_policy = self.config.config.get("execution_policy")
        if execution_policy:
            valid_policies = ["Restricted", "AllSigned", "RemoteSigned", "Unrestricted", "Bypass"]
            if execution_policy not in valid_policies:
                errors.append(f"execution_policy must be one of: {', '.join(valid_policies)}")
        
        # Security validations
        script_content = script or ""
        if script_path:
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            except Exception:
                pass  # Will be caught during execution
        
        # Check for dangerous commands
        dangerous_commands = [
            "Remove-Item", "rd", "rmdir", "del", "Format-Volume", "Remove-Computer",
            "Restart-Computer", "Stop-Computer", "Invoke-Expression", "iex",
            "Invoke-Command", "icm", "Start-Process", "saps"
        ]
        
        script_lower = script_content.lower()
        for cmd in dangerous_commands:
            if cmd.lower() in script_lower:
                errors.append(f"Potentially dangerous PowerShell command detected: {cmd}")
        
        return errors
    
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """Execute PowerShell script"""
        script = self.config.config.get("script")
        script_path = self.config.config.get("script_path")
        parameters = self.config.config.get("parameters", {})
        execution_policy = self.config.config.get("execution_policy", "RemoteSigned")
        working_directory = self.config.config.get("working_directory", os.getcwd())
        
        start_time = datetime.now(timezone.utc)
        
        # Create result object
        result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.RUNNING,
            start_time=start_time
        )
        
        temp_script_path = None
        
        try:
            # Validate that we have either script or script_path
            if not script and not script_path:
                raise StepExecutionError("PowerShell script or script_path is required")
            
            # Prepare script
            if script:
                # Create temporary script file
                temp_script_path = self._create_temp_script(script)
                script_to_execute = temp_script_path
                self.log_progress("Created temporary script file", job_logger)
            elif script_path:
                script_to_execute = script_path
                if not os.path.exists(script_to_execute):
                    raise StepExecutionError(f"Script file not found: {script_to_execute}")
                self.log_progress(f"Using script file: {script_to_execute}", job_logger)
            else:
                raise StepExecutionError("PowerShell script or script_path is required")
            
            # Build PowerShell command
            ps_command = self._build_powershell_command(
                script_to_execute, 
                parameters, 
                execution_policy,
                working_directory
            )
            
            self.log_progress(f"Executing PowerShell with policy: {execution_policy}", job_logger)
            
            # Execute in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                ps_result = await loop.run_in_executor(
                    executor,
                    self._execute_powershell_sync,
                    ps_command,
                    working_directory,
                    job_logger
                )
            
            # Process results
            return_code, stdout, stderr, execution_time = ps_result
            
            # Format output
            output = []
            if stdout:
                output.append(f"STDOUT:\n{stdout}")
            if stderr:
                output.append(f"STDERR:\n{stderr}")
            
            output_text = "\n".join(output) if output else "PowerShell script executed with no output"
            
            # Determine success/failure based on return code
            if return_code == 0:
                status = StepStatus.SUCCESS
                self.log_progress("PowerShell script executed successfully", job_logger)
            else:
                status = StepStatus.FAILED
                error_message = f"PowerShell script failed with exit code {return_code}"
                if stderr:
                    error_message += f": {stderr}"
                result.error_message = error_message
                self.log_progress(error_message, job_logger)
            
            # Add metadata
            result.add_metadata("return_code", return_code)
            result.add_metadata("execution_policy", execution_policy)
            result.add_metadata("working_directory", working_directory)
            result.add_metadata("execution_time", execution_time)
            
            if script:
                result.add_metadata("script_type", "inline")
                result.add_metadata("script_length", len(script))
            else:
                result.add_metadata("script_type", "file")
                result.add_metadata("script_path", script_path)
            
            if parameters:
                result.add_metadata("parameters", parameters)
            
            # Log output
            if len(output_text) > 2000:  # Truncate very long outputs
                self.log_output(output_text[:2000] + "...\n[Output truncated]", job_logger)
            else:
                self.log_output(output_text, job_logger)
            
            result.mark_completed(status, output_text)
            
            # Add context variables for subsequent steps
            self.add_context_variable("return_code", return_code, context)
            self.add_context_variable("stdout", stdout, context)
            self.add_context_variable("stderr", stderr, context)
            
            return result
            
        except Exception as e:
            error_message = f"PowerShell execution failed: {str(e)}"
            self.logger.error(f"PowerShell step error: {error_message}")
            
            result.mark_completed(StepStatus.FAILED, error_message=error_message)
            result.add_metadata("error_type", type(e).__name__)
            
            return result
            
        finally:
            # Clean up temporary script file
            if temp_script_path and os.path.exists(temp_script_path):
                try:
                    os.unlink(temp_script_path)
                    self.log_progress("Cleaned up temporary script file", job_logger)
                except Exception:
                    pass
    
    def _create_temp_script(self, script_content: str) -> str:
        """Create temporary PowerShell script file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
            f.write(script_content)
            return f.name
    
    def _build_powershell_command(self, script_path: str, parameters: Dict[str, Any], 
                                execution_policy: str, working_directory: str) -> List[str]:
        """Build PowerShell command with parameters"""
        ps_path = windows_utils.get_powershell_path()
        if ps_path is None:
            ps_path = "powershell.exe"  # Fallback
            
        command = [
            ps_path,
            "-ExecutionPolicy", execution_policy,
            "-NoProfile",
            "-NonInteractive",
            "-File", script_path
        ]
        
        # Add parameters
        for key, value in parameters.items():
            command.extend(["-" + key, str(value)])
        
        return command
    
    def _execute_powershell_sync(self, command: List[str], working_directory: str, 
                               job_logger: JobLogger) -> tuple:
        """Execute PowerShell command synchronously"""
        start_time = datetime.now()
        
        try:
            # Log command (mask sensitive parameters)
            masked_command = []
            for i, part in enumerate(command):
                if i > 0 and command[i-1].lower() in ['-password', '-pwd', '-secret', '-key']:
                    masked_command.append('***')
                else:
                    masked_command.append(part)
            
            self.log_progress(f"Command: {' '.join(masked_command)}", job_logger)
            
            # Execute command
            process = subprocess.Popen(
                command,
                cwd=working_directory,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                shell=False
            )
            
            # Wait for completion with timeout
            timeout = self.config.timeout or 300
            stdout, stderr = process.communicate(timeout=timeout)
            return_code = process.returncode
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self.log_progress(f"PowerShell completed in {execution_time:.2f}s with return code {return_code}", job_logger)
            
            return return_code, stdout, stderr, execution_time
            
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()  # Clean up
            raise StepExecutionError(f"PowerShell script timed out after {timeout} seconds")
        
        except Exception as e:
            raise StepExecutionError(f"Failed to execute PowerShell script: {str(e)}")


@register_step("azure_devops")
class AzureDevOpsStep(ExecutionStep):
    """Azure DevOps pipeline trigger step (placeholder for future implementation)"""
    
    @property
    def step_type(self) -> str:
        return "azure_devops"
    
    def validate_config(self) -> List[str]:
        """Validate Azure DevOps step configuration"""
        errors = super().validate_config()
        
        required_fields = ["organization", "project", "pipeline_id"]
        for field in required_fields:
            if field not in self.config.config:
                errors.append(f"Missing required field: {field}")
        
        # For now, return warning that this step is not implemented
        errors.append("Azure DevOps integration is not yet implemented in V2")
        
        return errors
    
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """Execute Azure DevOps pipeline trigger (placeholder)"""
        start_time = datetime.now(timezone.utc)
        
        result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.FAILED,
            start_time=start_time,
            error_message="Azure DevOps integration not yet implemented in V2"
        )
        
        self.log_progress("Azure DevOps step is not yet implemented", job_logger)
        
        return result


@register_step("http")
class HttpStep(ExecutionStep):
    """HTTP request step for API calls and webhooks"""
    
    @property
    def step_type(self) -> str:
        return "http"
    
    def validate_config(self) -> List[str]:
        """Validate HTTP step configuration"""
        errors = super().validate_config()
        
        # Required fields
        if "url" not in self.config.config:
            errors.append("Missing required field: url")
        
        # Validate URL
        url = self.config.config.get("url", "")
        if not url.startswith(("http://", "https://")):
            errors.append("URL must start with http:// or https://")
        
        # Validate method
        method = self.config.config.get("method", "GET").upper()
        valid_methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        if method not in valid_methods:
            errors.append(f"Invalid HTTP method. Must be one of: {', '.join(valid_methods)}")
        
        # Validate headers
        headers = self.config.config.get("headers", {})
        if not isinstance(headers, dict):
            errors.append("headers must be a dictionary")
        
        # Validate expected_status_codes
        expected_codes = self.config.config.get("expected_status_codes", [200])
        if not isinstance(expected_codes, list):
            errors.append("expected_status_codes must be a list")
        
        return errors
    
    async def execute_impl(self, context: ExecutionContext, job_logger: JobLogger, tz_logger: TimezoneLogger) -> StepResult:
        """Execute HTTP request (placeholder - would need aiohttp)"""
        start_time = datetime.now(timezone.utc)
        
        result = StepResult(
            step_id=self.config.step_id,
            step_name=self.config.step_name,
            step_type=self.step_type,
            status=StepStatus.FAILED,
            start_time=start_time,
            error_message="HTTP step requires aiohttp library (not implemented yet)"
        )
        
        self.log_progress("HTTP step requires additional dependencies", job_logger)
        
        return result


# Helper function to get all registered step types
def get_available_step_types() -> Dict[str, Dict[str, Any]]:
    """Get information about all available step types"""
    from .step_framework import StepFactory
    return StepFactory.get_all_step_info()


# Helper function to create step from legacy job
def create_step_from_legacy_job(legacy_job: Dict[str, Any]) -> ExecutionStep:
    """Create a step from legacy job format"""
    job_type = legacy_job.get('job_type', legacy_job.get('type', 'unknown'))
    
    if job_type == 'sql':
        config = StepConfiguration(
            step_id="legacy_sql_step",
            step_name=f"{legacy_job.get('name', 'Legacy SQL Job')} Step",
            step_type="sql",
            config={
                "query": legacy_job.get('sql_query', ''),
                "connection_name": legacy_job.get('connection_name', 'default'),
                "timeout": legacy_job.get('timeout', 300)
            },
            timeout=legacy_job.get('timeout', 300)
        )
    elif job_type == 'powershell':
        config = StepConfiguration(
            step_id="legacy_ps_step",
            step_name=f"{legacy_job.get('name', 'Legacy PowerShell Job')} Step",
            step_type="powershell",
            config={
                "script": legacy_job.get('script', ''),
                "parameters": legacy_job.get('parameters', {}),
                "timeout": legacy_job.get('timeout', 300)
            },
            timeout=legacy_job.get('timeout', 300)
        )
    else:
        raise ValueError(f"Unknown legacy job type: {job_type}")
    
    from .step_framework import StepFactory
    return StepFactory.create_step(config)