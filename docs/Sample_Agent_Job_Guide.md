# Sample Agent Job Guide

This guide demonstrates how to create your first agent job using the Job Scheduler's agent-based execution system.

## 1. Sample Job Overview

I've created a comprehensive sample agent job (`sample_agent_job.yaml`) that demonstrates:

- **Multi-step execution** with different action types
- **Environment variable usage** 
- **Data processing workflow**
- **Cross-platform compatibility**
- **Error handling and timeouts**
- **File operations and reporting**

## 2. How to Create and Run the Sample Job

### Step 1: Access the Job Creator
1. Open your web browser
2. Navigate to: `http://your-master-server:5000/jobs/create`
3. Select **"Agent Job"** (third option with server icon)

### Step 2: Configure Basic Settings
```yaml
Job Name: Sample System Check and Data Processing
Description: Comprehensive agent job demonstrating multiple capabilities
Agent Pool: default (or your preferred pool)
Execution Strategy: Default Pool
Timeout: 1800 seconds (30 minutes)
```

### Step 3: YAML Configuration
Copy the contents of `sample_agent_job.yaml` into the YAML editor in the web interface.

### Step 4: Execute the Job
1. Click "Create and Run Job" or "Submit Job"
2. Monitor execution through the web interface
3. Check agent logs for detailed output

## 3. What the Sample Job Does

### Step 1: Environment Setup
- Displays job context information (Agent ID, Job ID, etc.)
- Creates working directories
- Validates environment

### Step 2: System Information Gathering (Python)
- Collects system specs (CPU, memory, platform)
- Gathers agent information
- Saves data to JSON file

### Step 3: Sample Data Creation (Python)
- Generates realistic sales dataset using pandas
- Creates CSV file with 249 days of data
- Includes categories, regions, and revenue calculations

### Step 4: Data Analysis (Python)
- Loads and analyzes the generated data
- Calculates summary statistics
- Groups data by category and region
- Saves analysis results to JSON

### Step 5: Report Generation (Shell)
- Creates comprehensive execution report
- Lists all generated files
- Summarizes results

### Step 6: Windows-Specific Checks (PowerShell)
- Runs only on Windows agents
- Gathers Windows system information
- Creates PowerShell-specific report
- Uses `continue_on_error: true` for cross-platform compatibility

### Step 7: Cleanup and Summary
- Removes temporary files
- Provides final execution summary
- Lists all created files and statistics

## 4. Expected Output Files

After successful execution, the job creates:

```
./data/input/
  └── sales_data.csv          # Generated sample dataset

./data/output/
  ├── system_info.json        # System information
  ├── analysis_results.json   # Data analysis results  
  ├── execution_report.txt    # Comprehensive report
  └── powershell_report.json  # Windows-specific info (if Windows)

./logs/                       # Log directory (created but may be empty)
```

## 5. Environment Variables Available

Your YAML jobs automatically have access to these variables:

- `$AGENT_ID` - Unique agent identifier
- `$JOB_ID` - Current job identifier  
- `$JOB_NAME` - Human-readable job name
- `$AGENT_POOL` - Agent pool assignment
- `$AGENT_HOSTNAME` - Agent machine hostname
- `$JOB_RUN_DATE` - Job execution timestamp

## 6. Customizing the Sample Job

### Change Agent Pool
```yaml
# In the web interface, select different pool:
Agent Pool: production  # Instead of default
```

### Add Database Operations
```yaml
steps:
  - name: Database Query
    action: sql
    connection: your_connection_name
    query: |
      SELECT COUNT(*) as record_count 
      FROM your_table 
      WHERE created_date >= DATEADD(day, -7, GETDATE())
    timeout: 120
```

### Add HTTP Requests
```yaml
steps:
  - name: API Call
    action: python
    script: |
      import requests
      import json
      
      response = requests.get('https://api.example.com/data')
      print(f"API Response: {response.status_code}")
      
      with open('./data/output/api_response.json', 'w') as f:
          json.dump(response.json(), f, indent=2)
    timeout: 60
```

## 7. Multi-Configuration Example

To run the same job with different configurations:

```yaml
# Create multiple configurations in the web interface:
Configuration 1:
  Environment: development
  DataSize: small
  
Configuration 2:  
  Environment: production
  DataSize: large

# Then reference in your YAML:
steps:
  - name: Environment-Specific Processing
    action: python
    script: |
      import os
      env = os.environ.get('CONFIG_ENVIRONMENT', 'default')
      size = os.environ.get('CONFIG_DATASIZE', 'medium')
      
      print(f"Running in {env} environment with {size} dataset")
```

## 8. Monitoring and Logs

### Agent Logs
```bash
# On the agent machine:
tail -f agent_YOUR-AGENT-ID.log
```

### Master Server Logs
```bash  
# Check web interface at:
http://your-master-server:5000/logs

# Or check file directly:
tail -f logs/scheduler.log
```

## 9. Troubleshooting

### Common Issues:

**Job doesn't start:**
- Verify agent is online and registered
- Check agent capabilities match job requirements
- Ensure agent pool is correct

**Python steps fail:**
- Verify required packages are installed on agent
- Check Python path and permissions
- Review timeout settings

**File operations fail:**
- Check directory permissions
- Verify disk space availability  
- Ensure working directory exists

**PowerShell steps fail:**
- Verify execution policy allows scripts
- Check if running on Windows
- Use `continue_on_error: true` for optional steps

## 10. Next Steps

1. **Run the sample job** to understand the execution flow
2. **Modify the YAML** to match your specific requirements
3. **Create custom job types** for your business logic
4. **Set up multiple agents** for distributed processing
5. **Implement monitoring** for production workloads

## 11. Advanced Features

### Conditional Execution
```yaml
steps:
  - name: Production Only Task
    action: shell
    command: echo "Running production deployment"
    condition: "$AGENT_POOL == 'production'"
```

### Error Handling
```yaml
steps:
  - name: Risky Operation
    action: shell
    command: some-command-that-might-fail
    timeout: 300
    continue_on_error: true
    
  - name: Cleanup After Failure
    action: shell  
    command: cleanup-script.sh
    condition: "previous_step.failed"
```

This sample job provides a comprehensive foundation for understanding agent-based job execution. Customize it based on your specific requirements and gradually add more complex logic as needed.