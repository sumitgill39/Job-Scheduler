#!/usr/bin/env python3
"""
Check job execution history in the database
"""

from database.sqlalchemy_models import get_db_session, JobExecutionHistory, JobExecutionHistoryV2
from sqlalchemy import desc

def main():
    try:
        print("Checking job execution history...")
        
        with get_db_session() as session:
            # Check both V1 and V2 execution history tables
            print("\n=== V2 Execution History (job_execution_history_v2) ===")
            executions_v2 = session.query(JobExecutionHistoryV2).order_by(desc(JobExecutionHistoryV2.start_time)).limit(10).all()
            
            print(f"Found {len(executions_v2)} V2 execution records:")
            print("=" * 80)
            
            for execution in executions_v2:
                print(f"Execution ID: {execution.execution_id}")
                print(f"Job ID: {execution.job_id}")
                print(f"Job Name: {execution.job_name}")
                print(f"Status: {execution.status}")
                print(f"Start Time: {execution.start_time}")
                print(f"End Time: {execution.end_time}")
                print(f"Duration: {execution.duration_seconds} seconds")
                print(f"Output: {execution.output_log[:100]}..." if execution.output_log else "No output")
                print(f"Error: {execution.error_message}" if execution.error_message else "No error")
                print("-" * 80)
            
            print("\n=== V1 Execution History (job_execution_history) ===")
            executions = session.query(JobExecutionHistory).order_by(desc(JobExecutionHistory.start_time)).limit(5).all()
            
            print(f"Found {len(executions)} V1 execution records:")
            print("=" * 80)
            
            for execution in executions:
                print(f"Execution ID: {execution.execution_id}")
                print(f"Job ID: {execution.job_id}")
                print(f"Job Name: {execution.job_name}")
                print(f"Status: {execution.status}")
                print(f"Start Time: {execution.start_time}")
                print(f"End Time: {execution.end_time}")
                print(f"Duration: {execution.duration_seconds} seconds")
                print(f"Output: {execution.output[:100]}..." if execution.output else "No output")
                print(f"Error: {execution.error_message}" if execution.error_message else "No error")
                print("-" * 80)
                
            if len(executions_v2) == 0 and len(executions) == 0:
                print("No execution history found in either table!")
                
    except Exception as e:
        print(f"Error checking execution history: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()