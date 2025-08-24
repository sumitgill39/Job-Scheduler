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
        """Initialize logging system with enhanced crash diagnosis"""
        try:
            # Use DEBUG level for comprehensive logging during crash investigation
            self.logger = setup_logger("JobScheduler", "DEBUG")
            self.logger.info("=" * 80)
            self.logger.info("🚀 WINDOWS JOB SCHEDULER STARTING - ENHANCED LOGGING MODE")
            self.logger.info("=" * 80)
            self.logger.debug(f"Python version: {sys.version}")
            self.logger.debug(f"Platform: {sys.platform}")
            self.logger.debug(f"Process ID: {os.getpid()}")
            self.logger.debug(f"Working directory: {os.getcwd()}")
            self.logger.debug(f"Command line args: {sys.argv}")
            self.logger.info("📋 Logging system initialized successfully")
        except Exception as e:
            print(f"💥 CRITICAL: Failed to initialize logging: {e}")
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
        """Initialize scheduler manager with enhanced logging"""
        try:
            self.logger.info("⏰ Initializing Scheduler Manager...")
            
            # Determine storage type from config or default to YAML
            storage_type = "yaml"  # Can be configured later
            storage_config = {
                "yaml_file": str(Path("config") / "jobs.yaml"),
                "history_file": str(Path("config") / "job_history.yaml")
            }
            
            self.logger.debug(f"📁 Storage type: {storage_type}")
            self.logger.debug(f"📁 Storage config: {storage_config}")
            
            self.scheduler_manager = SchedulerManager(storage_type, storage_config)
            self.logger.info("✅ Scheduler manager initialized successfully")
            
        except Exception as e:
            self.logger.error(f"💥 CRITICAL: Failed to initialize scheduler: {e}")
            import traceback
            self.logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
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
        """Start the application with comprehensive crash detection"""
        try:
            self.logger.info("🚀 STARTING APPLICATION...")
            self.logger.info(f"📋 Mode: {self.mode}")
            
            # Setup signal handlers
            self.logger.debug("🔧 Setting up signal handlers...")
            self.setup_signal_handlers()
            self.logger.debug("✅ Signal handlers configured")
            
            # Start scheduler
            self.logger.info("⏰ Starting scheduler manager...")
            self.scheduler_manager.start()
            self.logger.info("✅ Scheduler started successfully")
            
            if self.mode == "cli":
                self.logger.info("💻 Running in CLI mode")
                self._run_cli_mode()
            elif self.mode == "web":
                self.logger.info("🌐 Running in WEB mode")
                self._run_web_mode()
            elif self.mode == "both":
                self.logger.info("🔄 Running in BOTH CLI+WEB mode")
                self._run_both_modes()
            else:
                self.logger.error(f"💥 CRITICAL: Unknown mode: {self.mode}")
                sys.exit(1)
                
        except KeyboardInterrupt:
            self.logger.info("⌨️  Keyboard interrupt received - graceful shutdown")
            self.shutdown()
        except Exception as e:
            self.logger.error(f"💥 CRITICAL ERROR starting application: {e}")
            import traceback
            self.logger.error(f"🔍 Full stack trace: {traceback.format_exc()}")
            self.logger.error("🛑 APPLICATION WILL EXIT")
            sys.exit(1)
    
    def _run_cli_mode(self):
        """Run in CLI-only mode"""
        self.logger.info("Starting CLI interface")
        self.cli_manager.start()
    
    def _run_web_mode(self):
        """Run in web-only mode with enhanced logging"""
        self.logger.info("🌐 Starting web interface...")
        
        # Get configuration
        host = "127.0.0.1"
        port = 5000
        debug = True
        
        try:
            import yaml
            config_path = Path("config/config.yaml")
            self.logger.debug(f"📁 Looking for config at: {config_path}")
            
            if config_path.exists():
                self.logger.debug("📄 Loading web configuration from file")
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    web_config = config.get('web', {})
                    host = web_config.get('host', host)
                    port = web_config.get('port', port)
                    debug = web_config.get('debug', debug)
                    self.logger.debug(f"⚙️  Loaded config: host={host}, port={port}, debug={debug}")
            else:
                self.logger.debug("📄 Using default web configuration")
        except Exception as e:
            self.logger.warning(f"⚠️  Could not load web config: {e}")
        
        self.logger.info(f"🌍 Web server starting on http://{host}:{port}")
        self.logger.info(f"🔧 Debug mode: {debug}")
        
        try:
            # Auto-open browser to API documentation as requested
            self._auto_open_browser(host, port)
            
            # Start web server
            self.logger.info("🚀 Starting Flask web server...")
            self.web_app.run(
                host=host,
                port=port,
                debug=debug,
                use_reloader=False,  # Disable reloader to avoid issues with scheduler
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"💥 CRITICAL: Web server failed to start: {e}")
            import traceback
            self.logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
            raise
    
    def _auto_open_browser(self, host, port):
        """Auto-open browser to main dashboard in a new tab"""
        try:
            import webbrowser
            import threading
            import time
            
            url = f"http://{host}:{port}/"
            self.logger.info(f"🌐 Auto-opening browser to main dashboard: {url}")
            
            def open_browser():
                # Wait a moment for the server to start
                time.sleep(2)
                try:
                    webbrowser.open_new_tab(url)
                    self.logger.info("✅ Browser opened successfully")
                except Exception as e:
                    self.logger.warning(f"⚠️  Could not auto-open browser: {e}")
            
            # Open browser in background thread to avoid blocking server startup
            browser_thread = threading.Thread(target=open_browser, daemon=True)
            browser_thread.start()
            
        except Exception as e:
            self.logger.warning(f"⚠️  Auto-open browser failed: {e}")
    
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
        """Graceful shutdown with comprehensive logging"""
        self.logger.info("🛑 INITIATING GRACEFUL SHUTDOWN...")
        self.logger.info("=" * 60)
        
        try:
            # Signal shutdown
            self.logger.debug("📢 Setting shutdown event...")
            self.shutdown_event.set()
            
            # Stop scheduler
            if self.scheduler_manager:
                self.logger.info("⏰ Stopping scheduler manager...")
                self.scheduler_manager.stop(wait=True)
                self.logger.info("✅ Scheduler stopped")
            else:
                self.logger.debug("ℹ️  No scheduler manager to stop")
            
            # Stop CLI if running
            if self.cli_manager:
                self.logger.info("💻 Stopping CLI manager...")
                self.cli_manager.stop()
                self.logger.info("✅ CLI stopped")
            else:
                self.logger.debug("ℹ️  No CLI manager to stop")
            
            self.logger.info("🏁 SHUTDOWN COMPLETED SUCCESSFULLY")
            
        except Exception as e:
            self.logger.error(f"💥 Error during shutdown: {e}")
            import traceback
            self.logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        
        finally:
            self.logger.info("🔚 PROCESS EXITING...")
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
        from database.simple_connection_manager import get_database_manager
        
        db_manager = get_database_manager()
        test_result = db_manager.test_connection()
        
        status = "✓ SUCCESS" if test_result['success'] else "✗ FAILED"
        print(f"   system: {status}")
        if not test_result['success']:
            print(f"     Error: {test_result.get('error', 'Unknown error')}")
        else:
            print(f"     Response time: {test_result['response_time']:.2f}s")
        
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