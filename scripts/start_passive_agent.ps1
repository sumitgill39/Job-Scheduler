# Passive Agent Startup Script for Windows PowerShell
# This script starts the passive agent and registers it with the Job Scheduler

param(
    [string]$SchedulerUrl = "http://127.0.0.1:5000",
    [string]$AgentId = "passive-agent-$env:COMPUTERNAME",
    [string]$AgentName = "Passive Agent - $env:COMPUTERNAME",
    [string]$AgentPool = "default",
    [int]$AgentPort = 8080,
    [int]$HeartbeatInterval = 30,
    [string]$LogLevel = "INFO",
    [string]$WorkDir = "",
    [switch]$InstallService,
    [switch]$Help
)

# Show help
if ($Help) {
    Write-Host @"
Passive Agent Startup Script

Parameters:
  -SchedulerUrl        URL of the Job Scheduler (default: http://127.0.0.1:5000)
  -AgentId            Unique agent identifier (default: passive-agent-COMPUTERNAME)
  -AgentName          Human-readable agent name (default: Passive Agent - COMPUTERNAME)
  -AgentPool          Agent pool assignment (default: default)
  -AgentPort          Port for agent HTTP server (default: 8080)
  -HeartbeatInterval  Heartbeat interval in seconds (default: 30)
  -LogLevel           Logging level (default: INFO)
  -WorkDir            Base working directory for agent
  -InstallService     Install agent as Windows service
  -Help               Show this help message

Examples:
  .\start_passive_agent.ps1
  .\start_passive_agent.ps1 -SchedulerUrl "http://job-server:5000" -AgentPool "production"
  .\start_passive_agent.ps1 -InstallService
"@
    exit 0
}

# Set default work directory
if ([string]::IsNullOrEmpty($WorkDir)) {
    $WorkDir = Join-Path $PSScriptRoot "..\agent_workspace"
}

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to install Windows service
function Install-PassiveAgentService {
    if (-not (Test-Administrator)) {
        Write-Error "Administrator privileges required to install service. Run as Administrator."
        exit 1
    }
    
    Write-Host "Installing Passive Agent as Windows Service..." -ForegroundColor Yellow
    
    $serviceName = "PassiveJobAgent_$AgentId"
    $serviceDisplayName = "Passive Job Agent - $AgentName"
    $pythonPath = (Get-Command python).Source
    $scriptPath = Join-Path $PSScriptRoot "..\docs\PassiveAgentSetup.py"
    
    $serviceArgs = @(
        $scriptPath,
        "--scheduler-url", $SchedulerUrl,
        "--agent-id", $AgentId,
        "--agent-name", $AgentName,
        "--agent-pool", $AgentPool,
        "--agent-port", $AgentPort,
        "--heartbeat-interval", $HeartbeatInterval,
        "--log-level", $LogLevel,
        "--work-dir", $WorkDir
    )
    
    $serviceCommand = "`"$pythonPath`" " + ($serviceArgs -join " ")
    
    try {
        # Remove existing service if it exists
        $existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
        if ($existingService) {
            Write-Host "Removing existing service..." -ForegroundColor Yellow
            Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
            & sc.exe delete $serviceName
            Start-Sleep -Seconds 2
        }
        
        # Create new service
        & sc.exe create $serviceName binPath= $serviceCommand DisplayName= $serviceDisplayName start= auto
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Service installed successfully: $serviceName" -ForegroundColor Green
            Write-Host "Starting service..." -ForegroundColor Yellow
            Start-Service -Name $serviceName
            Write-Host "Service started successfully!" -ForegroundColor Green
            
            # Show service status
            Get-Service -Name $serviceName | Format-Table -AutoSize
        } else {
            Write-Error "Failed to install service"
            exit 1
        }
    } catch {
        Write-Error "Error installing service: $_"
        exit 1
    }
}

# Main execution
try {
    Write-Host "`n====================================" -ForegroundColor Cyan
    Write-Host " Passive Agent Configuration" -ForegroundColor Cyan
    Write-Host "====================================" -ForegroundColor Cyan
    Write-Host "Scheduler URL: $SchedulerUrl"
    Write-Host "Agent ID: $AgentId"
    Write-Host "Agent Name: $AgentName"
    Write-Host "Agent Pool: $AgentPool"
    Write-Host "Agent Port: $AgentPort"
    Write-Host "Work Directory: $WorkDir"
    Write-Host "Log Level: $LogLevel"
    Write-Host "====================================" -ForegroundColor Cyan
    
    # Check if Python is available
    Write-Host "`nChecking Python installation..." -ForegroundColor Yellow
    try {
        $pythonVersion = & python --version 2>&1
        Write-Host "Found: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Error "Python is not installed or not in PATH. Please install Python 3.7 or higher."
        exit 1
    }
    
    # Check required packages
    Write-Host "Checking required Python packages..." -ForegroundColor Yellow
    $requiredPackages = @("requests", "pyyaml", "psutil", "flask")
    $missingPackages = @()
    
    foreach ($package in $requiredPackages) {
        try {
            & python -c "import $package" 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ $package" -ForegroundColor Green
            } else {
                $missingPackages += $package
                Write-Host "  ✗ $package (missing)" -ForegroundColor Red
            }
        } catch {
            $missingPackages += $package
            Write-Host "  ✗ $package (missing)" -ForegroundColor Red
        }
    }
    
    # Install missing packages
    if ($missingPackages.Count -gt 0) {
        Write-Host "`nInstalling missing packages..." -ForegroundColor Yellow
        $packagesString = $missingPackages -join " "
        & pip install $packagesString
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install required packages: $packagesString"
            exit 1
        }
        Write-Host "Packages installed successfully!" -ForegroundColor Green
    }
    
    # Create work directory
    if (-not (Test-Path $WorkDir)) {
        New-Item -ItemType Directory -Path $WorkDir -Force | Out-Null
        Write-Host "Created work directory: $WorkDir" -ForegroundColor Green
    }
    
    # Install as service if requested
    if ($InstallService) {
        Install-PassiveAgentService
        exit 0
    }
    
    # Start the passive agent
    Write-Host "`nStarting Passive Agent..." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to stop the agent" -ForegroundColor Gray
    
    $scriptPath = Join-Path $PSScriptRoot "..\docs\PassiveAgentSetup.py"
    
    & python $scriptPath `
        --scheduler-url $SchedulerUrl `
        --agent-id $AgentId `
        --agent-name $AgentName `
        --agent-pool $AgentPool `
        --agent-port $AgentPort `
        --heartbeat-interval $HeartbeatInterval `
        --log-level $LogLevel `
        --work-dir $WorkDir

} catch {
    Write-Error "Error starting passive agent: $_"
    exit 1
} finally {
    Write-Host "`nPassive Agent has stopped." -ForegroundColor Yellow
    Read-Host "Press Enter to continue"
}