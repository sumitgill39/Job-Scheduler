#!/usr/bin/env python3
"""
Windows Database Connection Test
Tests the database connection string format for Windows compatibility
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_windows_connection():
    """Test Windows database connection"""
    print("=" * 60)
    print("WINDOWS DATABASE CONNECTION TEST")
    print("=" * 60)
    
    try:
        # Test environment loading
        print("\n1. Testing environment loading...")
        from dotenv import load_dotenv
        import os
        
        # Load .env file
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"✓ .env file loaded from: {env_path}")
        else:
            print(f"✗ .env file not found at: {env_path}")
            return False
        
        # Test database configuration
        print("\n2. Testing database configuration...")
        from database.simple_connection_manager import DatabaseConfig
        
        config = DatabaseConfig()
        print(f"✓ Driver: {config.driver}")
        print(f"✓ Server: {config.server}:{config.port}")
        print(f"✓ Database: {config.database}")
        print(f"✓ Username: {config.username}")
        print(f"✓ Trusted Connection: {config.trusted_connection}")
        
        # Test connection string building
        print("\n3. Testing connection string building...")
        connection_string = config.build_connection_string()
        print(f"✓ Connection String: {connection_string}")
        
        # Verify Windows-specific elements
        print("\n4. Verifying Windows compatibility...")
        checks = [
            ("ODBC Driver", "ODBC Driver 17 for SQL Server" in connection_string),
            ("Named Instance", "\\" in config.server),
            ("SQL Server Auth", f"UID={config.username}" in connection_string),
            ("No Windows Auth", "Trusted_Connection=yes" not in connection_string),
            ("Server Certificate", "TrustServerCertificate=yes" in connection_string)
        ]
        
        all_passed = True
        for check_name, result in checks:
            status = "✓" if result else "✗"
            print(f"{status} {check_name}: {'PASS' if result else 'FAIL'}")
            if not result:
                all_passed = False
        
        # Test database manager
        print("\n5. Testing database manager...")
        from database.simple_connection_manager import get_database_manager
        
        db_manager = get_database_manager()
        print(f"✓ Database manager created: {type(db_manager).__name__}")
        
        # Test connection (without actually connecting on non-Windows)
        if sys.platform == "win32":
            print("\n6. Testing actual database connection...")
            try:
                test_result = db_manager.test_connection()
                if test_result['success']:
                    print(f"✓ Connection successful! ({test_result['response_time']:.2f}s)")
                    print(f"✓ Server version: {test_result.get('server_version', 'Unknown')}")
                else:
                    print(f"✗ Connection failed: {test_result['error']}")
                    all_passed = False
            except Exception as e:
                print(f"✗ Connection test error: {e}")
                all_passed = False
        else:
            print("\n6. Skipping actual connection test (not on Windows)")
        
        print("\n" + "=" * 60)
        if all_passed:
            print("✓ ALL TESTS PASSED - Windows compatibility verified!")
        else:
            print("✗ Some tests failed - review configuration")
        print("=" * 60)
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        print(f"Stack trace: {traceback.format_exc()}")
        return False

def test_windows_utils():
    """Test Windows utilities"""
    print("\n" + "=" * 60)
    print("WINDOWS UTILITIES TEST")
    print("=" * 60)
    
    try:
        from utils.windows_utils import WindowsUtils
        
        utils = WindowsUtils()
        
        # Test platform detection
        print(f"✓ Is Windows: {utils.is_windows()}")
        print(f"✓ Platform: {sys.platform}")
        
        # Test PowerShell detection
        if utils.is_windows():
            ps_path = utils.get_powershell_path()
            print(f"✓ PowerShell Path: {ps_path}")
        else:
            print("  Skipping PowerShell test (not on Windows)")
        
        print("✓ Windows utilities test passed")
        return True
        
    except Exception as e:
        print(f"✗ Windows utilities test failed: {e}")
        return False

if __name__ == "__main__":
    success = True
    
    # Test database connection
    success &= test_windows_connection()
    
    # Test Windows utilities
    success &= test_windows_utils()
    
    print(f"\nOVERALL RESULT: {'✓ SUCCESS' if success else '✗ FAILED'}")
    
    sys.exit(0 if success else 1)