"""
Flask Web Application for Windows Job Scheduler
"""

import os
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from utils.logger import get_logger


def create_app(scheduler_manager=None):
    """Create and configure Flask application"""
    
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for simplicity
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    
    # Authentication Configuration
    app.config['AD_DOMAIN'] = os.environ.get('AD_DOMAIN', 'mgo.mersh.com')
    app.config['SESSION_TIMEOUT_MINUTES'] = int(os.environ.get('SESSION_TIMEOUT_MINUTES', '480'))  # 8 hours
    app.config['PERMANENT_SESSION_LIFETIME'] = app.config['SESSION_TIMEOUT_MINUTES'] * 60  # Convert to seconds
    
    # Initialize logger
    logger = get_logger(__name__)
    logger.info("Flask application created")
    
    # Track application start time for uptime calculation
    import time
    app._start_time = time.time()
    
    # Initialize global database connection pool and job manager (SINGLE INSTANCES)
    logger.info("🔧 Initializing Flask application components...")
    try:
        logger.debug("📦 Importing database and scheduler modules...")
        from database.connection_pool import get_connection_pool
        from core.job_manager import JobManager
        from core.integrated_scheduler import IntegratedScheduler
        
        logger.info("💾 Creating connection pool...")
        app.connection_pool = get_connection_pool()
        logger.info("✅ Connection pool created successfully")
        
        logger.info("📋 Creating job manager...")
        app.job_manager = JobManager()
        logger.info("✅ Job manager created successfully")
        
        # Initialize integrated scheduler (combines job management + scheduling)
        logger.info("⏰ Creating integrated scheduler...")
        try:
            app.integrated_scheduler = IntegratedScheduler()
            logger.info("✅ Integrated scheduler created, starting...")
            
            # Start the scheduler
            app.integrated_scheduler.start()
            logger.info("🚀 Integrated scheduler initialized and started successfully")
        except Exception as e:
            logger.error(f"💥 Integrated scheduler initialization failed: {e}")
            import traceback
            logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
            logger.info("📝 Falling back to basic job manager without scheduling")
            app.integrated_scheduler = None
        
        logger.info("✅ All Flask application components initialized successfully")
        
    except ImportError as e:
        logger.error(f"💥 Import error - Database components not available: {e}")
        import traceback
        logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        app.connection_pool = None
        app.job_manager = None
        app.integrated_scheduler = None
    
    except Exception as e:
        logger.error(f"💥 CRITICAL: Failed to initialize database components: {e}")
        import traceback
        logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        app.connection_pool = None
        app.job_manager = None
        app.integrated_scheduler = None
    
    # Store scheduler manager in app context
    if scheduler_manager:
        app.scheduler_manager = scheduler_manager
        logger.info(f"Scheduler manager attached to Flask app: {type(scheduler_manager)}")
    else:
        logger.warning("No scheduler manager provided to Flask app")
    
    # Register blueprints/routes
    from .routes import create_routes
    create_routes(app)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return "Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return "Internal server error", 500
    
    # Cleanup handler
    @app.teardown_appcontext
    def close_connections(error):
        """Clean up connections when request context ends"""
        pass  # Connection pool handles cleanup automatically
    
    # App shutdown handler with comprehensive logging
    def shutdown_handler():
        """Clean up resources when app shuts down"""
        logger.info("🛑 APPLICATION SHUTDOWN INITIATED")
        logger.info("=" * 60)
        
        try:
            # Stop integrated scheduler first
            if hasattr(app, 'integrated_scheduler') and app.integrated_scheduler:
                logger.info("⏰ Stopping integrated scheduler...")
                app.integrated_scheduler.stop(wait=True)
                logger.info("✅ Integrated scheduler stopped successfully")
            else:
                logger.debug("ℹ️  No integrated scheduler to stop")
        except Exception as e:
            logger.error(f"💥 Error stopping integrated scheduler: {e}")
            import traceback
            logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        
        try:
            if hasattr(app, 'connection_pool') and app.connection_pool:
                logger.info("💾 Shutting down connection pool...")
                app.connection_pool.shutdown()
                logger.info("✅ Connection pool shut down successfully")
            else:
                logger.debug("ℹ️  No connection pool to shutdown")
        except Exception as e:
            logger.error(f"💥 Error during connection pool shutdown: {e}")
            import traceback
            logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        
        logger.info("🏁 APPLICATION SHUTDOWN COMPLETED")
        logger.info("=" * 60)
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    return app