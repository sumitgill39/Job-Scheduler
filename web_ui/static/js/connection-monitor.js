/**
 * Background Connection Monitor
 * Efficiently monitors database connectivity without blocking UI
 */

class ConnectionMonitor {
    constructor() {
        this.statusCache = new Map();
        this.lastCheck = null;
        this.checkInterval = 30 * 1000; // 30 seconds
        this.isRunning = false;
        this.healthCheckUrl = '/api/system/database-status';
    }

    /**
     * Start background monitoring (only if not already running)
     */
    start() {
        if (this.isRunning) {
            return;
        }
        
        this.isRunning = true;
        console.log('[ConnectionMonitor] Starting background connection monitoring');
        
        // Check immediately if cache is empty
        if (!this.lastCheck) {
            this.performHealthCheck();
        }
        
        // Schedule periodic checks
        this.intervalId = setInterval(() => {
            this.performHealthCheck();
        }, this.checkInterval);
    }

    /**
     * Stop background monitoring
     */
    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
        this.isRunning = false;
        console.log('[ConnectionMonitor] Stopped background connection monitoring');
    }

    /**
     * Perform lightweight health check
     */
    async performHealthCheck() {
        try {
            console.log('[ConnectionMonitor] Performing background health check...');
            
            const response = await fetch(this.healthCheckUrl, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const data = await response.json();
            
            // Update cache
            this.statusCache.set('system_database', {
                status: data.success ? 'connected' : 'disconnected',
                timestamp: Date.now(),
                details: data
            });
            
            this.lastCheck = Date.now();
            
            // Update UI elements if they exist (but don't force check)
            this.updateUIElements(data);
            
            console.log(`[ConnectionMonitor] Health check completed: ${data.success ? 'CONNECTED' : 'DISCONNECTED'}`);
            
        } catch (error) {
            console.warn('[ConnectionMonitor] Background health check failed:', error);
            
            // Update cache with error state
            this.statusCache.set('system_database', {
                status: 'error',
                timestamp: Date.now(),
                error: error.message
            });
            
            this.lastCheck = Date.now();
        }
    }

    /**
     * Update UI elements with cached status (non-blocking)
     */
    updateUIElements(data) {
        // Update database status badge in header
        const statusElement = document.getElementById('database-status');
        if (statusElement) {
            if (data.success) {
                statusElement.className = 'badge bg-success';
                statusElement.textContent = 'Connected';
                statusElement.title = `Database: ${data.database} | Server: ${data.server}`;
            } else {
                statusElement.className = 'badge bg-danger';
                statusElement.textContent = 'Disconnected';
                statusElement.title = data.error || 'Database connection failed';
            }
        }

        // Update system database status on connections page
        const systemDbStatus = document.getElementById('system-db-status');
        if (systemDbStatus) {
            if (data.success) {
                systemDbStatus.className = 'badge bg-success ms-2';
                systemDbStatus.innerHTML = '<i class="fas fa-check me-1"></i>Connected';
            } else {
                systemDbStatus.className = 'badge bg-danger ms-2';
                systemDbStatus.innerHTML = '<i class="fas fa-times me-1"></i>Disconnected';
            }
        }
    }

    /**
     * Get cached status (immediate response)
     */
    getCachedStatus(connectionName = 'system_database') {
        const cached = this.statusCache.get(connectionName);
        if (!cached) {
            return { status: 'unknown', timestamp: null };
        }

        const age = Date.now() - cached.timestamp;
        const isStale = age > this.checkInterval;

        return {
            ...cached,
            age: age,
            isStale: isStale
        };
    }

    /**
     * Force immediate check (for user-triggered actions)
     */
    async forceCheck() {
        console.log('[ConnectionMonitor] Force checking connection status...');
        await this.performHealthCheck();
        return this.getCachedStatus();
    }

    /**
     * Check if monitoring should be active based on current page
     */
    shouldMonitor() {
        const path = window.location.pathname;
        
        // Always monitor on these pages
        const monitorPages = ['/connections', '/jobs/create', '/jobs'];
        if (monitorPages.some(page => path.startsWith(page))) {
            return true;
        }

        // Monitor on dashboard but less frequently
        if (path === '/' || path === '/dashboard') {
            return true;
        }

        return false;
    }
}

// Global connection monitor instance
window.connectionMonitor = new ConnectionMonitor();

// Auto-start monitoring based on page context
document.addEventListener('DOMContentLoaded', function() {
    if (window.connectionMonitor.shouldMonitor()) {
        // Delay start to avoid blocking page load
        setTimeout(() => {
            window.connectionMonitor.start();
        }, 1000);
    }

    // Make database status clickable for manual refresh
    const statusElement = document.getElementById('database-status');
    if (statusElement) {
        statusElement.style.cursor = 'pointer';
        statusElement.onclick = function() {
            statusElement.textContent = 'Checking...';
            statusElement.className = 'badge bg-secondary';
            
            window.connectionMonitor.forceCheck().then(() => {
                console.log('Manual connection check completed');
            });
        };
    }
});

// Stop monitoring when page unloads
window.addEventListener('beforeunload', function() {
    if (window.connectionMonitor) {
        window.connectionMonitor.stop();
    }
});

// Export for use in other scripts
window.ConnectionMonitor = ConnectionMonitor;