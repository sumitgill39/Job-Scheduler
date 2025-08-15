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
    
    # Initialize logger
    logger = get_logger(__name__)
    logger.info("Flask application created")
    
    # Initialize global database connection pool and job manager (SINGLE INSTANCES)
    try:
        from database.connection_pool import get_connection_pool
        from core.job_manager import JobManager
        
        # Create single instances to be shared across all routes
        app.connection_pool = get_connection_pool()
        app.job_manager = JobManager()
        
        logger.info("✅ Global connection pool and job manager initialized successfully")
        
    except ImportError as e:
        logger.warning(f"⚠️  Database components not available: {e}")
        app.connection_pool = None
        app.job_manager = None
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize database components: {e}")
        app.connection_pool = None
        app.job_manager = None
    
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
    
    # App shutdown handler
    def shutdown_handler():
        """Clean up resources when app shuts down"""
        try:
            if hasattr(app, 'connection_pool') and app.connection_pool:
                app.connection_pool.shutdown()
                logger.info("Connection pool shut down successfully")
        except Exception as e:
            logger.error(f"Error during connection pool shutdown: {e}")
    
    # Register shutdown handler
    import atexit
    atexit.register(shutdown_handler)
    
    return app