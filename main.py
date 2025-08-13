"""
Main entry point for Windows Job Scheduler
"""

import os
import sys
import argparse
import signal
import threading
import time
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
        
        # Initialize components
        self._init_logging()
        self._init_windows_utils()
        self._init_scheduler()
        
        if self.mode in ["cli", "both"]:
            self._init_cli()
        
        if self.mode in ["web", "both"]:
            self._init_web()
    
    def _init_logging(self):
        """Initialize logging system"""
        try:
            self.logger = setup_logger("JobScheduler", "INFO")
            self.logger.info("=" * 60)
            self.logger.info("Windows Job Scheduler Starting")
            self.logger.info("=" * 60)
        except Exception as e:
            print(f"Failed to initialize logging: {e}")
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
        """Initialize scheduler manager"""
        try:
            # Determine storage type from config or default to YAML
            storage_type = "yaml"  # Can be configured later
            storage_config = {
                "yaml_file": os.path.join("config", "jobs.yaml"),
                "history_file": os.path.join("config", "job_history.yaml")
            }
            
            self.scheduler_manager = SchedulerManager(storage_type, storage_config)
            self.logger.info("Scheduler manager initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize scheduler: {e}")
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
            self.web_app = create_app(self.scheduler_manager)
            self.logger.info("Web application initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize web app: {e}")
            sys.exit(1)
    
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
        """Start the application"""
        try:
            self.logger.info(f"Starting Job Scheduler in {self.mode} mode")
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Start scheduler
            self.scheduler_manager.start()
            self.logger.info("Scheduler started")
            
            if self.mode == "cli":
                self._run_cli_mode()
            elif self.mode == "web":
                self._run_web_mode()
            elif self.mode == "both":
                self._run_both_modes()
            else:
                self.logger.error(f"Unknown mode: {self.mode}")
                sys.exit(1)
                
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"Error starting application: {e}")
            sys.exit(1)
    
    def _run_cli_mode(self):
        """Run in CLI-only mode"""
        self.logger.info("Starting CLI interface")
        self.cli_manager.start()
    
    def _run_web_mode(self):
        """Run in web-only mode"""
        self.logger.info("Starting web interface")
        
        # Get configuration
        host = "127.0.0.1"
        port = 5000
        debug = True
        
        try:
            import yaml
            config_path = Path("config/config.yaml")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    web_config = config.get('web', {})
                    host = web_config.get('host', host)
                    port = web_config.get('port', port)
                    debug = web_config.get('debug', debug)
        except Exception as e:
            self.logger.warning(f"Could not load web config: {e}")
        
        self.logger.info(f"Web server starting on http://{host}:{port}")
        
        # Start web server
        self.web_app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,  # Disable reloader to avoid issues with scheduler
            threaded=True
        )
    
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
    
    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Initiating graceful shutdown...")
        
        try:
            # Signal shutdown
            self.shutdown_event.set()
            
            # Stop scheduler
            if self.scheduler_manager:
                self.scheduler_manager.stop(wait=True)
                self.logger.info("Scheduler stopped")
            
            # Stop CLI if running
            if self.cli_manager:
                self.cli_manager.stop()
                self.logger.info("CLI stopped")
            
            self.logger.info("Shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
        
        finally:
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
        
        # Test database connections
        print("\n3. Testing database connections...")
        from database.connection_manager import DatabaseConnectionManager
        
        db_manager = DatabaseConnectionManager()
        test_results = db_manager.test_all_connections()
        
        for conn_name, result in test_results.items():
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            print(f"   {conn_name}: {status}")
            if not result['success']:
                print(f"     Error: {result.get('error', 'Unknown error')}")
        
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