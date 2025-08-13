"""
Flask Routes for Windows Job Scheduler Web UI
"""

import time
from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from utils.logger import get_logger


def create_routes(app):
    """Create all routes for the Flask application"""
    
    logger = get_logger(__name__)
    
    @app.route('/')
    def index():
        """Dashboard page"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                logger.error("Scheduler manager not found in app context")
                return render_template('error.html', error="Scheduler not available")
            
            # Debug: Print available methods
            available_methods = [method for method in dir(scheduler) if not method.startswith('_')]
            logger.info(f"Available scheduler methods: {available_methods}")
            
            # Check if the required method exists
            if not hasattr(scheduler, 'get_all_jobs'):
                logger.error("SchedulerManager missing get_all_jobs method")
                return render_template('error.html', error="Scheduler missing required methods")
            
            # Get scheduler status
            status = scheduler.get_scheduler_status()
            
            # Get recent jobs
            jobs = scheduler.get_all_jobs()  # This should return a dict {job_id: job_object}
            recent_jobs = list(jobs.values())[:5] if jobs else []
            
            return render_template('index.html', 
                                 status=status, 
                                 recent_jobs=recent_jobs,
                                 total_jobs=len(jobs) if jobs else 0)
        
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            return render_template('error.html', error=str(e))
    
    @app.route('/jobs')
    def job_list():
        """Job list page"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                flash('Scheduler not available', 'error')
                return redirect(url_for('index'))
            
            jobs = scheduler.get_all_jobs()  # Returns dict {job_id: job_object}
            job_list = []
            
            for job_id, job in jobs.items():
                job_data = {
                    'id': job.job_id,
                    'name': job.name,
                    'type': job.job_type,
                    'enabled': job.enabled,
                    'status': job.current_status.value,
                    'last_run': job.last_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.last_run_time else 'Never',
                    'is_running': job.is_running
                }
                job_list.append(job_data)
            
            return render_template('job_list.html', jobs=job_list)
        
        except Exception as e:
            logger.error(f"Job list error: {e}")
            flash(f'Error loading jobs: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/jobs/create')
    def create_job():
        """Job creation page"""
        return render_template('create_job.html')
    
    @app.route('/jobs/<job_id>')
    def job_details(job_id):
        """Job details page"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                flash('Scheduler not available', 'error')
                return redirect(url_for('job_list'))
            
            job = scheduler.get_job(job_id)
            if not job:
                flash('Job not found', 'error')
                return redirect(url_for('job_list'))
            
            # Get job status
            status = scheduler.get_job_status(job_id)
            
            # Get execution history
            history = scheduler.get_execution_history(job_id, limit=20)
            
            return render_template('job_details.html', 
                                 job=job, 
                                 status=status, 
                                 history=history)
        
        except Exception as e:
            logger.error(f"Job details error: {e}")
            flash(f'Error loading job details: {str(e)}', 'error')
            return redirect(url_for('job_list'))
    
    # API Routes
    
    @app.route('/api/status')
    def api_status():
        """API endpoint for scheduler status"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            status = scheduler.get_scheduler_status()
            return jsonify(status)
        
        except Exception as e:
            logger.error(f"API status error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/jobs', methods=['GET'])
    def api_jobs():
        """API endpoint for job list"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            jobs = scheduler.get_all_jobs()  # Returns dict {job_id: job_object}
            job_data = {}
            
            for job_id, job in jobs.items():
                job_data[job_id] = {
                    'id': job.job_id,
                    'name': job.name,
                    'type': job.job_type,
                    'enabled': job.enabled,
                    'status': job.current_status.value,
                    'is_running': job.is_running,
                    'last_run': job.last_run_time.isoformat() if job.last_run_time else None
                }
            
            return jsonify(job_data)
        
        except Exception as e:
            logger.error(f"API jobs error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/jobs', methods=['POST'])
    def api_create_job():
        """API endpoint for job creation"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            job_type = data.get('type')
            name = data.get('name')
            
            if not job_type or not name:
                return jsonify({'error': 'Job type and name are required'}), 400
            
            job_id = None
            
            if job_type == 'sql':
                # Handle custom connection if provided
                connection_name = data.get('connection_name', 'default')
                custom_connection = data.get('custom_connection')
                
                if custom_connection:
                    # Create a temporary connection for this job
                    from database.connection_manager import DatabaseConnectionManager
                    import uuid
                    
                    db_manager = DatabaseConnectionManager()
                    temp_conn_name = f"job_{uuid.uuid4().hex[:8]}"
                    
                    success = db_manager.create_custom_connection(
                        name=temp_conn_name,
                        server=custom_connection.get('server'),
                        database=custom_connection.get('database'),
                        port=custom_connection.get('port', 1433),
                        auth_type=custom_connection.get('auth_type', 'windows'),
                        username=custom_connection.get('username'),
                        password=custom_connection.get('password'),
                        description=f"Auto-created for job: {name}"
                    )
                    
                    if success:
                        connection_name = temp_conn_name
                    else:
                        return jsonify({'error': 'Failed to create custom database connection'}), 500
                
                job_id = scheduler.create_sql_job(
                    name=name,
                    description=data.get('description', ''),
                    sql_query=data.get('sql_query', ''),
                    connection_name=connection_name,
                    query_timeout=data.get('query_timeout', 300),
                    max_rows=data.get('max_rows', 1000),
                    timeout=data.get('timeout', 300),
                    max_retries=data.get('max_retries', 3),
                    retry_delay=data.get('retry_delay', 60),
                    run_as=data.get('run_as'),
                    schedule=data.get('schedule')
                )
            
            elif job_type == 'powershell':
                job_id = scheduler.create_powershell_job(
                    name=name,
                    description=data.get('description', ''),
                    script_path=data.get('script_path'),
                    script_content=data.get('script_content'),
                    parameters=data.get('parameters', []),
                    schedule=data.get('schedule')
                )
            
            else:
                return jsonify({'error': f'Unknown job type: {job_type}'}), 400
            
            if job_id:
                return jsonify({'job_id': job_id, 'message': 'Job created successfully'}), 201
            else:
                return jsonify({'error': 'Failed to create job'}), 500
        
        except Exception as e:
            logger.error(f"API create job error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/jobs/<job_id>/run', methods=['POST'])
    def api_run_job(job_id):
        """API endpoint to run a job immediately"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            result = scheduler.run_job_once(job_id)
            
            if result:
                return jsonify({
                    'message': 'Job executed',
                    'status': result.status.value,
                    'duration': result.duration_seconds,
                    'output': result.output[:1000] if result.output else ''  # Limit output
                })
            else:
                return jsonify({'error': 'Failed to run job'}), 500
        
        except Exception as e:
            logger.error(f"API run job error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/jobs/<job_id>/toggle', methods=['POST'])
    def api_toggle_job(job_id):
        """API endpoint to enable/disable a job"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            job = scheduler.get_job(job_id)
            if not job:
                return jsonify({'error': 'Job not found'}), 404
            
            if job.enabled:
                success = scheduler.pause_job(job_id)
                action = 'disabled'
            else:
                success = scheduler.resume_job(job_id)
                action = 'enabled'
            
            if success:
                return jsonify({'message': f'Job {action} successfully'})
            else:
                return jsonify({'error': f'Failed to {action[:-1]} job'}), 500
        
        except Exception as e:
            logger.error(f"API toggle job error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/jobs/<job_id>', methods=['DELETE'])
    def api_delete_job(job_id):
        """API endpoint to delete a job"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            success = scheduler.remove_job(job_id)
            
            if success:
                return jsonify({'message': 'Job deleted successfully'})
            else:
                return jsonify({'error': 'Failed to delete job'}), 500
        
        except Exception as e:
            logger.error(f"API delete job error: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/connections', methods=['GET'])
    def api_get_connections():
        """API endpoint to get available database connections"""
        try:
            from database.connection_manager import DatabaseConnectionManager
            db_manager = DatabaseConnectionManager()
            
            connections = []
            for conn_name in db_manager.list_connections():
                conn_info = db_manager.get_connection_info(conn_name)
                if conn_info:
                    connections.append({
                        'name': conn_name,
                        'server': conn_info.get('server'),
                        'database': conn_info.get('database'),
                        'description': conn_info.get('description', ''),
                        'auth_type': 'windows' if conn_info.get('trusted_connection') else 'sql'
                    })
            
            return jsonify({'success': True, 'connections': connections})
            
        except Exception as e:
            logger.error(f"API get connections error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections', methods=['POST'])
    def api_create_connection():
        """API endpoint to create a new database connection"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            from database.connection_manager import DatabaseConnectionManager
            db_manager = DatabaseConnectionManager()
            
            result = db_manager.create_custom_connection(
                name=data.get('name'),
                server=data.get('server'),
                database=data.get('database'),
                port=data.get('port', 1433),
                auth_type=data.get('auth_type', 'windows'),
                username=data.get('username'),
                password=data.get('password'),
                description=data.get('description')
            )
            
            if result['success']:
                return jsonify({
                    'success': True, 
                    'message': result['message'],
                    'test_details': result.get('test_details', {})
                })
            else:
                return jsonify({
                    'success': False, 
                    'error': result['error'],
                    'test_details': result.get('test_details', {})
                }), 400
                
        except Exception as e:
            logger.error(f"API create connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>', methods=['DELETE'])
    def api_delete_connection(connection_name):
        """API endpoint to delete a database connection"""
        try:
            from database.connection_manager import DatabaseConnectionManager
            db_manager = DatabaseConnectionManager()
            
            success = db_manager.remove_connection(connection_name)
            
            if success:
                return jsonify({'success': True, 'message': f'Connection "{connection_name}" deleted successfully'})
            else:
                return jsonify({'success': False, 'error': f'Connection "{connection_name}" not found'}), 404
                
        except Exception as e:
            logger.error(f"API delete connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/test-connection', methods=['POST'])
    def api_test_connection():
        """API endpoint to test a database connection"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Validate required fields
            required_fields = ['server', 'database']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'error': f'{field} is required'}), 400
            
            # Import required modules
            import pyodbc
            import time
            
            # Build connection string directly for testing
            server = data.get('server')
            port = data.get('port', 1433)
            database = data.get('database')
            auth_type = data.get('auth_type', 'windows')
            username = data.get('username')
            password = data.get('password')
            
            # Build connection string components
            components = []
            components.append("DRIVER={ODBC Driver 17 for SQL Server}")
            
            # Handle server and port
            if '\\' in server:
                # Named instance - don't add port
                components.append(f"SERVER={server}")
            elif port and port != 1433:
                # Custom port
                components.append(f"SERVER={server},{port}")
            else:
                # Default port
                components.append(f"SERVER={server}")
            
            components.append(f"DATABASE={database}")
            
            # Authentication
            if auth_type == 'windows':
                components.append("Trusted_Connection=yes")
            else:
                if not username or not password:
                    return jsonify({'success': False, 'error': 'Username and password required for SQL authentication'}), 400
                components.append(f"UID={username}")
                components.append(f"PWD={password}")
            
            # Connection settings
            components.extend([
                "Connection Timeout=10",
                "Command Timeout=30",
                "Encrypt=no",
                "TrustServerCertificate=yes"
            ])
            
            connection_string = ";".join(components)
            
            # Test the connection
            start_time = time.time()
            
            try:
                logger.info(f"Testing connection to {server}\\{database}")
                
                connection = pyodbc.connect(connection_string)
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as test, @@VERSION as version")
                result = cursor.fetchone()
                cursor.close()
                connection.close()
                
                response_time = time.time() - start_time
                
                return jsonify({
                    'success': True,
                    'message': 'Connection successful',
                    'response_time': response_time,
                    'server_info': {
                        'test_result': result[0] if result else None,
                        'version': result[1][:100] if result and len(result) > 1 else 'Unknown'
                    }
                })
                
            except pyodbc.Error as e:
                response_time = time.time() - start_time
                error_msg = str(e)
                
                # Extract more user-friendly error message
                if "Login failed" in error_msg:
                    error_msg = "Login failed - check username and password"
                elif "Server does not exist" in error_msg:
                    error_msg = "Server not found - check server name and port"
                elif "Database" in error_msg and "does not exist" in error_msg:
                    error_msg = "Database not found - check database name"
                elif "timeout" in error_msg.lower():
                    error_msg = "Connection timeout - check server accessibility"
                
                logger.error(f"Connection test failed: {e}")
                
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'response_time': response_time
                })
                
        except ImportError as e:
            logger.error(f"Import error in test connection: {e}")
            return jsonify({
                'success': False,
                'error': 'pyodbc driver not available - please install ODBC Driver for SQL Server'
            }), 500
            
        except Exception as e:
            logger.error(f"API test connection error: {e}")
            return jsonify({
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }), 500
    
    @app.route('/connections')
    def connections():
        """Database connections management page"""
        try:
            from database.connection_manager import DatabaseConnectionManager
            db_manager = DatabaseConnectionManager()
            
            connections = []
            for conn_name in db_manager.list_connections():
                conn_info = db_manager.get_connection_info(conn_name)
                if conn_info:
                    # Don't test connection status immediately to avoid page load delays
                    # Status will be tested on demand via AJAX
                    connections.append({
                        'name': conn_name,
                        'server': conn_info.get('server'),
                        'database': conn_info.get('database'),
                        'port': conn_info.get('port', 1433),
                        'description': conn_info.get('description', ''),
                        'auth_type': 'Windows' if conn_info.get('trusted_connection') else 'SQL Server',
                        'status': 'Unknown',  # Will be tested via AJAX
                        'response_time': 0,
                        'error': ''
                    })
            
            return render_template('connections.html', connections=connections)
            
        except Exception as e:
            logger.error(f"Connections page error: {e}")
            flash(f'Error loading connections: {str(e)}', 'error')
            return redirect(url_for('index'))
    
    @app.route('/jobs/<job_id>/history')
    def job_history(job_id):
        """Job execution history page"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                flash('Scheduler not available', 'error')
                return redirect(url_for('job_list'))
            
            job = scheduler.get_job(job_id)
            if not job:
                flash('Job not found', 'error')
                return redirect(url_for('job_list'))
            
            # Get execution history
            history = scheduler.get_execution_history(job_id, limit=100)
            
            return render_template('job_history.html', job=job, history=history)
            
        except Exception as e:
            logger.error(f"Job history error: {e}")
            flash(f'Error loading job history: {str(e)}', 'error')
            return redirect(url_for('job_list'))
    
    @app.route('/api/jobs/<job_id>/history')
    def api_job_history(job_id):
        """API endpoint for job execution history"""
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if not scheduler:
                return jsonify({'error': 'Scheduler not available'}), 500
            
            limit = request.args.get('limit', 50, type=int)
            history = scheduler.get_execution_history(job_id, limit)
            
            return jsonify(history)
        
        except Exception as e:
            logger.error(f"API job history error: {e}")
            return jsonify({'error': str(e)}), 500