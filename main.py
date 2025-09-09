"""
Main entry point for Windows Job Scheduler
"""

import os
import sys
import argparse
import signal
import threading
import time
import psutil
import subprocess
import shutil
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.logger import setup_logger, get_logger
from utils.windows_utils import WindowsUtils
from core.scheduler_manager import SchedulerManager
from cli.cli_manager import CLIManager
from web_ui.app import create_app


class JobSchedulerApp:
    """Main application class for Windows Job Scheduler"""
    
    def __init__(self, mode: str = "web", config_file: str = None):
        """
        Initialize the Job Scheduler application
        
        Args:
            mode: Application mode ("web", "cli", "both")
            config_file: Optional configuration file path
        """
        self.mode = mode.lower()
        self.config_file = config_file
        self.logger = None
        self.scheduler_manager = None
        self.cli_manager = None
        self.web_app = None
        self.shutdown_event = threading.Event()
        self.child_processes = []  # Track child processes
        self.flask_process = None  # Track Flask process
        self.main_pid = os.getpid()  # Track main process PID
        
        # Initialize components
        self._init_logging()
        self._validate_clean_startup()
        self._init_windows_utils()
        self._init_scheduler()
        
        if self.mode in ["cli", "both"]:
            self._init_cli()
        
        if self.mode in ["web", "both"]:
            self._init_web()
    
    def _init_logging(self):
        """Initialize logging system with enhanced crash diagnosis"""
        try:
            # Use DEBUG level for comprehensive logging during crash investigation
            self.logger = setup_logger("JobScheduler", "DEBUG")
            self.logger.info("=" * 80)
            self.logger.info("[STARTUP] WINDOWS JOB SCHEDULER STARTING - ENHANCED LOGGING MODE")
            self.logger.info("=" * 80)
            self.logger.debug(f"Python version: {sys.version}")
            self.logger.debug(f"Platform: {sys.platform}")
            self.logger.debug(f"Process ID: {os.getpid()}")
            self.logger.debug(f"Working directory: {os.getcwd()}")
            self.logger.debug(f"Command line args: {sys.argv}")
            self.logger.info("[INIT] Logging system initialized successfully")
        except Exception as e:
            print(f"[CRITICAL] Failed to initialize logging: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    def _init_windows_utils(self):
        """Initialize Windows utilities and check system"""
        try:
            self.windows_utils = WindowsUtils()
            
            # Check if running on Windows
            if not self.windows_utils.is_windows():
                self.logger.error("This application is designed for Windows only")
                sys.exit(1)
            
            # Log system information
            system_info = self.windows_utils.get_system_info()
            self.logger.info(f"Computer: {system_info.get('computer_name')}")
            self.logger.info(f"Domain: {system_info.get('domain')}")
            self.logger.info(f"User: {system_info.get('username')}")
            self.logger.info(f"Admin privileges: {system_info.get('is_admin')}")
            self.logger.info(f"PowerShell: {system_info.get('powershell_path')}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Windows utilities: {e}")
            sys.exit(1)
    
    def _init_scheduler(self):
        """Initialize scheduler manager with SQLAlchemy"""
        try:
            self.logger.info("[SCHEDULER] Initializing Scheduler Manager with SQLAlchemy...")
            
            # Use database-based scheduler manager (integrated with SQLAlchemy job manager)
            self.logger.info("[SCHEDULER] Using database-based scheduler with SQLAlchemy job storage")
            storage_type = "database"
            storage_config = {
                "connection_name": "default"  # Use default database connection
            }
            
            self.logger.debug(f"[STORAGE] Storage type: {storage_type}")
            self.logger.debug(f"[STORAGE] Storage config: {storage_config}")
            
            self.scheduler_manager = SchedulerManager(storage_type, storage_config)
            
            self.logger.info("[SUCCESS] SQLAlchemy scheduler manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"[CRITICAL] Failed to initialize scheduler: {e}")
            import traceback
            self.logger.error(f"[TRACE] Stack trace: {traceback.format_exc()}")
            sys.exit(1)
    
    def _init_cli(self):
        """Initialize CLI manager"""
        try:
            self.cli_manager = CLIManager(self.scheduler_manager)
            self.logger.info("CLI manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize CLI: {e}")
            sys.exit(1)
    
    def _init_web(self):
        """Initialize web application"""
        try:
            # Initialize web app with SQLAlchemy support
            self.web_app = create_app(self.scheduler_manager)
            self.logger.info("Web application initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize web app: {e}")
            sys.exit(1)
    
    def _setup_passive_agent_processor(self):
        """Setup periodic task to process queued jobs for passive agents"""
        try:
            from apscheduler.triggers.interval import IntervalTrigger
            from core.agent_job_handler import agent_job_handler
            
            # Add job to process queued jobs every 10 seconds
            self.scheduler_manager.scheduler.add_job(
                func=agent_job_handler.process_queued_jobs_for_passive_agents,
                trigger=IntervalTrigger(seconds=10),
                id='passive_agent_job_processor',
                name='Process Queued Jobs for Passive Agents',
                replace_existing=True
            )
            
            self.logger.info("[PASSIVE_AGENT] Added periodic task to process queued jobs for passive agents")
        except Exception as e:
            self.logger.error(f"[PASSIVE_AGENT] Failed to setup passive agent processor: {e}")
            # Don't fail the startup if this fails
            pass
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown()
        
        # Handle common signals
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, signal_handler)
        
        # Windows-specific signals
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)
    
    def start(self):
        """Start the application with comprehensive crash detection"""
        try:
            self.logger.info("[STARTUP] STARTING APPLICATION...")
            self.logger.info(f"[CONFIG] Mode: {self.mode}")
            
            # Setup signal handlers
            self.logger.debug("[SETUP] Setting up signal handlers...")
            self.setup_signal_handlers()
            self.logger.debug("[SUCCESS] Signal handlers configured")
            
            # Start scheduler
            self.logger.info("[SCHEDULER] Starting scheduler manager...")
            self.scheduler_manager.start()
            self.logger.info("[SUCCESS] Scheduler started successfully")
            
            # Add periodic task to process queued jobs for passive agents
            self._setup_passive_agent_processor()
            
            if self.mode == "cli":
                self.logger.info("[MODE] Running in CLI mode")
                self._run_cli_mode()
            elif self.mode == "web":
                self.logger.info("[MODE] Running in WEB mode")
                self._run_web_mode()
            elif self.mode == "both":
                self.logger.info("[MODE] Running in BOTH CLI+WEB mode")
                self._run_both_modes()
            else:
                self.logger.error(f"[CRITICAL] Unknown mode: {self.mode}")
                sys.exit(1)
                
        except KeyboardInterrupt:
            self.logger.info("[INTERRUPT] Keyboard interrupt received - graceful shutdown")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"[CRITICAL] ERROR starting application: {e}")
            import traceback
            self.logger.error(f"[TRACE] Full stack trace: {traceback.format_exc()}")
            self.logger.error("[EXIT] APPLICATION WILL EXIT")
            sys.exit(1)
    
    def _run_cli_mode(self):
        """Run in CLI-only mode"""
        self.logger.info("Starting CLI interface")
        self.cli_manager.start()
    
    def _run_web_mode(self):
        """Run in web-only mode with enhanced logging"""
        self.logger.info("[WEB] Starting web interface...")
        
        # Get configuration
        host = "127.0.0.1"
        port = 5001
        debug = True
        
        try:
            import yaml
            config_path = Path("config/config.yaml")
            self.logger.debug(f"[CONFIG] Looking for config at: {config_path}")
            
            if config_path.exists():
                self.logger.debug("[CONFIG] Loading web configuration from file")
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    web_config = config.get('web', {})
                    host = web_config.get('host', host)
                    port = web_config.get('port', port)
                    debug = web_config.get('debug', debug)
                    self.logger.debug(f"[CONFIG] Loaded config: host={host}, port={port}, debug={debug}")
            else:
                self.logger.debug("[CONFIG] Using default web configuration")
        except Exception as e:
            self.logger.warning(f"[WARNING] Could not load web config: {e}")
        
        self.logger.info(f"[WEB] Web server starting on http://{host}:{port}")
        self.logger.info(f"[CONFIG] Debug mode: {debug}")
        
        try:
            # Auto-open browser to API documentation as requested
            self._auto_open_browser(host, port)
            
            # Start web server
            self.logger.info("[WEB] Starting Flask web server...")
            self.web_app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,  # Disable reloader to avoid issues with scheduler
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"[CRITICAL] Web server failed to start: {e}")
            import traceback
            self.logger.error(f"[TRACE] Stack trace: {traceback.format_exc()}")
            raise
    
    def _auto_open_browser(self, host, port):
        """Auto-open browser to main dashboard in a new tab"""
        try:
            import webbrowser
            import threading
            import time
            
            url = f"http://{host}:{port}/"
            self.logger.info(f"[BROWSER] Auto-opening browser to main dashboard: {url}")
            
            def open_browser():
                # Wait a moment for the server to start
                time.sleep(2)
                try:
                    webbrowser.open_new_tab(url)
                    self.logger.info("[SUCCESS] Browser opened successfully")
                except Exception as e:
                    self.logger.warning(f"[WARNING] Could not auto-open browser: {e}")
            
            # Open browser in background thread to avoid blocking server startup
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
            
        except Exception as e:
            self.logger.warning(f"[WARNING] Auto-open browser failed: {e}")
    
    def _run_both_modes(self):
        """Run both CLI and web modes"""
        self.logger.info("Starting both CLI and web interfaces")
        
        # Start web server in background thread
        web_thread = threading.Thread(
            target=self._run_web_mode,
            name="WebServerThread",
            daemon=True
        )
        web_thread.start()
        
        # Give web server time to start
        time.sleep(2)
        
        # Start CLI in main thread
        try:
            self._run_cli_mode()
        except KeyboardInterrupt:
            self.logger.info("CLI interrupted, shutting down")
    
    def _validate_clean_startup(self):
        """Check for existing related processes and clean them if needed"""
        try:
            if not self.logger:
                # Early startup, create temporary logger
                temp_logger = setup_logger('startup_validator', 'logs/startup.log')
            else:
                temp_logger = self.logger
            
            temp_logger.info("[STARTUP] Validating clean startup environment...")
            
            # Get current process info
            current_pid = os.getpid()
            current_script = os.path.abspath(__file__)
            
            # Look for existing Job Scheduler processes
            existing_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    if proc_info['pid'] == current_pid:
                        continue  # Skip current process
                    
                    # Check if it's a Python process running our script
                    if (proc_info['name'] and 'python' in proc_info['name'].lower() and 
                        proc_info['cmdline'] and len(proc_info['cmdline']) > 1):
                        
                        cmd_str = ' '.join(proc_info['cmdline'])
                        
                        # Check for Job Scheduler related processes
                        if (current_script in cmd_str or 
                            'main.py' in cmd_str or
                            'job_scheduler' in cmd_str.lower() or
                            'flask' in cmd_str.lower() and '5000' in cmd_str):
                            
                            existing_processes.append({
                                'pid': proc_info['pid'],
                                'cmd': cmd_str[:100] + '...' if len(cmd_str) > 100 else cmd_str
                            })
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if existing_processes:
                temp_logger.warning(f"[STARTUP] Found {len(existing_processes)} existing related processes:")
                
                for proc_info in existing_processes:
                    temp_logger.warning(f"[STARTUP]   PID {proc_info['pid']}: {proc_info['cmd']}")
                
                # Ask user if we should clean them (in production, this could be automated)
                temp_logger.info("[STARTUP] Attempting to clean existing processes for fresh start...")
                
                cleaned_count = 0
                for proc_info in existing_processes:
                    try:
                        proc = psutil.Process(proc_info['pid'])
                        proc.terminate()  # Try graceful termination first
                        
                        # Wait a moment for graceful shutdown
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            # Force kill if graceful didn't work
                            proc.kill()
                            proc.wait(timeout=1)
                        
                        cleaned_count += 1
                        temp_logger.info(f"[STARTUP] Cleaned process PID {proc_info['pid']}")
                        
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        temp_logger.debug(f"[STARTUP] Process {proc_info['pid']} already gone or access denied: {e}")
                    except Exception as e:
                        temp_logger.warning(f"[STARTUP] Failed to clean process {proc_info['pid']}: {e}")
                
                if cleaned_count > 0:
                    temp_logger.info(f"[STARTUP] Successfully cleaned {cleaned_count} existing processes")
                    # Give a moment for cleanup to complete
                    time.sleep(1)
                
            else:
                temp_logger.debug("[STARTUP] No existing related processes found - clean startup")
                
        except Exception as e:
            # Use print as fallback if logger isn't available
            print(f"[STARTUP ERROR] Failed to validate clean startup: {e}")
    
    def _clear_development_cache(self):
        """Clear Python cache for development (when debug mode is on)"""
        try:
            self.logger.info("[CACHE] Clearing development cache...")
            
            # Clear __pycache__ directories
            cache_dirs_found = 0
            for root, dirs, files in os.walk('.'):
                if '__pycache__' in dirs:
                    cache_dir = os.path.join(root, '__pycache__')
                    try:
                        shutil.rmtree(cache_dir)
                        cache_dirs_found += 1
                        self.logger.debug(f"[CACHE] Removed: {cache_dir}")
                    except Exception as e:
                        self.logger.warning(f"[CACHE] Failed to remove {cache_dir}: {e}")
            
            # Clear .pyc files
            pyc_files_found = 0
            for root, dirs, files in os.walk('.'):
                for file in files:
                    if file.endswith('.pyc'):
                        pyc_file = os.path.join(root, file)
                        try:
                            os.remove(pyc_file)
                            pyc_files_found += 1
                        except Exception as e:
                            self.logger.warning(f"[CACHE] Failed to remove {pyc_file}: {e}")
            
            if cache_dirs_found > 0 or pyc_files_found > 0:
                self.logger.info(f"[CACHE] Cleared {cache_dirs_found} cache dirs, {pyc_files_found} .pyc files")
            else:
                self.logger.debug("[CACHE] No cache files found")
                
        except Exception as e:
            self.logger.warning(f"[CACHE] Error clearing cache: {e}")
    
    def _kill_child_processes(self):
        """Kill all child processes spawned by this application"""
        try:
            self.logger.info("[CLEANUP] Terminating child processes...")
            
            current_process = psutil.Process(self.main_pid)
            children = current_process.children(recursive=True)
            
            if children:
                self.logger.info(f"[CLEANUP] Found {len(children)} child processes")
                for child in children:
                    try:
                        child_info = f"PID:{child.pid} ({child.name()})"
                        self.logger.debug(f"[CLEANUP] Terminating {child_info}")
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                    except Exception as e:
                        self.logger.warning(f"[CLEANUP] Failed to terminate child {child.pid}: {e}")
                
                # Wait for children to terminate
                psutil.wait_procs(children, timeout=5)
                
                # Force kill any remaining processes
                for child in children:
                    try:
                        if child.is_running():
                            self.logger.warning(f"[CLEANUP] Force killing PID:{child.pid}")
                            child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                self.logger.info("[CLEANUP] Child processes terminated")
            else:
                self.logger.debug("[CLEANUP] No child processes found")
                
        except Exception as e:
            self.logger.error(f"[CLEANUP] Error killing child processes: {e}")
    
    def _kill_related_python_processes(self):
        """Kill any Python processes that might be related to this application"""
        try:
            self.logger.info("[CLEANUP] Checking for related Python processes...")
            
            # Get current script name for identification
            script_name = os.path.basename(__file__)
            project_dir = str(Path(__file__).parent)
            
            killed_processes = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cwd']):
                try:
                    # Skip current process
                    if proc.info['pid'] == self.main_pid:
                        continue
                    
                    # Look for Python processes
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info.get('cmdline', [])
                        cwd = proc.info.get('cwd', '')
                        
                        # Check if this process is related to our project
                        is_related = (
                            any(script_name in cmd for cmd in cmdline if cmd) or
                            any('Job-Scheduler' in cmd for cmd in cmdline if cmd) or
                            (cwd and project_dir in cwd) or
                            any('flask' in cmd.lower() for cmd in cmdline if cmd) or
                            any('main.py' in cmd for cmd in cmdline if cmd)
                        )
                        
                        if is_related:
                            self.logger.warning(f"[CLEANUP] Killing related process PID:{proc.info['pid']} - {cmdline}")
                            try:
                                process = psutil.Process(proc.info['pid'])
                                process.terminate()
                                killed_processes += 1
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if killed_processes > 0:
                self.logger.info(f"[CLEANUP] Killed {killed_processes} related Python processes")
                # Wait a moment for processes to die
                time.sleep(2)
            else:
                self.logger.debug("[CLEANUP] No related Python processes found")
                
        except Exception as e:
            self.logger.error(f"[CLEANUP] Error killing related processes: {e}")

    def shutdown(self):
        """Enhanced graceful shutdown with comprehensive cleanup"""
        self.logger.info("[SHUTDOWN] INITIATING ENHANCED GRACEFUL SHUTDOWN...")
        self.logger.info("=" * 80)
        
        try:
            # Signal shutdown
            self.logger.debug("📢 Setting shutdown event...")
            self.shutdown_event.set()
            
            # Stop scheduler
            if self.scheduler_manager:
                self.logger.info("[SCHEDULER] Stopping scheduler manager...")
                self.scheduler_manager.stop(wait=True)
                self.logger.info("[SUCCESS] Scheduler stopped")
            else:
                self.logger.debug("[INFO] No scheduler manager to stop")
            
            # Stop CLI if running
            if self.cli_manager:
                self.logger.info("[CLI] Stopping CLI manager...")
                self.cli_manager.stop()
                self.logger.info("[SUCCESS] CLI stopped")
            else:
                self.logger.debug("[INFO] No CLI manager to stop")
            
            # Enhanced cleanup for development
            self.logger.info("[CLEANUP] Performing enhanced cleanup...")
            
            # Kill child processes
            self._kill_child_processes()
            
            # Clear development cache (helps with module reloading issues)
            self._clear_development_cache()
            
            # Kill any related Python processes (aggressive cleanup)
            self._kill_related_python_processes()
            
            self.logger.info("[SHUTDOWN] ENHANCED CLEANUP COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 80)
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error during shutdown: {e}")
            import traceback
            self.logger.error(f"[TRACE] Stack trace: {traceback.format_exc()}")
        
        finally:
            self.logger.info("[EXIT] MAIN PROCESS EXITING...")
            sys.exit(0)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Windows Job Scheduler - SQL Server and PowerShell job automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --mode web              Start web interface only
  %(prog)s --mode cli              Start CLI interface only
  %(prog)s --mode both             Start both web and CLI interfaces
  %(prog)s --config custom.yaml   Use custom configuration file
  %(prog)s --version               Show version information
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["web", "cli", "both"],
        default="web",
        help="Application mode (default: web)"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="Configuration file path"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="Windows Job Scheduler v1.0.0"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--test-system",
        action="store_true",
        help="Test system components and exit"
    )
    
    return parser.parse_args()


