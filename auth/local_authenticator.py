"""
Local User Authentication Module for Windows Job Scheduler
Simple username-based authentication for admin users (bypasses AD)
"""

from typing import Dict, Optional, Any
import hashlib
import os
from utils.logger import get_logger


class LocalAuthenticator:
    """Local authentication handler for admin users"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.logger.info("[LOCAL_AUTH] Local authenticator initialized")
        
        # Default admin users (in production, store these in database)
        self.default_users = {
            'admin': {
                'username': 'admin',
                'display_name': 'System Administrator',
                'email': 'admin@jobscheduler.local',
                'groups': ['Domain Admins', 'Administrators', 'Job Scheduler Admins'],
                'enabled': True,
                'password_hash': None  # No password required for now
            },
            'scheduler': {
                'username': 'scheduler', 
                'display_name': 'Job Scheduler Admin',
                'email': 'scheduler@jobscheduler.local',
                'groups': ['Job Scheduler Admins', 'Administrators'],
                'enabled': True,
                'password_hash': None
            },
            'operator': {
                'username': 'operator',
                'display_name': 'Job Operator', 
                'email': 'operator@jobscheduler.local',
                'groups': ['Job Scheduler Users'],
                'enabled': True,
                'password_hash': None
            }
        }
    
    def authenticate(self, username: str, password: str = None) -> Dict[str, Any]:
        """
        Authenticate user against local user table
        
        Args:
            username: Username 
            password: Password (optional for now)
            
        Returns:
            Dict with authentication result and user information
        """
        try:
            self.logger.info(f"[LOCAL_AUTH] Local authentication attempt for user: {username}")
            
            # Clean up username
            username = username.strip().lower()
            
            # Check if user exists in default users
            if username in self.default_users:
                user = self.default_users[username]
                
                if not user['enabled']:
                    self.logger.warning(f"[LOCAL_AUTH] User '{username}' is disabled")
                    return {
                        'success': False,
                        'error': 'User account is disabled',
                        'username': username
                    }
                
                # For now, allow any password or no password
                # In production, you'd check password_hash here
                
                self.logger.info(f"[LOCAL_AUTH] Local authentication successful for user: {username}")
                
                return {
                    'success': True,
                    'username': user['username'],
                    'display_name': user['display_name'], 
                    'email': user['email'],
                    'groups': user['groups'],
                    'domain': 'local',
                    'auth_type': 'local',
                    'is_admin': self._is_admin_user(user['groups'])
                }
            else:
                self.logger.warning(f"[LOCAL_AUTH] User '{username}' not found in local users")
                return {
                    'success': False,
                    'error': 'Invalid username - use: admin, scheduler, or operator',
                    'username': username,
                    'available_users': list(self.default_users.keys())
                }
                
        except Exception as e:
            self.logger.error(f"[LOCAL_AUTH] Local authentication error: {e}")
            return {
                'success': False,
                'error': f'Local authentication system error: {str(e)}',
                'username': username
            }
    
    def _is_admin_user(self, groups: list) -> bool:
        """Check if user has admin privileges"""
        admin_groups = ['Domain Admins', 'Administrators', 'Job Scheduler Admins']
        return any(group in admin_groups for group in groups)
    
    def list_users(self) -> Dict[str, Any]:
        """List all local users"""
        users = []
        for username, user_data in self.default_users.items():
            users.append({
                'username': user_data['username'],
                'display_name': user_data['display_name'],
                'email': user_data['email'],
                'groups': user_data['groups'],
                'enabled': user_data['enabled'],
                'is_admin': self._is_admin_user(user_data['groups'])
            })
        
        return {
            'success': True,
            'users': users,
            'total_users': len(users)
        }
    
    def get_user_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific user"""
        username = username.strip().lower()
        
        if username in self.default_users:
            user = self.default_users[username]
            return {
                'username': user['username'],
                'display_name': user['display_name'],
                'email': user['email'], 
                'groups': user['groups'],
                'enabled': user['enabled'],
                'is_admin': self._is_admin_user(user['groups']),
                'auth_type': 'local'
            }
        
        return None
    
    def test_connection(self) -> Dict[str, Any]:
        """Test local authentication system"""
        try:
            # Test by checking available users
            users = self.list_users()
            
            return {
                'success': True,
                'message': 'Local authentication system operational',
                'available_users': len(users['users']),
                'admin_users': len([u for u in users['users'] if u['is_admin']]),
                'enabled_users': len([u for u in users['users'] if u['enabled']])
            }
            
        except Exception as e:
            self.logger.error(f"[LOCAL_AUTH] Test connection error: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Singleton instance for application use
_local_auth_instance = None

def get_local_authenticator() -> LocalAuthenticator:
    """Get singleton local authenticator instance"""
    global _local_auth_instance
    if _local_auth_instance is None:
        _local_auth_instance = LocalAuthenticator()
    return _local_auth_instance