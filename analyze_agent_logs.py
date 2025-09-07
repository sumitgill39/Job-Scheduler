"""
Agent Log Analyzer
Analyzes logs/scheduler.log for agent system activities and statistics
"""

import re
import sys
from datetime import datetime, timedelta
from collections import defaultdict, Counter

def analyze_agent_logs(log_file="logs/scheduler.log", hours_back=24):
    """Analyze agent logs for the last N hours"""
    
    print("="*60)
    print("AGENT SYSTEM LOG ANALYSIS")
    print("="*60)
    print(f"Analyzing: {log_file}")
    print(f"Time range: Last {hours_back} hours")
    print("-"*60)
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ Log file not found: {log_file}")
        return False
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        return False
    
    # Calculate time threshold
    cutoff_time = datetime.now() - timedelta(hours=hours_back)
    
    # Counters for different events
    stats = {
        'registrations': 0,
        'heartbeats': 0,
        'job_assignments': 0,
        'job_completions': 0,
        'job_polls': 0,
        'approvals': 0,
        'errors': 0,
        'agents': set(),
        'jobs': set()
    }
    
    # Agent-specific counters
    agent_stats = defaultdict(lambda: {
        'heartbeats': 0,
        'jobs_assigned': 0,
        'jobs_completed': 0,
        'last_seen': None
    })
    
    recent_events = []
    
    # Analyze each line
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line contains agent-related information
        if not re.search(r'AGENT|agent_api|AgentAPI|AgentJobHandler', line, re.IGNORECASE):
            continue
        
        # Try to parse timestamp
        timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            try:
                log_time = datetime.strptime(timestamp_match.group(1), '%Y-%m-%d %H:%M:%S')
                if log_time < cutoff_time:
                    continue  # Skip old entries
            except ValueError:
                pass  # If we can't parse timestamp, include the line anyway
        
        # Count different types of events
        if 'AGENT_REGISTRATION' in line:
            stats['registrations'] += 1
            agent_match = re.search(r'Agent: (\S+)', line)
            if agent_match:
                agent_id = agent_match.group(1)
                stats['agents'].add(agent_id)
                
        elif 'AGENT_HEARTBEAT' in line:
            stats['heartbeats'] += 1
            agent_match = re.search(r'Agent: (\S+)', line)
            if agent_match:
                agent_id = agent_match.group(1)
                stats['agents'].add(agent_id)
                agent_stats[agent_id]['heartbeats'] += 1
                agent_stats[agent_id]['last_seen'] = log_time if timestamp_match else datetime.now()
                
        elif 'JOB_ASSIGNMENT' in line:
            stats['job_assignments'] += 1
            job_match = re.search(r'Job (\S+) assigned to agent (\S+)', line)
            if job_match:
                job_id, agent_id = job_match.groups()
                stats['jobs'].add(job_id)
                stats['agents'].add(agent_id)
                agent_stats[agent_id]['jobs_assigned'] += 1
                
        elif 'JOB_COMPLETION' in line:
            stats['job_completions'] += 1
            execution_match = re.search(r'Execution (\S+) completed', line)
            agent_match = re.search(r'Agent: (\S+)', line)
            if execution_match and agent_match:
                execution_id = execution_match.group(1)
                agent_id = agent_match.group(1)
                stats['jobs'].add(execution_id)
                stats['agents'].add(agent_id)
                agent_stats[agent_id]['jobs_completed'] += 1
                
        elif 'JOB_POLLING' in line:
            stats['job_polls'] += 1
            
        elif 'AGENT_APPROVAL' in line:
            stats['approvals'] += 1
            
        elif re.search(r'ERROR|AGENT_ERROR', line, re.IGNORECASE):
            stats['errors'] += 1
            
        # Keep track of recent events (last 20)
        recent_events.append(line)
        if len(recent_events) > 20:
            recent_events.pop(0)
    
    # Print statistics
    print(f"📊 AGENT SYSTEM STATISTICS")
    print(f"   Total Agents Seen: {len(stats['agents'])}")
    print(f"   Agent Registrations: {stats['registrations']}")
    print(f"   Agent Heartbeats: {stats['heartbeats']}")
    print(f"   Agent Approvals: {stats['approvals']}")
    print(f"   Job Assignments: {stats['job_assignments']}")
    print(f"   Job Completions: {stats['job_completions']}")
    print(f"   Job Polls: {stats['job_polls']}")
    print(f"   Unique Jobs: {len(stats['jobs'])}")
    print(f"   Errors: {stats['errors']}")
    
    # Print per-agent statistics
    if agent_stats:
        print(f"\n👥 PER-AGENT STATISTICS")
        print("-" * 40)
        for agent_id, data in agent_stats.items():
            print(f"Agent: {agent_id}")
            print(f"  Heartbeats: {data['heartbeats']}")
            print(f"  Jobs Assigned: {data['jobs_assigned']}")
            print(f"  Jobs Completed: {data['jobs_completed']}")
            if data['last_seen']:
                print(f"  Last Seen: {data['last_seen'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    
    # Print recent events
    if recent_events:
        print(f"📋 RECENT AGENT EVENTS")
        print("-" * 40)
        for event in recent_events[-10:]:  # Show last 10 events
            print(f"   {event}")
    
    print("\n" + "="*60)
    
    return True

def monitor_live_logs(log_file="logs/scheduler.log"):
    """Monitor agent logs in real-time (simple version)"""
    
    print("="*60)
    print("LIVE AGENT LOG MONITOR")
    print("="*60)
    print(f"Monitoring: {log_file}")
    print("Press Ctrl+C to stop")
    print("-"*60)
    
    try:
        import time
        
        # Read existing content first
        with open(log_file, 'r', encoding='utf-8') as f:
            f.seek(0, 2)  # Go to end of file
            
        print("🔍 Monitoring for new agent events...")
        
        while True:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                # Check recent lines for agent content
                for line in lines[-5:]:  # Check last 5 lines
                    line = line.strip()
                    if re.search(r'AGENT|agent_api|AgentAPI|AgentJobHandler', line, re.IGNORECASE):
                        timestamp = datetime.now().strftime('%H:%M:%S')
                        print(f"[{timestamp}] {line}")
                        
                time.sleep(2)  # Check every 2 seconds
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error monitoring: {e}")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n👋 Monitoring stopped by user")
    except Exception as e:
        print(f"❌ Error setting up monitoring: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--live":
        monitor_live_logs()
    else:
        # Default: analyze last 24 hours
        hours = 24
        if len(sys.argv) > 1:
            try:
                hours = int(sys.argv[1])
            except ValueError:
                print("Usage: python analyze_agent_logs.py [hours_back] or --live")
                sys.exit(1)
        
        success = analyze_agent_logs(hours_back=hours)
        if not success:
            sys.exit(1)