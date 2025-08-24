#!/usr/bin/env python3
"""
Script to update job_manager.py to use proper connection return
"""

import re

def update_job_manager():
    file_path = "/Users/sumeet/Documents/GitHub/Job Scheduler/core/job_manager.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace connection close patterns with proper return
    patterns = [
        # Replace "Don't close connection - let pool manage it" comments with actual return
        (
            r"cursor\.close\(\)\s*\n\s*# Don't close connection - let pool manage it",
            "cursor.close()\n            self.db_manager.return_connection(system_connection)"
        ),
        # Replace standalone cursor.close() where there should be a connection return
        (
            r"cursor\.close\(\)\s*\n\s*\n\s*(if|return|self\.logger)",
            "cursor.close()\n            self.db_manager.return_connection(system_connection)\n            \n            \\1"
        )
    ]
    
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("✅ Updated job_manager.py connection handling")

if __name__ == "__main__":
    update_job_manager()