"""
Simple test to verify agent logging works
"""

# Test basic agent logger functionality
try:
    from utils.agent_logger import agent_logger
    print("✅ Agent logger imported successfully")
    
    # Test logging methods
    agent_logger.log_agent_registration(
        agent_id='test-001',
        agent_data={
            'hostname': 'test-host',
            'ip_address': '127.0.0.1',
            'agent_pool': 'default'
        },
        status='created'
    )
    
    agent_logger.log_system_stats(
        total_agents=1,
        online_agents=1, 
        total_pools=1,
        queued_jobs=0
    )
    
    print("✅ Agent logging test completed - check logs/scheduler.log")
    
except Exception as e:
    print(f"❌ Agent logging test failed: {e}")
    import traceback
    traceback.print_exc()