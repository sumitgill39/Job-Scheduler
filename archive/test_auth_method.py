#!/usr/bin/env python3
"""
Test which authentication method is being used
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_authentication_method():
    print("=" * 60)
    print("Authentication Method Test")
    print("=" * 60)
    
    try:
        # Import and create the Flask app (this will initialize all components)
        from web_ui.app import create_app
        
        print("Creating Flask application...")
        app = create_app()
        
        if hasattr(app, 'db_manager') and app.db_manager:
            print("✅ Database manager found in Flask app")
            
            # Get the configuration from the database manager
            config = app.db_manager.config
            
            print(f"Server: {config.server}")
            print(f"Port: {config.port}")  
            print(f"Database: {config.database}")
            print(f"Username: {config.username}")
            print(f"Password: {'SET' if config.password else 'NOT SET'}")
            print(f"Trusted Connection: {config.trusted_connection}")
            
            # Generate connection string to see what will be used
            conn_str = config.get_safe_connection_string()
            print(f"\nConnection String Preview:")
            print(f"{conn_str}")
            
            # Analyze authentication method
            if config.trusted_connection:
                print("\n❌ ISSUE: Will use Windows Authentication (your local user)")
                print("   Your Windows username will be used to connect to SQL Server")
            else:
                print(f"\n✅ CORRECT: Will use SQL Server Authentication")
                print(f"   Username '{config.username}' will be used to connect to SQL Server")
                
            # Try to determine what credentials would actually be used
            if "Trusted_Connection=yes" in conn_str:
                print("\n⚠️  WARNING: Connection string contains Trusted_Connection=yes")
                print("   This means Windows Authentication will be attempted")
                print("   Your local Windows user will be used")
            elif "UID=" in conn_str and "PWD=" in conn_str:
                print("\n✅ CONFIRMED: Connection string uses SQL Server Authentication")
                print("   The svc user credentials will be used")
            
        else:
            print("❌ No database manager found in Flask app")
            
    except Exception as e:
        print(f"❌ Error testing authentication: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_authentication_method()