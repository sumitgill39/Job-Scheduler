#!/usr/bin/env python3
"""
Script to update routes.py to use the new database manager
"""

import re

def update_routes_file():
    routes_file = "/Users/sumeet/Documents/GitHub/Job Scheduler/web_ui/routes.py"
    
    # Read the file
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Pattern replacements
    replacements = [
        # Replace connection pool references with db_manager
        (
            r"pool = getattr\(app, 'connection_pool', None\)",
            "db_manager = getattr(app, 'db_manager', None)"
        ),
        (
            r"if not pool:",
            "if not db_manager:"
        ),
        (
            r"db_manager = pool\.db_manager",
            "# db_manager already set above"
        ),
        # Remove connection pool specific patterns
        (
            r"pool\.get_connection\(",
            "db_manager.get_connection("
        ),
        (
            r"pool\.return_connection\(",
            "db_manager.return_connection("
        ),
        # Fix connection usage patterns
        (
            r"connection = pool\.get_connection\('system'\)",
            "connection = db_manager.get_connection()"
        )
    ]
    
    # Apply replacements
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write back
    with open(routes_file, 'w') as f:
        f.write(content)
    
    print("✅ Updated routes.py to use new database manager")

if __name__ == "__main__":
    update_routes_file()