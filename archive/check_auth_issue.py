#!/usr/bin/env python3
"""
Check authentication issue - debug why it's using local credentials
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_auth_issue():
    print("=" * 60)
    print("Authentication Issue Debug")
    print("=" * 60)
    
    # 1. Check .env file contents directly
    print("1. Checking .env file contents:")
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    if 'PASSWORD' in line:
                        key, _ = line.split('=', 1)
                        print(f"   {key}=***")
                    else:
                        print(f"   {line.strip()}")
    
    # 2. Load dotenv and check environment variables
    print("\n2. Loading environment variables:")
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print("   ✅ dotenv loaded successfully")
    except Exception as e:
        print(f"   ❌ dotenv loading failed: {e}")
        return
    
    # 3. Check specific variables
    print("\n3. Environment variables after loading:")
    critical_vars = {
        'DB_TRUSTED_CONNECTION': os.getenv('DB_TRUSTED_CONNECTION'),
        'DB_USERNAME': os.getenv('DB_USERNAME'), 
        'DB_PASSWORD': '***' if os.getenv('DB_PASSWORD') else None,
        'DB_SERVER': os.getenv('DB_SERVER'),
    }
    
    for var, value in critical_vars.items():
        print(f"   {var}: {value}")
    
    # 4. Check boolean conversion
    trusted_conn_str = os.getenv('DB_TRUSTED_CONNECTION', 'false')
    trusted_conn_bool = trusted_conn_str.lower() == 'true'
    print(f"\n4. Boolean conversion:")
    print(f"   DB_TRUSTED_CONNECTION string: '{trusted_conn_str}'")
    print(f"   DB_TRUSTED_CONNECTION boolean: {trusted_conn_bool}")
    
    # 5. Test DatabaseConfig class
    print("\n5. Testing DatabaseConfig class:")
    try:
        from database.simple_connection_manager import DatabaseConfig
        config = DatabaseConfig()
        
        print(f"   config.trusted_connection: {config.trusted_connection}")
        print(f"   config.username: {config.username}")
        print(f"   config.password: {'SET' if config.password else 'NOT SET'}")
        
        # Generate connection string
        conn_str = config.build_connection_string()
        
        print(f"\n6. Connection string analysis:")
        if "Trusted_Connection=yes" in conn_str:
            print("   ❌ PROBLEM: Connection string contains 'Trusted_Connection=yes'")
            print("   This will use Windows Authentication (your local user)")
        elif "UID=" in conn_str and "PWD=" in conn_str:
            print("   ✅ CORRECT: Connection string uses SQL Server Authentication")
            print("   This will use the svc user from .env file")
        else:
            print("   ⚠️  UNKNOWN: Cannot determine authentication method")
        
        # Show masked connection string
        masked_conn_str = config.get_safe_connection_string()
        print(f"   Connection string: {masked_conn_str}")
        
    except Exception as e:
        print(f"   ❌ Error testing DatabaseConfig: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. Check for any old configuration files
    print(f"\n7. Checking for old configuration files:")
    old_config_files = [
        'config/database_config.yaml',
        'config/config.yaml'
    ]
    
    for config_file in old_config_files:
        if Path(config_file).exists():
            print(f"   ⚠️  WARNING: {config_file} still exists")
            print("   This might be interfering with the new system")
        else:
            print(f"   ✅ {config_file} does not exist")

if __name__ == "__main__":
    check_auth_issue()