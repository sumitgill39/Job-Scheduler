# Passive Agent Installation and Deployment Script
# This script helps deploy the passive agent to remote machines

param(
    [string]$RemoteComputer = "",
    [string]$SchedulerUrl = "http://127.0.0.1:5000",
    [string]$AgentPool = "default",
    [string]$SourcePath = "",
    [string]$DestinationPath = "C:\JobSchedulerAgent",
    [PSCredential]$Credential,
    [switch]$InstallService,
    [switch]$LocalInstall,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
Passive Agent Installation Script

This script helps deploy the passive agent to local or remote machines.

Parameters:
  -RemoteComputer     Target computer name or IP address
  -SchedulerUrl       URL of the Job Scheduler (default: http://127.0.0.1:5000)
  -AgentPool          Agent pool assignment (default: default)
  -SourcePath         Source path containing agent files (auto-detected if empty)
  -DestinationPath    Destination path on target machine (default: C:\JobSchedulerAgent)
  -Credential         Credentials for remote access (will prompt if needed)
  -InstallService     Install agent as Windows service after deployment
  -LocalInstall       Install on local machine
  -Help               Show this help message

Examples:
  # Install locally
  .\install_passive_agent.ps1 -LocalInstall

  # Deploy to remote machine
  .\install_passive_agent.ps1 -RemoteComputer "SERVER01" -SchedulerUrl "http://job-server:5000"

  # Deploy and install as service
  .\install_passive_agent.ps1 -RemoteComputer "SERVER01" -InstallService
"@
    exit 0
}

# Auto-detect source path if not provided
if ([string]::IsNullOrEmpty($SourcePath)) {
    $SourcePath = Split-Path $PSScriptRoot -Parent
}

# Validate source path
if (-not (Test-Path $SourcePath)) {
    Write-Error "Source path not found: $SourcePath"
    exit 1
}

# Function to copy files to destination
function Copy-AgentFiles {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Computer = "localhost",
        [PSCredential]$Cred = $null
    )
    
    Write-Host "Copying agent files..." -ForegroundColor Yellow
    
    $filesToCopy = @(
        "docs\PassiveAgentSetup.py",
        "scripts\start_passive_agent.ps1",
        "scripts\start_passive_agent.bat"
    )
    
    if ($Computer -eq "localhost" -or [string]::IsNullOrEmpty($Computer)) {
        # Local installation
        if (-not (Test-Path $Destination)) {
            New-Item -ItemType Directory -Path $Destination -Force | Out-Null
        }
        
        foreach ($file in $filesToCopy) {
            $sourcePath = Join-Path $Source $file
            if (Test-Path $sourcePath) {
                $destDir = Join-Path $Destination (Split-Path $file -Parent)
                if (-not (Test-Path $destDir)) {
                    New-Item -ItemType Directory -Path $destDir -Force | Out-Null
                }
                Copy-Item -Path $sourcePath -Destination (Join-Path $Destination $file) -Force
                Write-Host "  ✓ Copied: $file" -ForegroundColor Green
            } else {
                Write-Warning "File not found: $sourcePath"
            }
        }
    } else {
        # Remote installation
        $session = $null
        try {
            if ($Cred) {
                $session = New-PSSession -ComputerName $Computer -Credential $Cred -ErrorAction Stop
            } else {
                $session = New-PSSession -ComputerName $Computer -ErrorAction Stop
            }
            
            # Create destination directory
            Invoke-Command -Session $session -ScriptBlock {
                param($dest)
                if (-not (Test-Path $dest)) {
                    New-Item -ItemType Directory -Path $dest -Force | Out-Null
                }
            } -ArgumentList $Destination
            
            # Copy files
            foreach ($file in $filesToCopy) {
                $sourcePath = Join-Path $Source $file
                if (Test-Path $sourcePath) {
                    $destPath = Join-Path $Destination $file
                    $destDir = Split-Path $destPath -Parent
                    
                    # Create directory structure on remote machine
                    Invoke-Command -Session $session -ScriptBlock {
                        param($dir)
                        if (-not (Test-Path $dir)) {
                            New-Item -ItemType Directory -Path $dir -Force | Out-Null
                        }
                    } -ArgumentList $destDir
                    
                    # Copy file
                    Copy-Item -Path $sourcePath -Destination $destPath -ToSession $session -Force
                    Write-Host "  ✓ Copied: $file" -ForegroundColor Green
                } else {
                    Write-Warning "File not found: $sourcePath"
                }
            }
            
        } catch {
            Write-Error "Failed to connect to remote computer: $_"
            return $false
        } finally {
            if ($session) {
                Remove-PSSession -Session $session
            }
        }
    }
    
    return $true
}

