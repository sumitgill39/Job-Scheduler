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
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            jobs = job_manager.list_jobs()
            
            logger.info(f"[JOB_LIST] Displaying {len(jobs)} jobs")
            
            return render_template('job_list.html', jobs=jobs)
        
        except Exception as e:
            logger.error(f"[JOB_LIST] Job list error: {e}")
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
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            job = job_manager.get_job(job_id)
            if not job:
                flash('Job not found', 'error')
                return redirect(url_for('job_list'))
            
            logger.info(f"[JOB_DETAILS] Displaying details for job: {job['name']}")
            
            return render_template('job_details.html', job=job)
        
        except Exception as e:
            logger.error(f"[JOB_DETAILS] Job details error: {e}")
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
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            # Get query parameters
            job_type = request.args.get('type')
            enabled_only = request.args.get('enabled_only', 'false').lower() == 'true'
            
            jobs = job_manager.list_jobs(job_type=job_type, enabled_only=enabled_only)
            
            logger.info(f"[API_JOBS] Retrieved {len(jobs)} jobs")
            
            return jsonify({
                'success': True,
                'jobs': jobs,
                'total_count': len(jobs)
            })
        
        except Exception as e:
            logger.error(f"[API_JOBS] API jobs error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/jobs', methods=['POST'])
    def api_create_job():
        """API endpoint for job creation"""
        logger.info("[API_JOB_CREATE] Received job creation request")
        
        try:
            data = request.get_json()
            if not data:
                logger.error("[API_JOB_CREATE] No data provided")
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            logger.info(f"[API_JOB_CREATE] Creating {data.get('type', 'unknown')} job '{data.get('name', 'unnamed')}'")
            
            # Debug: Log the complete received data
            logger.info(f"[API_JOB_CREATE] Received data: {data}")
            if data.get('type') == 'sql':
                logger.info(f"[API_JOB_CREATE] SQL Query received: '{data.get('sql_query', 'NONE')}'")
                logger.info(f"[API_JOB_CREATE] Connection name received: '{data.get('connection_name', 'NONE')}'")
            
            # Use JobManager to create job
            from core.job_manager import JobManager
            job_manager = JobManager()
            
            result = job_manager.create_job(data)
            
            if result['success']:
                logger.info(f"[API_JOB_CREATE] Job created successfully: {result['job_id']}")
                return jsonify(result), 201
            else:
                logger.warning(f"[API_JOB_CREATE] Job creation failed: {result['error']}")
                return jsonify(result), 400
        
        except Exception as e:
            logger.error(f"[API_JOB_CREATE] API create job error: {e}")
            return jsonify({
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }), 500
    
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
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            db_manager = pool.db_manager
            
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
            
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            db_manager = pool.db_manager
            
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
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            db_manager = pool.db_manager
            
            success = db_manager.remove_connection(connection_name)
            
            if success:
                return jsonify({'success': True, 'message': f'Connection "{connection_name}" deleted successfully'})
            else:
                return jsonify({'success': False, 'error': f'Connection "{connection_name}" not found'}), 404
                
        except Exception as e:
            logger.error(f"API delete connection error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/connections/<connection_name>/test', methods=['POST'])
    def api_test_existing_connection(connection_name):
        """API endpoint to test an existing saved database connection"""
        logger.info(f"[API_TEST] Testing existing connection '{connection_name}' via API")
        
        try:
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            db_manager = pool.db_manager
            
            # Test the existing connection
            test_result = db_manager.test_connection(connection_name)
            
            if test_result['success']:
                logger.info(f"[API_TEST] Connection '{connection_name}' test successful via API")
                return jsonify({
                    'success': True,
                    'message': test_result.get('message', 'Connection successful'),
                    'response_time': test_result.get('response_time', 0),
                    'server_info': test_result.get('server_info', {})
                })
            else:
                logger.warning(f"[API_TEST] Connection '{connection_name}' test failed via API: {test_result.get('error')}")
                return jsonify({
                    'success': False,
                    'error': test_result.get('error', 'Connection test failed'),
                    'response_time': test_result.get('response_time', 0)
                }), 400
                
        except Exception as e:
            logger.error(f"[API_TEST] API test existing connection error for '{connection_name}': {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/system/database-status', methods=['GET'])
    def api_system_database_status():
        """Get system database connection status"""
        try:
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            db_manager = pool.db_manager
            
            # Test system database connection
            system_status = db_manager.test_connection("system")
            
            if system_status['success']:
                # Get system connection info dynamically
                system_info = db_manager.get_connection_info("system")
                database_name = system_info.get('database', 'Unknown') if system_info else 'Unknown'
                server_name = system_info.get('server', 'Unknown') if system_info else 'Unknown'
                port = system_info.get('port') if system_info else None
                
                # Build server display string
                server_display = server_name
                if port and port != 1433:
                    server_display += f":{port}"
                
                return jsonify({
                    'success': True,
                    'connected': True,
                    'database': database_name,
                    'server': server_display,
                    'response_time': system_status['response_time'],
                    'server_info': system_status.get('server_info', {})
                })
            else:
                return jsonify({
                    'success': False,
                    'connected': False,
                    'error': system_status['error'],
                    'response_time': system_status.get('response_time', 0)
                })
                
        except Exception as e:
            logger.error(f"API system database status error: {e}")
            return jsonify({
                'success': False,
                'connected': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/connections/validate-all', methods=['POST'])
    def api_validate_all_connections():
        """Validate all saved connections in parallel"""
        import time
        start_time = time.time()
        
        logger.info("[PARALLEL_VALIDATION] Starting parallel validation of all connections")
        
        try:
            from database.connection_pool import get_connection_pool
            import concurrent.futures
            import threading
            
            pool = get_connection_pool()
            connections = pool.db_manager.list_connections()
            
            logger.info(f"[PARALLEL_VALIDATION] Found {len(connections)} connections to validate: {', '.join(connections)}")
            
            if not connections:
                logger.info("[PARALLEL_VALIDATION] No connections found to validate")
                return jsonify({
                    'success': True,
                    'results': {},
                    'message': 'No connections to validate',
                    'total_time': time.time() - start_time
                })
            
            # Function to test a single connection with detailed logging
            def test_single_connection(conn_name):
                thread_start = time.time()
                logger.debug(f"[PARALLEL_VALIDATION] Starting test for connection '{conn_name}' in thread {threading.current_thread().name}")
                
                try:
                    result = pool.db_manager.test_connection(conn_name)
                    thread_time = time.time() - thread_start
                    
                    if result['success']:
                        logger.info(f"[PARALLEL_VALIDATION] Connection '{conn_name}' validated successfully in {thread_time:.2f}s (response: {result['response_time']:.2f}s)")
                    else:
                        logger.warning(f"[PARALLEL_VALIDATION] Connection '{conn_name}' validation failed in {thread_time:.2f}s: {result.get('error', 'Unknown error')}")
                    
                    return conn_name, {
                        'success': result['success'],
                        'status': 'valid' if result['success'] else 'invalid',
                        'response_time': result.get('response_time', 0),
                        'thread_time': thread_time,
                        'error': result.get('error', ''),
                        'server_info': result.get('server_info', {})
                    }
                except Exception as e:
                    thread_time = time.time() - thread_start
                    logger.error(f"[PARALLEL_VALIDATION] Exception testing connection '{conn_name}' in {thread_time:.2f}s: {e}")
                    
                    return conn_name, {
                        'success': False,
                        'status': 'error',
                        'response_time': 0,
                        'thread_time': thread_time,
                        'error': str(e),
                        'server_info': {}
                    }
            
            # Test all connections in parallel with timing
            logger.info(f"[PARALLEL_VALIDATION] Starting parallel execution with max 5 worker threads")
            parallel_start = time.time()
            
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Submit all connection tests
                future_to_conn = {
                    executor.submit(test_single_connection, conn_name): conn_name 
                    for conn_name in connections
                }
                
                logger.debug(f"[PARALLEL_VALIDATION] Submitted {len(future_to_conn)} test tasks to thread pool")
                
                # Collect results as they complete
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_conn):
                    conn_name, result = future.result()
                    results[conn_name] = result
                    completed_count += 1
                    
                    logger.debug(f"[PARALLEL_VALIDATION] Completed {completed_count}/{len(connections)}: '{conn_name}' -> {result['status']}")
            
            parallel_time = time.time() - parallel_start
            total_time = time.time() - start_time
            
            # Calculate statistics
            valid_count = sum(1 for r in results.values() if r['success'])
            invalid_count = sum(1 for r in results.values() if not r['success'])
            avg_response_time = sum(r['response_time'] for r in results.values()) / len(results) if results else 0
            avg_thread_time = sum(r['thread_time'] for r in results.values()) / len(results) if results else 0
            
            logger.info(f"[PARALLEL_VALIDATION] Completed parallel validation: {valid_count} valid, {invalid_count} invalid")
            logger.info(f"[PARALLEL_VALIDATION] Timing: parallel={parallel_time:.2f}s, total={total_time:.2f}s")
            logger.info(f"[PARALLEL_VALIDATION] Average response time: {avg_response_time:.2f}s, average thread time: {avg_thread_time:.2f}s")
            
            # Log detailed results
            for conn_name, result in results.items():
                status = "✓" if result['success'] else "✗"
                logger.debug(f"[PARALLEL_VALIDATION] {status} {conn_name}: {result['status']} ({result['response_time']:.2f}s)")
            
            return jsonify({
                'success': True,
                'results': results,
                'total_connections': len(connections),
                'valid_connections': valid_count,
                'invalid_connections': invalid_count,
                'timing': {
                    'total_time': total_time,
                    'parallel_time': parallel_time,
                    'average_response_time': avg_response_time,
                    'average_thread_time': avg_thread_time
                }
            })
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[PARALLEL_VALIDATION] API validate all connections error after {total_time:.2f}s: {e}")
            return jsonify({
                'success': False, 
                'error': str(e), 
                'total_time': total_time
            }), 500
    
    @app.route('/api/connections/audit-trail', methods=['GET'])
    def api_connection_audit_trail():
        """Get connection audit trail"""
        try:
            from database.connection_manager import DatabaseConnectionManager
            
            connection_name = request.args.get('connection_name')
            limit = request.args.get('limit', 50, type=int)
            
            logger.info(f"[AUDIT_API] Retrieving audit trail" + (f" for connection '{connection_name}'" if connection_name else " (all connections)") + f" (limit: {limit})")
            
            db_manager = DatabaseConnectionManager()
            audit_entries = db_manager.get_connection_audit_trail(connection_name, limit)
            
            logger.info(f"[AUDIT_API] Retrieved {len(audit_entries)} audit entries")
            
            # Format entries for API response
            formatted_entries = []
            for entry in audit_entries:
                formatted_entry = {
                    'timestamp': entry['timestamp'].isoformat() if hasattr(entry['timestamp'], 'isoformat') else str(entry['timestamp']),
                    'user': entry['user'],
                    'host': entry['host'],
                    'action': entry['action'],
                    'connection_name': entry['connection_name'],
                    'details': entry['details']
                }
                formatted_entries.append(formatted_entry)
            
            return jsonify({
                'success': True,
                'audit_entries': formatted_entries,
                'total_count': len(formatted_entries),
                'filter': {
                    'connection_name': connection_name,
                    'limit': limit
                }
            })
            
        except Exception as e:
            logger.error(f"[AUDIT_API] Error retrieving audit trail: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/system/connection-pool-stats', methods=['GET'])
    def api_connection_pool_stats():
        """Get connection pool statistics"""
        try:
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            
            stats = pool.get_pool_stats()
            
            logger.info(f"[POOL_STATS] Retrieved connection pool statistics: {stats['total_connections']} active connections")
            
            return jsonify({
                'success': True,
                'pool_stats': stats,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            logger.error(f"[POOL_STATS] Error retrieving pool stats: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/system/cleanup-pool', methods=['POST'])
    def api_cleanup_pool():
        """Manually trigger connection pool cleanup"""
        try:
            from database.connection_pool import get_connection_pool
            pool = get_connection_pool()
            
            # Get stats before cleanup
            stats_before = pool.get_pool_stats()
            
            # Perform cleanup
            pool.cleanup_pool()
            
            # Get stats after cleanup
            stats_after = pool.get_pool_stats()
            
            cleaned_connections = stats_before['total_connections'] - stats_after['total_connections']
            
            logger.info(f"[POOL_CLEANUP] Manual cleanup completed: removed {cleaned_connections} connections")
            
            return jsonify({
                'success': True,
                'message': f'Pool cleanup completed: removed {cleaned_connections} expired connections',
                'before': stats_before,
                'after': stats_after,
                'cleaned_connections': cleaned_connections
            })
            
        except Exception as e:
            logger.error(f"[POOL_CLEANUP] Error during pool cleanup: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
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
            if '\\' in server and port and port != 1433:
                # Named instance with custom port
                components.append(f"SERVER={server},{port}")
            elif '\\' in server:
                # Named instance - don't add port for default
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
            
            # Log the connection string for debugging (without password)
            debug_string = connection_string.replace(password, "***") if password else connection_string
            logger.info(f"Testing connection with string: {debug_string}")
            
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
            # Simply render the template - connections are loaded dynamically via JavaScript
            logger.info("Rendering connections page - connections will be loaded dynamically")
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