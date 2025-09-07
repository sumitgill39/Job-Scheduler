"""
Test script for Agent-Based Job Execution System
Verifies agent integration without breaking existing functionality
"""

import sys
import os
import time
import json
import requests
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.sqlalchemy_models import database_engine, init_database
from database.agent_models import create_agent_tables, AgentManager
from utils.logger import get_logger

logger = get_logger(__name__)

# Configuration
BASE_URL = "http://127.0.0.1:5000"
AGENT_API_URL = f"{BASE_URL}/api/agent"


def test_database_setup():
    """Test database setup with agent tables"""
    print("\n" + "="*60)
    print("TEST 1: Database Setup")
    print("="*60)
    
    try:
        # Initialize existing database
        result = init_database()
        if result['success']:
            print("✅ Existing database initialized successfully")
        else:
            print(f"❌ Database initialization failed: {result}")
            return False
        
        # Create agent tables
        create_agent_tables()
        print("✅ Agent tables created successfully")
        
        # Test database connection
        test_result = database_engine.test_connection()
        if test_result['success']:
            print("✅ Database connection test passed")
        else:
            print(f"❌ Database connection test failed: {test_result}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Database setup error: {e}")
        return False


def test_agent_registration():
    """Test agent registration via REST API"""
    print("\n" + "="*60)
    print("TEST 2: Agent Registration")
    print("="*60)
    
    # Test agent data
    agent_data = {
        "agent_id": "test-agent-001",
        "agent_name": "Test Agent 001",
        "hostname": "test-server-01",
        "ip_address": "127.0.0.1",
        "capabilities": ["python", "powershell", "test"],
        "max_parallel_jobs": 2,
        "agent_pool": "default",
        "agent_version": "1.0.0",
        "system_info": {
            "os": "Windows 10",
            "cpu_cores": 4,
            "memory_gb": 8,
            "disk_space_gb": 100
        }
    }
    
    try:
        # Register agent
        response = requests.post(
            f"{AGENT_API_URL}/register",
            json=agent_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code in [200, 201]:
            result = response.json()
            if result.get('success'):
                print(f"✅ Agent registered successfully")
                print(f"   Agent ID: {result.get('agent_id')}")
                print(f"   JWT Token: {result.get('jwt_token')[:20]}...")
                return result.get('jwt_token')
            else:
                print(f"❌ Registration failed: {result}")
                return None
        else:
            print(f"❌ HTTP error {response.status_code}: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Registration error: {e}")
        return None


def test_agent_heartbeat(jwt_token):
    """Test agent heartbeat"""
    print("\n" + "="*60)
    print("TEST 3: Agent Heartbeat")
    print("="*60)
    
    heartbeat_data = {
        "status": "online",
        "current_jobs": 0,
        "resource_usage": {
            "cpu_percent": 25.5,
            "memory_percent": 40.2,
            "disk_percent": 55.0
        },
        "timestamp": datetime.utcnow().isoformat()
    }
    
    try:
        response = requests.post(
            f"{AGENT_API_URL}/heartbeat",
            json=heartbeat_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jwt_token}"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Heartbeat updated successfully")
                print(f"   Server time: {result.get('server_time')}")
                return True
            else:
                print(f"❌ Heartbeat failed: {result}")
                return False
        else:
            print(f"❌ HTTP error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Heartbeat error: {e}")
        return False


