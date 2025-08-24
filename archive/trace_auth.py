#!/usr/bin/env python3
"""
Trace authentication method being used in the application
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def trace_authentication():
    print("=" * 60)
    print("Authentication Method Tracer")
    print("=" * 60)
    
    # Step 1: Check environment setup
    print("1. Environment Setup:")
    
    # Load dotenv
    try:
        from dotenv import load_dotenv
        env_file = Path('.env')
        load_dotenv(env_file)
        print(f"   ✅ Loaded .env from: {env_file.absolute()}")
    except Exception as e:
        print(f"   ❌ Failed to load .env: {e}")
        return
    
    # Check critical variables
    trusted_conn = os.getenv('DB_TRUSTED_CONNECTION', 'NOT_SET')
    username = os.getenv('DB_USERNAME', 'NOT_SET')
    password = os.getenv('DB_PASSWORD', 'NOT_SET')
    
    print(f"   DB_TRUSTED_CONNECTION: '{trusted_conn}'")
    print(f"   DB_USERNAME: '{username}'")
    print(f"   DB_PASSWORD: {'SET' if password != 'NOT_SET' else 'NOT_SET'}")
    
    # Step 2: Test DatabaseConfig
    print("\n2. DatabaseConfig Class:")
    try:
        from database.simple_connection_manager import DatabaseConfig
        config = DatabaseConfig()
        
        print(f"   trusted_connection: {config.trusted_connection}")
        print(f"   username: '{config.username}'")
        print(f"   password: {'SET' if config.password else 'NOT_SET'}")
        
        # Build connection string
        conn_str = config.build_connection_string()
        
        # Analyze the connection string
        print(f"\n3. Connection String Analysis:")
        if "Trusted_Connection=yes" in conn_str:
            print("   ❌ USING WINDOWS AUTHENTICATION")
            print("   Your local Windows user will be used")
        elif "UID=" in conn_str and "PWD=" in conn_str:
            print("   ✅ USING SQL SERVER AUTHENTICATION")  
            print(f"   SQL Server user '{config.username}' will be used")
        else:
            print("   ⚠️  UNKNOWN AUTHENTICATION METHOD")
        
        # Show the connection string (masked)
        masked_conn_str = config.get_safe_connection_string()
        print(f"   Connection String: {masked_conn_str}")
        
    except Exception as e:
        print(f"   ❌ Error with DatabaseConfig: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Test Flask App Creation (which initializes the database manager)
    print(f"\n4. Flask Application Test:")
    try:
        from web_ui.app import create_app
        
        # Intercept database manager creation
        print("   Creating Flask app (this will create database manager)...")
        
        # Create the app
        app = create_app()
        
        if hasattr(app, 'db_manager') and app.db_manager:
            app_config = app.db_manager.config
            print(f"   App DB Manager - trusted_connection: {app_config.trusted_connection}")
            print(f"   App DB Manager - username: '{app_config.username}'")
            
            # Check the connection string the app will use
            app_conn_str = app_config.build_connection_string()
            if "Trusted_Connection=yes" in app_conn_str:
                print("   ❌ APP WILL USE WINDOWS AUTHENTICATION")
            elif "UID=" in app_conn_str:
                print("   ✅ APP WILL USE SQL SERVER AUTHENTICATION")
            else:
                print("   ⚠️  APP AUTHENTICATION METHOD UNKNOWN")
                
        else:
            print("   ❌ No database manager in Flask app")
            
    except Exception as e:
        print(f"   ❌ Error creating Flask app: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n5. Conclusion:")
    if trusted_conn.lower() == 'false' and username != 'NOT_SET':
        print("   ✅ Configuration appears correct for SQL Server authentication")
        print("   If you're still seeing Windows authentication, check:")
        print("   - Are you running from the correct directory?")
        print("   - Is there another .env file being loaded?")
        print("   - Are there any cached connections?")
    else:
        print("   ❌ Configuration issue detected")
        print("   Check your .env file settings")

if __name__ == "__main__":
    trace_authentication()