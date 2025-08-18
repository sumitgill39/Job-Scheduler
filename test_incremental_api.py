#!/usr/bin/env python3
"""
Test script for the new incremental polling API endpoint
"""

import requests
import json
import time
from datetime import datetime

def test_incremental_api():
    base_url = "http://localhost:5000"  # Adjust if your server runs on different port
    
    # Test with a dummy job ID - replace with actual job ID when testing
    job_id = "test-job-id"
    
    print("🧪 Testing Incremental Polling API")
    print("=" * 50)
    
    # Test 1: Initial fetch (no timestamp)
    print("\n1️⃣ Testing initial fetch (no since parameter)")
    try:
        response = requests.get(f"{base_url}/api/jobs/{job_id}/history/incremental?limit=5")
        data = response.json()
        
        print(f"Status Code: {response.status_code}")
        print(f"Success: {data.get('success', False)}")
        print(f"Records Count: {len(data.get('execution_history', []))}")
        print(f"Latest Timestamp: {data.get('latest_timestamp', 'None')}")
        
        latest_timestamp = data.get('latest_timestamp')
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Make sure the web server is running")
        return
    except Exception as e:
        print(f"❌ Error: {e}")
        return
    
    # Test 2: Incremental fetch (with timestamp)
    if latest_timestamp:
        print("\n2️⃣ Testing incremental fetch (with since parameter)")
        try:
            response = requests.get(f"{base_url}/api/jobs/{job_id}/history/incremental?since={latest_timestamp}&limit=5")
            data = response.json()
            
            print(f"Status Code: {response.status_code}")
            print(f"Success: {data.get('success', False)}")
            print(f"Records Count: {len(data.get('execution_history', []))}")
            print(f"Since Timestamp: {data.get('since_timestamp', 'None')}")
            print(f"Latest Timestamp: {data.get('latest_timestamp', 'None')}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test 3: Compare with regular API
    print("\n3️⃣ Comparing with regular history API")
    try:
        response = requests.get(f"{base_url}/api/jobs/{job_id}/history?limit=5")
        data = response.json()
        
        print(f"Regular API - Status Code: {response.status_code}")
        print(f"Regular API - Success: {data.get('success', False)}")
        print(f"Regular API - Records Count: {len(data.get('execution_history', []))}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n✅ API endpoint test completed!")
    print("\n💡 To test with real data:")
    print("1. Start the web application")
    print("2. Replace 'test-job-id' with an actual job ID")
    print("3. Run this script again")

if __name__ == "__main__":
    test_incremental_api()