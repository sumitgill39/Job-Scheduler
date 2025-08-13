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
    
    # Store scheduler manager in app context
    if scheduler_manager:
        app.scheduler_manager = scheduler_manager
        logger = get_logger(__name__)
        logger.info(f"Scheduler manager attached to Flask app: {type(scheduler_manager)}")
    else:
        logger = get_logger(__name__)
        logger.warning("No scheduler manager provided to Flask app")
    
    # Initialize logger
    logger = get_logger(__name__)
    logger.info("Flask application created")
    
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
    
    return app