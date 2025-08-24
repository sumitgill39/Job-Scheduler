#!/usr/bin/env python3
"""
Test script to start web UI in mock mode for testing job execution
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    from web_ui.app import create_app
    
    print("Creating Flask app...")
    app = create_app(scheduler_manager=None)  # No scheduler manager for testing
    
    print("Starting Flask development server...")
    print("Web UI will be available at: http://localhost:5000")
    print("Note: Running in mock mode - database connections will not work")
    
    app.run(debug=True, host='127.0.0.1', port=5000)
    
except Exception as e:
    print(f"Error starting web UI: {e}")
    import traceback
    traceback.print_exc()