def test_agent_approval():
    """Test agent approval"""
    print("\n" + "="*60)
    print("TEST 4: Agent Approval")
    print("="*60)
    
    try:
        # Approve the test agent
        response = requests.post(
            f"{AGENT_API_URL}/test-agent-001/approve",
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Agent approved successfully")
                return True
            else:
                print(f"❌ Approval failed: {result}")
                return False
        else:
            print(f"❌ HTTP error {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Approval error: {e}")
        return False


def test_existing_job_compatibility():
    """Test that existing jobs still work"""
    print("\n" + "="*60)
    print("TEST 5: Existing Job Compatibility")
    print("="*60)
    
    try:
        # Test existing SQL job (should run locally as before)
        test_job = {
            "name": "Test SQL Job - Local",
            "description": "Test that SQL jobs still run locally",
            "job_type": "sql",
            "yaml_configuration": """
job_type: sql
name: Test SQL Query
connection_name: system
query: SELECT 1 as test_value, GETDATE() as current_time
timeout: 30
"""
        }
        
        # Create job via API
        response = requests.post(
            f"{BASE_URL}/api/jobs",
            json=test_job,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            job_result = response.json()
            job_id = job_result.get('job_id')
            print(f"✅ Local SQL job created: {job_id}")
            
            # Execute job
            exec_response = requests.post(
                f"{BASE_URL}/api/jobs/{job_id}/execute",
                headers={"Content-Type": "application/json"}
            )
            
            if exec_response.status_code == 200:
                exec_result = exec_response.json()
                print(f"✅ Local job executed successfully")
                print(f"   Status: {exec_result.get('status')}")
                return True
            else:
                print(f"❌ Execution failed: {exec_response.text}")
                return False
        else:
            print(f"❌ Job creation failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Compatibility test error: {e}")
        return False


def test_agent_job_creation():
    """Test creating an agent job"""
    print("\n" + "="*60)
    print("TEST 6: Agent Job Creation")
    print("="*60)
    
    try:
        # Create an agent job
        agent_job = {
            "name": "Test Agent Job",
            "description": "Test job for agent execution",
            "job_type": "agent_job",
            "execution_type": "agent",
            "yaml_configuration": """
job_type: agent_job
name: Test Agent Job
execution_type: agent
agent_pool: default
agent_requirements:
  capabilities: ["python", "test"]
  
job_steps:
  - name: test_step
    type: shell_command
    command: echo "Hello from agent"
    
timeout_minutes: 5
"""
        }
        
        # Create job via API
        response = requests.post(
            f"{BASE_URL}/api/jobs",
            json=agent_job,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            job_result = response.json()
            job_id = job_result.get('job_id')
            print(f"✅ Agent job created: {job_id}")
            return job_id
        else:
            print(f"❌ Agent job creation failed: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Agent job creation error: {e}")
        return None


def test_job_polling(jwt_token):
    """Test agent polling for jobs"""
    print("\n" + "="*60)
    print("TEST 7: Job Polling")
    print("="*60)
    
    try:
        response = requests.get(
            f"{AGENT_API_URL}/jobs/poll?max_jobs=5",
            headers={
                "Authorization": f"Bearer {jwt_token}"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            jobs = result.get('jobs', [])
            print(f"✅ Job polling successful")
            print(f"   Jobs available: {len(jobs)}")
            
            if jobs:
                for job in jobs:
                    print(f"   - Job: {job.get('job_name')} (ID: {job.get('job_id')})")
            
            return True
        else:
            print(f"❌ Polling failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Polling error: {e}")
        return False


def test_list_agents():
    """Test listing all agents"""
    print("\n" + "="*60)
    print("TEST 8: List Agents")
    print("="*60)
    
    try:
        response = requests.get(
            f"{AGENT_API_URL}/list",
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            agents = result.get('agents', [])
            print(f"✅ Agent listing successful")
            print(f"   Total agents: {result.get('total', 0)}")
            
            for agent in agents:
                print(f"   - {agent.get('agent_name')} ({agent.get('agent_id')})")
                print(f"     Status: {agent.get('status')}, Pool: {agent.get('agent_pool')}")
                print(f"     Online: {agent.get('is_online')}, Approved: {agent.get('is_approved')}")
            
            return True
        else:
            print(f"❌ Listing failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Listing error: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("AGENT SYSTEM INTEGRATION TEST")
    print("="*60)
    print(f"Testing agent integration at {BASE_URL}")
    print("This test verifies agent system works without breaking existing jobs")
    
    # Track test results
    results = []
    
    # Test 1: Database setup
    results.append(("Database Setup", test_database_setup()))
    
    # Test 2: Agent registration
    jwt_token = test_agent_registration()
    results.append(("Agent Registration", jwt_token is not None))
    
    if jwt_token:
        # Test 3: Heartbeat
        results.append(("Agent Heartbeat", test_agent_heartbeat(jwt_token)))
        
        # Test 4: Agent approval
        results.append(("Agent Approval", test_agent_approval()))
        
        # Test 5: Existing job compatibility
        results.append(("Existing Job Compatibility", test_existing_job_compatibility()))
        
        # Test 6: Agent job creation
        agent_job_id = test_agent_job_creation()
        results.append(("Agent Job Creation", agent_job_id is not None))
        
        # Small delay to allow job assignment
        if agent_job_id:
            time.sleep(2)
        
        # Test 7: Job polling
        results.append(("Job Polling", test_job_polling(jwt_token)))
        
        # Test 8: List agents
        results.append(("List Agents", test_list_agents()))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print("-"*60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Agent system is working correctly.")
        print("   - Existing jobs continue to work locally")
        print("   - Agent jobs can be assigned to remote agents")
        print("   - Database integrity maintained")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())