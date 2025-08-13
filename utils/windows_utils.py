"""
Windows-specific utilities for Job Scheduler
"""

import os
import sys
import subprocess
import psutil
import win32api
import win32con
import win32security
import win32net
import win32netcon
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from .logger import get_logger


class WindowsUtils:
    """Windows-specific utility functions"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
    
    @staticmethod
    def is_windows() -> bool:
        """Check if running on Windows"""
        return sys.platform == "win32"
    
    def get_windows_version(self) -> Dict[str, str]:
        """Get Windows version information"""
        try:
            version_info = win32api.GetVersionEx()
            return {
                'major': str(version_info[0]),
                'minor': str(version_info[1]),
                'build': str(version_info[2]),
                'platform': str(version_info[3]),
                'version_string': win32api.GetVersion()
            }
        except Exception as e:
            self.logger.error(f"Could not get Windows version: {e}")
            return {'error': str(e)}
    
    def get_current_user(self) -> Dict[str, str]:
        """Get current Windows user information"""
        try:
            username = win32api.GetUserName()
            domain = win32api.GetDomainName()
            
            return {
                'username': username,
                'domain': domain,
                'full_name': f"{domain}\\{username}" if domain else username
            }
        except Exception as e:
            self.logger.error(f"Could not get current user: {e}")
            return {'username': os.getenv('USERNAME', 'Unknown')}
    
    def validate_domain_user(self, domain: str, username: str) -> bool:
        """Validate if domain user exists"""
        try:
            # Try to get user info
            user_info = win32net.NetUserGetInfo(domain, username, 1)
            return user_info is not None
        except Exception as e:
            self.logger.debug(f"Domain user validation failed for {domain}\\{username}: {e}")
            return False
    
    def check_admin_privileges(self) -> bool:
        """Check if running with administrator privileges"""
        try:
            return win32security.GetTokenInformation(
                win32security.GetCurrentProcessToken(),
                win32security.TokenElevation
            )
        except Exception:
            return False
    
    def get_powershell_path(self) -> str:
        """Get PowerShell executable path"""
        # Try PowerShell 7+ first
        ps7_paths = [
            r"C:\Program Files\PowerShell\7\pwsh.exe",
            r"C:\Program Files (x86)\PowerShell\7\pwsh.exe"
        ]
        
        for path in ps7_paths:
            if os.path.exists(path):
                return path
        
        # Fall back to Windows PowerShell 5.1
        ps5_path = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        if os.path.exists(ps5_path):
            return ps5_path
        
        # Last resort - try to find in PATH
        try:
            result = subprocess.run(['where', 'powershell'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except Exception:
            pass
        
        # Default fallback
        return "powershell.exe"
    
    def execute_powershell_script(self, script_path: str, 
                                 parameters: List[str] = None,
                                 execution_policy: str = "RemoteSigned",
                                 timeout: int = 300,
                                 run_as_user: str = None) -> Dict[str, any]:
        """Execute PowerShell script on Windows"""
        try:
            ps_path = self.get_powershell_path()
            parameters = parameters or []
            
            # Build command
            cmd = [
                ps_path,
                "-ExecutionPolicy", execution_policy,
                "-NoProfile",
                "-NonInteractive",
                "-File", script_path
            ]
            
            # Add parameters
            cmd.extend(parameters)
            
            self.logger.info(f"Executing PowerShell: {' '.join(cmd)}")
            
            # Execute with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            
            return {
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }
            
        except subprocess.TimeoutExpired as e:
            error_msg = f"PowerShell script timed out after {timeout} seconds"
            self.logger.error(error_msg)
            return {
                'success': False,
                'return_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'command': ' '.join(cmd) if 'cmd' in locals() else ''
            }
        except Exception as e:
            error_msg = f"Failed to execute PowerShell script: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'return_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'command': script_path
            }
    
    def execute_powershell_command(self, command: str,
                                  execution_policy: str = "RemoteSigned",
                                  timeout: int = 300) -> Dict[str, any]:
        """Execute inline PowerShell command"""
        try:
            ps_path = self.get_powershell_path()
            
            cmd = [
                ps_path,
                "-ExecutionPolicy", execution_policy,
                "-NoProfile",
                "-NonInteractive",
                "-Command", command
            ]
            
            self.logger.info(f"Executing PowerShell command: {command}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            
            return {
                'success': result.returncode == 0,
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': command
            }
            
        except subprocess.TimeoutExpired:
            error_msg = f"PowerShell command timed out after {timeout} seconds"
            self.logger.error(error_msg)
            return {
                'success': False,
                'return_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'command': command
            }
        except Exception as e:
            error_msg = f"Failed to execute PowerShell command: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'return_code': -1,
                'stdout': '',
                'stderr': error_msg,
                'command': command
            }
    
    def get_system_info(self) -> Dict[str, any]:
        """Get Windows system information"""
        try:
            return {
                'platform': sys.platform,
                'architecture': os.environ.get('PROCESSOR_ARCHITECTURE', 'Unknown'),
                'computer_name': os.environ.get('COMPUTERNAME', 'Unknown'),
                'domain': os.environ.get('USERDOMAIN', 'Unknown'),
                'username': os.environ.get('USERNAME', 'Unknown'),
                'cpu_count': os.cpu_count(),
                'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2),
                'windows_version': self.get_windows_version(),
                'is_admin': self.check_admin_privileges(),
                'powershell_path': self.get_powershell_path()
            }
        except Exception as e:
            self.logger.error(f"Could not get system info: {e}")
            return {'error': str(e)}
    
    def validate_file_path(self, file_path: str) -> bool:
        """Validate Windows file path"""
        try:
            path = Path(file_path)
            
            # Check for invalid characters
            invalid_chars = '<>:"|?*'
            if any(char in str(path) for char in invalid_chars):
                return False
            
            # Check path length (Windows MAX_PATH limitation)
            if len(str(path.resolve())) > 260:
                self.logger.warning(f"Path might be too long: {len(str(path.resolve()))} characters")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Invalid file path {file_path}: {e}")
            return False
    
    def normalize_windows_path(self, path: str) -> str:
        """Normalize path for Windows"""
        try:
            # Convert forward slashes to backslashes
            normalized = path.replace('/', '\\')
            
            # Resolve to absolute path
            abs_path = os.path.abspath(normalized)
            
            return abs_path
            
        except Exception as e:
            self.logger.error(f"Could not normalize path {path}: {e}")
            return path
    
    def check_process_running(self, process_name: str) -> List[Dict[str, any]]:
        """Check if process is running"""
        try:
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        processes.append({
                            'pid': proc.info['pid'],
                            'name': proc.info['name'],
                            'exe': proc.info['exe'],
                            'cmdline': ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            return processes
            
        except Exception as e:
            self.logger.error(f"Could not check process {process_name}: {e}")
            return []
    
    def get_available_drives(self) -> List[Dict[str, str]]:
        """Get available Windows drives"""
        try:
            drives = []
            for partition in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    drives.append({
                        'drive': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'total_gb': round(usage.total / (1024**3), 2),
                        'free_gb': round(usage.free / (1024**3), 2),
                        'used_percent': round((usage.used / usage.total) * 100, 1)
                    })
                except Exception:
                    # Drive might not be ready
                    drives.append({
                        'drive': partition.device,
                        'mountpoint': partition.mountpoint,
                        'fstype': partition.fstype,
                        'status': 'Not Ready'
                    })
            
            return drives
            
        except Exception as e:
            self.logger.error(f"Could not get drives info: {e}")
            return []


# Global instance
windows_utils = WindowsUtils()


if __name__ == "__main__":
    # Test Windows utilities
    utils = WindowsUtils()
    
    print("=== System Information ===")
    system_info = utils.get_system_info()
    for key, value in system_info.items():
        print(f"{key}: {value}")
    
    print("\n=== Current User ===")
    user_info = utils.get_current_user()
    for key, value in user_info.items():
        print(f"{key}: {value}")
    
    print("\n=== Available Drives ===")
    drives = utils.get_available_drives()
    for drive in drives:
        print(drive)
    
    print("\n=== PowerShell Test ===")
    result = utils.execute_powershell_command("Get-Date")
    print(f"Success: {result['success']}")
    print(f"Output: {result['stdout'].strip()}")