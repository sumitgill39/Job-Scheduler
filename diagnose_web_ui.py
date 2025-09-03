#!/usr/bin/env python3
"""
Diagnose why the History page isn't showing executions
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_web_server():
    """Check if web server is accessible"""
    print("Checking web server accessibility...")
    
    try:
        import urllib.request
        import json
        
        # Test if server is running
        print("1. Testing if server responds...")
        try:
            response = urllib.request.urlopen("http://localhost:5000", timeout=5)
            print("   ✓ Web server is running on localhost:5000")
            server_running = True
        except Exception as e:
            print(f"   ✗ Web server not accessible: {e}")
            server_running = False
        
        if not server_running:
            return False
        
        # Test API endpoint
        print("2. Testing /api/executions/history endpoint...")
        try:
            response = urllib.request.urlopen("http://localhost:5000/api/executions/history?limit=5", timeout=10)
            data = json.loads(response.read().decode())
            
            print(f"   ✓ API responds: success={data.get('success')}")
            print(f"   ✓ Total executions: {data.get('total_count', 0)}")
            
            executions = data.get('executions', [])
            p1_count = len([ex for ex in executions if ex.get('job_name') == 'P1'])
            print(f"   ✓ P1 executions in API: {p1_count}")
            
            if p1_count > 0:
                print("   ✓ Recent P1 executions are available via API")
                return True
            else:
                print("   ✗ No P1 executions in API response")
                return False
                
        except Exception as e:
            print(f"   ✗ API endpoint error: {e}")
            return False
            
    except ImportError:
        print("   ! Cannot test web server (urllib not available)")
        return None

def check_browser_issues():
    """Provide browser troubleshooting tips"""
    print("\\nBrowser troubleshooting checklist:")
    print("1. ✓ Hard refresh the History page (Ctrl+F5 or Cmd+Shift+R)")
    print("2. ✓ Clear browser cache and cookies for localhost:5000") 
    print("3. ✓ Open browser DevTools (F12) and check:")
    print("   - Console tab for JavaScript errors")
    print("   - Network tab for failed API requests")
    print("   - Make sure /api/executions/history returns data")
    print("4. ✓ Try accessing History page in incognito/private mode")
    print("5. ✓ Verify URL: http://localhost:5000/executions/history")

def main():
    """Main diagnostic function"""
    print("Web UI History Page Diagnostics")
    print("=" * 50)
    
    # Check if data exists in backend
    print("Backend data check:")
    try:
        from core.job_manager import JobManager
        job_manager = JobManager()
        history = job_manager.get_all_execution_history(5)
        p1_count = len([h for h in history if h.get('job_name') == 'P1'])
        print(f"✓ Backend has {len(history)} total executions")
        print(f"✓ Backend has {p1_count} P1 executions")
        backend_ok = p1_count > 0
    except Exception as e:
        print(f"✗ Backend error: {e}")
        backend_ok = False
    
    print()
    
    # Check web server
    server_ok = check_web_server()
    
    print()
    
    # Diagnosis
    if backend_ok and server_ok:
        print("[DIAGNOSIS] Backend and API are working correctly!")
        print("   The issue is likely in the browser or web page JavaScript.")
        check_browser_issues()
        
        print("\\n[NEXT STEPS] NEXT STEPS:")
        print("1. Open browser DevTools (F12)")
        print("2. Go to History page: http://localhost:5000/executions/history")
        print("3. Check Console for JavaScript errors")
        print("4. Check Network tab - look for /api/executions/history request")
        print("5. Verify the API request returns recent P1 executions")
        
    elif backend_ok and server_ok is None:
        print("[WARNING] DIAGNOSIS: Backend works, cannot test web server")
        print("   Please manually verify web server is running on localhost:5000")
        
    elif backend_ok:
        print("[DIAGNOSIS] Backend works, but web server is not running")
        print("\\n[SOLUTION] SOLUTION: Start the web server:")
        print("   python run_web.py")
        print("   or")
        print("   python web_ui/app.py")
        
    else:
        print("💥 DIAGNOSIS: Backend data issue")
        print("   Recent job executions are not being saved to database")
    
    print("\\n" + "=" * 50)

if __name__ == "__main__":
    main()