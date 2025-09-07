#!/usr/bin/env python3
"""
Job Scheduler Agent Client
Connects to the master Job Scheduler server and executes jobs
"""

import requests
import time
import json
import uuid
import os
import sys
import subprocess
import threading
import logging
from datetime import datetime
import platform
import psutil
import argparse

class JobSchedulerAgent:
    def __init__(self, config):
        self.config = config
        self.scheduler_url = config['scheduler_url']
        self.agent_id = config['agent_id']
        self.jwt_token = None
        self.running = False
        self.current_jobs = []
        
        # Setup logging
        self.setup_logging()
        
        # System info
        self.system_info = self.get_system_info()
        
        self.logger.info(f"Agent {self.agent_id} initialized")
        self.logger.info(f"Scheduler URL: {self.scheduler_url}")
        self.logger.info(f"System: {self.system_info['os_info']}")
    
    def setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(f'agent_{self.agent_id}.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f'Agent-{self.agent_id}')
    
    def get_system_info(self):
        """Get system information"""
        try:
            return {
                'os_info': f"{platform.system()} {platform.release()}",
                'cpu_cores': psutil.cpu_count(),
                'memory_gb': round(psutil.virtual_memory().total / (1024**3)),
                'disk_space_gb': round(psutil.disk_usage('/').total / (1024**3)) if platform.system() != 'Windows' 
                                else round(psutil.disk_usage('C:').total / (1024**3))
            }
        except Exception as e:
            self.logger.error(f"Failed to get system info: {e}")
            return {
                'os_info': platform.system(),
                'cpu_cores': 1,
                'memory_gb': 1,
                'disk_space_gb': 10
            }
    
    def get_resource_usage(self):
        """Get current resource usage"""
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent if platform.system() != 'Windows'
                               else psutil.disk_usage('C:').percent
            }
        except Exception as e:
            self.logger.error(f"Failed to get resource usage: {e}")
            return {'cpu_percent': 0, 'memory_percent': 0, 'disk_percent': 0}
    
    def register(self):
        """Register agent with the scheduler"""
        registration_data = {
            "agent_id": self.agent_id,
            "agent_name": self.config.get('agent_name', f"Agent {self.agent_id}"),
            "hostname": platform.node(),
            "ip_address": self.get_local_ip(),
            "agent_pool": self.config.get('agent_pool', 'default'),
            "capabilities": self.config.get('capabilities', []),
            "max_parallel_jobs": self.config.get('max_parallel_jobs', 2),
            "agent_version": "1.0.0",
            **self.system_info
        }
        
        try:
            self.logger.info(f"Registering agent {self.agent_id} with scheduler...")
            response = requests.post(
                f"{self.scheduler_url}/api/agent/register",
                json=registration_data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                if data.get('success'):
                    self.jwt_token = data.get('jwt_token')
                    self.logger.info(f"✅ Agent {self.agent_id} registered successfully")
                    self.logger.info(f"Status: {data.get('status', 'registered')}")
                    self.logger.info(f"Token expires in: {data.get('token_expires_in', 0)} seconds")
                    return True
                else:
                    self.logger.error(f"Registration failed: {data.get('error', 'Unknown error')}")
            else:
                self.logger.error(f"Registration failed with status {response.status_code}: {response.text}")
                
        except Exception as e:
            self.logger.error(f"Registration error: {e}")
            
        return False
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def send_heartbeat(self):
        """Send heartbeat to scheduler"""
        if not self.jwt_token:
            return False
            
        heartbeat_data = {
            "agent_id": self.agent_id,
            "timestamp": datetime.now().isoformat(),
            "status": "available" if len(self.current_jobs) == 0 else "busy",
            "current_jobs": [job['job_id'] for job in self.current_jobs],
            "resource_usage": self.get_resource_usage(),
            "last_job_completed": None  # TODO: Track last completed job
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/heartbeat",
                json=heartbeat_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.jwt_token}"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                self.logger.debug("Heartbeat sent successfully")
                return True
            else:
                self.logger.warning(f"Heartbeat failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")
            
        return False
    
    def poll_for_jobs(self):
        """Poll scheduler for available jobs"""
        if not self.jwt_token:
            return []
            
        try:
            response = requests.get(
                f"{self.scheduler_url}/api/agent/jobs/poll",
                params={
                    "agent_id": self.agent_id, 
                    "max_jobs": max(1, self.config.get('max_parallel_jobs', 2) - len(self.current_jobs))
                },
                headers={"Authorization": f"Bearer {self.jwt_token}"},
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('jobs', [])
            else:
                self.logger.warning(f"Job polling failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Job polling error: {e}")
            
        return []
    
    def execute_job_step(self, step, job_context):
        """Execute a single job step"""
        step_name = step.get('name', 'Unnamed Step')
        action = step.get('action', 'unknown')
        
        self.logger.info(f"Executing step: {step_name} (action: {action})")
        
        try:
            if action == 'shell':
                return self.execute_shell_command(step, job_context)
            elif action == 'python':
                return self.execute_python_script(step, job_context)
            elif action == 'powershell':
                return self.execute_powershell_script(step, job_context)
            else:
                self.logger.warning(f"Unsupported action: {action}")
                return {
                    'status': 'failed',
                    'message': f'Unsupported action: {action}',
                    'output': '',
                    'duration_seconds': 0
                }
                
        except Exception as e:
            self.logger.error(f"Step execution error: {e}")
            return {
                'status': 'failed',
                'message': str(e),
                'output': '',
                'duration_seconds': 0
            }
    
    def execute_shell_command(self, step, job_context):
        """Execute shell command"""
        command = step.get('command', '')
        timeout = step.get('timeout', 300)
        
        start_time = time.time()
        
        try:
            # Set environment variables from job context
            env = os.environ.copy()
            env.update({
                'AGENT_ID': self.agent_id,
                'JOB_ID': job_context.get('job_id', ''),
                'JOB_NAME': job_context.get('job_name', ''),
                'AGENT_POOL': self.config.get('agent_pool', 'default'),
                'JOB_RUN_DATE': datetime.now().isoformat(),
                'EXECUTION_STRATEGY': 'default_pool',
                'AGENT_HOSTNAME': platform.node()
            })
            
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            duration = time.time() - start_time
            
            return {
                'status': 'success' if result.returncode == 0 else 'failed',
                'message': f'Command executed with return code {result.returncode}',
                'output': result.stdout + result.stderr,
                'return_code': result.returncode,
                'duration_seconds': duration
            }
            
        except subprocess.TimeoutExpired:
            return {
                'status': 'timeout',
                'message': f'Command timed out after {timeout} seconds',
                'output': '',
                'duration_seconds': timeout
            }
    
    def execute_python_script(self, step, job_context):
        """Execute Python script"""
        script = step.get('script', '')
        timeout = step.get('timeout', 300)
        
        start_time = time.time()
        
        try:
            # Create temporary script file
            script_file = f"temp_script_{uuid.uuid4().hex[:8]}.py"
            
            # Add environment setup to script
            full_script = f"""
import os
import sys
from datetime import datetime

# Set job context variables
AGENT_ID = "{self.agent_id}"
JOB_ID = "{job_context.get('job_id', '')}"
JOB_NAME = "{job_context.get('job_name', '')}"
AGENT_POOL = "{self.config.get('agent_pool', 'default')}"
JOB_RUN_DATE = "{datetime.now().isoformat()}"

# User script
{script}
"""
            
            with open(script_file, 'w') as f:
                f.write(full_script)
            
            # Execute script
            result = subprocess.run(
                [sys.executable, script_file],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            # Cleanup
            if os.path.exists(script_file):
                os.remove(script_file)
            
            duration = time.time() - start_time
            
            return {
                'status': 'success' if result.returncode == 0 else 'failed',
                'message': f'Python script executed with return code {result.returncode}',
                'output': result.stdout + result.stderr,
                'return_code': result.returncode,
                'duration_seconds': duration
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': str(e),
                'output': '',
                'duration_seconds': time.time() - start_time
            }
    
    def execute_powershell_script(self, step, job_context):
        """Execute PowerShell script (Windows only)"""
        if platform.system() != 'Windows':
            return {
                'status': 'failed',
                'message': 'PowerShell is only supported on Windows',
                'output': '',
                'duration_seconds': 0
            }
        
        script = step.get('script', '')
        timeout = step.get('timeout', 300)
        
        start_time = time.time()
        
        try:
            # Execute PowerShell script
            result = subprocess.run(
                ['powershell', '-Command', script],
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            return {
                'status': 'success' if result.returncode == 0 else 'failed',
                'message': f'PowerShell script executed with return code {result.returncode}',
                'output': result.stdout + result.stderr,
                'return_code': result.returncode,
                'duration_seconds': duration
            }
            
        except Exception as e:
            return {
                'status': 'failed',
                'message': str(e),
                'output': '',
                'duration_seconds': time.time() - start_time
            }
    
    def execute_job(self, job):
        """Execute a complete job"""
        job_id = job['job_id']
        execution_id = job['execution_id']
        
        self.logger.info(f"Starting job execution: {job['job_name']} ({job_id})")
        
        # Add to current jobs
        self.current_jobs.append(job)
        
        # Parse YAML configuration
        try:
            import yaml
            job_config = yaml.safe_load(job['yaml_configuration'])
        except Exception as e:
            self.logger.error(f"Failed to parse job YAML: {e}")
            self.report_job_completion(execution_id, 'failed', f'YAML parsing error: {e}', [])
            return
        
        # Update job status to running
        self.update_job_status(execution_id, 'running', 'Job started', 0)
        
        # Execute steps
        step_results = []
        overall_start = time.time()
        
        try:
            steps = job_config.get('steps', [])
            if not steps:
                raise Exception("No steps defined in job configuration")
            
            for i, step in enumerate(steps):
                step_result = self.execute_job_step(step, {
                    'job_id': job_id,
                    'job_name': job['job_name'],
                    'execution_id': execution_id
                })
                
                step_results.append({
                    'step_name': step.get('name', f'Step {i+1}'),
                    'status': step_result['status'],
                    'duration_seconds': step_result.get('duration_seconds', 0),
                    'output': step_result.get('output', ''),
                    'message': step_result.get('message', '')
                })
                
                # Update progress
                progress = int(((i + 1) / len(steps)) * 100)
                self.update_job_status(execution_id, 'running', f'Completed step: {step.get("name", f"Step {i+1}")}', progress)
                
                # Check if step failed and should stop
                if step_result['status'] == 'failed' and not step.get('continue_on_error', False):
                    raise Exception(f"Step failed: {step_result.get('message', 'Unknown error')}")
            
            # All steps completed successfully
            total_duration = time.time() - overall_start
            self.logger.info(f"Job {job_id} completed successfully in {total_duration:.2f}s")
            
            self.report_job_completion(
                execution_id, 
                'success', 
                f'Job completed successfully in {total_duration:.2f} seconds',
                step_results
            )
            
        except Exception as e:
            total_duration = time.time() - overall_start
            self.logger.error(f"Job {job_id} failed: {e}")
            
            self.report_job_completion(
                execution_id,
                'failed',
                str(e),
                step_results
            )
        
        finally:
            # Remove from current jobs
            self.current_jobs = [j for j in self.current_jobs if j['job_id'] != job_id]
    
    def update_job_status(self, execution_id, status, message, progress):
        """Update job status"""
        if not self.jwt_token:
            return
            
        status_data = {
            "agent_id": self.agent_id,
            "status": status,
            "progress_percent": progress,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "resource_usage": self.get_resource_usage()
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{execution_id}/status",
                json=status_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.jwt_token}"
                },
                timeout=15
            )
            
            if response.status_code != 200:
                self.logger.warning(f"Status update failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Status update error: {e}")
    
    def report_job_completion(self, execution_id, status, message, step_results):
        """Report job completion"""
        if not self.jwt_token:
            return
            
        completion_data = {
            "agent_id": self.agent_id,
            "status": status,
            "message": message,
            "step_results": step_results,
            "end_time": datetime.now().isoformat(),
            "resource_summary": self.get_resource_usage()
        }
        
        try:
            response = requests.post(
                f"{self.scheduler_url}/api/agent/jobs/{execution_id}/complete",
                json=completion_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.jwt_token}"
                },
                timeout=15
            )
            
            if response.status_code == 200:
                self.logger.info(f"Job completion reported: {status}")
            else:
                self.logger.warning(f"Completion report failed: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Completion report error: {e}")
    
    def run(self):
        """Main agent loop"""
        if not self.register():
            self.logger.error("Failed to register agent. Exiting.")
            return
            
        self.running = True
        self.logger.info(f"🚀 Agent {self.agent_id} starting main loop...")
        
        heartbeat_interval = self.config.get('heartbeat_interval', 30)
        poll_interval = self.config.get('poll_interval', 10)
        
        last_heartbeat = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Send heartbeat
                if current_time - last_heartbeat >= heartbeat_interval:
                    self.send_heartbeat()
                    last_heartbeat = current_time
                
                # Poll for jobs if we have capacity
                max_jobs = self.config.get('max_parallel_jobs', 2)
                if len(self.current_jobs) < max_jobs:
                    jobs = self.poll_for_jobs()
                    for job in jobs:
                        if len(self.current_jobs) < max_jobs:
                            # Execute job in separate thread
                            job_thread = threading.Thread(
                                target=self.execute_job, 
                                args=(job,),
                                daemon=True
                            )
                            job_thread.start()
                
                # Wait before next cycle
                time.sleep(poll_interval)
                
            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal...")
                break
            except Exception as e:
                self.logger.error(f"Main loop error: {e}")
                time.sleep(30)  # Wait longer on error
        
        self.running = False
        self.logger.info(f"👋 Agent {self.agent_id} shutting down...")


