"""
SQL Job implementation for Windows Job Scheduler
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from .job_base import JobBase, JobResult, JobStatus
from database.connection_manager import DatabaseConnectionManager

# Import pyodbc with error handling
try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False
    pyodbc = None


class SqlJob(JobBase):
    """SQL Server job implementation"""
    
    def __init__(self, sql_query: str = "", connection_name: str = "default",
                 connection_string: str = None, database_name: str = None,
                 query_timeout: int = 300, fetch_size: int = 1000, max_rows: int = 10000,
                 **kwargs):
        """
        Initialize SQL job
        
        Args:
            sql_query: SQL query to execute
            connection_name: Named connection from config
            connection_string: Direct connection string (overrides connection_name)
            database_name: Target database name
            query_timeout: Query timeout in seconds
            fetch_size: Number of rows to fetch at once
            max_rows: Maximum number of rows to return
            **kwargs: Base job parameters
        """
        # Extract SQL-specific parameters from kwargs to avoid passing them to base class
        sql_specific_params = ['query_timeout', 'fetch_size', 'max_rows']
        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in sql_specific_params}
        
        super().__init__(**filtered_kwargs)
        self.job_type = "sql"
        self.sql_query = sql_query
        self.connection_name = connection_name
        self.connection_string = connection_string
        self.database_name = database_name
        
        # SQL-specific settings
        self.query_timeout = query_timeout
        self.fetch_size = fetch_size
        self.max_rows = max_rows
        
        # Initialize connection manager
        self.db_manager = DatabaseConnectionManager()
        
        self.job_logger.info(f"Initialized SQL job with query: {self.sql_query[:50]}...")
    
    def execute(self, execution_logger=None) -> JobResult:
        """Execute SQL query"""
        start_time = datetime.now()
        
        if execution_logger:
            execution_logger.info("Starting SQL job execution", "SQL_JOB", {
                'query_preview': self.sql_query[:100] + "..." if len(self.sql_query) > 100 else self.sql_query,
                'connection_name': self.connection_name,
                'query_timeout': self.query_timeout,
                'max_rows': self.max_rows
            })
        
        if not HAS_PYODBC:
            if execution_logger:
                execution_logger.error("pyodbc not available - SQL Server drivers not installed", "SQL_JOB")
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message="pyodbc not available - SQL Server drivers not installed"
            )
        
        try:
            if execution_logger:
                execution_logger.info(f"Executing SQL query on connection: {self.connection_name}", "SQL_JOB")
            self.job_logger.info(f"Executing SQL query on connection: {self.connection_name}")
            
            # Get connection
            if execution_logger:
                execution_logger.debug("Attempting to get database connection", "SQL_JOB")
            connection = self._get_connection()
            if not connection:
                return JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.FAILED,
                    start_time=start_time,
                    end_time=datetime.now(),
                    error_message="Failed to establish database connection"
                )
            
            try:
                # Execute query
                cursor = connection.cursor()
                cursor.settimeout(self.query_timeout)
                
                self.job_logger.debug(f"Executing query: {self.sql_query}")
                start_exec = datetime.now()
                
                cursor.execute(self.sql_query)
                
                # Handle different query types
                if cursor.description:
                    # SELECT query - fetch results
                    rows = cursor.fetchmany(self.max_rows)
                    columns = [column[0] for column in cursor.description]
                    
                    # Format results
                    result_data = {
                        'columns': columns,
                        'rows': [list(row) for row in rows],
                        'row_count': len(rows)
                    }
                    
                    if len(rows) >= self.max_rows:
                        self.job_logger.warning(f"Result truncated to {self.max_rows} rows")
                        result_data['truncated'] = True
                    
                    output = f"Query executed successfully. Returned {len(rows)} rows."
                    
                else:
                    # Non-SELECT query (INSERT, UPDATE, DELETE, etc.)
                    rows_affected = cursor.rowcount
                    result_data = {
                        'rows_affected': rows_affected,
                        'query_type': 'non_select'
                    }
                    output = f"Query executed successfully. {rows_affected} rows affected."
                
                # Commit transaction for non-SELECT queries
                if not cursor.description:
                    connection.commit()
                
                exec_time = (datetime.now() - start_exec).total_seconds()
                self.job_logger.info(f"Query completed in {exec_time:.2f} seconds")
                
                return JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.SUCCESS,
                    start_time=start_time,
                    end_time=datetime.now(),
                    output=output,
                    metadata={
                        'query': self.sql_query,
                        'execution_time_seconds': exec_time,
                        'result_data': result_data,
                        'connection_name': self.connection_name
                    }
                )
                
            except pyodbc.Error as e:
                error_msg = f"SQL execution error: {str(e)}"
                self.job_logger.error(error_msg)
                
                # Try to rollback on error
                try:
                    connection.rollback()
                except:
                    pass
                
                return JobResult(
                    job_id=self.job_id,
                    job_name=self.name,
                    status=JobStatus.FAILED,
                    start_time=start_time,
                    end_time=datetime.now(),
                    error_message=error_msg,
                    metadata={
                        'query': self.sql_query,
                        'connection_name': self.connection_name,
                        'sql_error': str(e)
                    }
                )
            
            finally:
                # Close connection
                try:
                    connection.close()
                except:
                    pass
        
        except Exception as e:
            error_msg = f"Unexpected error in SQL job: {str(e)}"
            self.job_logger.exception(error_msg)
            
            return JobResult(
                job_id=self.job_id,
                job_name=self.name,
                status=JobStatus.FAILED,
                start_time=start_time,
                end_time=datetime.now(),
                error_message=error_msg,
                metadata={
                    'query': self.sql_query,
                    'connection_name': self.connection_name
                }
            )
    
    def _get_connection(self):
        """Get database connection"""
        try:
            if self.connection_string:
                # Use direct connection string
                self.job_logger.debug("Using direct connection string")
                return pyodbc.connect(self.connection_string, timeout=30)
            else:
                # Use named connection from config
                self.job_logger.debug(f"Using named connection: {self.connection_name}")
                return self.db_manager.get_connection(self.connection_name)
        
        except Exception as e:
            self.job_logger.error(f"Failed to get database connection: {e}")
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """Test database connection"""
        try:
            connection = self._get_connection()
            if connection:
                cursor = connection.cursor()
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                connection.close()
                
                return {
                    'success': True,
                    'message': 'Connection successful',
                    'test_result': result[0] if result else None
                }
            else:
                return {
                    'success': False,
                    'message': 'Failed to establish connection'
                }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Connection test failed: {str(e)}'
            }
    
    def validate_query(self) -> Dict[str, Any]:
        """Validate SQL query syntax"""
        try:
            connection = self._get_connection()
            if not connection:
                return {
                    'valid': False,
                    'error': 'Cannot establish database connection for validation'
                }
            
            try:
                cursor = connection.cursor()
                # Try to prepare the query (syntax check)
                cursor.prepare(self.sql_query)
                connection.close()
                
                return {
                    'valid': True,
                    'message': 'Query syntax is valid'
                }
            
            except pyodbc.Error as e:
                connection.close()
                return {
                    'valid': False,
                    'error': f'SQL syntax error: {str(e)}'
                }
        
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation failed: {str(e)}'
            }
    
    def get_query_plan(self) -> Dict[str, Any]:
        """Get SQL query execution plan (if supported)"""
        try:
            connection = self._get_connection()
            if not connection:
                return {
                    'success': False,
                    'error': 'Cannot establish database connection'
                }
            
            try:
                cursor = connection.cursor()
                
                # Enable execution plan
                cursor.execute("SET SHOWPLAN_ALL ON")
                cursor.execute(self.sql_query)
                
                # Fetch execution plan
                plan_rows = cursor.fetchall()
                columns = [column[0] for column in cursor.description]
                
                cursor.execute("SET SHOWPLAN_ALL OFF")
                connection.close()
                
                return {
                    'success': True,
                    'execution_plan': {
                        'columns': columns,
                        'rows': [list(row) for row in plan_rows]
                    }
                }
            
            except pyodbc.Error as e:
                connection.close()
                return {
                    'success': False,
                    'error': f'Failed to get execution plan: {str(e)}'
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': f'Execution plan failed: {str(e)}'
            }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert SQL job to dictionary"""
        base_dict = super().to_dict()
        base_dict.update({
            'sql_query': self.sql_query,
            'connection_name': self.connection_name,
            'connection_string': self.connection_string,
            'database_name': self.database_name,
            'query_timeout': self.query_timeout,
            'fetch_size': self.fetch_size,
            'max_rows': self.max_rows
        })
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SqlJob':
        """Create SQL job from dictionary"""
        # Extract SQL-specific parameters
        sql_params = {
            'sql_query': data.get('sql_query', ''),
            'connection_name': data.get('connection_name', 'default'),
            'connection_string': data.get('connection_string'),
            'database_name': data.get('database_name'),
            'query_timeout': data.get('query_timeout', 300),
            'fetch_size': data.get('fetch_size', 1000),
            'max_rows': data.get('max_rows', 10000)
        }
        
        # Extract base job parameters
        base_params = {
            'job_id': data.get('job_id'),
            'name': data.get('name', ''),
            'description': data.get('description', ''),
            'timeout': data.get('timeout', 300),
            'max_retries': data.get('max_retries', 3),
            'retry_delay': data.get('retry_delay', 60),
            'run_as': data.get('run_as'),
            'enabled': data.get('enabled', True),
            'metadata': data.get('metadata', {})
        }
        
        # Combine parameters
        all_params = {**base_params, **sql_params}
        
        return cls(**all_params)
    
    def clone(self, new_name: str = None) -> 'SqlJob':
        """Create a copy of this SQL job"""
        job_dict = self.to_dict()
        job_dict['job_id'] = None  # Will generate new ID
        if new_name:
            job_dict['name'] = new_name
        return self.from_dict(job_dict)


if __name__ == "__main__":
    # Test SQL job
    job = SqlJob(
        name="Test SQL Job",
        description="A test SQL job",
        sql_query="SELECT GETDATE() as current_time, 'Hello from SQL Server' as message",
        connection_name="default",
        timeout=60
    )
    
    print(f"Created SQL job: {job}")
    print(f"Job config: {job.to_dict()}")
    
    # Test connection
    conn_test = job.test_connection()
    print(f"Connection test: {conn_test}")
    
    if conn_test['success']:
        # Validate query
        validation = job.validate_query()
        print(f"Query validation: {validation}")
        
        if validation['valid']:
            # Execute job
            result = job.run()
            print(f"Execution result: {result.status.value}")
            print(f"Output: {result.output}")
            if result.metadata:
                print(f"Metadata: {result.metadata}")
    else:
        print("Skipping execution due to connection failure")