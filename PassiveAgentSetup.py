#!/usr/bin/env python3
"""
Passive Job Scheduler Agent - New Architecture
=============================================

This agent implements a passive architecture where:
1. Agent waits passively for job assignments from Job Executor
2. Creates complete local execution environments for assigned jobs
3. Provides comprehensive logging throughout execution
4. Reports completion status back to Job Executor

The Job Executor proactively assigns jobs to specific agents rather than
agents polling for work.

Usage:
    python PassiveAgentSetup.py --scheduler-url http://127.0.0.1:5000 --agent-id agent-001 --agent-name "Passive Agent 01" --agent-pool default

Requirements:
    pip install requests pyyaml psutil flask
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
from pathlib import Path
from flask import Flask, request, jsonify
import signal
import shutil
import uuid

class PassiveJobAgent:
    def __init__(self, scheduler_url, agent_id, agent_name="", agent_pool="default", 
                 agent_port=8080, heartbeat_interval=30, log_level="INFO", work_dir=None):
        """
        Initialize the Passive Job Scheduler Agent
        
        Args:
            scheduler_url (str): Master server URL (e.g., http://127.0.0.1:5000)
            agent_id (str): Unique agent identifier
            agent_name (str): Human-readable agent name
            agent_pool (str): Agent pool assignment
            agent_port (int): Port for agent's HTTP server
            heartbeat_interval (int): Heartbeat interval in seconds
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
            work_dir (str): Base working directory for agent
        """
        self.scheduler_url = scheduler_url.rstrip('/')
        self.agent_id = agent_id
        self.agent_name = agent_name or agent_id
        self.agent_pool = agent_pool
        self.agent_port = agent_port
        self.heartbeat_interval = heartbeat_interval
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "_agent_workspace"
        
        # Create work directory structure
        self.work_dir.mkdir(exist_ok=True)
        self.jobs_dir = self.work_dir / "jobs"
        self.jobs_dir.mkdir(exist_ok=True)
        self.logs_dir = self.work_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        
        # Setup logging
        self._setup_logging(log_level)
        
        # Agent state
        self.auth_token = None
        self.active_jobs = {}
        self.job_logs = {}
        self.is_running = False
        self.heartbeat_thread = None
        self.flask_app = None
        
        # System info
        self.system_info = self._get_system_info()
        
        self.logger.info(f"Passive Agent {self.agent_id} initialized")
        self.logger.info(f"Work directory: {self.work_dir}")
        self.logger.info(f"Agent will listen on port: {self.agent_port}")

    def _setup_logging(self, log_level):
        """Setup comprehensive logging system"""
        # Create agent-specific log file
        log_file = self.logs_dir / f"agent_{self.agent_id}.log"
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(f"PassiveAgent-{self.agent_id}")

    def _get_system_info(self):
        """Get system information for capability reporting"""
        import socket
        
        # Get local IP address
        try:
            # Connect to a public DNS to get the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
        
        return {
            "hostname": platform.node(),
            "ip_address": local_ip,
            "platform": platform.platform(),
            "os_info": platform.platform(),  # Full OS info
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "cpu_cores": psutil.cpu_count(logical=False),  # Physical cores
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "disk_free_gb": round(shutil.disk_usage(str(self.work_dir)).free / (1024**3), 2),
            "disk_space_gb": round(shutil.disk_usage(str(self.work_dir)).total / (1024**3), 2),
            "python_version": platform.python_version(),
            "agent_version": "1.0.0-passive"
        }

    def register_with_scheduler(self):
        """Register this passive agent with the Job Scheduler"""
        registration_data = {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "hostname": self.system_info.get("hostname"),
            "ip_address": self.system_info.get("ip_address"),
            "agent_pool": self.agent_pool,
            "agent_type": "passive",
            "agent_port": self.agent_port,
            "agent_endpoint": f"http://{self.system_info.get('ip_address')}:{self.agent_port}",
            "capabilities": ["powershell", "cmd", "python", "passive_execution"],
            "max_parallel_jobs": 3,
            "agent_version": self.system_info.get("agent_version", "1.0.0-passive"),
            "os_info": self.system_info.get("os_info"),
            "cpu_cores": self.system_info.get("cpu_cores", 0),
            "memory_gb": self.system_info.get("memory_gb", 0),
            "disk_space_gb": self.system_info.get("disk_space_gb", 0),
            "system_info": self.system_info,
            "work_directory": str(self.work_dir)
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/register",
                json=registration_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                self.auth_token = result.get("auth_token")
                self.logger.info(f"Successfully registered with scheduler. Token received: {bool(self.auth_token)}")
                return True
            else:
                self.logger.error(f"Registration failed: {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Registration error: {e}")
            return False

    def send_heartbeat(self):
        """Send heartbeat to scheduler"""
        if not self.auth_token:
            return False
            
        heartbeat_data = {
            "agent_id": self.agent_id,
            "status": "online",
            "active_jobs": len(self.active_jobs),
            "system_status": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_free_gb": round(shutil.disk_usage(str(self.work_dir)).free / (1024**3), 2)
            },
            "agent_port": self.agent_port
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/heartbeat",
                json=heartbeat_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.debug("Heartbeat sent successfully")
                return True
            else:
                self.logger.warning(f"Heartbeat failed: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Heartbeat error: {e}")
            return False

    def _heartbeat_worker(self):
        """Background thread for sending heartbeats"""
        while self.is_running:
            try:
                self.send_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"Heartbeat worker error: {e}")
                time.sleep(5)

    def create_job_workspace(self, execution_id, job_name):
        """Create a complete local execution environment for a job execution"""
        # Create _work directory structure following the established convention
        work_dir = self.work_dir / "_work" / execution_id
        
        # Create job directory structure matching the existing system
        workspace_structure = {
            'root': work_dir,
            's': work_dir / 's',  # Sources directory (short name)
            'b': work_dir / 'b',  # Binaries directory (short name)
            'a': work_dir / 'a',  # Artifacts directory (short name)
            'sources': work_dir / 's',  # Alias for sources
            'binaries': work_dir / 'b',  # Alias for binaries
            'artifacts': work_dir / 'a',  # Alias for artifacts
            'logs': work_dir / 'logs',
            'temp': work_dir / 'temp'
        }
        
        # Create all directories
        for dir_path in workspace_structure.values():
            if isinstance(dir_path, Path):  # Skip aliases
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create job execution metadata files
        job_config_file = workspace_structure['root'] / "job_config.yaml"
        job_log_file = workspace_structure['logs'] / "execution.log"
        
        # Create execution metadata file
        metadata = {
            'execution_id': execution_id,
            'job_name': job_name,
            'agent_id': self.agent_id,
            'created_at': datetime.now().isoformat(),
            'workspace_structure': {k: str(v) for k, v in workspace_structure.items() if isinstance(v, Path)}
        }
        
        metadata_file = workspace_structure['root'] / "execution_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Created execution workspace for {execution_id} at: {work_dir}")
        return workspace_structure

    def setup_job_environment(self, execution_id, job_name, workspace):
        """Setup environment variables for job execution"""
        env = os.environ.copy()
        env.update({
            # Job-specific variables
            "EXECUTION_ID": str(execution_id),
            "JOB_NAME": job_name,
            "JOB_EXECUTION_ID": str(execution_id),
            
            # Agent variables
            "AGENT_ID": self.agent_id,
            "AGENT_NAME": self.agent_name,
            "AGENT_HOSTNAME": platform.node(),
            "AGENT_POOL": self.agent_pool,
            "AGENT_WORK_DIR": str(self.work_dir),
            
            # Workspace paths (full paths)
            "WORKSPACE_ROOT": str(workspace['root']),
            "WORKSPACE_SOURCES": str(workspace['sources']),
            "WORKSPACE_BINARIES": str(workspace['binaries']),
            "WORKSPACE_ARTIFACTS": str(workspace['artifacts']),
            "WORKSPACE_LOGS": str(workspace['logs']),
            "WORKSPACE_TEMP": str(workspace['temp']),
            
            # Standard pipeline aliases
            "BUILD_SOURCESDIRECTORY": str(workspace['sources']),
            "BUILD_BINARIESDIRECTORY": str(workspace['binaries']),
            "BUILD_ARTIFACTSDIRECTORY": str(workspace['artifacts']),
            "AGENT_BUILDDIRECTORY": str(workspace['root']),
            
            # Execution metadata
            "EXECUTION_TIME": datetime.now().isoformat(),
            "AGENT_VERSION": "1.0.0-passive"
        })
        
        return env

    def create_flask_app(self):
        """Create Flask app to receive job assignments"""
        app = Flask(f"PassiveAgent-{self.agent_id}")
        
        @app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            return jsonify({
                "status": "healthy",
                "agent_id": self.agent_id,
                "active_jobs": len(self.active_jobs),
                "uptime_seconds": time.time() - getattr(self, 'start_time', time.time())
            })
        
        @app.route('/api/job/assign', methods=['POST'])
        def receive_job_assignment():
            """Receive job assignment from Job Executor"""
            try:
                job_data = request.get_json()
                execution_id = job_data.get('execution_id')
                job_id = job_data.get('job_id')
                job_name = job_data.get('job_name', f'Job-{job_id}')
                job_yaml = job_data.get('job_yaml', '')
                
                if not execution_id:
                    raise ValueError("execution_id is required for job assignment")
                
                self.logger.info(f"Received job assignment - Execution ID: {execution_id}, Job: {job_id} - {job_name}")
                
                # Start job execution in background thread
                job_thread = threading.Thread(
                    target=self.execute_assigned_job, 
                    args=(job_data,),
                    daemon=True
                )
                job_thread.start()
                
                return jsonify({
                    "success": True,
                    "message": f"Job execution {execution_id} accepted and started",
                    "execution_id": execution_id,
                    "agent_id": self.agent_id
                })
                
            except Exception as e:
                self.logger.error(f"Error receiving job assignment: {e}")
                return jsonify({
                    "success": False,
                    "error": str(e)
                }), 500
        
        @app.route('/api/job/<execution_id>/status', methods=['GET'])
        def get_job_status(execution_id):
            """Get current status of a job execution"""
            if execution_id in self.active_jobs:
                job_info = self.active_jobs[execution_id]
                return jsonify({
                    "execution_id": execution_id,
                    "job_id": job_info.get('job_id'),
                    "status": job_info.get('status', 'unknown'),
                    "start_time": job_info.get('start_time'),
                    "current_step": job_info.get('current_step'),
                    "agent_id": self.agent_id
                })
            else:
                return jsonify({"error": "Job execution not found"}), 404
        
        @app.route('/api/job/<execution_id>/logs', methods=['GET'])
        def get_job_logs(execution_id):
            """Get execution logs for a job"""
            if execution_id in self.job_logs:
                return jsonify({
                    "execution_id": execution_id,
                    "logs": self.job_logs[execution_id],
                    "agent_id": self.agent_id
                })
            else:
                return jsonify({"error": "Job execution logs not found"}), 404
        
        return app

    def execute_assigned_job(self, job_data):
        """Execute a job assigned by the Job Executor"""
        execution_id = job_data.get('execution_id')
        job_id = job_data.get('job_id')
        job_name = job_data.get('job_name', f'Job-{job_id}')
        job_yaml = job_data.get('job_yaml', '')
        
        # Initialize job tracking using execution_id as the key
        self.active_jobs[execution_id] = {
            "execution_id": execution_id,
            "job_id": job_id,
            "job_name": job_name,
            "status": "initializing",
            "start_time": datetime.now().isoformat(),
            "current_step": "setup"
        }
        self.job_logs[execution_id] = []
        
        workspace = None
        execution_success = False
        execution_output = ""
        execution_error = ""
        
        try:
            self.log_job_message(execution_id, f"Starting job execution: {job_name}")
            
            # Create complete job workspace using execution_id
            workspace = self.create_job_workspace(execution_id, job_name)
            self.log_job_message(execution_id, f"Job workspace created at: {workspace['root']}")
            
            # Setup execution environment
            env = self.setup_job_environment(execution_id, job_name, workspace)
            self.log_job_message(execution_id, f"Job environment configured with {len(env)} variables")
            
            # Parse job configuration
            if job_yaml:
                try:
                    job_config = yaml.safe_load(job_yaml)
                    self.log_job_message(execution_id, "Job YAML configuration parsed successfully")
                except yaml.YAMLError as e:
                    raise Exception(f"Invalid YAML configuration: {e}")
            else:
                raise Exception("No job configuration provided")
            
            # Save job configuration to workspace
            config_file = workspace['root'] / "job_config.yaml"
            with open(config_file, 'w') as f:
                f.write(job_yaml)
            
            # Update status to running
            self.active_jobs[execution_id]["status"] = "running"
            self.report_job_status(execution_id, "running", "Job execution started")
            
            # Execute job steps
            steps = job_config.get("steps", [])
            self.log_job_message(execution_id, f"Executing {len(steps)} job steps")
            
            all_output = []
            
            for i, step in enumerate(steps, 1):
                step_name = step.get("name", f"Step {i}")
                self.active_jobs[execution_id]["current_step"] = step_name
                self.log_job_message(execution_id, f"Executing step {i}/{len(steps)}: {step_name}")
                
                step_output = self.execute_job_step(execution_id, step, env, workspace)
                all_output.append(f"=== Step {i}: {step_name} ===\\n{step_output}\\n")
            
            # Job completed successfully
            execution_success = True
            execution_output = "\\n".join(all_output)
            self.log_job_message(execution_id, "Job completed successfully")
            
        except Exception as e:
            execution_success = False
            execution_error = str(e)
            self.log_job_message(execution_id, f"Job failed with error: {e}")
            self.logger.error(f"Job {execution_id} execution failed: {e}")
            
        finally:
            # Clean up and report completion
            self.active_jobs[execution_id]["status"] = "completed" if execution_success else "failed"
            self.active_jobs[execution_id]["end_time"] = datetime.now().isoformat()
            
            # Report completion to Job Executor
            self.report_job_completion(
                execution_id, 
                execution_success, 
                execution_output, 
                execution_error
            )
            
            # Clean up job from active jobs after reporting
            if execution_id in self.active_jobs:
                del self.active_jobs[execution_id]

    def execute_job_step(self, execution_id, step, env, workspace):
        """Execute a single job step with comprehensive logging"""
        step_name = step.get("name", "Unnamed Step")
        action = step.get("action", "").lower()
        
        self.log_job_message(execution_id, f"Starting step: {step_name} (action: {action})")
        
        if action == "powershell":
            return self._execute_powershell_step(execution_id, step, env, workspace)
        elif action == "cmd" or action == "command":
            return self._execute_cmd_step(execution_id, step, env, workspace)
        elif action == "python":
            return self._execute_python_step(execution_id, step, env, workspace)
        else:
            error_msg = f"Unsupported action: {action}"
            self.log_job_message(execution_id, error_msg)
            raise Exception(error_msg)

    def _execute_powershell_step(self, execution_id, step, env, workspace):
        """Execute PowerShell step"""
        script = step.get("script", "")
        timeout = step.get("timeout", 300)
        
        if not script:
            raise Exception("No PowerShell script provided")
        
        # Create PowerShell script file
        script_file = workspace['temp'] / f"step_{int(time.time())}.ps1"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        self.log_job_message(execution_id, f"Executing PowerShell script: {script_file}")
        
        # Execute PowerShell
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script_file)]
        
        return self._run_command(execution_id, cmd, env, workspace['root'], timeout)

    def _execute_cmd_step(self, execution_id, step, env, workspace):
        """Execute Command Prompt step"""
        command = step.get("command", "")
        timeout = step.get("timeout", 300)
        
        if not command:
            raise Exception("No command provided")
        
        self.log_job_message(execution_id, f"Executing command: {command}")
        
        return self._run_command(execution_id, command, env, workspace['root'], timeout, shell=True)

    def _execute_python_step(self, execution_id, step, env, workspace):
        """Execute Python step"""
        script = step.get("script", "")
        timeout = step.get("timeout", 300)
        
        if not script:
            raise Exception("No Python script provided")
        
        # Create Python script file
        script_file = workspace['temp'] / f"step_{int(time.time())}.py"
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(script)
        
        self.log_job_message(execution_id, f"Executing Python script: {script_file}")
        
        cmd = [sys.executable, str(script_file)]
        
        return self._run_command(execution_id, cmd, env, workspace['root'], timeout)

    def _run_command(self, execution_id, cmd, env, cwd, timeout, shell=False):
        """Run a command with comprehensive logging"""
        self.log_job_message(execution_id, f"Running command: {cmd if isinstance(cmd, str) else ' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                cwd=str(cwd),
                shell=shell,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            
            # Read output in real-time
            for line in iter(process.stdout.readline, ''):
                line = line.rstrip()
                if line:
                    output_lines.append(line)
                    self.log_job_message(execution_id, f"  {line}")
            
            # Wait for process completion
            process.wait(timeout=timeout)
            
            full_output = "\\n".join(output_lines)
            
            if process.returncode == 0:
                self.log_job_message(execution_id, f"Command completed successfully (exit code: {process.returncode})")
            else:
                self.log_job_message(execution_id, f"Command failed with exit code: {process.returncode}")
                raise Exception(f"Command failed with exit code {process.returncode}\\n{full_output}")
            
            return full_output
            
        except subprocess.TimeoutExpired:
            process.kill()
            error_msg = f"Command timed out after {timeout} seconds"
            self.log_job_message(execution_id, error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Command execution error: {e}"
            self.log_job_message(execution_id, error_msg)
            raise Exception(error_msg)

    def log_job_message(self, execution_id, message):
        """Log a message for a specific job execution"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        
        # Add to job-specific logs
        if execution_id not in self.job_logs:
            self.job_logs[execution_id] = []
        self.job_logs[execution_id].append(log_entry)
        
        # Write to agent log
        self.logger.info(f"EXEC[{execution_id}] {message}")
        
        # Write to execution-specific log file in _work/{execution_id}/logs/
        execution_log_file = self.work_dir / "_work" / execution_id / "logs" / "execution.log"
        if execution_log_file.parent.exists():
            with open(execution_log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry + "\\n")

    def report_job_status(self, execution_id, status, message=""):
        """Report job status to the Job Executor"""
        if not self.auth_token:
            return
            
        status_data = {
            "execution_id": execution_id,
            "status": status,
            "message": message,
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{execution_id}/status",
                json=status_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                self.log_job_message(execution_id, f"Status reported: {status}")
            else:
                self.logger.warning(f"Status report failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Status report error: {e}")

    def report_job_completion(self, execution_id, success, output, error_message=""):
        """Report job completion to the Job Executor"""
        if not self.auth_token:
            return
            
        completion_data = {
            "execution_id": execution_id,
            "success": success,
            "output": output,
            "error_message": error_message,
            "completed_by": self.agent_id,
            "completed_at": datetime.now().isoformat(),
            "execution_logs": self.job_logs.get(execution_id, [])
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{execution_id}/complete",
                json=completion_data,
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                self.log_job_message(execution_id, f"Completion reported: {'SUCCESS' if success else 'FAILED'}")
            else:
                self.logger.warning(f"Completion report failed: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            self.logger.warning(f"Completion report error: {e}")

    def start(self):
        """Start the passive agent"""
        self.logger.info(f"Starting Passive Agent {self.agent_id}...")
        self.start_time = time.time()
        
        # Register with scheduler
        if not self.register_with_scheduler():
            self.logger.error("Failed to register with scheduler. Exiting.")
            return False
        
        # Create Flask app
        self.flask_app = self.create_flask_app()
        
        # Start heartbeat thread
        self.is_running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()
        
        self.logger.info(f"Passive Agent {self.agent_id} is now waiting for job assignments...")
        self.logger.info(f"Agent listening on http://0.0.0.0:{self.agent_port}")
        
        try:
            # Start Flask server
            self.flask_app.run(
                host='0.0.0.0', 
                port=self.agent_port, 
                debug=False,
                use_reloader=False
            )
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        except Exception as e:
            self.logger.error(f"Flask server error: {e}")
        finally:
            self.shutdown()
        
        return True

    def shutdown(self):
        """Gracefully shutdown the agent"""
        self.logger.info("Shutting down Passive Agent...")
        self.is_running = False
        
        # Wait for active jobs to complete (with timeout)
        shutdown_timeout = 60
        start_time = time.time()
        
        while self.active_jobs and (time.time() - start_time) < shutdown_timeout:
            self.logger.info(f"Waiting for {len(self.active_jobs)} active jobs to complete...")
            time.sleep(2)
        
        if self.active_jobs:
            self.logger.warning(f"Force shutting down with {len(self.active_jobs)} active jobs")
        
        self.logger.info("Passive Agent shutdown complete")


def main():
    parser = argparse.ArgumentParser(description="Passive Job Scheduler Agent")
    
    parser.add_argument("--scheduler-url", required=True, 
                       help="Job Scheduler master server URL")
    parser.add_argument("--agent-id", required=True, 
                       help="Unique agent identifier")
    parser.add_argument("--agent-name", default="", 
                       help="Human-readable agent name")
    parser.add_argument("--agent-pool", default="default", 
                       help="Agent pool assignment")
    parser.add_argument("--agent-port", type=int, default=8080, 
                       help="Port for agent HTTP server")
    parser.add_argument("--heartbeat-interval", type=int, default=30, 
                       help="Heartbeat interval in seconds")
    parser.add_argument("--log-level", default="INFO", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="Logging level")
    parser.add_argument("--work-dir", 
                       help="Base working directory for agent")
    
    args = parser.parse_args()
    
    # Create and start passive agent
    agent = PassiveJobAgent(
        scheduler_url=args.scheduler_url,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
        agent_pool=args.agent_pool,
        agent_port=args.agent_port,
        heartbeat_interval=args.heartbeat_interval,
        log_level=args.log_level,
        work_dir=args.work_dir
    )
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        print(f"\\nReceived signal {signum}, shutting down...")
        agent.shutdown()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start the agent
    try:
        success = agent.start()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Agent startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()