def load_config(config_file):
    """Load agent configuration"""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config file: {e}")
    
    # Default configuration
    return {
        "scheduler_url": "http://127.0.0.1:5000",
        "agent_id": f"agent-{uuid.uuid4().hex[:8]}",
        "agent_name": f"Agent-{platform.node()}",
        "agent_pool": "default",
        "capabilities": ["shell", "python"],
        "max_parallel_jobs": 2,
        "heartbeat_interval": 30,
        "poll_interval": 10
    }


def main():
    parser = argparse.ArgumentParser(description='Job Scheduler Agent Client')
    parser.add_argument('--config', '-c', default='agent_config.json', 
                       help='Configuration file path')
    parser.add_argument('--scheduler-url', '-s', 
                       help='Job Scheduler URL (overrides config)')
    parser.add_argument('--agent-id', '-i', 
                       help='Agent ID (overrides config)')
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Override with command line arguments
    if args.scheduler_url:
        config['scheduler_url'] = args.scheduler_url
    if args.agent_id:
        config['agent_id'] = args.agent_id
    
    print("="*60)
    print("JOB SCHEDULER AGENT CLIENT")
    print("="*60)
    print(f"Agent ID: {config['agent_id']}")
    print(f"Scheduler URL: {config['scheduler_url']}")
    print(f"Agent Pool: {config['agent_pool']}")
    print(f"Capabilities: {', '.join(config['capabilities'])}")
    print(f"Max Parallel Jobs: {config['max_parallel_jobs']}")
    print("-"*60)
    
    # Create and run agent
    agent = JobSchedulerAgent(config)
    
    try:
        agent.run()
    except KeyboardInterrupt:
        print("\n\nAgent stopped by user")
    except Exception as e:
        print(f"Agent error: {e}")


if __name__ == "__main__":
    main()