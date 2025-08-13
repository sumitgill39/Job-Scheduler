// filepath: /Users/sumeet/Documents/GitHub/Job Scheduler/web_ui/routes.py
"""
Flask Routes for Windows Job Scheduler Web UI
"""

from flask import render_template, request, jsonify
from utils.logger import get_logger

logger = get_logger(__name__)

def create_routes(app):
    """Create all routes for the Flask application"""
    
    @app.route('/')
    def index():
        """Dashboard page"""
        return render_template('index.html')

    @app.route('/connections')
    def connections():
        """Render connections page"""
        return render_template('connections.html')

    @app.route('/api/connections', methods=['GET'])
    def api_get_connections():
        """API endpoint to get available database connections"""
        try:
            # Default test connection
            default_connection = {
                'name': 'default-sql-connection',
                'server': 'USDF11DB197CI1\\PRD_DB01',
                'port': 3433,
                'database': 'master',
                'auth_type': 'sql',
                'username': 'svc-con',
                'description': 'Default SQL Server Connection',
                'is_active': True,
                'status': 'unknown',
                'last_checked': None,
                'response_time': None
            }
            
            return jsonify({
                'success': True,
                'connections': [default_connection],
                'count': 1
            })
            
        except Exception as e:
            logger.error(f"API get connections error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/jobs')
    def job_list():
        """Job list page"""
        return render_template('job_list.html')

    return app