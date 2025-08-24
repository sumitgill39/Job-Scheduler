"""
Setup script for configuring the system database connection
"""

import yaml
from pathlib import Path

def setup_system_database():
    """Configure the system database connection"""
    print("=" * 60)
    print("Windows Job Scheduler - System Database Setup")
    print("=" * 60)
    
    print("\nThis script will configure the system database connection for storing user connections.")
    print("Please provide the details for your SQL Server database:")
    
    # Get database details from user
    server = input("\nSQL Server name/IP (e.g., localhost, 192.168.1.100): ").strip()
    if not server:
        server = "localhost"
    
    port = input("Port (press Enter for default 1433): ").strip()
    if not port:
        port = 1433
    else:
        try:
            port = int(port)
        except:
            port = 1433
    
    database = input("Database name (e.g., JobScheduler): ").strip()
    if not database:
        database = "JobScheduler"
    
    print("\nAuthentication type:")
    print("1. Windows Authentication (recommended)")
    print("2. SQL Server Authentication")
    auth_choice = input("Choose (1 or 2): ").strip()
    
    if auth_choice == "2":
        # SQL Server Authentication
        username = input("SQL Server username: ").strip()
        password = input("SQL Server password: ").strip()
        trusted_connection = False
    else:
        # Windows Authentication
        username = None
        password = None
        trusted_connection = True
        print("Using Windows Authentication")
    
    # Build configuration
    config = {
        'databases': {
            'system': {
                'driver': '{ODBC Driver 17 for SQL Server}',
                'server': server,
                'port': port if port != 1433 else None,
                'database': database,
                'trusted_connection': trusted_connection,
                'username': username,
                'password': password,
                'connection_timeout': 30,
                'command_timeout': 300,
                'description': 'System database for storing user connections',
                'is_system_connection': True
            }
        },
        'connection_pool': {
            'max_connections': 10,
            'min_connections': 2,
            'connection_lifetime': 3600
        },
        'retry_settings': {
            'max_retries': 3,
            'retry_delay': 5,
            'backoff_factor': 2
        },
        'query_settings': {
            'default_timeout': 300,
            'long_running_timeout': 1800,
            'batch_size': 1000
        },
        'validation': {
            'test_query': 'SELECT 1',
            'validate_on_borrow': True,
            'validation_timeout': 5
        }
    }
    
    # Save configuration
    config_path = Path('config/database_config.yaml')
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print(f"\n✅ Configuration saved to: {config_path}")
    
    # Test the connection
    print("\n🔍 Testing database connection...")
    try:
        from database.connection_manager import DatabaseConnectionManager
        
        db_manager = DatabaseConnectionManager()
        test_result = db_manager.test_connection("system")
        
        if test_result['success']:
            print(f"✅ Connection successful! ({test_result['response_time']:.2f}s)")
            print("📋 System database tables will be created automatically on first run.")
        else:
            print(f"❌ Connection failed: {test_result['error']}")
            print("\n🔧 Please check your connection details and try again.")
            return False
            
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ System database setup completed successfully!")
    print("\nYou can now:")
    print("1. Start the Job Scheduler application")
    print("2. Navigate to the Connections page")
    print("3. Add your SQL Server connections")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    try:
        setup_system_database()
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
    except Exception as e:
        print(f"\nError during setup: {e}")