# Function to install agent on target machine
function Install-Agent {
    param(
        [string]$Computer = "localhost",
        [string]$InstallPath,
        [string]$SchedulerUrl,
        [string]$AgentPool,
        [bool]$AsService,
        [PSCredential]$Cred = $null
    )
    
    Write-Host "Installing passive agent..." -ForegroundColor Yellow
    
    $agentId = "passive-agent-$Computer"
    $agentName = "Passive Agent - $Computer"
    
    $installScript = @"
# Change to agent directory
Set-Location '$InstallPath'

# Install required packages
Write-Host 'Installing required Python packages...'
pip install requests pyyaml psutil flask

if (`$LASTEXITCODE -ne 0) {
    Write-Error 'Failed to install required packages'
    exit 1
}

Write-Host 'Python packages installed successfully!'

# Test agent startup
Write-Host 'Testing agent configuration...'
python docs\PassiveAgentSetup.py --help | Out-Null

if (`$LASTEXITCODE -eq 0) {
    Write-Host 'Agent configuration test successful!'
} else {
    Write-Error 'Agent configuration test failed'
    exit 1
}
"@

    if ($AsService) {
        $installScript += @"

# Install as Windows service
Write-Host 'Installing agent as Windows service...'
.\scripts\start_passive_agent.ps1 -SchedulerUrl '$SchedulerUrl' -AgentId '$agentId' -AgentName '$agentName' -AgentPool '$AgentPool' -InstallService

if (`$LASTEXITCODE -eq 0) {
    Write-Host 'Agent service installed and started successfully!'
} else {
    Write-Error 'Failed to install agent service'
    exit 1
}
"@
    } else {
        $installScript += @"

Write-Host 'Agent installed successfully!'
Write-Host 'To start the agent manually, run:'
Write-Host "    .\scripts\start_passive_agent.ps1 -SchedulerUrl '$SchedulerUrl' -AgentId '$agentId' -AgentName '$agentName' -AgentPool '$AgentPool'"
"@
    }
    
    if ($Computer -eq "localhost" -or [string]::IsNullOrEmpty($Computer)) {
        # Local execution
        Invoke-Expression $installScript
    } else {
        # Remote execution
        $session = $null
        try {
            if ($Cred) {
                $session = New-PSSession -ComputerName $Computer -Credential $Cred -ErrorAction Stop
            } else {
                $session = New-PSSession -ComputerName $Computer -ErrorAction Stop
            }
            
            Invoke-Command -Session $session -ScriptBlock ([ScriptBlock]::Create($installScript))
            
        } catch {
            Write-Error "Failed to install on remote computer: $_"
            return $false
        } finally {
            if ($session) {
                Remove-PSSession -Session $session
            }
        }
    }
    
    return $true
}

# Main execution
try {
    Write-Host "`n================================================" -ForegroundColor Cyan
    Write-Host " Passive Agent Installation" -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    
    if ($LocalInstall) {
        $targetComputer = "localhost"
    } elseif ([string]::IsNullOrEmpty($RemoteComputer)) {
        $targetComputer = Read-Host "Enter target computer name or IP address"
        if ([string]::IsNullOrEmpty($targetComputer)) {
            Write-Error "Target computer is required"
            exit 1
        }
    } else {
        $targetComputer = $RemoteComputer
    }
    
    Write-Host "Target Computer: $targetComputer"
    Write-Host "Source Path: $SourcePath"
    Write-Host "Destination Path: $DestinationPath"
    Write-Host "Scheduler URL: $SchedulerUrl"
    Write-Host "Agent Pool: $AgentPool"
    Write-Host "Install as Service: $InstallService"
    Write-Host "================================================" -ForegroundColor Cyan
    
    # Get credentials for remote installation if needed
    if ($targetComputer -ne "localhost" -and -not $Credential) {
        Write-Host "`nRemote installation requires credentials." -ForegroundColor Yellow
        $Credential = Get-Credential -Message "Enter credentials for $targetComputer"
        if (-not $Credential) {
            Write-Error "Credentials are required for remote installation"
            exit 1
        }
    }
    
    # Copy agent files
    Write-Host "`nStep 1: Copying agent files to $targetComputer..." -ForegroundColor Yellow
    $copySuccess = Copy-AgentFiles -Source $SourcePath -Destination $DestinationPath -Computer $targetComputer -Cred $Credential
    
    if (-not $copySuccess) {
        Write-Error "Failed to copy agent files"
        exit 1
    }
    
    # Install agent
    Write-Host "`nStep 2: Installing agent on $targetComputer..." -ForegroundColor Yellow
    $installSuccess = Install-Agent -Computer $targetComputer -InstallPath $DestinationPath -SchedulerUrl $SchedulerUrl -AgentPool $AgentPool -AsService $InstallService -Cred $Credential
    
    if (-not $installSuccess) {
        Write-Error "Failed to install agent"
        exit 1
    }
    
    Write-Host "`n================================================" -ForegroundColor Green
    Write-Host " Installation Complete!" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "Agent installed on: $targetComputer"
    Write-Host "Installation path: $DestinationPath"
    
    if ($InstallService) {
        Write-Host "Agent service: Running"
        Write-Host "`nThe agent is now running as a Windows service and will start automatically on boot."
    } else {
        Write-Host "`nTo start the agent, connect to $targetComputer and run:"
        Write-Host "  cd $DestinationPath"
        Write-Host "  .\scripts\start_passive_agent.ps1"
    }
    
} catch {
    Write-Error "Installation failed: $_"
    exit 1
}