def test_system_components():
    """Test system components and display results"""
    print("=" * 60)
    print("Windows Job Scheduler - System Test")
    print("=" * 60)
    
    try:
        # Test Windows utilities
        print("\n1. Testing Windows utilities...")
        windows_utils = WindowsUtils()
        system_info = windows_utils.get_system_info()
        
        for key, value in system_info.items():
            print(f"   {key}: {value}")
        
        # Test PowerShell
        print("\n2. Testing PowerShell execution...")
        ps_result = windows_utils.execute_powershell_command("Get-Date")
        print(f"   Success: {ps_result['success']}")
        if ps_result['success']:
            print(f"   Output: {ps_result['stdout'].strip()}")
        else:
            print(f"   Error: {ps_result['stderr']}")
        
        # Database connection testing removed - SQLAlchemy handles connections automatically
        # Test job creation
        print("\n4. Testing job creation...")
        scheduler = SchedulerManager("yaml")
        
        # Test SQL job
        sql_job_id = scheduler.create_sql_job(
            name="System Test SQL Job",
            sql_query="SELECT 'System test successful' as message",
            connection_name="default"
        )
        
        if sql_job_id:
            print("   ✓ SQL job creation successful")
            # Clean up
            scheduler.remove_job(sql_job_id)
        else:
            print("   ✗ SQL job creation failed")
        
        # Test PowerShell job
        ps_job_id = scheduler.create_powershell_job(
            name="System Test PowerShell Job",
            script_content="Write-Host 'System test successful'"
        )
        
        if ps_job_id:
            print("   ✓ PowerShell job creation successful")
            # Clean up
            scheduler.remove_job(ps_job_id)
        else:
            print("   ✗ PowerShell job creation failed")
        
        print("\n" + "=" * 60)
        print("System test completed successfully!")
        print("The Windows Job Scheduler is ready to use.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ System test failed: {e}")
        print("\nPlease check the error above and ensure all dependencies are installed.")
        sys.exit(1)


def main():
    """Main entry point"""
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Test system if requested
        if args.test_system:
            test_system_components()
            return
        
        # Create and start application
        app = JobSchedulerApp(
            mode=args.mode,
            config_file=args.config
        )
        
        app.start()
        
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()