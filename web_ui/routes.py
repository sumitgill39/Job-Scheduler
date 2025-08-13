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
        return render_template('index.html')

    @app.route('/connections')
    def connections():
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
                'response_time': None,
                'error': None
            }
            
            logger.info("Returning default connection configuration")
            return jsonify({
                'success': True,
                'connections': [default_connection],
                'count': 1
            })
            
        except Exception as e:
            logger.error(f"API get connections error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/test-connection', methods=['POST'])
    def api_test_connection():
        """API endpoint to test a database connection"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400

            # Mock successful test response
            return jsonify({
                'success': True,
                'message': 'Connection test successful',
                'response_time': 100
            })
            
        except Exception as e:
            logger.error(f"API test connection error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    return app