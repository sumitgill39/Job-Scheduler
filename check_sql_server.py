"""
SQL Server Express Diagnostic Script
Helps diagnose issues with local SQL Express connection
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and return the result"""
    print(f"\n--- {description} ---")
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=30)
        if result.returncode == 0:
            print(f"[SUCCESS] {result.stdout.strip()}")
            return True, result.stdout.strip()
        else:
            print(f"[FAILED] {result.stderr.strip()}")
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] Command timed out")
        return False, "Timeout"
    except Exception as e:
        print(f"[ERROR] {e}")
        return False, str(e)

def main():
    """Main diagnostic function"""
    print("=" * 60)
    print("SQL Server Express Diagnostic Tool")
    print("=" * 60)
    
    # Check for SQL Server services
    print("\n1. Checking for SQL Server services...")
    success, output = run_command(
        'powershell "Get-Service | Where-Object {$_.Name -like \'*SQL*\'} | Select-Object Name, Status, DisplayName | Format-Table -AutoSize"',
        "SQL Server Services"
    )
    
    # Check for SQL Server instances
    print("\n2. Checking for SQL Server instances...")
    success, output = run_command(
        'sqlcmd -L',
        "SQL Server Instances (sqlcmd -L)"
    )
    
    # Try to connect to the specific instance
    print("\n3. Testing connection to DESKTOP-4ADGDVE\\SQLEXPRESS...")
    success, output = run_command(
        'sqlcmd -S "DESKTOP-4ADGDVE\\SQLEXPRESS" -E -Q "SELECT @@VERSION"',
        "Direct Connection Test"
    )
    
    if not success:
        print("\n4. Checking if SQL Server Express is installed...")
        success, output = run_command(
            'reg query "HKLM\\SOFTWARE\\Microsoft\\Microsoft SQL Server\\Instance Names\\SQL"',
            "Registry Check for SQL Server Instances"
        )
    
    # Check network configuration
    print("\n5. Checking network configuration...")
    success, output = run_command(
        'netstat -an | findstr 1433',
        "Checking if port 1433 is listening"
    )
    
    print("\n" + "=" * 60)
    print("Diagnostic completed. Based on the results above:")
    print("1. If no SQL services are running, start SQL Server Express")
    print("2. If no instances are found, SQL Server Express might not be installed")
    print("3. If connection fails, check SQL Server Configuration Manager")
    print("4. Ensure TCP/IP is enabled and SQL Browser service is running")
    print("=" * 60)

if __name__ == "__main__":
    main()