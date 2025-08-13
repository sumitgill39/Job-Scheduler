"""
Flask Routes for Windows Job Scheduler Web UI
"""

import time
from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from utils.logger import get_logger
from database.enhanced_connection_manager import EnhancedConnectionManager, ConnectionInfo

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

            logger.info(f"Testing connection to server: {data.get('server')}")
            
            # Create ConnectionInfo object for testing
            connection_info = ConnectionInfo(
                name=data.get('name', 'test-connection'),
                server=data.get('server'),
                database=data.get('database', 'master'),
                port=int(data.get('port', 3433)),
                auth_type=data.get('auth_type', 'sql'),
                username=data.get('username', 'svc-con'),
                password=data.get('password', 'admin@1234'),
                description=data.get('description', ''),
                is_active=data.get('is_active', True),
                encrypt=data.get('encrypt', False),
                trust_server_certificate=data.get('trust_server_certificate', True),
                connection_timeout=int(data.get('connection_timeout', 30)),
                command_timeout=int(data.get('command_timeout', 300))
            )

            # Get connection manager instance
            conn_manager = EnhancedConnectionManager()
            
            # Test the connection
            start_time = time.time()
            success, error = conn_manager.test_connection(connection_info)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            if success:
                return jsonify({
                    'success': True,
                    'message': 'Connection test successful',
                    'response_time': response_time
                })
            else:
                return jsonify({
                    'success': False,
                    'error': str(error)
                })

        except Exception as e:
            logger.error(f"API test connection error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/connections/<connection_id>', methods=['PUT'])
    def api_update_connection(connection_id):
        """API endpoint to update an existing connection"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400

            logger.info(f"Updating connection: {connection_id}")
            
            # Create ConnectionInfo object for update
            connection_info = ConnectionInfo(
                name=connection_id,
                server=data.get('server'),
                database=data.get('database', 'master'),
                port=int(data.get('port', 3433)),
                auth_type=data.get('auth_type', 'sql'),
                username=data.get('username', 'svc-con'),
                password=data.get('password'),  # Only update if provided
                description=data.get('description', ''),
                is_active=data.get('is_active', True),
                encrypt=data.get('encrypt', False),
                trust_server_certificate=data.get('trust_server_certificate', True),
                connection_timeout=int(data.get('connection_timeout', 30)),
                command_timeout=int(data.get('command_timeout', 300))
            )

            # Get connection manager instance
            conn_manager = EnhancedConnectionManager()
            
            # Update the connection
            success = conn_manager.update_connection(connection_info)

            if success:
                return jsonify({
                    'success': True,
                    'message': f'Connection "{connection_id}" updated successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to update connection'
                })

        except Exception as e:
            logger.error(f"API update connection error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    return app