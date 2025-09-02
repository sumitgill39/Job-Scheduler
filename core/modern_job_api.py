"""
Modern Job API using the new execution engine
Clean, simple, reliable job execution endpoints
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
from flask import jsonify, request

from .new_execution_engine import (
    NewExecutionEngine, JobDefinition, StepFactory,
    JobExecutionResult, JobStatus, StepStatus
)
from utils.logger import get_logger


class ModernJobAPI:
    """Modern job API with timezone-based execution"""
    
    def __init__(self):
        self.execution_engine = NewExecutionEngine()
        self.logger = get_logger("ModernJobAPI")
        self._loop = None
        self._started = False
    
    async def start(self):
        """Start the execution engine"""
        if not self._started:
            await self.execution_engine.start()
            self._started = True
            self.logger.info("[MODERN_API] Execution engine started")
    
    async def stop(self):
        """Stop the execution engine"""
        if self._started:
            await self.execution_engine.stop()
            self._started = False
            self.logger.info("[MODERN_API] Execution engine stopped")
    
    def _ensure_loop(self):
        """Ensure we have an event loop for async operations"""
        if self._loop is None:
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
    
    def _run_async(self, coro):
        """Run async function in sync context"""
        self._ensure_loop()
        if self._loop.is_running():
            # If loop is already running, create a task
            task = self._loop.create_task(coro)
            return task
        else:
            # If loop is not running, run until complete
            return self._loop.run_until_complete(coro)
    
    def execute_job_immediately(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a job immediately and return the result
        Modern replacement for the old execute_job method
        """
        self.logger.info(f"[MODERN_API] Received immediate execution request for job: {job_data.get('name', 'unnamed')}")
        
        try:
            # Parse job data into JobDefinition
            job = self._parse_job_data(job_data)
            
            # Start engine if not started
            if not self._started:
                async def start_and_execute():
                    await self.start()
                    return await self.execution_engine.execute_job_now(job)
                
                result = self._run_async(start_and_execute())
            else:
                # Execute immediately
                result = self._run_async(self.execution_engine.execute_job_now(job))
            
            # Convert result to API response
            return self._format_execution_response(result)
            
        except Exception as e:
            self.logger.error(f"[MODERN_API] Error executing job immediately: {e}")
            return {
                'success': False,
                'error': f'Job execution failed: {str(e)}',
                'job_id': job_data.get('id', 'unknown'),
                'status': 'failed',
                'execution_id': None,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def schedule_job(self, job_data: Dict[str, Any], scheduled_time: datetime) -> Dict[str, Any]:
        """Schedule a job for future execution"""
        self.logger.info(f"[MODERN_API] Scheduling job: {job_data.get('name', 'unnamed')} for {scheduled_time}")
        
        try:
            # Parse job data into JobDefinition
            job = self._parse_job_data(job_data)
            
            # Start engine if not started
            if not self._started:
                async def start_and_schedule():
                    await self.start()
                    await self.execution_engine.schedule_job(job, scheduled_time)
                
                self._run_async(start_and_schedule())
            else:
                # Schedule job
                self._run_async(self.execution_engine.schedule_job(job, scheduled_time))
            
            return {
                'success': True,
                'message': f'Job {job.job_name} scheduled successfully',
                'job_id': job.job_id,
                'scheduled_time': scheduled_time.isoformat(),
                'timezone': job.timezone,
                'status': 'scheduled'
            }
            
        except Exception as e:
            self.logger.error(f"[MODERN_API] Error scheduling job: {e}")
            return {
                'success': False,
                'error': f'Job scheduling failed: {str(e)}',
                'job_id': job_data.get('id', 'unknown')
            }
    
    def get_execution_status(self) -> Dict[str, Any]:
        """Get status of all timezone queues"""
        try:
            status = self.execution_engine.get_queue_status()
            
            return {
                'success': True,
                'engine_started': self._started,
                'timezone_queues': status,
                'total_queues': len(status),
                'total_active_executions': sum(q['active_executions'] for q in status.values()),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"[MODERN_API] Error getting execution status: {e}")
            return {
                'success': False,
                'error': f'Failed to get execution status: {str(e)}'
            }
    
    def get_available_step_types(self) -> Dict[str, Any]:
        """Get list of available step types"""
        try:
            step_types = StepFactory.get_available_step_types()
            
            return {
                'success': True,
                'step_types': step_types,
                'count': len(step_types),
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"[MODERN_API] Error getting step types: {e}")
            return {
                'success': False,
                'error': f'Failed to get step types: {str(e)}'
            }
    
    def _parse_job_data(self, job_data: Dict[str, Any]) -> JobDefinition:
        """Parse job data from API request into JobDefinition"""
        # Extract job metadata
        job_id = job_data.get('id', job_data.get('job_id', f"job_{datetime.utcnow().timestamp()}"))
        job_name = job_data.get('name', job_data.get('job_name', 'Unnamed Job'))
        description = job_data.get('description', '')
        timezone = job_data.get('timezone', 'UTC')
        enabled = job_data.get('enabled', True)
        max_retries = job_data.get('max_retries', 0)
        timeout_seconds = job_data.get('timeout_seconds', job_data.get('timeout', 3600))
        
        # Handle different job formats (old vs new)
        steps = []
        
        if 'steps' in job_data:
            # New multi-step format
            steps = job_data['steps']
        else:
            # Legacy single-step format - convert to new format
            job_type = job_data.get('type', job_data.get('job_type', ''))
            
            if job_type == 'sql':
                steps = [{
                    'id': 'main_step',
                    'name': 'SQL Execution',
                    'type': 'sql',
                    'query': job_data.get('sql_query', job_data.get('query', '')),
                    'connection_name': job_data.get('connection_name', 'default'),
                    'timeout': job_data.get('query_timeout', 300)
                }]
            elif job_type == 'powershell':
                steps = [{
                    'id': 'main_step',
                    'name': 'PowerShell Execution',
                    'type': 'powershell',
                    'script': job_data.get('script_content', job_data.get('script', '')),
                    'script_path': job_data.get('script_path', ''),
                    'parameters': job_data.get('parameters', {}),
                    'timeout': job_data.get('timeout', 300)
                }]
            else:
                raise ValueError(f"Unknown job type: {job_type}")
        
        return JobDefinition(
            job_id=job_id,
            job_name=job_name,
            description=description,
            timezone=timezone,
            steps=steps,
            enabled=enabled,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            metadata=job_data.get('metadata', {})
        )
    
    def _format_execution_response(self, result: JobExecutionResult) -> Dict[str, Any]:
        """Format JobExecutionResult into API response"""
        # Determine overall success
        success = result.status in [JobStatus.SUCCESS, JobStatus.PARTIAL_SUCCESS]
        
        # Format steps
        steps = []
        for step in result.steps:
            steps.append({
                'step_id': step.step_id,
                'step_name': step.step_name,
                'step_type': step.step_type,
                'status': step.status.value,
                'duration_seconds': step.duration_seconds,
                'output': step.output[:500] if step.output else '',  # Limit output size
                'error_message': step.error_message,
                'metadata': step.metadata
            })
        
        return {
            'success': success,
            'message': f'Job {result.job_name} {result.status.value}',
            'execution_id': result.execution_id,
            'job_id': result.job_id,
            'job_name': result.job_name,
            'status': result.status.value,
            'timezone': result.timezone,
            'start_time': result.start_time.isoformat() if result.start_time else None,
            'end_time': result.end_time.isoformat() if result.end_time else None,
            'duration_seconds': result.duration_seconds,
            'steps': steps,
            'step_count': len(steps),
            'successful_steps': len([s for s in result.steps if s.status == StepStatus.SUCCESS]),
            'failed_steps': len([s for s in result.steps if s.status == StepStatus.FAILED]),
            'metadata': result.metadata
        }


# Global instance for use in Flask routes
modern_job_api = ModernJobAPI()


def create_modern_job_routes(app):
    """Create modern job execution routes"""
    
    @app.route('/api/v2/jobs/execute', methods=['POST'])
    def api_v2_execute_job():
        """Execute a job immediately using the new engine"""
        try:
            job_data = request.get_json()
            if not job_data:
                return jsonify({
                    'success': False,
                    'error': 'No job data provided'
                }), 400
            
            result = modern_job_api.execute_job_immediately(job_data)
            status_code = 200 if result['success'] else 400
            
            return jsonify(result), status_code
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'API error: {str(e)}'
            }), 500
    
    @app.route('/api/v2/jobs/schedule', methods=['POST'])
    def api_v2_schedule_job():
        """Schedule a job for future execution"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            job_data = data.get('job', {})
            scheduled_time_str = data.get('scheduled_time', '')
            
            if not scheduled_time_str:
                return jsonify({
                    'success': False,
                    'error': 'scheduled_time is required'
                }), 400
            
            # Parse scheduled time
            try:
                scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid scheduled_time format. Use ISO 8601 format.'
                }), 400
            
            result = modern_job_api.schedule_job(job_data, scheduled_time)
            status_code = 200 if result['success'] else 400
            
            return jsonify(result), status_code
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'API error: {str(e)}'
            }), 500
    
    @app.route('/api/v2/execution/status', methods=['GET'])
    def api_v2_execution_status():
        """Get execution engine status"""
        try:
            result = modern_job_api.get_execution_status()
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'API error: {str(e)}'
            }), 500
    
    @app.route('/api/v2/steps/types', methods=['GET'])
    def api_v2_step_types():
        """Get available step types"""
        try:
            result = modern_job_api.get_available_step_types()
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'API error: {str(e)}'
            }), 500
    
    return modern_job_api