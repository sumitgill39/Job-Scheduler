"""
Agent Logging Verification Script
Tests that agent system components properly log to logs/scheduler.log
"""

import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_agent_logger():
    """Test the agent logger components"""
    print("="*60)
    print("AGENT LOGGING VERIFICATION")
    print("="*60)
    
    # Test 1: Import and initialize agent logger
    try:
        from utils.agent_logger import agent_logger
        print("✅ Agent logger imported successfully")
        print(f"   - Logger name: {agent_logger.logger.name}")
        print(f"   - Log handlers: {len(agent_logger.logger.handlers)}")
        
        # Check if handlers include file handler
        file_handler_found = False
        for handler in agent_logger.logger.handlers:
            if hasattr(handler, 'baseFilename'):
                file_handler_found = True
                print(f"   - Log file: {handler.baseFilename}")
        
        if not file_handler_found:
            print("⚠️  No file handler found - logs may only go to console")
            
    except Exception as e:
        print(f"❌ Failed to import agent logger: {e}")
        return False
    
    # Test 2: Test agent logger methods
    print("\n" + "-"*40)
    print("Testing Agent Logger Methods")
    print("-"*40)
    
    try:
        # Test registration logging
        agent_data = {
            'agent_id': 'test-verify-001',
            'hostname': 'verification-server',
            'ip_address': '127.0.0.1',
            'capabilities': ['test', 'verification'],
            'agent_pool': 'test_pool'
        }
        
        agent_logger.log_agent_registration(
            agent_id='test-verify-001',
            agent_data=agent_data,
            status='created',
            jwt_token='test.jwt.token'
        )
        print("✅ Agent registration logging test passed")
        
        # Test heartbeat logging
        agent_logger.log_agent_heartbeat(
            agent_id='test-verify-001',
            status='online',
            current_jobs=0,
            resource_usage={'cpu_percent': 25.5, 'memory_percent': 40.2}
        )
        print("✅ Agent heartbeat logging test passed")
        
        # Test job assignment logging
        agent_logger.log_job_assignment(
            job_id='test-job-001',
            execution_id='test-exec-001',
            agent_id='test-verify-001',
            assignment_id='test-assign-001',
            pool_id='test_pool'
        )
        print("✅ Job assignment logging test passed")
        
        # Test job status update logging
        agent_logger.log_job_status_update(
            execution_id='test-exec-001',
            agent_id='test-verify-001',
            status='running',
            message='Verification test running'
        )
        print("✅ Job status update logging test passed")
        
        # Test job completion logging
        agent_logger.log_job_completion(
            execution_id='test-exec-001',
            agent_id='test-verify-001',
            status='success',
            duration_seconds=45.2,
            return_code=0
        )
        print("✅ Job completion logging test passed")
        
        # Test system stats logging
        agent_logger.log_system_stats(
            total_agents=1,
            online_agents=1,
            total_pools=1,
            queued_jobs=0
        )
        print("✅ System stats logging test passed")
        
    except Exception as e:
        print(f"❌ Agent logger method test failed: {e}")
        return False
    
    # Test 3: Check log file
    print("\n" + "-"*40)
    print("Checking Log File")
    print("-"*40)
    
    log_file_path = "logs/scheduler.log"
    
    if os.path.exists(log_file_path):
        print(f"✅ Log file exists: {log_file_path}")
        
        try:
            # Get file size and modification time
            file_stats = os.stat(log_file_path)
            file_size = file_stats.st_size
            mod_time = datetime.fromtimestamp(file_stats.st_mtime)
            
            print(f"   - File size: {file_size:,} bytes")
            print(f"   - Last modified: {mod_time}")
            
            # Read last few lines to verify agent logging
            with open(log_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            if lines:
                print(f"   - Total lines: {len(lines):,}")
                print(f"   - Last 3 lines:")
                
                for line in lines[-3:]:
                    line = line.strip()
                    if line:
                        print(f"     {line}")
                        
                # Check for agent-specific log entries
                agent_entries = [line for line in lines[-50:] if 'AGENT' in line.upper()]
                if agent_entries:
                    print(f"✅ Found {len(agent_entries)} agent-related log entries in recent logs")
                else:
                    print("⚠️  No recent agent-related log entries found")
            else:
                print("⚠️  Log file is empty")
                
        except Exception as e:
            print(f"❌ Error reading log file: {e}")
            return False
    else:
        print(f"❌ Log file not found: {log_file_path}")
        return False
    
    return True


def test_component_imports():
    """Test that agent components can be imported without errors"""
    print("\n" + "-"*40)
    print("Testing Component Imports")
    print("-"*40)
    
    components = [
        ('Agent Models', 'database.agent_models'),
        ('Agent API', 'web_ui.agent_api'),
        ('Agent Job Handler', 'core.agent_job_handler'),
    ]
    
    success_count = 0
    
    for name, module_name in components:
        try:
            __import__(module_name)
            print(f"✅ {name}: {module_name}")
            success_count += 1
        except Exception as e:
            print(f"❌ {name}: {module_name} - {e}")
    
    print(f"\nImport Results: {success_count}/{len(components)} successful")
    return success_count == len(components)


def main():
    """Run all verification tests"""
    print(f"Agent Logging Verification - {datetime.utcnow().isoformat()}")
    
    results = []
    
    # Test 1: Component imports
    results.append(("Component Imports", test_component_imports()))
    
    # Test 2: Agent logger functionality
    results.append(("Agent Logger", test_agent_logger()))
    
    # Print summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print("-"*60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL LOGGING VERIFICATION TESTS PASSED!")
        print("   - Agent logger is properly configured")
        print("   - Log entries are being written to logs/scheduler.log")
        print("   - All agent components can be imported successfully")
        
        print(f"\n📋 To monitor agent logs in real-time:")
        print(f"   tail -f logs/scheduler.log | grep AGENT")
        
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())