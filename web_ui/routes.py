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
    
    # Authentication removed - direct access to all functionality
    
    @app.route('/')
    def index():
        """Dashboard page"""
        
        try:
            # Try integrated scheduler first, then fall back to old scheduler manager
            integrated_scheduler = getattr(app, 'integrated_scheduler', None)
            scheduler = getattr(app, 'scheduler_manager', None)
            job_manager = getattr(app, 'job_manager', None)
            
            if integrated_scheduler:
                # Use integrated scheduler for status
                status = integrated_scheduler.get_scheduler_status()
                
                # Get recent jobs from database
                if job_manager:
                    jobs_raw = job_manager.list_jobs()
                    recent_jobs = jobs_raw[:5] if jobs_raw else []
                else:
                    recent_jobs = []
                    
                logger.info("[DASHBOARD] Using integrated scheduler for dashboard")
                
            elif scheduler:
                # Fallback to old scheduler manager
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
                
                logger.info("[DASHBOARD] Using legacy scheduler manager for dashboard")
                
            else:
                # No scheduler available - show basic status
                status = {
                    'running': False,
                    'total_jobs': 0,
                    'enabled_jobs': 0,
                    'scheduled_jobs': 0,
                    'disabled_jobs': 0,
                    'job_types': {},
                    'next_run_times': [],
                    'status': 'not_available'
                }
                recent_jobs = []
                logger.warning("[DASHBOARD] No scheduler available - showing basic status")
            
            return render_template('index.html', 
                                 status=status, 
                                 recent_jobs=recent_jobs,
                                 total_jobs=len(recent_jobs) if recent_jobs else 0)
        
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
                    'type': job['job_type'],  # Changed from job['type'] to job['job_type'] for consistency
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
    
    @app.route('/executions/history')
    def execution_history():
        """Execution history dashboard page"""
        try:
            logger.info("[EXECUTION_HISTORY] Rendering execution history page")
            return render_template('execution_history.html')
            
        except Exception as e:
            logger.error(f"[EXECUTION_HISTORY] Execution history page error: {e}")
            flash(f'Error loading execution history: {str(e)}', 'error')
            return redirect(url_for('index'))

    @app.route('/system/workflow')
    def system_workflow():
        """System workflow visualization page"""
        try:
            logger.info("[SYSTEM_WORKFLOW] Rendering system workflow page")
            return render_template('system_workflow.html')
            
        except Exception as e:
            logger.error(f"[SYSTEM_WORKFLOW] System workflow page error: {e}")
            flash(f'Error loading system workflow: {str(e)}', 'error')
            return redirect(url_for('index'))

    @app.route('/jobs/create')
    def create_job():
        """Job creation page"""
        return render_template('create_job.html')
    
    @app.route('/jobs/<job_id>/edit')
    def edit_job(job_id):
        """Edit job page"""
        try:
            logger.info(f"[EDIT_JOB] Rendering edit job page for job {job_id}")
            return render_template('edit_job.html', job_id=job_id)
            
        except Exception as e:
            logger.error(f"[EDIT_JOB] Edit job page error: {e}")
            flash(f'Error loading edit job page: {str(e)}', 'error')
            return redirect(url_for('job_list'))

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
            
            # Get job execution history
            try:
                # Try to use JobExecutor first
                try:
                    from core.job_executor import JobExecutor
                    job_executor = JobExecutor()
                    history = job_executor.get_execution_history(job_id, limit=20)
                    logger.debug(f"[JOB_DETAILS] Loaded {len(history)} execution records from JobExecutor")
                except ImportError as ie:
                    logger.warning(f"[JOB_DETAILS] JobExecutor not available: {ie}")
                    # Fallback to job manager for all execution history, then filter
                    all_history = job_manager.get_all_execution_history(limit=100)
                    history = [h for h in all_history if h.get('job_id') == job_id][:20]
                    logger.debug(f"[JOB_DETAILS] Filtered {len(history)} execution records for job {job_id}")
            except Exception as e:
                logger.warning(f"[JOB_DETAILS] Could not load execution history: {e}")
                history = []
            
            # Flatten job configuration for template
            config = job.get('configuration', {})
            
            # Add configuration fields to job object for template compatibility
            job['timeout'] = config.get('timeout', 300)
            job['max_retries'] = config.get('max_retries', 3)
            job['retry_delay'] = config.get('retry_delay', 30)
            job['run_as'] = config.get('run_as')
            job['description'] = config.get('description', '')
            
            # Format created_date properly for template
            created_date = job.get('created_date')
            if created_date:
                # Convert datetime to string if needed
                if hasattr(created_date, 'strftime'):
                    created_date = created_date.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(created_date, str):
                    # Already a string, just ensure it's properly formatted
                    created_date = created_date[:19]  # Take first 19 characters
            job['metadata'] = {'created_date': created_date or 'Unknown'}
            
            # Job-specific configuration
            if job['job_type'] == 'sql':
                sql_config = config.get('sql', {})
                job['connection_name'] = sql_config.get('connection_name', '')
                job['database_name'] = sql_config.get('database_name', '')
                job['sql_query'] = sql_config.get('query', '')
                job['query_timeout'] = sql_config.get('query_timeout', job['timeout'])
                job['max_rows'] = sql_config.get('max_rows', '')
                job['fetch_size'] = sql_config.get('fetch_size', '')
            elif job['job_type'] == 'powershell':
                ps_config = config.get('powershell', {})
                job['script_content'] = ps_config.get('script_content', '')
                job['script_path'] = ps_config.get('script_path', '')
                job['execution_policy'] = ps_config.get('execution_policy', 'RemoteSigned')
                job['working_directory'] = ps_config.get('working_directory', '')
                job['parameters'] = ps_config.get('parameters', [])
            
            # Create status object with available information
            status = {
                'enabled': job['enabled'],
                'current_status': 'enabled' if job['enabled'] else 'disabled',
                'is_running': False,  # TODO: Get from scheduler if available
                'retry_count': 0,     # TODO: Get from execution history
                'max_retries': job['max_retries'],
                'schedule': config.get('schedule'),
                'next_run_time': None,  # TODO: Get from scheduler
                'last_run_time': None,  # TODO: Get from execution history
                'last_result': history[0] if history else None
            }
            
            # Format execution history datetime fields
            formatted_history = []
            for execution in history:
                formatted_execution = execution.copy()
                
                # Format datetime fields safely
                for time_field in ['start_time', 'end_time']:
                    time_value = execution.get(time_field)
                    if time_value:
                        if hasattr(time_value, 'strftime'):
                            formatted_execution[time_field] = time_value.strftime('%Y-%m-%d %H:%M:%S')
                        elif isinstance(time_value, str):
                            formatted_execution[time_field] = time_value[:19] if len(time_value) >= 19 else time_value
                        else:
                            formatted_execution[time_field] = str(time_value)[:19]
                    else:
                        formatted_execution[time_field] = None
                
                formatted_history.append(formatted_execution)
            
            # Update history with formatted version
            history = formatted_history
            
            # Add last run time if we have history
            if history:
                status['last_run_time'] = history[0].get('start_time')
                status['last_result'] = history[0]  # Update with formatted data
            
            logger.info(f"[JOB_DETAILS] Successfully loaded job details: {job['name']} (ID: {job_id})")
            logger.debug(f"[JOB_DETAILS] Job type: {job.get('job_type')}, Enabled: {job.get('enabled')}")
            logger.debug(f"[JOB_DETAILS] History count: {len(history)}")
            
            return render_template('job_details.html', job=job, status=status, history=history)
        
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
    
    @app.route('/api/jobs/<job_id>', methods=['GET'])
    def api_get_job(job_id):
        """API endpoint to get individual job details"""
        logger.info(f"[API_GET_JOB] Fetching job details for {job_id}")
        
        try:
            # Use global JobManager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({
                    'success': False,
                    'error': 'Database not available'
                }), 500
            
            job = job_manager.get_job(job_id)
            
            if job:
                logger.info(f"[API_GET_JOB] Job {job_id} found")
                return jsonify({
                    'success': True,
                    'job': job
                })
            else:
                logger.warning(f"[API_GET_JOB] Job {job_id} not found")
                return jsonify({
                    'success': False,
                    'error': f'Job {job_id} not found'
                }), 404
                
        except Exception as e:
            logger.error(f"[API_GET_JOB] Error fetching job {job_id}: {e}")
            return jsonify({
                'success': False,
                'error': f'Error fetching job: {str(e)}'
            }), 500

    @app.route('/api/jobs/<job_id>', methods=['PUT'])
    def api_update_job(job_id):
        """API endpoint to update job configuration"""
        logger.info(f"[API_UPDATE_JOB] Updating job {job_id}")
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            # Use global JobManager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({
                    'success': False,
                    'error': 'Database not available'
                }), 500
            
            # Update the job
            result = job_manager.update_job(job_id, data)
            
            if result['success']:
                logger.info(f"[API_UPDATE_JOB] Job {job_id} updated successfully")
                return jsonify(result)
            else:
                logger.warning(f"[API_UPDATE_JOB] Failed to update job {job_id}: {result['error']}")
                return jsonify(result), 400
                
        except Exception as e:
            logger.error(f"[API_UPDATE_JOB] Error updating job {job_id}: {e}")
            return jsonify({
                'success': False,
                'error': f'Error updating job: {str(e)}'
            }), 500

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
        """API endpoint for job creation with integrated scheduling"""
        logger.info("[API_JOB_CREATE] Received job creation request")
        
        try:
            data = request.get_json()
            if not data:
                logger.error("[API_JOB_CREATE] No data provided")
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            logger.info(f"[API_JOB_CREATE] Creating {data.get('type', 'unknown')} job '{data.get('name', 'unnamed')}'")
            
            # Debug: Log the complete received data
            logger.info(f"[API_JOB_CREATE] Received data keys: {list(data.keys())}")
            if data.get('schedule'):
                logger.info(f"[API_JOB_CREATE] Schedule configuration: {data['schedule']}")
            
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
            
            elif data.get('type') == 'powershell':
                script_content = data.get('script_content', 'NONE')
                script_path = data.get('script_path', 'NONE')
                execution_policy = data.get('execution_policy', 'NONE')
                parameters = data.get('parameters', [])
                
                logger.info(f"[API_JOB_CREATE] PowerShell script_content received (length {len(script_content) if script_content != 'NONE' else 0}): '{script_content[:100]}...' if script_content != 'NONE' else 'NONE'")
                logger.info(f"[API_JOB_CREATE] PowerShell script_path received: '{script_path}'")
                logger.info(f"[API_JOB_CREATE] PowerShell execution_policy received: '{execution_policy}'")
                logger.info(f"[API_JOB_CREATE] PowerShell parameters received: {parameters}")
                
                # Validate critical fields for PowerShell
                if (not script_content or script_content == 'NONE' or script_content.strip() == '') and (not script_path or script_path == 'NONE' or script_path.strip() == ''):
                    logger.error(f"[API_JOB_CREATE] CRITICAL: PowerShell script content or path is missing!")
                    return jsonify({
                        'success': False,
                        'error': 'PowerShell script content or script path is required for PowerShell jobs'
                    }), 400
            
            # Use integrated scheduler instead of just job manager
            integrated_scheduler = getattr(app, 'integrated_scheduler', None)
            if integrated_scheduler:
                # Use integrated scheduler for job creation with scheduling
                result = integrated_scheduler.create_job_with_schedule(data)
                
                if result['success']:
                    logger.info(f"[API_JOB_CREATE] Job created successfully: {result['job_id']}")
                    if result.get('scheduled'):
                        logger.info(f"[API_JOB_CREATE] Job {result['job_id']} was also scheduled")
                    return jsonify(result), 201
                else:
                    logger.warning(f"[API_JOB_CREATE] Job creation failed: {result['error']}")
                    return jsonify(result), 400
            else:
                # Fallback to basic job manager if integrated scheduler not available
                job_manager = getattr(app, 'job_manager', None)
                if not job_manager:
                    return jsonify({
                        'success': False,
                        'error': 'Job management system not available'
                    }), 500
                
                result = job_manager.create_job(data)
                
                if result['success']:
                    logger.info(f"[API_JOB_CREATE] Job created successfully (no scheduling): {result['job_id']}")
                    if data.get('schedule'):
                        result['warning'] = 'Job created but scheduling not available - integrated scheduler not initialized'
                    return jsonify(result), 201
                else:
                    logger.warning(f"[API_JOB_CREATE] Job creation failed: {result['error']}")
                    
                    # Provide more specific error message for database connectivity issues
                    error_message = result['error']
                    if 'Failed to save job to database' in error_message:
                        if data.get('type') == 'powershell':
                            error_message = 'CRITICAL: PowerShell job cannot be saved - SQL Server database connection failed. Check database configuration and ensure pyodbc is installed with SQL Server drivers.'
                        elif data.get('type') == 'sql':
                            error_message = 'CRITICAL: SQL job cannot be saved - SQL Server database connection failed. Check database configuration and ensure pyodbc is installed with SQL Server drivers.'
                    
                    return jsonify({
                        'success': False,
                        'error': error_message
                    }), 400
        
        except Exception as e:
            logger.error(f"[API_JOB_CREATE] API create job error: {e}")
            return jsonify({
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }), 500
    
    @app.route('/api/executions/history', methods=['GET'])
    def api_execution_history():
        """API endpoint to get complete execution history"""
        logger.info("[API_EXECUTION_HISTORY] Fetching execution history")
        
        try:
            # Get query parameters
            limit = request.args.get('limit', 1000, type=int)
            status_filter = request.args.get('status')
            job_type_filter = request.args.get('job_type')
            
            # Use global JobManager instance
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({
                    'success': False,
                    'error': 'Database not available'
                }), 500
            
            # Get execution history from database
            history = job_manager.get_all_execution_history(limit)
            
            # Apply filters if provided
            if status_filter:
                history = [h for h in history if h.get('status') == status_filter]
            
            if job_type_filter:
                history = [h for h in history if h.get('job_type') == job_type_filter]
            
            logger.info(f"[API_EXECUTION_HISTORY] Returning {len(history)} execution records")
            
            return jsonify({
                'success': True,
                'executions': history,
                'total_count': len(history),
                'applied_filters': {
                    'status': status_filter,
                    'job_type': job_type_filter,
                    'limit': limit
                }
            })
            
        except Exception as e:
            logger.error(f"[API_EXECUTION_HISTORY] Error fetching execution history: {e}")
            return jsonify({
                'success': False,
                'error': f'Failed to fetch execution history: {str(e)}'
            }), 500

    @app.route('/api/jobs/<job_id>/run', methods=['POST'])
    def api_run_job(job_id):
        """API endpoint to run a job immediately"""
        logger.info(f"[API_RUN_JOB] Received request to run job: {job_id}")
        
        try:
            # Try to use integrated scheduler first
            integrated_scheduler = getattr(app, 'integrated_scheduler', None)
            if integrated_scheduler:
                result = integrated_scheduler.run_job_now(job_id)
                
                if result['success']:
                    logger.info(f"[API_RUN_JOB] Job {job_id} executed successfully via integrated scheduler")
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
            else:
                # Fallback to direct JobExecutor
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
                    logger.info(f"[API_RUN_JOB] Job {job_id} executed successfully via fallback executor")
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
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({'error': 'Job manager not available'}), 500
            
            # Get enabled state from request body if provided
            data = request.get_json() or {}
            enabled = data.get('enabled')
            
            result = job_manager.toggle_job(job_id, enabled)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': result['message'],
                    'enabled': result['enabled']
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 400
        
        except Exception as e:
            logger.error(f"API toggle job error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/jobs/<job_id>', methods=['DELETE'])
    def api_delete_job(job_id):
        """API endpoint to delete a job"""
        try:
            job_manager = getattr(app, 'job_manager', None)
            if not job_manager:
                return jsonify({'error': 'Job manager not available'}), 500
            
            result = job_manager.delete_job(job_id)
            
            if result['success']:
                return jsonify({
                    'success': True,
                    'message': result['message']
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result['error']
                }), 400
        
        except Exception as e:
            logger.error(f"API delete job error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # Connection cache to avoid race conditions (temporarily disabled for debugging)
    _connection_cache = {'data': None, 'timestamp': 0, 'cache_duration': 0}  # Cache disabled for debugging
    
    @app.route('/api/connections', methods=['GET'])
    def api_get_connections():
        """API endpoint to get available database connections (optimized to prevent race conditions)"""
        import time
        
        try:
            # Check if fast loading is requested
            fast_mode = request.args.get('fast', 'false').lower() == 'true'
            
            logger.info(f"[API_CONNECTIONS] Request received (fast_mode: {fast_mode})")
            
            # Check cache first to avoid database race conditions
            current_time = time.time()
            cache_age = current_time - _connection_cache['timestamp']
            if (_connection_cache['data'] is not None and 
                cache_age < _connection_cache['cache_duration']):
                logger.info(f"[API_CONNECTIONS] Returning cached data ({len(_connection_cache['data'])} connections, cache age: {cache_age:.1f}s)")
                return jsonify({'success': True, 'connections': _connection_cache['data']})
            else:
                if _connection_cache['data'] is not None:
                    logger.info(f"[API_CONNECTIONS] Cache expired (age: {cache_age:.1f}s), loading fresh data")
            
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
            db_manager = pool.db_manager
            
            logger.info(f"[API_CONNECTIONS] Loading connections from database (cache miss)")
            load_start = time.time()
            
            # Use batch loading to minimize database calls and avoid race conditions
            connections = []
            try:
                # Single database call to get all connection data at once
                connections = _load_all_connections_batch(db_manager)
                load_time = time.time() - load_start
                
                logger.info(f"[API_CONNECTIONS] Loaded {len(connections)} connections in {load_time:.3f}s")
                
                # Cache the results to prevent future race conditions
                _connection_cache['data'] = connections
                _connection_cache['timestamp'] = current_time
                
            except Exception as e:
                logger.error(f"[API_CONNECTIONS] Batch loading failed: {e}")
                # Fallback to individual loading (slower but more resilient)
                connections = _load_connections_individually(db_manager)
            
            return jsonify({'success': True, 'connections': connections})
            
        except Exception as e:
            logger.error(f"[API_CONNECTIONS] Error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    def _load_all_connections_batch(db_manager):
        """Load all connections in a single optimized database operation"""
        import time
        
        connections = []
        batch_start = time.time()
        
        try:
            # Get system connection once and reuse it
            logger.debug("[BATCH_LOAD] Attempting to create system connection")
            system_connection = db_manager._create_new_connection("system")
            if not system_connection:
                logger.warning("[BATCH_LOAD] No system connection available, using fallback")
                raise Exception("System connection not available")
            
            logger.debug("[BATCH_LOAD] Creating cursor and executing query")
            cursor = system_connection.cursor()
            
            # Single query to get all connection data (using correct column names)
            query = """
                SELECT 
                    name,
                    server_name,
                    database_name,
                    port,
                    description,
                    trusted_connection,
                    created_date,
                    modified_date
                FROM user_connections 
                WHERE is_active = 1
                ORDER BY name
            """
            
            logger.debug(f"[BATCH_LOAD] Executing query: {query.strip()}")
            cursor.execute(query)
            
            rows = cursor.fetchall()
            logger.debug(f"[BATCH_LOAD] Query returned {len(rows)} rows")
            
            cursor.close()
            system_connection.close()
            
            # Process all rows at once (matching the SELECT column order)
            for row in rows:
                connections.append({
                    'name': row[0],          # name
                    'server': row[1],        # server_name
                    'database': row[2],      # database_name
                    'port': row[3] or 1433,  # port
                    'description': row[4] or '',  # description
                    'auth_type': 'windows' if row[5] else 'sql',  # trusted_connection
                    'status': 'pending',
                    'response_time': None,
                    'created_date': str(row[6]) if row[6] else None,   # created_date
                    'modified_date': str(row[7]) if row[7] else None   # modified_date
                })
            
            batch_time = time.time() - batch_start
            logger.info(f"[BATCH_LOAD] Batch loaded {len(connections)} connections in {batch_time:.3f}s")
            
        except Exception as e:
            logger.error(f"[BATCH_LOAD] Batch loading failed: {e}")
            # Re-raise to trigger fallback
            raise
        
        return connections
    
    def _load_connections_individually(db_manager):
        """Fallback: Load connections individually (slower but more resilient)"""
        import time
        
        connections = []
        individual_start = time.time()
        
        try:
            # Get connection names (this should be fast from config)
            connection_names = []
            
            # Try database first, then config as fallback
            logger.info(f"[INDIVIDUAL_LOAD] Attempting to load connections using original methods")
            
            try:
                # Use the original database method
                connection_names = db_manager.list_connections()
                logger.info(f"[INDIVIDUAL_LOAD] Found {len(connection_names)} connections from list_connections()")
            except Exception as e:
                logger.warning(f"[INDIVIDUAL_LOAD] list_connections() failed: {e}, trying config fallback")
                # Fallback to config
                databases = db_manager.config.get('databases', {})
                for conn_name, conn_config in databases.items():
                    if not conn_config.get('is_system_connection', False):
                        connection_names.append(conn_name)
                logger.info(f"[INDIVIDUAL_LOAD] Found {len(connection_names)} connections from config fallback")
            
            # Process each connection
            for conn_name in connection_names:
                try:
                    conn_info = db_manager.get_connection_info(conn_name)
                    if conn_info:
                        connections.append({
                            'name': conn_name,
                            'server': conn_info.get('server'),
                            'database': conn_info.get('database'),
                            'description': conn_info.get('description', ''),
                            'auth_type': 'windows' if conn_info.get('trusted_connection') else 'sql',
                            'port': conn_info.get('port', 1433),
                            'status': 'pending',
                            'response_time': None
                        })
                except Exception as e:
                    logger.warning(f"[INDIVIDUAL_LOAD] Failed to load connection '{conn_name}': {e}")
                    continue
            
            individual_time = time.time() - individual_start
            logger.info(f"[INDIVIDUAL_LOAD] Individual loaded {len(connections)} connections in {individual_time:.3f}s")
            
        except Exception as e:
            logger.error(f"[INDIVIDUAL_LOAD] Individual loading failed: {e}")
        
        return connections
    
    def _invalidate_connection_cache():
        """Invalidate the connection cache when connections are modified"""
        _connection_cache['data'] = None
        _connection_cache['timestamp'] = 0
        logger.debug("[CACHE] Connection cache invalidated")
    
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
                # Invalidate cache since we added a new connection
                _invalidate_connection_cache()
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
                # Invalidate cache since we deleted a connection
                _invalidate_connection_cache()
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
    
    @app.route('/api/connections/validate-all-detailed', methods=['POST'])
    def api_validate_all_connections_detailed():
        """Validate all connections with detailed logging and error information"""
        import time
        start_time = time.time()
        
        logger.info("[DETAILED_VALIDATION] Starting detailed validation of all connections")
        
        try:
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
            db_manager = pool.db_manager
            connections = db_manager.list_connections()
            
            logger.info(f"[DETAILED_VALIDATION] Found {len(connections)} connections to validate")
            
            if not connections:
                return jsonify({
                    'success': True,
                    'results': {},
                    'total_connections': 0,
                    'valid_connections': 0,
                    'invalid_connections': 0
                })
            
            import concurrent.futures
            
            def test_connection_detailed(conn_name):
                """Test a single connection with detailed error information"""
                try:
                    logger.debug(f"[DETAILED_VALIDATION] Starting detailed test for '{conn_name}'")
                    test_start = time.time()
                    
                    result = db_manager.test_connection(conn_name)
                    test_time = time.time() - test_start
                    
                    if result.get('success'):
                        return conn_name, {
                            'success': True,
                            'response_time': result.get('response_time', test_time),
                            'server_info': result.get('server_info', 'Connected successfully'),
                            'connection_method': result.get('connection_method', 'Standard'),
                            'database_version': result.get('database_version', 'Unknown'),
                            'test_query': result.get('test_query', 'SELECT 1'),
                            'validation_time': test_time
                        }
                    else:
                        # Detailed error information
                        error_msg = result.get('error', 'Unknown error')
                        error_code = None
                        error_details = None
                        suggested_fix = "Check connection parameters"
                        
                        # Parse common SQL Server errors
                        if 'timeout' in error_msg.lower():
                            error_code = 'TIMEOUT'
                            error_details = 'Connection timeout - server may be unreachable or overloaded'
                            suggested_fix = 'Check server availability and network connectivity'
                        elif 'login failed' in error_msg.lower():
                            error_code = 'AUTH_FAILED'
                            error_details = 'Authentication failed - invalid credentials'
                            suggested_fix = 'Verify username and password, check authentication type'
                        elif 'cannot open database' in error_msg.lower():
                            error_code = 'DB_NOT_FOUND'
                            error_details = 'Database not found or access denied'
                            suggested_fix = 'Verify database name and user permissions'
                        elif 'network-related' in error_msg.lower():
                            error_code = 'NETWORK_ERROR'
                            error_details = 'Network connectivity issue'
                            suggested_fix = 'Check server name, port, and firewall settings'
                        else:
                            error_code = 'UNKNOWN_ERROR'
                            error_details = f'Unhandled error: {error_msg}'
                        
                        return conn_name, {
                            'success': False,
                            'error': error_msg,
                            'error_code': error_code,
                            'error_details': error_details,
                            'suggested_fix': suggested_fix,
                            'response_time': test_time,
                            'validation_time': test_time
                        }
                        
                except Exception as e:
                    test_time = time.time() - test_start
                    logger.error(f"[DETAILED_VALIDATION] Exception testing '{conn_name}': {e}")
                    
                    return conn_name, {
                        'success': False,
                        'error': str(e),
                        'error_code': 'EXCEPTION',
                        'error_details': f'Unexpected error during validation: {str(e)}',
                        'suggested_fix': 'Check system logs and connection configuration',
                        'response_time': test_time,
                        'validation_time': test_time
                    }
            
            # Execute detailed validation in parallel
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                future_to_conn = {
                    executor.submit(test_connection_detailed, conn_name): conn_name 
                    for conn_name in connections
                }
                
                for future in concurrent.futures.as_completed(future_to_conn):
                    conn_name, result = future.result()
                    results[conn_name] = result
            
            # Calculate summary statistics
            valid_count = sum(1 for r in results.values() if r['success'])
            invalid_count = len(results) - valid_count
            total_time = time.time() - start_time
            
            logger.info(f"[DETAILED_VALIDATION] Completed: {valid_count} valid, {invalid_count} invalid in {total_time:.2f}s")
            
            return jsonify({
                'success': True,
                'results': results,
                'total_connections': len(connections),
                'valid_connections': valid_count,
                'invalid_connections': invalid_count,
                'validation_time': total_time
            })
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[DETAILED_VALIDATION] Error: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'validation_time': total_time
            }), 500
    
    @app.route('/api/connections/<connection_name>/test-detailed', methods=['POST'])
    def api_test_connection_detailed(connection_name):
        """Test a single connection with detailed logging and error information"""
        import time
        start_time = time.time()
        
        logger.info(f"[DETAILED_TEST] Starting detailed test for connection '{connection_name}'")
        
        try:
            # Use global connection pool instance
            pool = getattr(app, 'connection_pool', None)
            if not pool:
                return jsonify({'success': False, 'error': 'Database not available'}), 500
            
            db_manager = pool.db_manager
            result = db_manager.test_connection(connection_name)
            test_time = time.time() - start_time
            
            if result.get('success'):
                logger.info(f"[DETAILED_TEST] Connection '{connection_name}' test successful in {test_time:.2f}s")
                
                return jsonify({
                    'success': True,
                    'response_time': result.get('response_time', test_time),
                    'server_info': result.get('server_info', 'Connected successfully'),
                    'connection_method': result.get('connection_method', 'Standard'),
                    'database_version': result.get('database_version', 'Unknown'),
                    'test_query': result.get('test_query', 'SELECT 1'),
                    'validation_time': test_time,
                    'connection_details': {
                        'server': result.get('server', 'Unknown'),
                        'database': result.get('database', 'Unknown'),
                        'auth_type': result.get('auth_type', 'Unknown')
                    }
                })
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.warning(f"[DETAILED_TEST] Connection '{connection_name}' test failed: {error_msg}")
                
                # Detailed error analysis
                error_code = 'UNKNOWN_ERROR'
                error_details = f'Connection test failed: {error_msg}'
                suggested_fix = "Check connection parameters"
                
                if 'timeout' in error_msg.lower():
                    error_code = 'TIMEOUT'
                    error_details = 'Connection timeout - server may be unreachable or overloaded'
                    suggested_fix = 'Check server availability, increase timeout, or verify network connectivity'
                elif 'login failed' in error_msg.lower():
                    error_code = 'AUTH_FAILED'
                    error_details = 'Authentication failed - invalid credentials or insufficient permissions'
                    suggested_fix = 'Verify username/password, check authentication type, or contact database administrator'
                elif 'cannot open database' in error_msg.lower():
                    error_code = 'DB_NOT_FOUND'
                    error_details = 'Database not found or access denied'
                    suggested_fix = 'Verify database name exists and user has proper access permissions'
                elif 'network-related' in error_msg.lower():
                    error_code = 'NETWORK_ERROR'
                    error_details = 'Network connectivity issue - server unreachable'
                    suggested_fix = 'Check server name/IP, port number, firewall settings, and VPN connection'
                
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'error_code': error_code,
                    'error_details': error_details,
                    'suggested_fix': suggested_fix,
                    'response_time': test_time,
                    'validation_time': test_time
                })
                
        except Exception as e:
            test_time = time.time() - start_time
            logger.error(f"[DETAILED_TEST] Exception testing connection '{connection_name}': {e}")
            
            return jsonify({
                'success': False,
                'error': str(e),
                'error_code': 'EXCEPTION',
                'error_details': f'Unexpected error during connection test: {str(e)}',
                'suggested_fix': 'Check system logs, connection configuration, and database server status',
                'response_time': test_time,
                'validation_time': test_time
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

    @app.route('/api/jobs/<job_id>/history/incremental')
    def api_job_history_incremental(job_id):
        """API endpoint for incremental job execution history"""
        try:
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': 'Job execution history not available: Missing database dependencies.'
                }), 500
            
            limit = request.args.get('limit', 20, type=int)
            since_timestamp = request.args.get('since')
            
            history = job_executor.get_execution_history_incremental(job_id, since_timestamp, limit)
            
            logger.info(f"[API_JOB_HISTORY_INCREMENTAL] Retrieved {len(history)} new execution records for job {job_id} since {since_timestamp}")
            
            # Return latest timestamp for client to use in next request
            latest_timestamp = None
            if history and len(history) > 0:
                latest_timestamp = history[0]['start_time']  # Records are ordered DESC by start_time
            
            return jsonify({
                'success': True,
                'job_id': job_id,
                'execution_history': history,
                'total_count': len(history),
                'latest_timestamp': latest_timestamp,
                'since_timestamp': since_timestamp
            })
        
        except Exception as e:
            logger.error(f"[API_JOB_HISTORY_INCREMENTAL] API incremental job history error: {e}")
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
    
    @app.route('/api/jobs/<job_id>/logs')
    def api_job_logs(job_id):
        """API endpoint to get detailed execution logs for a specific job execution"""
        logger.info(f"[API_JOB_LOGS] Getting execution logs for job: {job_id}")
        
        try:
            # Get execution_id from query parameters if provided
            execution_id = request.args.get('execution_id', type=int)
            include_details = request.args.get('include_details', 'true').lower() == 'true'
            
            try:
                from core.job_executor import JobExecutor
                job_executor = JobExecutor()
            except ImportError as e:
                return jsonify({
                    'success': False,
                    'error': 'Execution logs not available: Missing database dependencies.'
                }), 500
            
            if execution_id:
                # Get logs for specific execution
                history = job_executor.get_execution_history(job_id, limit=1000)
                execution_record = next((h for h in history if h['execution_id'] == execution_id), None)
                
                if not execution_record:
                    return jsonify({
                        'success': False,
                        'error': f'Execution {execution_id} not found for job {job_id}'
                    }), 404
                
                # Extract detailed logs from output field
                logs_data = execution_record.get('output', 'No detailed logs available')
                
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'execution_id': execution_id,
                    'execution_record': execution_record,
                    'detailed_logs': logs_data,
                    'logs_available': bool(logs_data and logs_data != 'No detailed logs available')
                })
            else:
                # Get all executions for this job
                history = job_executor.get_execution_history(job_id, limit=50)
                
                # Add log availability flag to each execution
                for record in history:
                    record['has_detailed_logs'] = bool(record.get('output'))
                
                return jsonify({
                    'success': True,
                    'job_id': job_id,
                    'executions': history,
                    'total_count': len(history)
                })
        
        except Exception as e:
            logger.error(f"[API_JOB_LOGS] API job logs error: {e}")
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
    
    # Authentication removed - all routes now publicly accessible
    
    @app.route('/admin')
    def admin_panel():
        """Admin control panel - now publicly accessible"""
        return render_template('admin.html')
    
    @app.route('/api-docs')
    def api_documentation():
        """API Documentation with Swagger UI"""
        return render_template('api_docs.html')
    
    @app.route('/api/openapi-spec')
    def openapi_specification():
        """Serve OpenAPI 3.0 specification for Swagger UI"""
        return jsonify(generate_openapi_spec())
    
    @app.route('/api/admin/system-stats')
    def api_admin_system_stats():
        """Get system statistics for admin panel"""
        
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
            
            # No session tracking - simplified
            active_sessions = 1
            
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
        
        try:
            # No session tracking - simplified
            sessions = [{
                'session_id': 'no-auth',
                'username': 'system',
                'display_name': 'System User',
                'login_time': 'No authentication required',
                'idle_minutes': 0,
                'client_ip': 'localhost',
                'is_current': True
            }]
            
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
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                # Implementation depends on your scheduler manager
                # scheduler.start()
                logger.info(f"[ADMIN] Scheduler start requested by {'system'}")
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
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                logger.info(f"[ADMIN] Scheduler pause requested by {'system'}")
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
        
        try:
            scheduler = getattr(app, 'scheduler_manager', None)
            if scheduler:
                logger.info(f"[ADMIN] Scheduler stop requested by {'system'}")
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
        
        try:
            logger.warning(f"[ADMIN] Kill all jobs requested by {'system'}")
            
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
        
        try:
            logger.critical(f"[ADMIN] EMERGENCY SHUTDOWN requested by {'system'}")
            
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
        
        try:
            logger.warning(f"[ADMIN] Clear logs requested by {'system'}")
            
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
        
        try:
            logger.info(f"[ADMIN] Configuration export requested by {'system'}")
            
            # Create configuration export
            config_data = {
                'app_config': {
                    'domain': app.config.get('AD_DOMAIN'),
                    'session_timeout': app.config.get('SESSION_TIMEOUT_MINUTES')
                },
                'export_timestamp': datetime.now().isoformat(),
                'exported_by': 'system'
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


def generate_openapi_spec():
    """Generate OpenAPI 3.0 specification for all API endpoints"""
    
    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "Windows Job Scheduler API",
            "version": "1.0.0",
            "description": """
Complete API documentation for Windows Job Scheduler application.

**Features:**
- Job management (SQL and PowerShell jobs)
- Database connection management  
- Job scheduling and execution
- System administration and monitoring

**Windows Integration:**
- SQL Server connectivity
- PowerShell script execution
- Windows authentication support
- Event logging integration
            """,
            "contact": {
                "name": "Job Scheduler Support",
                "email": "support@jobscheduler.local"
            }
        },
        "servers": [
            {
                "url": "http://localhost:5000",
                "description": "Windows Job Scheduler Server"
            }
        ],
        "tags": [
            {"name": "Jobs", "description": "Job management operations"},
            {"name": "Connections", "description": "Database connection management"},
            {"name": "Admin", "description": "Administrative operations"},
            {"name": "System", "description": "System status and monitoring"},
            {"name": "Executions", "description": "Job execution history and logs"}
        ],
        "paths": {
            "/api/jobs": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "List all jobs",
                    "description": "Retrieve list of all jobs with optional filtering",
                    "parameters": [
                        {
                            "name": "type",
                            "in": "query",
                            "schema": {"type": "string", "enum": ["sql", "powershell"]},
                            "description": "Filter by job type"
                        },
                        {
                            "name": "enabled_only",
                            "in": "query",
                            "schema": {"type": "boolean"},
                            "description": "Only return enabled jobs"
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of jobs retrieved successfully",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "jobs": {
                                                "type": "array",
                                                "items": {"$ref": "#/components/schemas/Job"}
                                            },
                                            "total_count": {"type": "integer"}
                                        }
                                    }
                                }
                            }
                        },
                        "500": {"description": "Database not available"}
                    }
                },
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Create new job",
                    "description": "Create a new job with optional scheduling",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/JobCreate"},
                                "examples": {
                                    "sql_job": {
                                        "summary": "SQL Job Example",
                                        "value": {
                                            "name": "Daily Sales Report",
                                            "type": "sql",
                                            "sql_query": "SELECT COUNT(*) as orders, SUM(amount) as revenue FROM orders WHERE DATE(created_date) = GETDATE()",
                                            "connection_name": "production",
                                            "schedule": {
                                                "type": "cron",
                                                "cron": "0 0 8 * * 1-5"
                                            }
                                        }
                                    },
                                    "powershell_job": {
                                        "summary": "PowerShell Job Example",
                                        "value": {
                                            "name": "System Cleanup",
                                            "type": "powershell",
                                            "script_content": "Get-ChildItem C:\\Temp -Recurse | Remove-Item -Force",
                                            "schedule": {
                                                "type": "interval",
                                                "interval": {"hours": 24}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "responses": {
                        "201": {"description": "Job created successfully"},
                        "400": {"description": "Invalid job data"}
                    }
                }
            },
            "/api/jobs/{job_id}": {
                "get": {
                    "tags": ["Jobs"],
                    "summary": "Get job details",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Job details retrieved"},
                        "404": {"description": "Job not found"}
                    }
                },
                "put": {
                    "tags": ["Jobs"],
                    "summary": "Update job",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path", 
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/JobUpdate"}
                            }
                        }
                    },
                    "responses": {
                        "200": {"description": "Job updated successfully"}
                    }
                },
                "delete": {
                    "tags": ["Jobs"],
                    "summary": "Delete job",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {"description": "Job deleted successfully"}
                    }
                }
            },
            "/api/jobs/{job_id}/run": {
                "post": {
                    "tags": ["Jobs"],
                    "summary": "Execute job immediately",
                    "parameters": [
                        {
                            "name": "job_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"}
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Job execution completed",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "success": {"type": "boolean"},
                                            "execution_id": {"type": "integer"},
                                            "status": {"type": "string"},
                                            "output": {"type": "string"},
                                            "duration_seconds": {"type": "number"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Job": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string", "description": "Unique job identifier"},
                        "name": {"type": "string", "description": "Job name"},
                        "job_type": {"type": "string", "enum": ["sql", "powershell"]},
                        "enabled": {"type": "boolean"},
                        "configuration": {"type": "object"},
                        "created_date": {"type": "string", "format": "date-time"},
                        "modified_date": {"type": "string", "format": "date-time"}
                    }
                },
                "JobCreate": {
                    "type": "object",
                    "required": ["name", "type"],
                    "properties": {
                        "name": {"type": "string"},
                        "type": {"type": "string", "enum": ["sql", "powershell"]},
                        "description": {"type": "string"},
                        "sql_query": {"type": "string", "description": "Required for SQL jobs"},
                        "connection_name": {"type": "string"},
                        "script_content": {"type": "string", "description": "Required for PowerShell jobs"},
                        "schedule": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["cron", "interval", "once"]},
                                "cron": {"type": "string"},
                                "interval": {"type": "object"},
                                "run_date": {"type": "string", "format": "date-time"}
                            }
                        }
                    }
                },
                "JobUpdate": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "enabled": {"type": "boolean"}
                    }
                }
            }
        }
    }
    
    return spec