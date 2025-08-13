"""
Validation utilities for Job Scheduler
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Union
from datetime import datetime
import yaml
from .logger import get_logger
from .windows_utils import WindowsUtils


class JobValidator:
    """Validator for job configurations and parameters"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.windows_utils = WindowsUtils()
        self.allowed_domains = self._load_allowed_domains()
    
    def _load_allowed_domains(self) -> List[str]:
        """Load allowed domains from configuration"""
        try:
            config_path = Path("config/config.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    return config.get('security', {}).get('allowed_domains', [])
        except Exception as e:
            self.logger.warning(f"Could not load allowed domains: {e}")
        
        # Default allowed domains
        return ["dmzprod01", "dmzweb01", "MGD", "Mercer"]
    
    def validate_job_name(self, name: str) -> Dict[str, Union[bool, str]]:
        """Validate job name"""
        if not name or not isinstance(name, str):
            return {"valid": False, "error": "Job name is required and must be a string"}
        
        name = name.strip()
        if len(name) < 1:
            return {"valid": False, "error": "Job name cannot be empty"}
        
        if len(name) > 100:
            return {"valid": False, "error": "Job name must be less than 100 characters"}
        
        # Check for invalid characters
        invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(invalid_chars, name):
            return {"valid": False, "error": "Job name contains invalid characters"}
        
        return {"valid": True, "error": None}
    
    def validate_cron_expression(self, cron_expr: str) -> Dict[str, Union[bool, str]]:
        """Validate cron expression (basic validation)"""
        if not cron_expr or not isinstance(cron_expr, str):
            return {"valid": False, "error": "Cron expression is required"}
        
        cron_expr = cron_expr.strip()
        parts = cron_expr.split()
        
        # Basic cron validation (second minute hour day month day_of_week)
        if len(parts) != 6:
            return {"valid": False, "error": "Cron expression must have 6 parts (second minute hour day month day_of_week)"}
        
        # Validate each part has valid characters
        valid_chars = r'^[0-9\-\*\/\,\?LW#]+$'
        for i, part in enumerate(parts):
            if not re.match(valid_chars, part):
                return {"valid": False, "error": f"Invalid characters in cron part {i+1}: {part}"}
        
        return {"valid": True, "error": None}
    
    def validate_sql_query(self, query: str) -> Dict[str, Union[bool, str]]:
        """Validate SQL query (basic validation)"""
        if not query or not isinstance(query, str):
            return {"valid": False, "error": "SQL query is required"}
        
        query = query.strip()
        if len(query) < 1:
            return {"valid": False, "error": "SQL query cannot be empty"}
        
        # Check for potentially dangerous SQL commands
        dangerous_keywords = [
            'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE',
            'EXEC', 'EXECUTE', 'sp_', 'xp_', 'OPENQUERY', 'OPENROWSET'
        ]
        
        query_upper = query.upper()
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return {"valid": False, "error": f"Potentially dangerous SQL keyword detected: {keyword}"}
        
        # Basic syntax check (very basic)
        if not query_upper.strip().startswith('SELECT'):
            return {"valid": False, "error": "Only SELECT queries are allowed"}
        
        return {"valid": True, "error": None}
    
    def validate_powershell_script(self, script_path: str = None, script_content: str = None) -> Dict[str, Union[bool, str]]:
        """Validate PowerShell script"""
        if script_path:
            return self._validate_powershell_file(script_path)
        elif script_content:
            return self._validate_powershell_content(script_content)
        else:
            return {"valid": False, "error": "Either script_path or script_content must be provided"}
    
    def _validate_powershell_file(self, script_path: str) -> Dict[str, Union[bool, str]]:
        """Validate PowerShell script file"""
        if not script_path or not isinstance(script_path, str):
            return {"valid": False, "error": "Script path is required"}
        
        # Normalize path for Windows
        script_path = self.windows_utils.normalize_windows_path(script_path)
        
        # Check if file exists
        if not os.path.exists(script_path):
            return {"valid": False, "error": f"Script file does not exist: {script_path}"}
        
        # Check file extension
        if not script_path.lower().endswith('.ps1'):
            return {"valid": False, "error": "Script file must have .ps1 extension"}
        
        # Check file size (max 10MB)
        try:
            file_size = os.path.getsize(script_path)
            if file_size > 10 * 1024 * 1024:  # 10MB
                return {"valid": False, "error": "Script file too large (max 10MB)"}
        except Exception as e:
            return {"valid": False, "error": f"Could not check file size: {e}"}
        
        # Read and validate content
        try:
            with open(script_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            return self._validate_powershell_content(content)
        except Exception as e:
            return {"valid": False, "error": f"Could not read script file: {e}"}
    
    def _validate_powershell_content(self, content: str) -> Dict[str, Union[bool, str]]:
        """Validate PowerShell script content"""
        if not content or not isinstance(content, str):
            return {"valid": False, "error": "Script content cannot be empty"}
        
        content = content.strip()
        if len(content) < 1:
            return {"valid": False, "error": "Script content cannot be empty"}
        
        # Check for potentially dangerous PowerShell commands
        dangerous_commands = [
            'Remove-Item', 'rm', 'del', 'rmdir', 'rd',
            'Format-Volume', 'Clear-Disk', 'Remove-Partition',
            'Invoke-Expression', 'iex', 'Invoke-Command', 'icm',
            'Start-Process', 'saps', 'New-Object System.Net.WebClient',
            'DownloadString', 'DownloadFile', 'IEX', 'Invoke-WebRequest',
            'curl', 'wget', 'bitsadmin', 'certutil',
            'powershell.exe', 'cmd.exe', 'wmic.exe'
        ]
        
        content_lower = content.lower()
        for cmd in dangerous_commands:
            if cmd.lower() in content_lower:
                self.logger.warning(f"Potentially dangerous PowerShell command detected: {cmd}")
                # Note: We log warning but don't block - admin can decide policy
        
        return {"valid": True, "error": None}
    
    def validate_domain_account(self, account: str) -> Dict[str, Union[bool, str]]:
        """Validate domain account format"""
        if not account or not isinstance(account, str):
            return {"valid": False, "error": "Account is required"}
        
        account = account.strip()
        
        # Check format: DOMAIN\username or username@domain.com
        if '\\' in account:
            parts = account.split('\\')
            if len(parts) != 2:
                return {"valid": False, "error": "Invalid domain\\username format"}
            
            domain, username = parts
            if not domain or not username:
                return {"valid": False, "error": "Domain and username cannot be empty"}
            
            # Check if domain is allowed
            if domain not in self.allowed_domains:
                return {"valid": False, "error": f"Domain '{domain}' is not in allowed domains: {self.allowed_domains}"}
            
        elif '@' in account:
            parts = account.split('@')
            if len(parts) != 2:
                return {"valid": False, "error": "Invalid username@domain format"}
            
            username, domain = parts
            if not username or not domain:
                return {"valid": False, "error": "Username and domain cannot be empty"}
            
        else:
            # Assume local account
            username = account
            if not username:
                return {"valid": False, "error": "Username cannot be empty"}
        
        return {"valid": True, "error": None}
    
    def validate_connection_string(self, conn_str: str) -> Dict[str, Union[bool, str]]:
        """Validate SQL Server connection string"""
        if not conn_str or not isinstance(conn_str, str):
            return {"valid": False, "error": "Connection string is required"}
        
        conn_str = conn_str.strip()
        if len(conn_str) < 10:
            return {"valid": False, "error": "Connection string too short"}
        
        # Check for required components
        required_parts = ['server', 'database']
        conn_lower = conn_str.lower()
        
        for part in required_parts:
            if part not in conn_lower:
                return {"valid": False, "error": f"Connection string missing '{part}' parameter"}
        
        return {"valid": True, "error": None}
    
    def validate_timeout(self, timeout: Union[int, str]) -> Dict[str, Union[bool, str]]:
        """Validate timeout value"""
        try:
            timeout_int = int(timeout)
            if timeout_int < 1:
                return {"valid": False, "error": "Timeout must be greater than 0"}
            if timeout_int > 86400:  # 24 hours
                return {"valid": False, "error": "Timeout cannot exceed 24 hours (86400 seconds)"}
            return {"valid": True, "error": None}
        except (ValueError, TypeError):
            return {"valid": False, "error": "Timeout must be a valid integer"}
    
    def validate_retry_count(self, retry_count: Union[int, str]) -> Dict[str, Union[bool, str]]:
        """Validate retry count"""
        try:
            retry_int = int(retry_count)
            if retry_int < 0:
                return {"valid": False, "error": "Retry count cannot be negative"}
            if retry_int > 10:
                return {"valid": False, "error": "Retry count cannot exceed 10"}
            return {"valid": True, "error": None}
        except (ValueError, TypeError):
            return {"valid": False, "error": "Retry count must be a valid integer"}
    
    def validate_job_config(self, job_config: Dict) -> Dict[str, Union[bool, List[str]]]:
        """Validate complete job configuration"""
        errors = []
        
        # Validate job name
        if 'name' in job_config:
            result = self.validate_job_name(job_config['name'])
            if not result['valid']:
                errors.append(f"Job name: {result['error']}")
        else:
            errors.append("Job name is required")
        
        # Validate job type
        if 'type' not in job_config:
            errors.append("Job type is required")
        elif job_config['type'] not in ['sql', 'powershell']:
            errors.append("Job type must be 'sql' or 'powershell'")
        
        # Validate schedule
        if 'schedule' in job_config and 'cron' in job_config['schedule']:
            result = self.validate_cron_expression(job_config['schedule']['cron'])
            if not result['valid']:
                errors.append(f"Schedule: {result['error']}")
        
        # Type-specific validation
        if job_config.get('type') == 'sql':
            if 'sql_query' in job_config:
                result = self.validate_sql_query(job_config['sql_query'])
                if not result['valid']:
                    errors.append(f"SQL Query: {result['error']}")
        
        elif job_config.get('type') == 'powershell':
            if 'script_path' in job_config:
                result = self.validate_powershell_script(script_path=job_config['script_path'])
                if not result['valid']:
                    errors.append(f"PowerShell Script: {result['error']}")
            elif 'script_content' in job_config:
                result = self.validate_powershell_script(script_content=job_config['script_content'])
                if not result['valid']:
                    errors.append(f"PowerShell Script: {result['error']}")
        
        # Validate timeout if present
        if 'timeout' in job_config:
            result = self.validate_timeout(job_config['timeout'])
            if not result['valid']:
                errors.append(f"Timeout: {result['error']}")
        
        # Validate retry count if present
        if 'retry_count' in job_config:
            result = self.validate_retry_count(job_config['retry_count'])
            if not result['valid']:
                errors.append(f"Retry count: {result['error']}")
        
        # Validate run_as account if present
        if 'run_as' in job_config:
            result = self.validate_domain_account(job_config['run_as'])
            if not result['valid']:
                errors.append(f"Run as account: {result['error']}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }


# Global validator instance
job_validator = JobValidator()


if __name__ == "__main__":
    # Test validators
    validator = JobValidator()
    
    print("=== Testing Job Name Validation ===")
    test_names = ["Valid Job", "Invalid<>Job", "", "A" * 101]
    for name in test_names:
        result = validator.validate_job_name(name)
        print(f"'{name}': Valid={result['valid']}, Error={result['error']}")
    
    print("\n=== Testing Cron Expression Validation ===")
    test_crons = ["0 0 12 * * ?", "invalid", "0 0 12 * *", "0 0 12 * * ? *"]
    for cron in test_crons:
        result = validator.validate_cron_expression(cron)
        print(f"'{cron}': Valid={result['valid']}, Error={result['error']}")
    
    print("\n=== Testing SQL Query Validation ===")
    test_queries = ["SELECT * FROM table", "DROP TABLE users", "SELECT name FROM users", ""]
    for query in test_queries:
        result = validator.validate_sql_query(query)
        print(f"'{query}': Valid={result['valid']}, Error={result['error']}")
    
    print("\n=== Testing Domain Account Validation ===")
    test_accounts = ["MGD\\testuser", "testuser@domain.com", "INVALID\\user", "testuser"]
    for account in test_accounts:
        result = validator.validate_domain_account(account)
        print(f"'{account}': Valid={result['valid']}, Error={result['error']}")