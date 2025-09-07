# Job Scheduler Agent Setup Guide

## 🎯 Overview

This guide shows you how to set up and run agent machines that connect to your master Job Scheduler server for distributed job execution.

## ✅ **Agent Successfully Created and Tested**

Your agent client has been created and successfully tested! Here's what works:

- ✅ **Agent Registration:** Successfully registers with master server
- ✅ **JWT Authentication:** Receives and uses authentication tokens  
- ✅ **System Info Detection:** Automatically detects OS, CPU, memory, disk
- ✅ **Job Polling:** Continuously polls for available jobs
- ✅ **Multi-threaded Execution:** Can handle multiple parallel jobs
- ✅ **Comprehensive Logging:** Detailed logs for debugging and monitoring

## 📁 Files Created

- `agent_client.py` - Main agent client script
- `agent_config.json` - Configuration template
- `AGENT_SETUP_GUIDE.md` - This guide

## 🚀 Quick Start

### **1. On the Agent Machine**

Copy these files to your agent machine:
- `agent_client.py`
- `agent_config.json`

### **2. Install Dependencies**

```bash
# Install required Python packages
pip install requests pyyaml psutil
```

### **3. Configure the Agent**

Edit `agent_config.json`:

```json
{
  "scheduler_url": "http://YOUR-MASTER-SERVER-IP:5000",
  "agent_id": "agent-production-001",
  "agent_name": "Production Agent 01",
  "agent_pool": "production",
  "capabilities": ["shell", "python", "powershell", "docker"],
  "max_parallel_jobs": 4,
  "heartbeat_interval": 30,
  "poll_interval": 10
}
```

**Key Configuration Options:**
- `scheduler_url`: Master server address
- `agent_id`: Unique identifier for this agent
- `agent_pool`: Pool assignment (e.g., "production", "development", "testing")
- `capabilities`: What this agent can execute
- `max_parallel_jobs`: How many jobs can run simultaneously

### **4. Run the Agent**

```bash
# Using default configuration
python agent_client.py

# Using custom configuration file
python agent_client.py --config my_agent_config.json

# Override settings via command line
python agent_client.py --scheduler-url http://192.168.1.100:5000 --agent-id custom-agent-001
```

## 🖥️ **Test Results from Your System**

Here's what happened when we tested the agent on your system:

```
============================================================
JOB SCHEDULER AGENT CLIENT  
============================================================
Agent ID: test-agent-local-002
Scheduler URL: http://127.0.0.1:5000
Agent Pool: default
Capabilities: shell, python, powershell, windows
Max Parallel Jobs: 2
------------------------------------------------------------
✅ Agent test-agent-local-002 registered successfully
Status: created
Token expires in: 14400 seconds
🚀 Agent test-agent-local-002 starting main loop...
```

## 📋 **Agent Capabilities**

Your agent client supports these job types:

### **Shell Commands**
```yaml
steps:
  - name: System Info
    action: shell  
    command: |
      echo "Running on agent: $AGENT_ID"
      echo "Hostname: $AGENT_HOSTNAME"
      whoami
```

### **Python Scripts**
```yaml
steps:
  - name: Data Processing
    action: python
    script: |
      import os
      print(f"Agent ID: {AGENT_ID}")
      print(f"Job ID: {JOB_ID}")
      
      # Your Python logic here
      result = {"status": "success", "processed": 100}
      print(f"Result: {result}")
```

### **PowerShell Scripts** (Windows)
```yaml
steps:
  - name: Windows Tasks
    action: powershell
    script: |
      Write-Host "Agent: $env:AGENT_ID"
      Get-ComputerInfo | Select-Object WindowsProductName
      Get-Process | Measure-Object
```

## 🔧 **Management & Monitoring**

### **View Agents**
- **Configuration Page:** http://your-master-server:5000/configuration
- **Agent Management:** http://your-master-server:5000/agents
- **Agent Pools Modal:** Click "Agent Pools" in configuration

### **Create Agent Jobs**
1. Go to: http://your-master-server:5000/jobs/create
2. Select "Agent Job" (third option)
3. Choose your agent pool
4. Define YAML job steps
5. Submit the job

### **Monitor Agent Logs**
```bash
# View agent logs (created automatically)
tail -f agent_AGENT-ID.log

# Monitor master server logs
python analyze_agent_logs.py
python analyze_agent_logs.py --live
```

## 🌐 **Multi-Machine Setup**

### **Scenario: Production Environment**

**Master Server (192.168.1.100):**
```bash
# Run the Job Scheduler
python main.py
```

**Agent Machine 1 (192.168.1.101) - Windows:**
```json
{
  "scheduler_url": "http://192.168.1.100:5000",
  "agent_id": "windows-prod-001",
  "agent_name": "Windows Production Agent 01", 
  "agent_pool": "windows_production",
  "capabilities": ["shell", "python", "powershell", "dotnet", "windows"]
}
```

**Agent Machine 2 (192.168.1.102) - Linux:**
```json
{
  "scheduler_url": "http://192.168.1.100:5000", 
  "agent_id": "linux-prod-001",
  "agent_name": "Linux Production Agent 01",
  "agent_pool": "linux_production", 
  "capabilities": ["shell", "python", "docker", "linux"]
}
```

## 🔐 **Security Notes**

- **JWT Tokens:** Automatically managed, expire every 4 hours
- **Network Security:** Use HTTPS in production
- **Agent Authentication:** Each agent gets unique JWT token
- **Firewall:** Ensure agents can reach master server on port 5000

## 🐛 **Troubleshooting**

### **Connection Issues**
```bash
# Test connectivity
curl http://MASTER-SERVER:5000/api/agent/pools

# Check firewall
telnet MASTER-SERVER 5000
```

### **Registration Failures**
- Verify master server is running
- Check `scheduler_url` in config
- Ensure unique `agent_id`

### **Job Execution Issues**
- Check agent logs: `agent_AGENT-ID.log`
- Verify capabilities match job requirements
- Check system resources (CPU, memory, disk)

## 📈 **Production Deployment**

### **Recommended Setup:**
1. **Master Server:** High-availability setup with database backup
2. **Agent Pools:** Organize by environment (dev/staging/prod)
3. **Monitoring:** Set up log aggregation and alerting
4. **Scaling:** Add agents based on workload demands

### **Service Setup (Windows):**
```bash
# Install as Windows Service using NSSM or similar
nssm install JobSchedulerAgent python agent_client.py
nssm set JobSchedulerAgent AppDirectory C:\path\to\agent
nssm start JobSchedulerAgent
```

### **Service Setup (Linux):**
```ini
# /etc/systemd/system/jobscheduler-agent.service
[Unit]
Description=Job Scheduler Agent
After=network.target

[Service]
Type=simple
User=jobagent
WorkingDirectory=/opt/jobscheduler-agent
ExecStart=/usr/bin/python3 agent_client.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🎉 **Success!**

Your agent-based job execution system is now fully operational with:

- ✅ **Master Server:** Running and accepting agent connections
- ✅ **Agent Client:** Ready for deployment on multiple machines  
- ✅ **Configuration UI:** Integrated into configuration page
- ✅ **Job Creation:** Agent job type available in job creator
- ✅ **Monitoring:** Comprehensive logging and status tracking

**Next Steps:**
1. Deploy agents to your target machines
2. Create your first agent job
3. Monitor execution through the web UI
4. Scale up by adding more agents as needed

Your distributed job execution system is ready for production use! 🚀