#!/usr/bin/env python3
"""
Debug script to check environment variable loading
"""

import os
from pathlib import Path

def debug_env_loading():
    print("=" * 60)
    print("Environment Variable Loading Debug")
    print("=" * 60)
    
    # Check if .env file exists
    env_file = Path('.env')
    print(f"1. .env file exists: {env_file.exists()}")
    if env_file.exists():
        print(f"   .env file path: {env_file.absolute()}")
        with open(env_file, 'r') as f:
            content = f.read()
            print(f"   .env file size: {len(content)} characters")
    
    # Try to load dotenv
    try:
        from dotenv import load_dotenv
        print("2. python-dotenv available: ✅")
        
        # Load the .env file
        result = load_dotenv(env_file)
        print(f"3. load_dotenv() result: {result}")
        
    except ImportError as e:
        print(f"2. python-dotenv NOT available: {e}")
        return
    
    # Check environment variables BEFORE loading our DatabaseConfig
    print("\n4. Environment variables (direct os.getenv):")
    db_vars = [
        'DB_DRIVER', 'DB_SERVER', 'DB_PORT', 'DB_DATABASE',
        'DB_USERNAME', 'DB_PASSWORD', 'DB_TRUSTED_CONNECTION',
        'DB_CONNECTION_TIMEOUT', 'DB_COMMAND_TIMEOUT'
    ]
    
    for var in db_vars:
        value = os.getenv(var)
        if var == 'DB_PASSWORD':
            display_value = "***" if value else "NOT SET"
        else:
            display_value = value if value is not None else "NOT SET"
        print(f"   {var}: {display_value}")
    
    # Test our DatabaseConfig class
    print("\n5. Testing DatabaseConfig class:")
    try:
        from database.simple_connection_manager import DatabaseConfig
        config = DatabaseConfig()
        
        print(f"   server: {config.server}")
        print(f"   port: {config.port}")
        print(f"   database: {config.database}")
        print(f"   username: {config.username}")
        print(f"   password: {'***' if config.password else 'NOT SET'}")
        print(f"   trusted_connection: {config.trusted_connection}")
        
        # Test connection string
        conn_str = config.get_safe_connection_string()
        print(f"\n6. Generated connection string:")
        print(f"   {conn_str}")
        
        # Check if it contains Trusted_Connection
        if "Trusted_Connection=yes" in conn_str:
            print("   ⚠️  ISSUE: Using Windows Authentication!")
        elif "UID=" in conn_str and "PWD=" in conn_str:
            print("   ✅ CORRECT: Using SQL Server Authentication")
        else:
            print("   ❌ ERROR: No authentication method detected!")
            
    except Exception as e:
        print(f"   ERROR loading DatabaseConfig: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_env_loading()