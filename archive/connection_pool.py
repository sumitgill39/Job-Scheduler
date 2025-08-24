"""
Singleton Connection Pool Manager for Database Connections
"""

from database.connection_manager import DatabaseConnectionManager
from utils.logger import get_logger
import threading
import time


class ConnectionPool:
    """Singleton connection pool manager"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ConnectionPool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.logger = get_logger("database.connection_pool")
            self.db_manager = DatabaseConnectionManager()
            self._cleanup_thread = None
            self._stop_cleanup = False
            self._start_cleanup_thread()
            self._initialized = True
            self.logger.info("[POOL_SINGLETON] Connection pool singleton initialized")
    
    def get_connection(self, connection_name: str = "system"):
        """Get connection from the singleton pool"""
        return self.db_manager.get_connection(connection_name)
    
    def get_pool_stats(self):
        """Get pool statistics"""
        return self.db_manager.get_pool_stats()
    
    def cleanup_pool(self):
        """Manually trigger pool cleanup"""
        return self.db_manager.cleanup_pool()
    
    def _start_cleanup_thread(self):
        """Start background cleanup thread"""
        def cleanup_worker():
            while not self._stop_cleanup:
                try:
                    self.db_manager.cleanup_pool()
                    time.sleep(1800)  # Clean up every 30 minutes (more conservative)
                except Exception as e:
                    self.logger.error(f"[POOL_SINGLETON] Cleanup thread error: {e}")
                    time.sleep(300)  # Wait 5 minutes before retrying
        
        self._cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        self.logger.info("[POOL_SINGLETON] Started cleanup thread")
    
    def shutdown(self):
        """Shutdown the connection pool"""
        self._stop_cleanup = True
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
        self.db_manager.close_all_connections()
        self.logger.info("[POOL_SINGLETON] Connection pool shutdown completed")


# Global instance getter
def get_connection_pool() -> ConnectionPool:
    """Get the global connection pool instance"""
    return ConnectionPool()