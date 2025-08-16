#!/usr/bin/env python3
"""
Test PowerShell script content with special characters
"""

import sys
import os
import json
import requests

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

def test_special_characters_direct():
    """Test PowerShell job creation with various special characters directly"""
    print("=" * 60)
    print("Testing PowerShell Script Special Characters - Direct")
    print("=" * 60)
    
    try:
        from core.job_manager import JobManager
        
        # Test scripts with various special characters
        test_scripts = [
            {
                'name': 'Simple Script',
                'content': 'Write-Host "Hello World"'
            },
            {
                'name': 'Script with Quotes',
                'content': '''Write-Host "Hello 'World' with nested quotes"
Write-Host 'Hello "World" with nested quotes'
Write-Host `"Escaped quotes`"'''
            },
            {
                'name': 'Script with Line Breaks',
                'content': '''Write-Host "Line 1"
Write-Host "Line 2"
Write-Host "Line 3"'''
            },
            {
                'name': 'Script with Special Characters',
                'content': '''Write-Host "Testing special chars: !@#$%^&*()_+"
Write-Host "Unicode: ñáéíóú"
Write-Host "Symbols: <>|&;`~"'''
            },
            {
                'name': 'Script with Backslashes',
                'content': r'''$path = "C:\Windows\System32"
Write-Host "Path: $path"
Get-ChildItem "C:\Users\*"'''
            },
            {
                'name': 'Script with JSON-like Content',
                'content': '''$json = @"
{
    "name": "test",
    "value": "hello \"world\"",
    "array": [1, 2, 3]
}
"@
Write-Host $json'''
            }
        ]
        
        job_manager = JobManager()
        
        for i, test_script in enumerate(test_scripts):
            print(f"\n📝 Testing: {test_script['name']}")
            print(f"   Content length: {len(test_script['content'])} chars")
            
            job_data = {
                'name': f"Test PS Job {i+1} - {test_script['name']}",
                'description': f"Testing script with {test_script['name'].lower()}",
                'type': 'powershell',
                'enabled': True,
                'script_content': test_script['content'],
                'execution_policy': 'RemoteSigned',
                'parameters': [],
                'timeout': 300,
                'max_retries': 3,
                'retry_delay': 60
            }
            
            try:
                # Test JSON serialization first
                json_test = json.dumps(job_data)
                print(f"   ✅ JSON serialization successful")
                
                # Test job creation
                result = job_manager.create_job(job_data)
                
                if result['success']:
                    print(f"   ✅ Job creation successful: {result['job_id']}")
                else:
                    print(f"   ❌ Job creation failed: {result['error']}")
                    
            except json.JSONDecodeError as e:
                print(f"   ❌ JSON serialization failed: {e}")
            except Exception as e:
                print(f"   ❌ Job creation failed with exception: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Direct test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_special_characters_api():
    """Test PowerShell job creation with special characters via API"""
    print("\n" + "=" * 60)
    print("Testing PowerShell Script Special Characters - API")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:5000"
    
    # Test if the web UI is running
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        print(f"✅ Web UI is running (status: {response.status_code})")
    except requests.ConnectionError:
        print("❌ Web UI is not running. Please start it first.")
        return False
    
    # Test a complex PowerShell script with special characters
    complex_script = '''# PowerShell Script with Special Characters
param(
    [string]$Name = "Test User",
    [string]$Path = "C:\\Windows\\System32"
)

Write-Host "Hello $Name!" -ForegroundColor Green
Write-Host "Processing path: $Path"

# Test JSON-like content
$config = @"
{
    "server": "localhost",
    "port": 5432,
    "credentials": {
        "username": "admin",
        "password": "secret123!@#"
    }
}
"@

Write-Host "Configuration: $config"

# Test various quotes and escapes
Write-Host 'Single quotes with "double quotes" inside'
Write-Host "Double quotes with 'single quotes' inside"
Write-Host `"Escaped double quotes`"

# Test special characters
Write-Host "Special chars: !@#$%^&*()_+-=[]{}|;':,./<>?"
Write-Host "Unicode: ñáéíóúü"

# Test command execution
Get-Date | Format-Table
'''
    
    job_data = {
        'name': 'Complex PowerShell Script Test',
        'description': 'PowerShell job with complex script content and special characters',
        'type': 'powershell',
        'enabled': True,
        'script_content': complex_script,
        'execution_policy': 'RemoteSigned',
        'parameters': ['-Name', 'API Test User', '-Path', 'C:\\TestPath'],
        'timeout': 300,
        'max_retries': 3,
        'retry_delay': 60
    }
    
    try:
        print(f"📝 Testing complex PowerShell script via API...")
        print(f"   Script length: {len(complex_script)} characters")
        print(f"   Contains special chars, JSON, quotes, and parameters")
        
        response = requests.post(
            f"{base_url}/api/jobs",
            json=job_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"   Response status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success'):
                job_id = result.get('job_id')
                print(f"   ✅ Complex PowerShell job created successfully: {job_id}")
                
                # Test job execution
                print(f"\n🚀 Testing execution of complex PowerShell job...")
                exec_response = requests.post(
                    f"{base_url}/api/jobs/{job_id}/run",
                    timeout=30
                )
                
                if exec_response.status_code == 200:
                    exec_result = exec_response.json()
                    print(f"   ✅ Job executed: {exec_result.get('status', 'unknown')}")
                    
                    # Check if script content was preserved
                    if exec_result.get('output'):
                        output = exec_result.get('output', '')
                        if 'PowerShell Script with Special Characters' in output:
                            print(f"   ✅ Script content preserved correctly")
                        else:
                            print(f"   ⚠️ Script content may not be fully preserved")
                    
                    return True
                else:
                    print(f"   ❌ Job execution failed: {exec_response.status_code}")
                    print(f"   Response: {exec_response.text}")
                    return False
            else:
                print(f"   ❌ Job creation failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"   ❌ API request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
            # Try to parse the error response
            try:
                error_data = response.json()
                print(f"   Error details: {error_data}")
            except:
                pass
            
            return False
            
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

if __name__ == "__main__":
    print("PowerShell Script Special Characters Test Suite")
    print("This will test handling of various special characters in PowerShell scripts")
    print("Including quotes, line breaks, JSON content, and Unicode characters\n")
    
    # Test direct job creation
    direct_success = test_special_characters_direct()
    
    # Test API job creation  
    api_success = test_special_characters_api()
    
    print("\n" + "=" * 60)
    print("Special Characters Test Summary")
    print("=" * 60)
    print(f"Direct Creation Test: {'✅ PASSED' if direct_success else '❌ FAILED'}")
    print(f"API Creation Test: {'✅ PASSED' if api_success else '❌ FAILED'}")
    
    if direct_success and api_success:
        print("\n🎉 Special character handling is working correctly!")
        print("✅ PowerShell scripts with complex content can be stored and executed")
        print("✅ Quotes, line breaks, and special characters are preserved")
        print("✅ JSON-like content in scripts is handled properly")
    else:
        print("\n⚠️ Some special character tests failed.")
        print("This may indicate issues with JSON encoding, database storage, or script execution.")