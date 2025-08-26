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
    logger.info("🚀 Creating Flask application with SQLAlchemy")
    
    # Track application start time for uptime calculation
    app._start_time = time.time()
    
    # Initialize SQLAlchemy database and components
    logger.info("🔧 Initializing SQLAlchemy components...")
    try:
        # Initialize SQLAlchemy database
        logger.info("💾 Initializing SQLAlchemy database...")
        from database.sqlalchemy_models import init_database, database_engine
        
        # Test database connection and create tables if needed
        db_test = init_database()
        if db_test['success']:
            logger.info("✅ SQLAlchemy database initialized successfully")
        else:
            logger.error(f"❌ SQLAlchemy database initialization failed: {db_test['error']}")
            # Continue anyway - let the app start but log the issue
        
        # Store database engine in app context for routes
        app.database_engine = database_engine
        
        # Initialize job manager with SQLAlchemy
        logger.info("📋 Creating SQLAlchemy job manager...")
        from core.job_manager import JobManager
        app.job_manager = JobManager()
        logger.info("✅ SQLAlchemy job manager created successfully")
        
        # Initialize job executor
        logger.info("⚡ Creating SQLAlchemy job executor...")
        from core.job_executor import JobExecutor
        app.job_executor = JobExecutor(job_manager=app.job_manager)
        logger.info("✅ SQLAlchemy job executor created successfully")
        
        # Initialize integrated scheduler if provided
        if scheduler_manager:
            app.scheduler_manager = scheduler_manager
            logger.info("✅ Scheduler manager attached to Flask app")
        else:
            logger.info("ℹ️ No scheduler manager provided")
            
            # Try to create integrated scheduler
            try:
                logger.info("⏰ Creating integrated scheduler...")
                from core.integrated_scheduler import IntegratedScheduler
                app.integrated_scheduler = IntegratedScheduler()
                
                # Start the scheduler
                app.integrated_scheduler.start()
                logger.info("✅ Integrated scheduler initialized and started successfully")
            except Exception as e:
                logger.error(f"💥 Integrated scheduler initialization failed: {e}")
                logger.info("📝 Continuing without integrated scheduler")
                app.integrated_scheduler = None
        
        logger.info("✅ All SQLAlchemy components initialized successfully")
        
    except Exception as e:
        logger.error(f"💥 CRITICAL: Failed to initialize SQLAlchemy components: {e}")
        import traceback
        logger.error(f"🔍 Stack trace: {traceback.format_exc()}")
        
        # Set minimal components so app can still start
        app.database_engine = None
        app.job_manager = None
        app.job_executor = None
        app.integrated_scheduler = None
    
    # Register blueprints/routes
    try:
        logger.info("📝 Registering application routes...")
        from .routes import create_routes
        create_routes(app)
        logger.info("✅ Routes registered successfully")
    except Exception as e:
        logger.error(f"💥 Failed to register routes: {e}")
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
        logger.info("🛑 APPLICATION SHUTDOWN INITIATED")
        logger.info("=" * 60)
        
        try:
            # Stop integrated scheduler first
            if hasattr(app, 'integrated_scheduler') and app.integrated_scheduler:
                logger.info("⏰ Stopping integrated scheduler...")
                app.integrated_scheduler.stop(wait=True)
                logger.info("✅ Integrated scheduler stopped successfully")
            else:
                logger.debug("ℹ️ No integrated scheduler to stop")
        except Exception as e:
            logger.error(f"💥 Error stopping integrated scheduler: {e}")
        
        try:
            # SQLAlchemy cleanup
            if hasattr(app, 'database_engine') and app.database_engine:
                logger.info("💾 Closing SQLAlchemy database engine...")
                app.database_engine.engine.dispose()
                logger.info("✅ SQLAlchemy database engine closed successfully")
            else:
                logger.debug("ℹ️ No database engine to close")
        except Exception as e:
            logger.error(f"💥 Error during SQLAlchemy cleanup: {e}")
        
        logger.info("🏁 APPLICATION SHUTDOWN COMPLETED")
        logger.info("=" * 60)
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    logger.info("🎉 Flask application created successfully with SQLAlchemy")
    return app