"""
Flask Web Application for Windows Job Scheduler
Using SQLAlchemy for clean database operations
"""

import os
import time
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from utils.logger import get_logger


def create_app(scheduler_manager=None):
    """Create and configure Flask application with SQLAlchemy"""
    
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for simplicity
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    
    # Initialize logger
    logger = get_logger(__name__)
    logger.info("[FLASK] Creating Flask application with SQLAlchemy")
    
    # Track application start time for uptime calculation
    app._start_time = time.time()
    
    # Always attach scheduler manager first (outside SQLAlchemy try/catch)
    if scheduler_manager:
        app.scheduler_manager = scheduler_manager
        logger.info("[SUCCESS] Scheduler manager attached to Flask app")
    else:
        app.scheduler_manager = None
        logger.info("[INFO] No scheduler manager provided")
    
    # Initialize SQLAlchemy database and components
    logger.info("[INIT] Initializing SQLAlchemy components...")
    try:
        # Initialize SQLAlchemy database
        logger.info("[DATABASE] Initializing SQLAlchemy database...")
        from database.sqlalchemy_models import init_database, database_engine
        
        # Test database connection and create tables if needed
        db_test = init_database()
        if db_test['success']:
            logger.info("[SUCCESS] SQLAlchemy database initialized successfully")
        else:
            logger.error(f"[ERROR] SQLAlchemy database initialization failed: {db_test['error']}")
            # Continue anyway - let the app start but log the issue
        
        # Store database engine in app context for routes
        app.database_engine = database_engine
        
        # Initialize job manager with SQLAlchemy
        logger.info("[MANAGER] Creating SQLAlchemy job manager...")
        from core.job_manager import JobManager
        from simple_connection_manager import simple_connection_manager
        
        app.job_manager = JobManager()
        
        # Add simple connection manager for routes compatibility
        app.db_manager = simple_connection_manager
        logger.info("[SUCCESS] SQLAlchemy job manager created successfully")
        
        # Initialize job executor
        logger.info("[EXECUTOR] Creating SQLAlchemy job executor...")
        from core.job_executor import JobExecutor
        app.job_executor = JobExecutor(job_manager=app.job_manager)
        logger.info("[SUCCESS] SQLAlchemy job executor created successfully")
        
        # Try to create integrated scheduler if no scheduler manager provided
        if not scheduler_manager:
            try:
                logger.info("[SCHEDULER] Creating integrated scheduler...")
                from core.integrated_scheduler import IntegratedScheduler
                app.integrated_scheduler = IntegratedScheduler()
                
                # Start the scheduler
                app.integrated_scheduler.start()
                logger.info("[SUCCESS] Integrated scheduler initialized and started successfully")
            except Exception as e:
                logger.error(f"[ERROR] Integrated scheduler initialization failed: {e}")
                logger.info("[INFO] Continuing without integrated scheduler")
                app.integrated_scheduler = None
        else:
            app.integrated_scheduler = None
        
        logger.info("[SUCCESS] All SQLAlchemy components initialized successfully")
        
    except Exception as e:
        logger.error(f"[CRITICAL] Failed to initialize SQLAlchemy components: {e}")
        import traceback
        logger.error(f"[TRACE] Stack trace: {traceback.format_exc()}")
        
        # Set minimal components so app can still start (but keep scheduler_manager)
        app.database_engine = None
        app.job_manager = None
        app.job_executor = None
        app.integrated_scheduler = None
        # Keep app.scheduler_manager as it was set above
    
    # Register blueprints/routes
    try:
        logger.info("[ROUTES] Registering application routes...")
        from .routes import create_routes
        create_routes(app)
        logger.info("[SUCCESS] Routes registered successfully")
        
        # Register Agent API blueprint
        logger.info("[AGENT API] Registering agent API routes...")
        from .agent_api import agent_api
        app.register_blueprint(agent_api)
        logger.info("[SUCCESS] Agent API routes registered at /api/agent")
    except Exception as e:
        logger.error(f"[ERROR] Failed to register routes: {e}")
        raise
    
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
        # SQLAlchemy handles connection cleanup automatically
        pass
    
    # App shutdown handler
    def shutdown_handler():
        """Clean up resources when app shuts down"""
        logger.info("[SHUTDOWN] APPLICATION SHUTDOWN INITIATED")
        logger.info("=" * 60)
        
        try:
            # Stop integrated scheduler first
            if hasattr(app, 'integrated_scheduler') and app.integrated_scheduler:
                logger.info("[SCHEDULER] Stopping integrated scheduler...")
                app.integrated_scheduler.stop(wait=True)
                logger.info("[SUCCESS] Integrated scheduler stopped successfully")
            else:
                logger.debug("[DEBUG] No integrated scheduler to stop")
        except Exception as e:
            logger.error(f"[ERROR] Error stopping integrated scheduler: {e}")
        
        try:
            # SQLAlchemy cleanup
            if hasattr(app, 'database_engine') and app.database_engine:
                logger.info("[DATABASE] Closing SQLAlchemy database engine...")
                app.database_engine.engine.dispose()
                logger.info("[SUCCESS] SQLAlchemy database engine closed successfully")
            else:
                logger.debug("[DEBUG] No database engine to close")
        except Exception as e:
            logger.error(f"[ERROR] Error during SQLAlchemy cleanup: {e}")
        
        logger.info("[SHUTDOWN] APPLICATION SHUTDOWN COMPLETED")
        logger.info("=" * 60)
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    logger.info("[SUCCESS] Flask application created successfully with SQLAlchemy")
    return app