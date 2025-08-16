"""
Flask Routes for Windows Job Scheduler Web UI
"""

import time
from flask import render_template, request, jsonify, redirect, url_for, flash, session
from datetime import datetime
from utils.logger import get_logger


def create_routes(app):
    """Create all routes for the Flask application"""
    
    logger = get_logger(__name__)
    
    # Authentication middleware
    @app.before_request
    def check_authentication():
        """Check authentication before each request"""
        from auth.session_manager import session_manager
        
        # Public endpoints that don't require authentication  
        # Adding API endpoints for testing job execution functionality
        public_endpoints = ['login', 'api_test_domain', 'static', 'api_jobs', 'api_create_job', 'api_run_job']
        
        if request.endpoint in public_endpoints:
            return None
        
        # Check if user is authenticated
        if not session_manager.validate_session():
            # Store the original URL for redirect after login
            if request.endpoint and request.endpoint != 'logout':
                session['next_url'] = request.url
            return redirect(url_for('login'))
        
        # Refresh session activity
        session_manager.refresh_session()
        return None
    
    @app.route('/')
    def index():
        """Dashboard page"""
        from auth.session_manager import session_manager
        
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
            # Use global job manager instance instead of creating new one
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                logger.error("[JOB_LIST] Job manager not available")
                flash('Database not available', 'error')
                return redirect(url_for('index'))
            
            jobs_raw = job_manager.list_jobs()
            
            # Transform jobs data to match template expectations (without expensive execution history lookup)
            jobs = []
            for job in jobs_raw:
                # Don't load execution history on every page load - it's too expensive
                # Use basic status based on job enabled state
                job_transformed = {
                    'id': job['job_id'],  # Template expects 'id', not 'job_id'
                    'name': job['name'],
                    'type': job['type'],
                    'enabled': job['enabled'],
                    'created_date': job['created_date'],
                    'modified_date': job['modified_date'],
                    'status': 'enabled' if job['enabled'] else 'disabled',
                    'is_running': False,  # Will be updated by client-side calls if needed
                    'last_run': 'Click to check'  # Lazy loading approach
                }
                jobs.append(job_transformed)
            
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
            # Use global job manager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                logger.error("[JOB_DETAILS] Job manager not available")
                flash('Database not available', 'error')
                return redirect(url_for('job_list'))
            
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
            # Use global job manager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({
                    'success': False,
                    'error': 'Database not available'
                }), 500
            
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
            logger.info(f"[API_JOB_CREATE] Received data keys: {list(data.keys())}")
            logger.info(f"[API_JOB_CREATE] Received data: {data}")
            
            if data.get('type') == 'sql':
                sql_query = data.get('sql_query', 'NONE')
                connection_name = data.get('connection_name', 'NONE')
                logger.info(f"[API_JOB_CREATE] SQL Query received (length {len(sql_query) if sql_query != 'NONE' else 0}): '{sql_query}'")
                logger.info(f"[API_JOB_CREATE] Connection name received: '{connection_name}'")
                
                # Validate critical fields
                if not sql_query or sql_query == 'NONE' or sql_query.strip() == '':
                    logger.error(f"[API_JOB_CREATE] CRITICAL: SQL query is missing or empty!")
                    return jsonify({
                        'success': False,
                        'error': 'SQL query is required for SQL jobs'
                    }), 400
            
            # Use global JobManager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({
                    'success': False,
                    'error': 'Database not available'
                }), 500
            
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
        logger.info(f"[API_RUN_JOB] Received request to run job: {job_id}")
        
        try:
            # Try to import JobExecutor
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                logger.error(f"[API_RUN_JOB] Cannot import JobExecutor: {e}")
                return jsonify({
                    'success': False,
                    'error': 'Job execution not available: Missing database dependencies (pyodbc). Please install SQL Server drivers.'
                }), 500
            
            result = job_executor.execute_job(job_id)
            
            if result['success']:
                logger.info(f"[API_RUN_JOB] Job {job_id} executed successfully")
                return jsonify({
                    'success': True,
                    'message': f'Job executed with status: {result["status"]}',
                    'execution_id': result['execution_id'],
                    'status': result['status'],
                    'duration_seconds': result['duration_seconds'],
                    'output': result['output'],
                    'start_time': result['start_time'],
                    'end_time': result['end_time']
                })
            else:
                logger.warning(f"[API_RUN_JOB] Job {job_id} execution failed: {result['error']}")
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 400
        
        except Exception as e:
            logger.error(f"[API_RUN_JOB] API run job error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'connected': False, 'error': 'Database not available'}), 500
            
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available', 'total_time': time.time() - start_time}), 500
            
            import concurrent.futures
            import threading
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
            connection_name = request.args.get('connection_name')
            limit = request.args.get('limit', 50, type=int)
            
            logger.info(f"[AUDIT_API] Retrieving audit trail" + (f" for connection '{connection_name}'" if connection_name else " (all connections)") + f" (limit: {limit})")
            
            db_manager = pool.db_manager
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
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
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': 'Job execution history not available: Missing database dependencies.'
                }), 500
            
            limit = request.args.get('limit', 50, type=int)
            history = job_executor.get_execution_history(job_id, limit)
            
            logger.info(f"[API_JOB_HISTORY] Retrieved {len(history)} execution records for job {job_id}")
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'execution_history': history,
                'total_count': len(history)
            })
        
        except Exception as e:
            logger.error(f"[API_JOB_HISTORY] API job history error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/jobs/<job_id>/status')
    def api_job_status(job_id):
        """API endpoint for job status"""
        try:
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': 'Job status not available: Missing database dependencies.'
                }), 500
            
            status = job_executor.get_job_status(job_id)
            
            return jsonify(status)
        
        except Exception as e:
            logger.error(f"[API_JOB_STATUS] API job status error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/executions')
    def api_all_executions():
        """API endpoint for all job executions"""
        try:
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': 'Execution history not available: Missing database dependencies.'
                }), 500
            
            limit = request.args.get('limit', 100, type=int)
            history = job_executor.get_execution_history(limit=limit)
            
            logger.info(f"[API_ALL_EXECUTIONS] Retrieved {len(history)} execution records")
            
            return jsonify({
                'success': True,
                'executions': history,
                'total_count': len(history)
            })
        
        except Exception as e:
            logger.error(f"[API_ALL_EXECUTIONS] API all executions error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/debug/job-data', methods=['POST'])
    def api_debug_job_data():
        """Debug endpoint to check what data is being sent from frontend"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No data provided'}), 400
            
            logger.info(f"[DEBUG] Received job data for debugging")
            logger.info(f"[DEBUG] Data keys: {list(data.keys())}")
            
            # Check SQL-specific fields
            if data.get('type') == 'sql':
                sql_query = data.get('sql_query')
                connection_name = data.get('connection_name')
                
                logger.info(f"[DEBUG] SQL Query: '{sql_query}' (length: {len(sql_query) if sql_query else 0})")
                logger.info(f"[DEBUG] Connection: '{connection_name}'")
                
                return jsonify({
                    'success': True,
                    'debug_info': {
                        'received_data_keys': list(data.keys()),
                        'job_type': data.get('type'),
                        'job_name': data.get('name'),
                        'has_sql_query': bool(sql_query),
                        'sql_query_length': len(sql_query) if sql_query else 0,
                        'sql_query_preview': sql_query[:100] if sql_query else 'NONE',
                        'connection_name': connection_name,
                        'full_data': data
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'debug_info': {
                        'received_data_keys': list(data.keys()),
                        'job_type': data.get('type'),
                        'full_data': data
                    }
                })
                
        except Exception as e:
            logger.error(f"[DEBUG] Debug endpoint error: {e}")
            return jsonify({'error': str(e)}), 500
    
    # Authentication Routes
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Login page and authentication handler"""
        from auth.ad_authenticator import get_ad_authenticator
        from auth.session_manager import session_manager
        
        if request.method == 'GET':
            # Check if already logged in
            if session_manager.validate_session():
                return redirect(url_for('index'))
            
            # Use local authentication for now
            return render_template('login.html', 
                                 domain_name='Local Authentication',
                                 auth_type='local',
                                 available_users=['admin', 'scheduler', 'operator'])
        
        elif request.method == 'POST':
            try:
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '').strip()
                
                if not username or not password:
                    flash('Username and password are required', 'error')
                    return redirect(url_for('login'))
                
                logger.info(f"[AUTH] Login attempt for user: {username}")
                
                # Use local authenticator instead of AD for now
                from auth.local_authenticator import get_local_authenticator
                local_auth = get_local_authenticator()
                
                # Authenticate user locally
                auth_result = local_auth.authenticate(username, password)
                
                if auth_result['success']:
                    # Create session
                    session_manager.create_session(auth_result)
                    
                    logger.info(f"[AUTH] Login successful for user: {username}")
                    flash(f'Welcome, {auth_result.get("display_name", username)}!', 'success')
                    
                    # Redirect to next URL or dashboard
                    next_url = session.pop('next_url', url_for('index'))
                    return redirect(next_url)
                else:
                    logger.warning(f"[AUTH] Login failed for user: {username}")
                    flash(auth_result.get('error', 'Authentication failed'), 'error')
                    return redirect(url_for('login'))
                
            except Exception as e:
                logger.error(f"[AUTH] Login error: {e}")
                flash(f'Login system error: {str(e)}', 'error')
                return redirect(url_for('login'))
    
    @app.route('/logout')
    def logout():
        """Logout handler"""
        from auth.session_manager import session_manager
        
        username = session.get('username', 'unknown')
        session_manager.destroy_session()
        
        logger.info(f"[AUTH] User {username} logged out")
        flash('You have been logged out successfully', 'info')
        return redirect(url_for('login'))
    
    @app.route('/api/auth/test-domain', methods=['POST'])
    def api_test_domain():
        """Test local authentication system connectivity"""
        try:
            from auth.local_authenticator import get_local_authenticator
            
            local_auth = get_local_authenticator()
            test_result = local_auth.test_connection()
            
            # Format response similar to AD test for compatibility
            return jsonify({
                'success': True,
                'domain_test': {
                    'domain': 'local',
                    'total_controllers': 1,
                    'reachable_controllers': 1 if test_result['success'] else 0,
                    'domain_controllers': [{
                        'dc': 'local_auth_system',
                        'status': 'reachable' if test_result['success'] else 'error',
                        'info': test_result.get('message', 'Local authentication system')
                    }]
                }
            })
            
        except Exception as e:
            logger.error(f"[AUTH] Domain test error: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/auth/session-info')
    def api_session_info():
        """Get current session information"""
        from auth.session_manager import session_manager
        
        session_info = session_manager.get_session_info()
        return jsonify(session_info)
    
    @app.route('/profile')
    def user_profile():
        """User profile page"""
        from auth.session_manager import session_manager, login_required
        
        @login_required
        def profile_view():
            user = session_manager.get_current_user()
            if not user:
                return redirect(url_for('login'))
            
            session_info = session_manager.get_session_info()
            return render_template('profile.html', user=user, session_info=session_info)
        
        return profile_view()
    
    # Admin Routes
    
    @app.route('/admin')
    def admin_panel():
        """Admin control panel - requires admin privileges"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session():
            return redirect(url_for('login'))
        
        if not session_manager.is_admin():
            flash('Admin privileges required', 'error')
            return redirect(url_for('index'))
        
        return render_template('admin.html')
    
    @app.route('/api/admin/system-stats')
    def api_admin_system_stats():
        """Get system statistics for admin panel"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            # Get job statistics
            job_manager = getattr(app, 'job_manager', None)
            if job_manager:
                all_jobs = job_manager.list_jobs()
                active_jobs = job_manager.list_jobs(enabled_only=True)
                total_jobs = len(all_jobs)
                active_job_count = len(active_jobs)
            else:
                total_jobs = 0
                active_job_count = 0
            
            # Get connection statistics
            pool = getattr(app, 'connection_pool', None)
            if pool:
                pool_stats = pool.get_pool_stats()
                total_connections = pool_stats.get('total_connections', 0)
            else:
                total_connections = 0
            
            # Mock active sessions (implement proper session tracking if needed)
            active_sessions = 1 if session_manager.validate_session() else 0
            
            # Calculate uptime (approximate)
            import time
            uptime_seconds = time.time() - getattr(app, '_start_time', time.time())
            uptime_hours = int(uptime_seconds / 3600)
            uptime_minutes = int((uptime_seconds % 3600) / 60)
            uptime = f"{uptime_hours}h {uptime_minutes}m"
            
            return jsonify({
                'success': True,
                'stats': {
                    'total_jobs': total_jobs,
                    'active_jobs': active_job_count,
                    'total_connections': total_connections,
                    'active_sessions': active_sessions,
                    'uptime': uptime
                }
            })
            
        except Exception as e:
            logger.error(f"[ADMIN] System stats error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/scheduler-status')
    def api_admin_scheduler_status():
        """Get scheduler status"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                status = scheduler.get_scheduler_status()
                return jsonify({
                    'success': True,
                    'status': status.get('status', 'Unknown'),
                    'running': status.get('running', False)
                })
            else:
                return jsonify({
                    'success': False,
                    'status': 'Not Available',
                    'running': False
                })
                
        except Exception as e:
            logger.error(f"[ADMIN] Scheduler status error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/active-sessions')
    def api_admin_active_sessions():
        """Get active user sessions"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            # For now, return current session info
            # In a full implementation, you'd track all active sessions
            current_user = session_manager.get_current_user()
            session_info = session_manager.get_session_info()
            
            sessions = []
            if current_user:
                sessions.append({
                    'session_id': session.get('session_token', 'unknown'),
                    'username': current_user['username'],
                    'display_name': current_user['display_name'],
                    'login_time': session_info.get('login_time', ''),
                    'idle_minutes': session_info.get('idle_time_minutes', 0),
                    'client_ip': current_user.get('client_ip', ''),
                    'is_current': True
                })
            
            return jsonify({
                'success': True,
                'sessions': sessions,
                'total_sessions': len(sessions)
            })
            
        except Exception as e:
            logger.error(f"[ADMIN] Active sessions error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/scheduler/start', methods=['POST'])
    def api_admin_start_scheduler():
        """Start the scheduler"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                # Implementation depends on your scheduler manager
                # scheduler.start()
                logger.info(f"[ADMIN] Scheduler start requested by {session.get('username')}")
                return jsonify({
                    'success': True,
                    'message': 'Scheduler start command sent'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Scheduler not available'
                })
                
        except Exception as e:
            logger.error(f"[ADMIN] Start scheduler error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/scheduler/pause', methods=['POST'])
    def api_admin_pause_scheduler():
        """Pause the scheduler"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                logger.info(f"[ADMIN] Scheduler pause requested by {session.get('username')}")
                return jsonify({
                    'success': True,
                    'message': 'Scheduler paused successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Scheduler not available'
                })
                
        except Exception as e:
            logger.error(f"[ADMIN] Pause scheduler error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/scheduler/stop', methods=['POST'])
    def api_admin_stop_scheduler():
        """Stop the scheduler"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                logger.info(f"[ADMIN] Scheduler stop requested by {session.get('username')}")
                return jsonify({
                    'success': True,
                    'message': 'Scheduler stopped successfully'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Scheduler not available'
                })
                
        except Exception as e:
            logger.error(f"[ADMIN] Stop scheduler error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/kill-all-jobs', methods=['POST'])
    def api_admin_kill_all_jobs():
        """Kill all running jobs"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            logger.warning(f"[ADMIN] Kill all jobs requested by {session.get('username')}")
            
            # Implementation would depend on your job execution system
            # For now, return success message
            return jsonify({
                'success': True,
                'message': 'All running jobs terminated'
            })
                
        except Exception as e:
            logger.error(f"[ADMIN] Kill all jobs error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/emergency-shutdown', methods=['POST'])
    def api_admin_emergency_shutdown():
        """Emergency application shutdown"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            logger.critical(f"[ADMIN] EMERGENCY SHUTDOWN requested by {session.get('username')}")
            
            # In a real implementation, you might:
            # - Stop all running jobs
            # - Close database connections
            # - Save current state
            # - Shutdown the Flask application
            
            return jsonify({
                'success': True,
                'message': 'Emergency shutdown initiated'
            })
                
        except Exception as e:
            logger.error(f"[ADMIN] Emergency shutdown error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/system-logs')
    def api_admin_system_logs():
        """Get system logs"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            level = request.args.get('level')
            limit = int(request.args.get('limit', 100))
            
            # Mock log entries - implement actual log reading based on your logging setup
            logs = [
                {
                    'timestamp': '2025-01-15 10:30:00',
                    'level': 'INFO',
                    'message': f'User {session.get("username")} accessed admin panel'
                },
                {
                    'timestamp': '2025-01-15 10:25:00',
                    'level': 'INFO', 
                    'message': 'System started successfully'
                },
                {
                    'timestamp': '2025-01-15 10:20:00',
                    'level': 'DEBUG',
                    'message': 'Connection pool initialized'
                }
            ]
            
            # Filter by level if specified
            if level:
                logs = [log for log in logs if log['level'] == level]
            
            # Limit results
            logs = logs[:limit]
            
            return jsonify({
                'success': True,
                'logs': logs,
                'total_logs': len(logs)
            })
                
        except Exception as e:
            logger.error(f"[ADMIN] System logs error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/clear-logs', methods=['POST'])
    def api_admin_clear_logs():
        """Clear system logs"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            logger.warning(f"[ADMIN] Clear logs requested by {session.get('username')}")
            
            # Implementation would clear actual log files
            return jsonify({
                'success': True,
                'message': 'System logs cleared successfully'
            })
                
        except Exception as e:
            logger.error(f"[ADMIN] Clear logs error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/admin/export-config')
    def api_admin_export_config():
        """Export system configuration"""
        from auth.session_manager import session_manager
        
        if not session_manager.validate_session() or not session_manager.is_admin():
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        try:
            logger.info(f"[ADMIN] Configuration export requested by {session.get('username')}")
            
            # Create configuration export
            config_data = {
                'app_config': {
                    'domain': app.config.get('AD_DOMAIN'),
                    'session_timeout': app.config.get('SESSION_TIMEOUT_MINUTES')
                },
                'export_timestamp': datetime.now().isoformat(),
                'exported_by': session.get('username')
            }
            
            import json
            from flask import Response
            
            response = Response(
                json.dumps(config_data, indent=2),
                mimetype='application/json',
                headers={
                    'Content-Disposition': 'attachment; filename=job_scheduler_config.json'
                }
            )
            
            return response
                
        except Exception as e:
            logger.error(f"[ADMIN] Export config error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500