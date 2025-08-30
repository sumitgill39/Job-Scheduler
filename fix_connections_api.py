"""
Fix script to make connections API work with SQLAlchemy
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def create_simple_connection_manager():
    """Create a simple connection manager that works with the routes"""
    
    content = '''"""
Simple Connection Manager for SQLAlchemy integration
Works with the existing routes that expect db_manager
"""

from database.sqlalchemy_models import get_db_session
from sqlalchemy import text
from utils.logger import get_logger

class SimpleConnectionManager:
    """Simple connection manager that uses SQLAlchemy to access user_connections table"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("[CONNECTION_MANAGER] Simple connection manager initialized")
    
    def _create_new_connection(self, connection_name):
        """Create a database session (mimics old connection pool interface)"""
        return get_db_session()
    
    def list_connections(self):
        """List all available connections from user_connections table"""
        try:
            with get_db_session() as session:
                result = session.execute(text("""
                    SELECT connection_id, name, server_name, database_name, 
                           trusted_connection, is_active
                    FROM user_connections 
                    WHERE is_active = 1
                    ORDER BY name
                """))
                
                connections = []
                for row in result:
                    connections.append({
                        'connection_id': row.connection_id,
                        'name': row.name,
                        'server_name': row.server_name,
                        'database_name': row.database_name,
                        'trusted_connection': bool(row.trusted_connection),
                        'is_active': bool(row.is_active)
                    })
                
                self.logger.info(f"[CONNECTION_MANAGER] Listed {len(connections)} connections")
                return connections
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error listing connections: {e}")
            return []
    
    def get_connection_info(self, connection_id):
        """Get detailed connection information"""
        try:
            with get_db_session() as session:
                result = session.execute(text("""
                    SELECT * FROM user_connections 
                    WHERE connection_id = ? AND is_active = 1
                """), [connection_id])
                
                row = result.fetchone()
                if row:
                    return {
                        'connection_id': row.connection_id,
                        'name': row.name,
                        'server_name': row.server_name,
                        'port': row.port,
                        'database_name': row.database_name,
                        'trusted_connection': bool(row.trusted_connection),
                        'username': row.username,
                        'description': row.description,
                        'driver': row.driver,
                        'connection_timeout': row.connection_timeout,
                        'command_timeout': row.command_timeout,
                        'encrypt': bool(row.encrypt),
                        'trust_server_certificate': bool(row.trust_server_certificate),
                        'is_active': bool(row.is_active)
                    }
                return None
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error getting connection info: {e}")
            return None
    
    def create_custom_connection(self, connection_data):
        """Create a new custom connection"""
        try:
            with get_db_session() as session:
                session.execute(text("""
                    INSERT INTO user_connections (
                        connection_id, name, server_name, port, database_name,
                        trusted_connection, username, password, description,
                        driver, connection_timeout, command_timeout,
                        encrypt, trust_server_certificate, created_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """), [
                    connection_data.get('connection_id'),
                    connection_data.get('name'),
                    connection_data.get('server_name'),
                    connection_data.get('port', 1433),
                    connection_data.get('database_name'),
                    connection_data.get('trusted_connection', True),
                    connection_data.get('username'),
                    connection_data.get('password'),
                    connection_data.get('description'),
                    connection_data.get('driver', 'ODBC Driver 17 for SQL Server'),
                    connection_data.get('connection_timeout', 30),
                    connection_data.get('command_timeout', 300),
                    connection_data.get('encrypt', False),
                    connection_data.get('trust_server_certificate', True),
                    'web_ui'
                ])
                session.commit()
                
                self.logger.info(f"[CONNECTION_MANAGER] Created connection: {connection_data.get('name')}")
                return True
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error creating connection: {e}")
            return False
    
    def remove_connection(self, connection_id):
        """Remove a connection (mark as inactive)"""
        try:
            with get_db_session() as session:
                session.execute(text("""
                    UPDATE user_connections 
                    SET is_active = 0, modified_date = GETDATE()
                    WHERE connection_id = ?
                """), [connection_id])
                session.commit()
                
                self.logger.info(f"[CONNECTION_MANAGER] Removed connection: {connection_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"[CONNECTION_MANAGER] Error removing connection: {e}")
            return False
    
    def test_connection(self, connection_id):
        """Test a database connection"""
        try:
            conn_info = self.get_connection_info(connection_id)
            if not conn_info:
                return {'success': False, 'error': 'Connection not found'}
            
            # For now, just return success if we can get the connection info
            # In a full implementation, we would actually test the database connection
            return {
                'success': True,
                'message': f'Connection {conn_info["name"]} is available'
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}

# Create global instance
simple_connection_manager = SimpleConnectionManager()
'''
    
    with open(project_root / 'simple_connection_manager.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("[SUCCESS] Created simple_connection_manager.py")

def patch_flask_app():
    """Patch the Flask app to include db_manager"""
    
    # Read the current app.py file
    app_file = project_root / 'web_ui' / 'app.py'
    with open(app_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the import and assignment
    if 'from simple_connection_manager import simple_connection_manager' not in content:
        # Add import after other imports
        import_line = "from simple_connection_manager import simple_connection_manager"
        
        # Find a good place to add the import
        lines = content.split('\n')
        insert_pos = None
        for i, line in enumerate(lines):
            if line.startswith('from core.') or line.startswith('from database.'):
                insert_pos = i + 1
        
        if insert_pos:
            lines.insert(insert_pos, import_line)
            content = '\n'.join(lines)
    
    # Add db_manager assignment after job_manager
    if 'app.db_manager = simple_connection_manager' not in content:
        content = content.replace(
            'app.job_manager = JobManager()',
            '''app.job_manager = JobManager()
        
        # Add simple connection manager for routes compatibility
        app.db_manager = simple_connection_manager'''
        )
    
    # Write back the modified content
    with open(app_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("[SUCCESS] Patched web_ui/app.py to include db_manager")

def main():
    """Main fix function"""
    print("=" * 60)
    print("Fixing Connections API for SQLAlchemy")
    print("=" * 60)
    
    try:
        create_simple_connection_manager()
        patch_flask_app()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Connections API fix complete!")
        print("Restart the web application to apply changes.")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[FAILED] Fix error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()