"""
Factory for creating disconnected database components
"""

import os
from dataclasses import dataclass
from database.disconnected_data_manager import DisconnectedDataManager
from core.disconnected_job_manager import DisconnectedJobManager
from utils.logger import get_logger


@dataclass
class DatabaseConfig:
    """Database configuration from environment variables"""
    db_driver: str
    db_server: str
    db_port: int
    db_database: str
    db_username: str
    db_password: str
    trusted_connection: bool
    connection_timeout: int
    command_timeout: int
    db_encrypt: bool = True
    db_trust_server_certificate: bool = False


def create_database_config() -> DatabaseConfig:
    """Create database configuration from environment variables"""
    return DatabaseConfig(
        db_driver=os.getenv('DB_DRIVER', 'ODBC Driver 17 for SQL Server'),
        db_server=os.getenv('DB_SERVER', 'localhost'),
        db_port=int(os.getenv('DB_PORT', '1433')),
        db_database=os.getenv('DB_DATABASE', 'scheduler_db'),
        db_username=os.getenv('DB_USERNAME', ''),
        db_password=os.getenv('DB_PASSWORD', ''),
        trusted_connection=os.getenv('DB_TRUSTED_CONNECTION', 'false').lower() == 'true',
        connection_timeout=int(os.getenv('DB_CONNECTION_TIMEOUT', '30')),
        command_timeout=int(os.getenv('DB_COMMAND_TIMEOUT', '300')),
        db_encrypt=os.getenv('DB_ENCRYPT', 'true').lower() == 'true',
        db_trust_server_certificate=os.getenv('DB_TRUST_SERVER_CERTIFICATE', 'false').lower() == 'true'
    )


def create_disconnected_components():
    """Create disconnected database components"""
    logger = get_logger("database.factory")
    
    try:
        # Create configuration
        config = create_database_config()
        logger.info("[FACTORY] Creating disconnected database components...")
        
        # Create disconnected data manager
        data_manager = DisconnectedDataManager(config)
        
        # Create disconnected job manager
        job_manager = DisconnectedJobManager(data_manager)
        
        # Create disconnected job executor (uses disconnected data access)
        from core.disconnected_job_executor import DisconnectedJobExecutor
        job_executor = DisconnectedJobExecutor(job_manager, data_manager)
        
        # Create integrated scheduler with disconnected components
        from core.integrated_scheduler import IntegratedScheduler
        components_for_scheduler = {
            'job_manager': job_manager,
            'job_executor': job_executor
        }
        integrated_scheduler = IntegratedScheduler(disconnected_components=components_for_scheduler)
        
        logger.info("[FACTORY] Disconnected components created successfully")
        
        return {
            'data_manager': data_manager,
            'job_manager': job_manager,
            'job_executor': job_executor,
            'integrated_scheduler': integrated_scheduler,
            'config': config
        }
        
    except Exception as e:
        logger.error(f"[FACTORY] Error creating disconnected components: {e}")
        raise


def test_disconnected_connection():
    """Test the disconnected database connection"""
    logger = get_logger("database.test")
    
    try:
        logger.info("[TEST] Testing disconnected database connection...")
        
        components = create_disconnected_components()
        data_manager = components['data_manager']
        
        # Test basic connectivity
        result = data_manager.execute_scalar("SELECT 1 as test_value")
        
        if result == 1:
            logger.info("[TEST] ✅ Disconnected database connection successful!")
            
            # Test dataset filling
            test_queries = {
                'system_info': "SELECT @@VERSION as version, GETDATE() as current_time"
            }
            
            dataset = data_manager.fill_dataset(test_queries, "TestDataSet")
            
            if dataset and dataset.get_table('system_info'):
                system_table = dataset.get_table('system_info')
                if system_table.count() > 0:
                    logger.info(f"[TEST] ✅ Dataset fill successful! Got {system_table.count()} rows")
                    return True
                else:
                    logger.error("[TEST] ❌ Dataset fill returned no rows")
                    return False
            else:
                logger.error("[TEST] ❌ Dataset fill failed")
                return False
        else:
            logger.error(f"[TEST] ❌ Connection test failed, expected 1 got {result}")
            return False
            
    except Exception as e:
        logger.error(f"[TEST] ❌ Connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test the disconnected connection when run directly
    test_disconnected_connection()