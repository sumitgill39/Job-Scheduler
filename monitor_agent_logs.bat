@echo off
echo ============================================
echo AGENT SYSTEM LOG MONITOR
echo ============================================
echo Monitoring logs/scheduler.log for agent activities...
echo Press Ctrl+C to stop monitoring
echo ============================================
echo.

REM Monitor all agent-related log entries
powershell -Command "Get-Content -Path 'logs\scheduler.log' -Wait -Tail 20 | Where-Object { $_ -match 'AGENT|agent_api|AgentAPI|AgentJobHandler' }"