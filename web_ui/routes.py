"""
Flask Routes for Windows Job Scheduler Web UI
"""

import time
from flask import render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from utils.logger import get_logger
from database.enhanced_connection_manager import get_enhanced_connection_manager


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
        return render_template('job_list.html')
    
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
    

    @app.route('/api/health', methods=['GET'])
    def api_health():
        """Simple health check endpoint"""
        return jsonify({
            'status': 'ok',
            'message': 'API is working',
            'timestamp': time.time()
        })

    @app.route('/api/connections', methods=['GET'])
    def api_get_connections():
        """API endpoint to get available database connections"""
        try:
            # Return default connection
            default_connection = {
                'name': 'default-sql-connection',
                'server': 'USDF11DB197CI1\\PRD_DB01',
                'port': 3433,
                'database': 'master',  # Default database
                'auth_type': 'sql',
                'username': 'svc-con',
                'description': 'Default SQL Server Connection',
                'is_active': True,
                'status': 'unknown',  # Will be updated when tested
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
    
    @app.route('/api/connections', methods=['POST'])
    def api_create_connection():
        """API endpoint to create a new database connection"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400

            logger.info(f"Creating connection with data: {data}")

            # Validate required fields
            required_fields = ['name', 'server', 'database']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return jsonify({
                    'success': False,
                    'error': f'Missing required fields: {", ".join(missing_fields)}'
                }), 400

            # Create ConnectionInfo object
            connection_info = ConnectionInfo(
                name=data['name'],
                server=data['server'],
                database=data['database'],
                port=int(data.get('port', 1433)),
                auth_type=data.get('auth_type', 'windows'),
                username=data.get('username'),
                password=data.get('password'),
                description=data.get('description', ''),
                is_active=data.get('is_active', True),
                encrypt=data.get('encrypt', False),
                trust_server_certificate=data.get('trust_server_certificate', True),
                connection_timeout=int(data.get('connection_timeout', 30)),
                command_timeout=int(data.get('command_timeout', 300))
            )

            # Get the connection manager
            conn_manager = get_enhanced_connection_manager()

            # Check if connection already exists
            if conn_manager.get_connection(data['name']):
                return jsonify({
                    'success': False,
                    'error': f'Connection with name "{data["name"]}" already exists'
                }), 409

            # Save the connection
            success = conn_manager.save_connection(connection_info)
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Connection "{data["name"]}" created successfully',
                    'connection': {
                        'name': connection_info.name,
                        'server': connection_info.server,
                        'database': connection_info.database,
                        'description': connection_info.description,
                        'is_active': connection_info.is_active
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to save connection'
                }), 500

        except Exception as e:
            logger.error(f"API create connection error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>', methods=['GET'])
    def api_get_connection(connection_name):
        """API endpoint to get a specific connection"""
        try:
            from database.enhanced_connection_manager import get_enhanced_connection_manager
            
            conn_manager = get_enhanced_connection_manager()
            connection = conn_manager.get_connection(connection_name)
            
            if not connection:
                return jsonify({'success': False, 'error': 'Connection not found'}), 404
            
            # Convert to dict and remove sensitive data for response
            conn_data = {
                'name': connection.name,
                'server': connection.server,
                'database': connection.database,
                'port': connection.port,
                'auth_type': connection.auth_type,
                'username': connection.username,
                'description': connection.description,
                'created_date': connection.created_date,
                'modified_date': connection.modified_date,
                'is_active': connection.is_active,
                'last_tested': connection.last_tested,
                'connection_timeout': connection.connection_timeout,
                'command_timeout': connection.command_timeout,
                'encrypt': connection.encrypt,
                'trust_server_certificate': connection.trust_server_certificate
            }
            
            # Add status information
            status = conn_manager.get_connection_status(connection_name)
            conn_data.update(status)
            
            return jsonify({'success': True, 'connection': conn_data})
            
        except Exception as e:
            logger.error(f"API get connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>', methods=['PUT'])
    def api_update_connection(connection_name):
        """API endpoint to update a connection"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            from database.enhanced_connection_manager import get_enhanced_connection_manager, ConnectionInfo
            
            # Create updated connection info object
            connection_info = ConnectionInfo(
                name=data.get('name', '').strip(),
                server=data.get('server', '').strip(),
                database=data.get('database', '').strip(),
                port=int(data.get('port', 1433)),
                auth_type=data.get('auth_type', 'windows').lower(),
                username=data.get('username', '').strip() if data.get('username') else None,
                password=data.get('password', '').strip() if data.get('password') else None,
                description=data.get('description', '').strip(),
                connection_timeout=int(data.get('connection_timeout', 30)),
                command_timeout=int(data.get('command_timeout', 300)),
                encrypt=bool(data.get('encrypt', False)),
                trust_server_certificate=bool(data.get('trust_server_certificate', True)),
                is_active=bool(data.get('is_active', True))
            )
            
            conn_manager = get_enhanced_connection_manager()
            success, message = conn_manager.update_connection(connection_name, connection_info)
            
            if success:
                return jsonify({'success': True, 'message': message})
            else:
                return jsonify({'success': False, 'error': message}), 400
                
        except Exception as e:
            logger.error(f"API update connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>', methods=['DELETE'])
    def api_delete_connection(connection_name):
        """API endpoint to delete a connection"""
        try:
            from database.enhanced_connection_manager import get_enhanced_connection_manager
            
            conn_manager = get_enhanced_connection_manager()
            success, message = conn_manager.delete_connection(connection_name)
            
            if success:
                return jsonify({'success': True, 'message': message})
            else:
                return jsonify({'success': False, 'error': message}), 404 if 'not found' in message.lower() else 500
                
        except Exception as e:
            logger.error(f"API delete connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>/test', methods=['POST'])
    def api_test_existing_connection(connection_name):
        """API endpoint to test an existing connection"""
        try:
            from database.enhanced_connection_manager import get_enhanced_connection_manager
            
            conn_manager = get_enhanced_connection_manager()
            result = conn_manager.test_connection(connection_name)
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"API test existing connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/test-connection', methods=['POST'])
    def api_test_connection():
        """API endpoint to test a database connection"""
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400

            logger.info(f"Testing connection with data: {data}")
            
            # Create a ConnectionInfo object
            connection_info = ConnectionInfo(
                name=data.get('name', 'test-connection'),
                server=data['server'],
                database=data['database'],
                port=int(data.get('port', 1433)),
                auth_type=data.get('auth_type', 'windows'),
                username=data.get('username'),
                password=data.get('password'),
                encrypt=data.get('encrypt', False),
                trust_server_certificate=data.get('trust_server_certificate', True),
                connection_timeout=int(data.get('connection_timeout', 30)),
                command_timeout=int(data.get('command_timeout', 300))
            )

            # Get the connection manager
            conn_manager = get_enhanced_connection_manager()
            
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
    
    @app.route('/api/connections/refresh', methods=['POST'])
    def api_refresh_connections():
        """API endpoint to refresh all connection statuses"""
        try:
            from database.enhanced_connection_manager import get_enhanced_connection_manager
            
            conn_manager = get_enhanced_connection_manager()
            results = conn_manager.refresh_all_connections()
            
            return jsonify({
                'success': True,
                'message': f'Refreshed {len(results)} connections',
                'results': results
            })
            
        except Exception as e:
            logger.error(f"API refresh connections error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/connections')
    def connections():
        """Database connections management page"""
        try:
            # Using the connections template
            return render_template('connections.html')
            
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