# Agent System Log Monitor
# Monitors logs/scheduler.log for agent-related activities

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "AGENT SYSTEM LOG MONITOR" -ForegroundColor Yellow
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Monitoring logs/scheduler.log for agent activities..." -ForegroundColor Green
Write-Host "Press Ctrl+C to stop monitoring" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Define colors for different log levels
$colors = @{
    'REGISTRATION' = 'Green'
    'HEARTBEAT' = 'DarkGray'
    'ASSIGNMENT' = 'Yellow'
    'COMPLETION' = 'Cyan'
    'ERROR' = 'Red'
    'WARNING' = 'Magenta'
    'POLLING' = 'Blue'
    'APPROVAL' = 'Green'
    'STATUS' = 'White'
}

# Function to colorize log entries
function Write-ColorizedLog {
    param([string]$LogLine)
    
    $color = 'White'
    foreach ($key in $colors.Keys) {
        if ($LogLine -match $key) {
            $color = $colors[$key]
            break
        }
    }
    
    # Add timestamp prefix
    $timestamp = Get-Date -Format "HH:mm:ss"
    Write-Host "[$timestamp] " -NoNewline -ForegroundColor DarkYellow
    Write-Host $LogLine -ForegroundColor $color
}

try {
    # Monitor the log file for agent-related entries
    Get-Content -Path "logs\scheduler.log" -Wait -Tail 10 | ForEach-Object {
        if ($_ -match "AGENT|agent_api|AgentAPI|AgentJobHandler|JWT|register_agent|heartbeat") {
            Write-ColorizedLog $_
        }
    }
} catch {
    Write-Host "Error monitoring log file: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Make sure logs/scheduler.log exists and is accessible." -ForegroundColor Yellow
}