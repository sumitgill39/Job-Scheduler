#!/usr/bin/env python3
"""
Job Scheduler Agent - Standalone Script
=======================================

All-in-one agent script that automatically connects to the Job Scheduler master server.
All configuration parameters are passed as command-line arguments for easy deployment.

Usage:
    python agent_standalone.py --scheduler-url http://192.168.1.100:5000 --agent-id prod-agent-001 --agent-name "Production Agent 01" --agent-pool production

Requirements:
    pip install requests pyyaml psutil
"""

import sys
import os
import json
import time
import threading
import requests
import subprocess
import platform
import psutil
import yaml
import argparse
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import signal

class JobSchedulerAgent:
    def __init__(self, scheduler_url, agent_id, agent_name="", agent_pool="default", 
                 capabilities=None, max_parallel_jobs=2, heartbeat_interval=30, 
                 poll_interval=10, log_level="INFO", work_dir=None):
        """
        Initialize the Job Scheduler Agent with command-line parameters
        
        Args:
            scheduler_url (str): Master server URL (e.g., http://192.168.1.100:5000)
            agent_id (str): Unique agent identifier
            agent_name (str): Human-readable agent name
            agent_pool (str): Agent pool assignment
            capabilities (list): List of capabilities (default: auto-detected)
            max_parallel_jobs (int): Maximum parallel job execution
            heartbeat_interval (int): Heartbeat interval in seconds
            poll_interval (int): Job polling interval in seconds
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
            work_dir (str): Base working directory for agent (default: ./_work)
        """
        self.scheduler_url = scheduler_url.rstrip('/')
        self.agent_id = agent_id
        self.agent_name = agent_name or agent_id
        self.agent_pool = agent_pool
        self.max_parallel_jobs = max_parallel_jobs
        self.heartbeat_interval = heartbeat_interval
        self.poll_interval = poll_interval
        
        # Setup working directory structure
        if work_dir:
            self.work_dir = os.path.abspath(work_dir)
        else:
            self.work_dir = os.path.abspath(os.path.join(os.getcwd(), '_work'))
        
        # Initialize working directory structure
        self._setup_work_directory()
        
        # Auto-detect capabilities if not provided
        if capabilities is None:
            self.capabilities = self._detect_capabilities()
        else:
            self.capabilities = capabilities
        
        # System information
        self.system_info = self._get_system_info()
        
        # Authentication
        self.auth_token = None
        self.token_expires = None
        
        # Job execution
        self.executor = ThreadPoolExecutor(max_workers=max_parallel_jobs)
        self.active_jobs = {}
        self.shutdown_requested = False
        
        # Setup logging
        self._setup_logging(log_level)
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self, log_level):
        """Setup logging configuration"""
        log_filename = f"agent_{self.agent_id.replace('-', '_').replace(' ', '_')}.log"
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Configure logger
        self.logger = logging.getLogger('JobSchedulerAgent')
        self.logger.setLevel(getattr(logging, log_level.upper()))
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown_requested = True
    
    def _setup_work_directory(self):
        """
        Setup the agent working directory structure
        Creates:
        - _work/              # Base working directory
        - _work/temp/         # Temporary files
        - _work/tools/        # Agent tools and utilities
        - _work/{exec_id}/    # Job execution directories (created per job)
            - a/              # Artifacts directory
            - b/              # Binaries/build output directory  
            - s/              # Sources directory (for checkouts)
        """
        # Create base work directory
        os.makedirs(self.work_dir, exist_ok=True)
        
        # Create subdirectories
        temp_dir = os.path.join(self.work_dir, 'temp')
        tools_dir = os.path.join(self.work_dir, 'tools')
        
        os.makedirs(temp_dir, exist_ok=True)
        os.makedirs(tools_dir, exist_ok=True)
        
        # Store paths for later use
        self.temp_dir = temp_dir
        self.tools_dir = tools_dir
        
        # Log directory creation
        if hasattr(self, 'logger'):
            self.logger.info(f"Working directory initialized at: {self.work_dir}")
    
    def _create_job_workspace(self, job_id):
        """
        Create workspace directories for a specific job execution
        
        Args:
            job_id: The job/execution ID
            
        Returns:
            dict: Paths to the created directories
        """
        # Create execution-specific directory
        exec_dir = os.path.join(self.work_dir, str(job_id))
        os.makedirs(exec_dir, exist_ok=True)
        
        # Create standard subdirectories (Azure DevOps style)
        paths = {
            'root': exec_dir,
            'a': os.path.join(exec_dir, 'a'),  # Artifacts
            'b': os.path.join(exec_dir, 'b'),  # Binaries/Build
            's': os.path.join(exec_dir, 's'),  # Sources
        }
        
        for dir_path in paths.values():
            os.makedirs(dir_path, exist_ok=True)
        
        return paths
    
    def _cleanup_job_workspace(self, job_id, keep_artifacts=False):
        """
        Clean up job workspace after execution
        
        Args:
            job_id: The job/execution ID
            keep_artifacts: Whether to preserve artifacts directory
        """
        exec_dir = os.path.join(self.work_dir, str(job_id))
        
        if not os.path.exists(exec_dir):
            return
        
        try:
            if keep_artifacts:
                # Keep artifacts, clean other directories
                for subdir in ['b', 's']:
                    dir_path = os.path.join(exec_dir, subdir)
                    if os.path.exists(dir_path):
                        import shutil
                        shutil.rmtree(dir_path, ignore_errors=True)
            else:
                # Clean entire execution directory
                import shutil
                shutil.rmtree(exec_dir, ignore_errors=True)
                
            if hasattr(self, 'logger'):
                self.logger.debug(f"Cleaned workspace for job {job_id}")
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to clean workspace for job {job_id}: {e}")
    
    def _detect_capabilities(self):
        """Auto-detect system capabilities"""
        capabilities = ["shell"]
        
        # Check Python
        if sys.executable:
            capabilities.append("python")
        
        # Check PowerShell (Windows)
        if platform.system() == "Windows":
            capabilities.extend(["powershell", "windows"])
            try:
                subprocess.run(["powershell", "-Command", "Get-Host"], 
                             capture_output=True, timeout=5)
            except:
                capabilities.remove("powershell")
        
        # Check Docker
        try:
            subprocess.run(["docker", "--version"], 
                         capture_output=True, timeout=5)
            capabilities.append("docker")
        except:
            pass
        
        # Add OS-specific capabilities
        os_name = platform.system().lower()
        if os_name not in capabilities:
            capabilities.append(os_name)
        
        return capabilities
    
    def _get_system_info(self):
        """Get system information"""
        try:
            # Get system information
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "hostname": platform.node(),
                "platform": platform.platform(),
                "architecture": platform.architecture()[0],
                "processor": platform.processor(),
                "cpu_cores": psutil.cpu_count(),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "memory_available_gb": round(memory.available / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "disk_free_gb": round(disk.free / (1024**3), 2),
                "python_version": platform.python_version(),
                "agent_version": "1.0.0"
            }
        except Exception as e:
            self.logger.warning(f"Could not gather complete system info: {e}")
            return {
                "hostname": platform.node(),
                "platform": platform.platform(),
                "agent_version": "1.0.0"
            }
    
    def register(self):
        """Register with the master server"""
        # Get IP address
        try:
            import socket
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
        except:
            hostname = platform.node()
            ip_address = "127.0.0.1"
        
        registration_data = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "hostname": hostname,
            "ip_address": ip_address,
            "agent_pool": self.agent_pool,
            "capabilities": self.capabilities,
            "max_parallel_jobs": self.max_parallel_jobs,
            "agent_version": "1.0.0",
            # System information fields directly
            "os_info": self.system_info.get("platform", "Unknown"),
            "cpu_cores": self.system_info.get("cpu_cores"),
            "memory_gb": int(self.system_info.get("memory_total_gb", 0)),
            "disk_space_gb": int(self.system_info.get("disk_total_gb", 0))
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/register",
                json=registration_data,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.auth_token = data.get("jwt_token") or data.get("token")
                
                # Calculate token expiration
                expires_in = data.get("token_expires_in") or data.get("expires_in", 14400)  # Default 4 hours
                self.token_expires = datetime.now() + timedelta(seconds=expires_in)
                
                self.logger.info(f"SUCCESS: Agent {self.agent_id} registered successfully")
                self.logger.info(f"Status: {data.get('status', 'unknown')}")
                self.logger.info(f"Token expires in: {expires_in} seconds")
                return True
            else:
                self.logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Registration error: {e}")
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to master server"""
        if not self.auth_token:
            return False
        
        # Get current system status
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            heartbeat_data = {
                "agent_id": self.agent_id,
                "status": "online",
                "active_jobs": len(self.active_jobs),
                "system_status": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": round(memory.available / (1024**3), 2)
                }
            }
        except:
            heartbeat_data = {
                "agent_id": self.agent_id,
                "status": "online",
                "active_jobs": len(self.active_jobs)
            }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/heartbeat",
                json=heartbeat_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                self.logger.warning(f"Heartbeat failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Heartbeat error: {e}")
            return False
    
    def poll_for_jobs(self):
        """Poll for available jobs"""
        if not self.auth_token:
            return []
        
        try:
            response = requests.get(
                f"{self.scheduler_url}/api/agent/jobs/poll",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                params={"agent_id": self.agent_id},
                timeout=10
            )
            
            if response.status_code == 200:
                jobs = response.json().get("jobs", [])
                return jobs
            else:
                self.logger.warning(f"Job polling failed: {response.status_code}")
                return []
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Job polling error: {e}")
            return []
    
    def update_job_status(self, job_id, status, output="", error_message=""):
        """Update job status on master server"""
        if not self.auth_token:
            return False
        
        status_data = {
            "status": status,
            "output": output,
            "error_message": error_message,
            "updated_by": self.agent_id
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{job_id}/status",
                json=status_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to update job {job_id} status: {e}")
            return False
    
    def complete_job(self, job_id, success, output="", error_message=""):
        """Mark job as completed on master server"""
        if not self.auth_token:
            return False
        
        completion_data = {
            "success": success,
            "output": output,
            "error_message": error_message,
            "completed_by": self.agent_id,
            "completed_at": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{job_id}/complete",
                json=completion_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10
            )
            
            return response.status_code == 200
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to complete job {job_id}: {e}")
            return False
    
    def execute_job(self, job):
        """Execute a job"""
        job_id = job.get("id")
        job_name = job.get("name", f"Job-{job_id}")
        workspace = None
        
        self.logger.info(f"STARTING JOB {job_id}: {job_name}")
        self.active_jobs[job_id] = job
        
        # Update status to running
        self.update_job_status(job_id, "running", f"Job started on agent {self.agent_id}")
        
        try:
            # Create job workspace
            workspace = self._create_job_workspace(job_id)
            self.logger.info(f"Job workspace created at: {workspace['root']}")
            
            # Parse job YAML
            job_yaml = job.get("job_yaml", "")
            if job_yaml:
                job_config = yaml.safe_load(job_yaml)
            else:
                raise Exception("No job configuration provided")
            
            # Set environment variables including workspace paths
            env = os.environ.copy()
            env.update({
                "JOB_ID": str(job_id),
                "JOB_NAME": job_name,
                "AGENT_ID": self.agent_id,
                "AGENT_NAME": self.agent_name,
                "AGENT_HOSTNAME": platform.node(),
                "AGENT_POOL": self.agent_pool,
                # Workspace paths
                "AGENT_WORKFOLDER": self.work_dir,
                "AGENT_BUILDDIRECTORY": workspace['root'],
                "BUILD_SOURCESDIRECTORY": workspace['s'],
                "BUILD_BINARIESDIRECTORY": workspace['b'],
                "BUILD_ARTIFACTSDIRECTORY": workspace['a'],
                # Short aliases
                "WORKSPACE": workspace['root'],
                "SOURCES_DIR": workspace['s'],
                "BINARIES_DIR": workspace['b'],
                "ARTIFACTS_DIR": workspace['a']
            })
            
            # Execute job steps
            all_output = []
            
            steps = job_config.get("steps", [])
            for i, step in enumerate(steps):
                step_name = step.get("name", f"Step {i+1}")
                action = step.get("action", "").lower()
                
                self.logger.info(f"  EXECUTING STEP: {step_name}")
                all_output.append(f"=== {step_name} ===")
                
                if action == "shell":
                    command = step.get("command", "")
                    output = self._execute_shell(command, env, workspace['s'])
                    
                elif action == "python":
                    script = step.get("script", "")
                    output = self._execute_python(script, env, workspace['s'])
                    
                elif action == "powershell":
                    script = step.get("script", "")
                    output = self._execute_powershell(script, env, workspace['s'])
                    
                else:
                    raise Exception(f"Unsupported action: {action}")
                
                all_output.append(output)
                all_output.append("")  # Empty line between steps
            
            # Job completed successfully
            final_output = "\n".join(all_output)
            self.complete_job(job_id, True, final_output)
            self.logger.info(f"SUCCESS: Job {job_id} completed successfully")
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"FAILED: Job {job_id} failed: {error_msg}")
            self.complete_job(job_id, False, "", error_msg)
        
        finally:
            # Remove from active jobs
            self.active_jobs.pop(job_id, None)
            
            # Clean up workspace (keeping artifacts for now)
            if workspace:
                self._cleanup_job_workspace(job_id, keep_artifacts=True)
    
    def _execute_shell(self, command, env, working_dir=None):
        """Execute shell command"""
        try:
            if platform.system() == "Windows":
                result = subprocess.run(
                    command, shell=True, capture_output=True, 
                    text=True, env=env, timeout=300, cwd=working_dir
                )
            else:
                result = subprocess.run(
                    ["bash", "-c", command], capture_output=True, 
                    text=True, env=env, timeout=300, cwd=working_dir
                )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            if result.returncode != 0:
                raise Exception(f"Command failed with exit code {result.returncode}: {output}")
            
            return output
            
        except subprocess.TimeoutExpired:
            raise Exception("Command timed out after 5 minutes")
        except Exception as e:
            raise Exception(f"Shell execution failed: {e}")
    
    def _execute_python(self, script, env, working_dir=None):
        """Execute Python script"""
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env, timeout=300, cwd=working_dir
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            if result.returncode != 0:
                raise Exception(f"Python script failed with exit code {result.returncode}: {output}")
            
            return output
            
        except subprocess.TimeoutExpired:
            raise Exception("Python script timed out after 5 minutes")
        except Exception as e:
            raise Exception(f"Python execution failed: {e}")
    
    def _execute_powershell(self, script, env, working_dir=None):
        """Execute PowerShell script (Windows only)"""
        if platform.system() != "Windows":
            raise Exception("PowerShell is only available on Windows")
        
        try:
            result = subprocess.run(
                ["powershell", "-Command", script],
                capture_output=True, text=True, env=env, timeout=300, cwd=working_dir
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            if result.returncode != 0:
                raise Exception(f"PowerShell script failed with exit code {result.returncode}: {output}")
            
            return output
            
        except subprocess.TimeoutExpired:
            raise Exception("PowerShell script timed out after 5 minutes")
        except Exception as e:
            raise Exception(f"PowerShell execution failed: {e}")
    
    def run(self):
        """Main agent loop"""
        # Display startup banner
        print("=" * 60)
        print("JOB SCHEDULER AGENT CLIENT")
        print("=" * 60)
        print(f"Agent ID: {self.agent_id}")
        print(f"Scheduler URL: {self.scheduler_url}")
        print(f"Agent Pool: {self.agent_pool}")
        print(f"Capabilities: {', '.join(self.capabilities)}")
        print(f"Max Parallel Jobs: {self.max_parallel_jobs}")
        print("-" * 60)
        
        # Register with master server
        if not self.register():
            self.logger.error("Failed to register with master server. Exiting.")
            return False
        
        print(f"STARTING: Agent {self.agent_id} starting main loop...")
        self.logger.info(f"Agent {self.agent_id} started successfully")
        
        # Start heartbeat thread
        heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        
        # Main job polling loop
        last_heartbeat = time.time()
        
        while not self.shutdown_requested:
            try:
                # Check if token needs refresh
                if self.token_expires and datetime.now() >= self.token_expires - timedelta(minutes=5):
                    self.logger.info("Token expiring soon, re-registering...")
                    self.register()
                
                # Poll for jobs
                jobs = self.poll_for_jobs()
                
                for job in jobs:
                    job_id = job.get("id")
                    if job_id not in self.active_jobs:
                        # Submit job to executor
                        self.executor.submit(self.execute_job, job)
                
                # Sleep before next poll
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Received interrupt signal, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                time.sleep(self.poll_interval)
        
        # Shutdown
        self.logger.info("Agent shutting down...")
        self.executor.shutdown(wait=True)
        return True
    
    def _heartbeat_loop(self):
        """Heartbeat loop running in separate thread"""
        while not self.shutdown_requested:
            try:
                self.send_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.warning(f"Heartbeat error: {e}")
                time.sleep(self.heartbeat_interval)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Job Scheduler Agent - Standalone Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python agent_standalone.py --scheduler-url http://192.168.1.100:5000 --agent-id prod-001

  # Full configuration
  python agent_standalone.py \\
    --scheduler-url http://192.168.1.100:5000 \\
    --agent-id windows-prod-001 \\
    --agent-name "Windows Production Agent 01" \\
    --agent-pool production \\
    --capabilities shell,python,powershell,windows \\
    --max-parallel-jobs 4 \\
    --heartbeat-interval 30 \\
    --poll-interval 10 \\
    --log-level INFO

Requirements:
  pip install requests pyyaml psutil
        """
    )
    
    # Required parameters
    parser.add_argument("--scheduler-url", required=True,
                       help="Master scheduler URL (e.g., http://192.168.1.100:5000)")
    parser.add_argument("--agent-id", required=True,
                       help="Unique agent identifier (e.g., prod-agent-001)")
    
    # Optional parameters
    parser.add_argument("--agent-name", default="",
                       help="Human-readable agent name (default: same as agent-id)")
    parser.add_argument("--agent-pool", default="default",
                       help="Agent pool assignment (default: default)")
    parser.add_argument("--capabilities",
                       help="Comma-separated list of capabilities (default: auto-detect)")
    parser.add_argument("--max-parallel-jobs", type=int, default=2,
                       help="Maximum parallel jobs (default: 2)")
    parser.add_argument("--heartbeat-interval", type=int, default=30,
                       help="Heartbeat interval in seconds (default: 30)")
    parser.add_argument("--poll-interval", type=int, default=10,
                       help="Job polling interval in seconds (default: 10)")
    parser.add_argument("--log-level", default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level (default: INFO)")
    parser.add_argument("--work-dir", 
                       help="Base working directory for agent (default: ./_work)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Process capabilities
    capabilities = None
    if args.capabilities:
        capabilities = [cap.strip() for cap in args.capabilities.split(",")]
    
    # Create and run agent
    agent = JobSchedulerAgent(
        scheduler_url=args.scheduler_url,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
        agent_pool=args.agent_pool,
        capabilities=capabilities,
        max_parallel_jobs=args.max_parallel_jobs,
        heartbeat_interval=args.heartbeat_interval,
        poll_interval=args.poll_interval,
        log_level=args.log_level
    )
    
    try:
        success = agent.run()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nAgent stopped by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()