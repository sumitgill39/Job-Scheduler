"""
CLI Manager for Windows Job Scheduler
Interactive command-line interface for managing jobs
"""

import os
import sys
import cmd
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import colorama
from colorama import Fore, Back, Style
from tabulate import tabulate

from core.scheduler_manager import SchedulerManager
from core.job_base import JobStatus
from utils.logger import get_logger
from utils.validators import JobValidator
from utils.windows_utils import WindowsUtils


class CLIManager(cmd.Cmd):
    """Interactive CLI for Windows Job Scheduler"""
    
    intro = f"""
{Fore.CYAN}{'='*60}
{Fore.YELLOW}    Windows Job Scheduler - Command Line Interface
{Fore.CYAN}{'='*60}{Style.RESET_ALL}

Welcome to the Windows Job Scheduler CLI!
Type 'help' or '?' to list available commands.
Type 'help <command>' for detailed help on a specific command.
Type 'quit' or 'exit' to exit the CLI.

{Fore.GREEN}Quick Start:
  - list                    : Show all jobs
  - create sql             : Create a new SQL job
  - create powershell      : Create a new PowerShell job
  - status                 : Show scheduler status
  - run <job_id>           : Run a job immediately{Style.RESET_ALL}
"""
    
    prompt = f'{Fore.CYAN}JobScheduler> {Style.RESET_ALL}'
    
    def __init__(self, scheduler_manager: SchedulerManager):
        super().__init__()
        
        # Initialize colorama for Windows
        colorama.init(autoreset=True)
        
        self.scheduler_manager = scheduler_manager
        self.logger = get_logger(__name__)
        self.validator = JobValidator()
        self.windows_utils = WindowsUtils()
        self._running = False
        
        # CLI state
        self.current_job_id = None
        self.last_command_success = True
        
        self.logger.info("CLI Manager initialized")
    
    def start(self):
        """Start the CLI interface"""
        self._running = True
        self.logger.info("Starting CLI interface")
        
        try:
            self.cmdloop()
        except KeyboardInterrupt:
            self.do_quit(None)
        except Exception as e:
            self.logger.error(f"CLI error: {e}")
            print(f"{Fore.RED}CLI Error: {e}{Style.RESET_ALL}")
    
    def stop(self):
        """Stop the CLI interface"""
        self._running = False
        self.logger.info("CLI interface stopped")
    
    # Utility Methods
    
    def _print_success(self, message: str):
        """Print success message"""
        print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")
        self.last_command_success = True
    
    def _print_error(self, message: str):
        """Print error message"""
        print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")
        self.last_command_success = False
    
    def _print_warning(self, message: str):
        """Print warning message"""
        print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")
    
    def _print_info(self, message: str):
        """Print info message"""
        print(f"{Fore.CYAN}ℹ {message}{Style.RESET_ALL}")
    
    def _format_table(self, data: List[Dict], headers: List[str] = None) -> str:
        """Format data as table"""
        if not data:
            return "No data to display"
        
        if headers is None:
            headers = list(data[0].keys()) if data else []
        
        # Format data for table
        table_data = []
        for row in data:
            table_row = []
            for header in headers:
                value = row.get(header, '')
                if isinstance(value, bool):
                    value = "Yes" if value else "No"
                elif isinstance(value, datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                elif value is None:
                    value = "N/A"
                table_row.append(str(value))
            table_data.append(table_row)
        
        return tabulate(table_data, headers=headers, tablefmt="grid")
    
    def _get_user_input(self, prompt: str, required: bool = True, default: str = None) -> Optional[str]:
        """Get user input with validation"""
        full_prompt = prompt
        if default:
            full_prompt += f" [{default}]"
        full_prompt += ": "
        
        try:
            value = input(full_prompt).strip()
            
            if not value and default:
                value = default
            
            if required and not value:
                self._print_error("This field is required")
                return None
            
            return value
        except KeyboardInterrupt:
            print("\nOperation cancelled")
            return None
    
    def _get_user_choice(self, prompt: str, choices: List[str], default: str = None) -> Optional[str]:
        """Get user choice from list"""
        choice_str = "/".join(choices)
        if default:
            choice_str = choice_str.replace(default, default.upper())
        
        full_prompt = f"{prompt} ({choice_str})"
        
        while True:
            value = self._get_user_input(full_prompt, required=False, default=default)
            if value is None:
                return None
            
            if value.lower() in [c.lower() for c in choices]:
                return value.lower()
            
            self._print_error(f"Invalid choice. Please select from: {', '.join(choices)}")
    
    # Command: quit/exit
    
    def do_quit(self, args):
        """Exit the CLI"""
        print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}")
        self._running = False
        return True
    
    def do_exit(self, args):
        """Exit the CLI"""
        return self.do_quit(args)
    
    def do_EOF(self, args):
        """Handle Ctrl+D"""
        return self.do_quit(args)
    
    # Command: clear
    
    def do_clear(self, args):
        """Clear the screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    # Command: status
    
    def do_status(self, args):
        """Show scheduler status"""
        try:
            status = self.scheduler_manager.get_scheduler_status()
            
            print(f"\n{Fore.CYAN}Scheduler Status:{Style.RESET_ALL}")
            print(f"Running: {Fore.GREEN if status['running'] else Fore.RED}{status['running']}{Style.RESET_ALL}")
            print(f"Total Jobs: {status['total_jobs']}")
            print(f"Scheduled Jobs: {status['scheduled_jobs']}")
            print(f"Enabled Jobs: {status['enabled_jobs']}")
            print(f"Disabled Jobs: {status['disabled_jobs']}")
            
            if status.get('job_types'):
                print(f"\nJob Types:")
                for job_type, count in status['job_types'].items():
                    print(f"  {job_type}: {count}")
            
            if status.get('next_run_times'):
                print(f"\n{Fore.CYAN}Next Scheduled Jobs:{Style.RESET_ALL}")
                headers = ['Job Name', 'Type', 'Next Run Time']
                table_data = []
                for job_info in status['next_run_times'][:5]:  # Show next 5
                    table_data.append([
                        job_info['job_name'],
                        job_info['job_type'],
                        job_info['next_run_time']
                    ])
                print(self._format_table(table_data, headers))
            
            self._print_success("Status retrieved successfully")
            
        except Exception as e:
            self._print_error(f"Failed to get status: {e}")
    
    # Command: list
    
    def do_list(self, args):
        """List all jobs
        Usage: list [enabled|disabled|running]
        """
        try:
            jobs = self.scheduler_manager.get_all_jobs()
            
            if not jobs:
                self._print_info("No jobs found")
                return
            
            # Filter jobs based on argument
            filter_type = args.strip().lower() if args else None
            filtered_jobs = []
            
            for job in jobs.values():
                if filter_type == "enabled" and not job.enabled:
                    continue
                elif filter_type == "disabled" and job.enabled:
                    continue
                elif filter_type == "running" and not job.is_running:
                    continue
                
                filtered_jobs.append({
                    'ID': job.job_id[:8] + "...",  # Truncate for display
                    'Name': job.name,
                    'Type': job.job_type,
                    'Status': job.current_status.value,
                    'Enabled': job.enabled,
                    'Running': job.is_running,
                    'Last Run': job.last_run_time.strftime("%m-%d %H:%M") if job.last_run_time else "Never"
                })
            
            if not filtered_jobs:
                self._print_info(f"No {filter_type or ''} jobs found")
                return
            
            title = f"Jobs ({filter_type or 'all'})" if filter_type else "All Jobs"
            print(f"\n{Fore.CYAN}{title}:{Style.RESET_ALL}")
            print(self._format_table(filtered_jobs))
            
        except Exception as e:
            self._print_error(f"Failed to list jobs: {e}")
    
    def help_list(self):
        print("List jobs in the scheduler")
        print("Usage: list [filter]")
        print("Filters:")
        print("  enabled  - Show only enabled jobs")
        print("  disabled - Show only disabled jobs") 
        print("  running  - Show only currently running jobs")
        print("  (no filter) - Show all jobs")
    
    # Command: show
    
    def do_show(self, args):
        """Show detailed information about a job
        Usage: show <job_id>
        """
        if not args:
            self._print_error("Please provide a job ID")
            return
        
        job_id = args.strip()
        
        try:
            # Try to find job by partial ID or name
            jobs = self.scheduler_manager.get_all_jobs()
            target_job = None
            
            for jid, job in jobs.items():
                if jid == job_id or jid.startswith(job_id) or job.name == job_id:
                    target_job = job
                    job_id = jid
                    break
            
            if not target_job:
                self._print_error(f"Job not found: {job_id}")
                return
            
            # Get detailed status
            status = self.scheduler_manager.get_job_status(job_id)
            
            print(f"\n{Fore.CYAN}Job Details:{Style.RESET_ALL}")
            print(f"ID: {status['job_id']}")
            print(f"Name: {status['name']}")
            print(f"Type: {status['job_type']}")
            print(f"Enabled: {Fore.GREEN if status['enabled'] else Fore.RED}{status['enabled']}{Style.RESET_ALL}")
            print(f"Current Status: {self._format_status(status['current_status'])}")
            print(f"Running: {Fore.GREEN if status['is_running'] else Fore.YELLOW}{status['is_running']}{Style.RESET_ALL}")
            print(f"Last Run: {status['last_run_time'] or 'Never'}")
            print(f"Next Run: {status['next_run_time'] or 'Not scheduled'}")
            print(f"Retry Count: {status['retry_count']}/{status['max_retries']}")
            
            # Show job-specific details
            if target_job.job_type == 'sql':
                print(f"\nSQL Query: {target_job.sql_query[:100]}{'...' if len(target_job.sql_query) > 100 else ''}")
                print(f"Connection: {target_job.connection_name}")
            elif target_job.job_type == 'powershell':
                if target_job.script_path:
                    print(f"\nScript Path: {target_job.script_path}")
                else:
                    print(f"\nScript Content: {len(target_job.script_content)} characters")
                print(f"Parameters: {target_job.parameters}")
            
            # Show last execution result
            if status.get('last_result'):
                result = status['last_result']
                print(f"\n{Fore.CYAN}Last Execution:{Style.RESET_ALL}")
                print(f"Status: {self._format_status(result['status'])}")
                print(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
                if result.get('error_message'):
                    print(f"Error: {Fore.RED}{result['error_message'][:200]}{Style.RESET_ALL}")
            
            self.current_job_id = job_id
            self._print_success(f"Showing details for job: {status['name']}")
            
        except Exception as e:
            self._print_error(f"Failed to show job details: {e}")
    
    def _format_status(self, status: str) -> str:
        """Format job status with colors"""
        color_map = {
            'success': Fore.GREEN,
            'running': Fore.BLUE,
            'failed': Fore.RED,
            'pending': Fore.YELLOW,
            'cancelled': Fore.MAGENTA,
            'timeout': Fore.RED,
            'retry': Fore.YELLOW
        }
        
        color = color_map.get(status.lower(), Fore.WHITE)
        return f"{color}{status}{Style.RESET_ALL}"
    
    # Command: create
    
    def do_create(self, args):
        """Create a new job
        Usage: create sql|powershell
        """
        if not args:
            job_type = self._get_user_choice("Select job type", ["sql", "powershell"])
        else:
            job_type = args.strip().lower()
        
        if job_type not in ["sql", "powershell"]:
            self._print_error("Invalid job type. Use 'sql' or 'powershell'")
            return
        
        try:
            if job_type == "sql":
                self._create_sql_job()
            elif job_type == "powershell":
                self._create_powershell_job()
                
        except KeyboardInterrupt:
            print("\nJob creation cancelled")
        except Exception as e:
            self._print_error(f"Failed to create job: {e}")
    
    def _create_sql_job(self):
        """Interactive SQL job creation"""
        print(f"\n{Fore.CYAN}Creating SQL Job{Style.RESET_ALL}")
        
        # Get basic information
        name = self._get_user_input("Job name", required=True)
        if not name:
            return
        
        description = self._get_user_input("Description", required=False)
        
        # Get SQL query
        print("\nEnter SQL query (end with empty line):")
        query_lines = []
        while True:
            line = input()
            if not line:
                break
            query_lines.append(line)
        
        sql_query = "\n".join(query_lines)
        if not sql_query.strip():
            self._print_error("SQL query is required")
            return
        
        # Validate query
        validation = self.validator.validate_sql_query(sql_query)
        if not validation['valid']:
            self._print_error(f"SQL validation failed: {validation['error']}")
            return
        
        # Get connection
        connection_name = self._get_user_input("Connection name", default="default")
        
        # Get schedule
        schedule = self._get_schedule_config()
        
        # Create job
        try:
            job_id = self.scheduler_manager.create_sql_job(
                name=name,
                description=description,
                sql_query=sql_query,
                connection_name=connection_name,
                schedule=schedule
            )
            
            if job_id:
                self._print_success(f"SQL job created successfully: {name} ({job_id[:8]}...)")
                self.current_job_id = job_id
            else:
                self._print_error("Failed to create SQL job")
                
        except Exception as e:
            self._print_error(f"Error creating SQL job: {e}")
    
    def _create_powershell_job(self):
        """Interactive PowerShell job creation"""
        print(f"\n{Fore.CYAN}Creating PowerShell Job{Style.RESET_ALL}")
        
        # Get basic information
        name = self._get_user_input("Job name", required=True)
        if not name:
            return
        
        description = self._get_user_input("Description", required=False)
        
        # Choose script type
        script_type = self._get_user_choice("Script type", ["file", "inline"], default="inline")
        if not script_type:
            return
        
        script_path = None
        script_content = None
        
        if script_type == "file":
            script_path = self._get_user_input("Script file path", required=True)
            if not script_path or not os.path.exists(script_path):
                self._print_error("Script file not found")
                return
        else:
            print("\nEnter PowerShell script (end with empty line):")
            script_lines = []
            while True:
                line = input()
                if not line:
                    break
                script_lines.append(line)
            
            script_content = "\n".join(script_lines)
            if not script_content.strip():
                self._print_error("Script content is required")
                return
        
        # Get parameters
        parameters_str = self._get_user_input("Parameters (space-separated)", required=False)
        parameters = parameters_str.split() if parameters_str else []
        
        # Get schedule
        schedule = self._get_schedule_config()
        
        # Create job
        try:
            job_id = self.scheduler_manager.create_powershell_job(
                name=name,
                description=description,
                script_path=script_path,
                script_content=script_content,
                parameters=parameters,
                schedule=schedule
            )
            
            if job_id:
                self._print_success(f"PowerShell job created successfully: {name} ({job_id[:8]}...)")
                self.current_job_id = job_id
            else:
                self._print_error("Failed to create PowerShell job")
                
        except Exception as e:
            self._print_error(f"Error creating PowerShell job: {e}")
    
    def _get_schedule_config(self) -> Optional[Dict[str, Any]]:
        """Get schedule configuration from user"""
        schedule_now = self._get_user_choice("Schedule this job", ["yes", "no"], default="no")
        
        if schedule_now != "yes":
            return None
        
        schedule_type = self._get_user_choice("Schedule type", ["cron", "interval", "once"], default="cron")
        
        if schedule_type == "cron":
            cron_expr = self._get_user_input("Cron expression (sec min hour day month dow)", required=True)
            if cron_expr:
                validation = self.validator.validate_cron_expression(cron_expr)
                if validation['valid']:
                    return {"type": "cron", "cron": cron_expr}
                else:
                    self._print_error(f"Invalid cron expression: {validation['error']}")
        
        elif schedule_type == "interval":
            minutes = self._get_user_input("Interval in minutes", required=True)
            try:
                minutes = int(minutes)
                return {
                    "type": "interval",
                    "interval": {"minutes": minutes}
                }
            except ValueError:
                self._print_error("Invalid interval")
        
        elif schedule_type == "once":
            run_time = self._get_user_input("Run time (YYYY-MM-DD HH:MM:SS)", required=True)
            try:
                run_date = datetime.strptime(run_time, "%Y-%m-%d %H:%M:%S")
                return {
                    "type": "date",
                    "run_date": run_date.isoformat()
                }
            except ValueError:
                self._print_error("Invalid date format")
        
        return None
    
    # Command: run
    
    def do_run(self, args):
        """Run a job immediately
        Usage: run <job_id>
        """
        job_id = args.strip() if args else self.current_job_id
        
        if not job_id:
            self._print_error("Please provide a job ID or use 'show' command first")
            return
        
        # Find job
        jobs = self.scheduler_manager.get_all_jobs()
        target_job_id = None
        
        for jid, job in jobs.items():
            if jid == job_id or jid.startswith(job_id) or job.name == job_id:
                target_job_id = jid
                break
        
        if not target_job_id:
            self._print_error(f"Job not found: {job_id}")
            return
        
        try:
            print(f"Running job: {jobs[target_job_id].name}")
            result = self.scheduler_manager.run_job_once(target_job_id)
            
            if result:
                print(f"\n{Fore.CYAN}Execution Result:{Style.RESET_ALL}")
                print(f"Status: {self._format_status(result.status.value)}")
                print(f"Duration: {result.duration_seconds:.2f} seconds")
                
                if result.output:
                    print(f"Output:\n{result.output[:500]}{'...' if len(result.output) > 500 else ''}")
                
                if result.error_message:
                    print(f"Error: {Fore.RED}{result.error_message}{Style.RESET_ALL}")
                
                if result.status.value == "success":
                    self._print_success("Job completed successfully")
                else:
                    self._print_error(f"Job failed with status: {result.status.value}")
            else:
                self._print_error("Failed to run job")
                
        except Exception as e:
            self._print_error(f"Error running job: {e}")
    
    # Command: history
    
    def do_history(self, args):
        """Show execution history for a job
        Usage: history <job_id> [limit]
        """
        parts = args.strip().split() if args else []
        job_id = parts[0] if parts else self.current_job_id
        limit = int(parts[1]) if len(parts) > 1 else 10
        
        if not job_id:
            self._print_error("Please provide a job ID")
            return
        
        try:
            history = self.scheduler_manager.get_execution_history(job_id, limit)
            
            if not history:
                self._print_info(f"No execution history found for job: {job_id}")
                return
            
            print(f"\n{Fore.CYAN}Execution History (last {len(history)} runs):{Style.RESET_ALL}")
            
            table_data = []
            for execution in reversed(history[-limit:]):  # Show most recent first
                table_data.append([
                    execution.get('start_time', '')[:16],  # Truncate timestamp
                    self._format_status(execution.get('status', '')),
                    f"{execution.get('duration_seconds', 0):.1f}s",
                    execution.get('error_message', '')[:50] if execution.get('error_message') else 'OK'
                ])
            
            headers = ['Start Time', 'Status', 'Duration', 'Result']
            print(self._format_table(table_data, headers))
            
        except Exception as e:
            self._print_error(f"Failed to get history: {e}")
    
    # Command: delete
    
    def do_delete(self, args):
        """Delete a job
        Usage: delete <job_id>
        """
        job_id = args.strip() if args else self.current_job_id
        
        if not job_id:
            self._print_error("Please provide a job ID")
            return
        
        # Find and confirm
        jobs = self.scheduler_manager.get_all_jobs()
        target_job = None
        target_job_id = None
        
        for jid, job in jobs.items():
            if jid == job_id or jid.startswith(job_id) or job.name == job_id:
                target_job = job
                target_job_id = jid
                break
        
        if not target_job:
            self._print_error(f"Job not found: {job_id}")
            return
        
        # Confirm deletion
        confirm = self._get_user_choice(f"Delete job '{target_job.name}'", ["yes", "no"], default="no")
        if confirm != "yes":
            print("Delete cancelled")
            return
        
        try:
            success = self.scheduler_manager.remove_job(target_job_id)
            
            if success:
                self._print_success(f"Job deleted: {target_job.name}")
                if self.current_job_id == target_job_id:
                    self.current_job_id = None
            else:
                self._print_error("Failed to delete job")
                
        except Exception as e:
            self._print_error(f"Error deleting job: {e}")
    
    # Command: enable/disable
    
    def do_enable(self, args):
        """Enable a job
        Usage: enable <job_id>
        """
        self._toggle_job(args, True)
    
    def do_disable(self, args):
        """Disable a job
        Usage: disable <job_id>
        """
        self._toggle_job(args, False)
    
    def _toggle_job(self, args: str, enabled: bool):
        """Enable or disable a job"""
        job_id = args.strip() if args else self.current_job_id
        
        if not job_id:
            self._print_error("Please provide a job ID")
            return
        
        try:
            if enabled:
                success = self.scheduler_manager.resume_job(job_id)
                action = "enabled"
            else:
                success = self.scheduler_manager.pause_job(job_id)
                action = "disabled"
            
            if success:
                self._print_success(f"Job {action} successfully")
            else:
                self._print_error(f"Failed to {action[:-1]} job")
                
        except Exception as e:
            self._print_error(f"Error {action[:-1]}ing job: {e}")
    
    # Help methods
    
    def help_create(self):
        print("Create a new job")
        print("Usage: create [sql|powershell]")
        print("If no type specified, you will be prompted to choose")
        print("The command will guide you through interactive job creation")
    
    def help_show(self):
        print("Show detailed information about a job")
        print("Usage: show <job_id>")
        print("You can use partial job ID or job name")
        print("This also sets the current job for other commands")
    
    def help_run(self):
        print("Run a job immediately")
        print("Usage: run [job_id]")
        print("If no job_id provided, uses the current job from 'show' command")


if __name__ == "__main__":
    # Test CLI manager
    from core.scheduler_manager import SchedulerManager
    
    scheduler = SchedulerManager("yaml")
    cli = CLIManager(scheduler)
    
    try:
        scheduler.start()
        cli.start()
    finally:
        scheduler.stop()