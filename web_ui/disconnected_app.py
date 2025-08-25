"""
Flask Web Application using Disconnected Data Access Pattern
Eliminates connection pooling issues by using ADO.NET-style disconnected data
"""

import os
import time
from flask import Flask
from flask_wtf.csrf import CSRFProtect
from utils.logger import get_logger
from database.disconnected_factory import create_disconnected_components, test_disconnected_connection


def create_disconnected_app(scheduler_manager=None):
    """Create Flask application with disconnected data access"""
    
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for simplicity
    app.config['WTF_CSRF_TIME_LIMIT'] = None
    
    # Initialize logger
    logger = get_logger(__name__)
    logger.info("[DISCONNECTED_APP] Creating Flask application with disconnected data access...")
    
    # Track application start time for uptime calculation
    app._start_time = time.time()
    
    try:
        # Test disconnected connection first
        logger.info("[DISCONNECTED_APP] 🔍 Testing disconnected database connection...")
        if not test_disconnected_connection():
            logger.error("[DISCONNECTED_APP] ❌ Disconnected database connection test failed")
            raise Exception("Disconnected database connection test failed")
        
        # Create disconnected components
        logger.info("[DISCONNECTED_APP] 🔧 Creating disconnected database components...")
        components = create_disconnected_components()
        
        # Store components in app context
        app.disconnected_data_manager = components['data_manager']
        app.disconnected_job_manager = components['job_manager']
        app.disconnected_job_executor = components['job_executor']
        app.db_config = components['config']
        
        # For backward compatibility with existing routes
        app.db_manager = components['data_manager']
        app.job_manager = components['job_manager']
        app.integrated_scheduler = components['integrated_scheduler']  # This is key for dashboard!
        
        logger.info("[DISCONNECTED_APP] ✅ Disconnected components created successfully")
        
        # Test job manager functionality
        logger.info("[DISCONNECTED_APP] 🧪 Testing job manager functionality...")
        try:
            jobs = app.disconnected_job_manager.list_jobs(limit=5)
            logger.info(f"[DISCONNECTED_APP] ✅ Job manager test successful - found {len(jobs)} jobs")
        except Exception as e:
            logger.warning(f"[DISCONNECTED_APP] ⚠️ Job manager test warning: {e}")
        
        # Initialize scheduler if provided
        if scheduler_manager:
            app.scheduler_manager = scheduler_manager
            logger.info("[DISCONNECTED_APP] ✅ Scheduler manager attached")
        else:
            logger.info("[DISCONNECTED_APP] ℹ️ No scheduler manager provided")
        
    except Exception as e:
        logger.error(f"[DISCONNECTED_APP] ❌ Failed to initialize disconnected components: {e}")
        logger.error("[DISCONNECTED_APP] This usually indicates database connectivity issues")
        logger.error("[DISCONNECTED_APP] Please check your .env file configuration")
        raise
    
    # Import and register routes
    try:
        logger.info("[DISCONNECTED_APP] 📝 Registering application routes...")
        from web_ui.routes import create_routes
        
        # Register routes with the app - they will automatically use app.job_manager and app.db_manager
        # which now point to our disconnected components
        create_routes(app)
        
        logger.info("[DISCONNECTED_APP] ✅ Routes registered successfully")
        
    except Exception as e:
        logger.error(f"[DISCONNECTED_APP] ❌ Failed to register routes: {e}")
        raise
    
    # Add disconnected-specific endpoints
    @app.route('/api/disconnected/cache-info')
    def disconnected_cache_info():
        """Get cache information for disconnected data manager"""
        try:
            cache_info = app.disconnected_job_manager.get_cache_info()
            return {
                'success': True,
                'cache_info': cache_info,
                'mode': 'disconnected'
            }
        except Exception as e:
            logger.error(f"[DISCONNECTED_APP] Error getting cache info: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @app.route('/api/disconnected/refresh-cache', methods=['POST'])
    def refresh_disconnected_cache():
        """Force refresh of disconnected cache"""
        try:
            app.disconnected_job_manager.refresh_data(force=True)
            logger.info("[DISCONNECTED_APP] Cache refreshed successfully")
            return {
                'success': True,
                'message': 'Cache refreshed successfully'
            }
        except Exception as e:
            logger.error(f"[DISCONNECTED_APP] Error refreshing cache: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @app.route('/api/disconnected/status')
    def disconnected_status():
        """Get disconnected system status"""
        try:
            cache_info = app.disconnected_job_manager.get_cache_info()
            
            # Test database connectivity
            test_value = app.disconnected_data_manager.execute_scalar("SELECT 1")
            
            return {
                'success': True,
                'mode': 'disconnected',
                'database_connectivity': test_value == 1,
                'cache_info': cache_info,
                'uptime_seconds': time.time() - app._start_time,
                'message': 'Disconnected mode - no connection pooling issues!'
            }
        except Exception as e:
            logger.error(f"[DISCONNECTED_APP] Error getting disconnected status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # Add context processor for template variables
    @app.context_processor
    def inject_disconnected_info():
        """Inject disconnected mode info into templates"""
        return {
            'disconnected_mode': True,
            'connection_pooling': False
        }
    
    # Add error handlers
    @app.errorhandler(500)
    def handle_500_error(e):
        logger.error(f"[DISCONNECTED_APP] Internal server error: {e}")
        return {
            'success': False,
            'error': 'Internal server error in disconnected mode',
            'mode': 'disconnected'
        }, 500
    
    @app.errorhandler(404)
    def handle_404_error(e):
        return {
            'success': False,
            'error': 'Not found',
            'mode': 'disconnected'
        }, 404
    
    # Add request logging for debugging
    @app.before_request
    def log_request_info():
        import flask
        if flask.request.path.startswith('/api/'):
            logger.debug(f"[DISCONNECTED_APP] API Request: {flask.request.method} {flask.request.path}")
    
    @app.after_request
    def log_response_info(response):
        import flask
        if flask.request.path.startswith('/api/disconnected/'):
            logger.debug(f"[DISCONNECTED_APP] Disconnected API Response: {response.status_code}")
        return response
    
    logger.info("[DISCONNECTED_APP] ✅ Flask application created successfully with disconnected data access")
    logger.info("[DISCONNECTED_APP] 🚀 No more connection pooling issues!")
    
    return app


def create_app(scheduler_manager=None):
    """
    Main factory function - creates disconnected app by default
    This maintains compatibility with existing code while using the new disconnected pattern
    """
    return create_disconnected_app(scheduler_manager)


if __name__ == '__main__':
    # Test the disconnected app creation
    logger = get_logger(__name__)
    
    try:
        logger.info("Testing disconnected app creation...")
        app = create_disconnected_app()
        logger.info("✅ Disconnected app created successfully!")
        
        # Test a few routes
        with app.test_client() as client:
            response = client.get('/api/disconnected/status')
            logger.info(f"Status endpoint test: {response.status_code}")
            
            if response.status_code == 200:
                data = response.get_json()
                logger.info(f"Status response: {data}")
            
    except Exception as e:
        logger.error(f"❌ Failed to create disconnected app: {e}")
        raise