"""
Session Management for Windows Job Scheduler
Handles user sessions, login/logout, and authentication state
"""

from flask import session, request, g
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
import secrets
import hashlib
from utils.logger import get_logger


class SessionManager:
    """Manages user sessions and authentication state"""
    
    def __init__(self, session_timeout_minutes: int = 480):  # 8 hours default
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
        self.logger = get_logger(__name__)
        self.logger.info(f"[SESSION] Session manager initialized with {session_timeout_minutes} minute timeout")
    
    def create_session(self, user_info: Dict[str, Any]) -> str:
        """
        Create a new user session
        
        Args:
            user_info: Dictionary containing user information from AD
            
        Returns:
            Session token
        """
        try:
            # Generate session token
            session_token = secrets.token_urlsafe(32)
            
            # Store user info in Flask session
            session['authenticated'] = True
            session['session_token'] = session_token
            session['username'] = user_info.get('username', '')
            session['display_name'] = user_info.get('display_name', '')
            session['email'] = user_info.get('email', '')
            session['groups'] = user_info.get('groups', [])
            session['domain'] = user_info.get('domain', '')
            session['login_time'] = datetime.now().isoformat()
            session['last_activity'] = datetime.now().isoformat()
            session['client_ip'] = request.remote_addr
            session['user_agent'] = request.headers.get('User-Agent', '')
            
            # Make session permanent with our timeout
            session.permanent = True
            
            self.logger.info(f"[SESSION] Created session for user: {user_info.get('username')} from {request.remote_addr}")
            
            return session_token
            
        except Exception as e:
            self.logger.error(f"[SESSION] Error creating session: {e}")
            raise
    
    def validate_session(self) -> bool:
        """
        Validate current session
        
        Returns:
            True if session is valid, False otherwise
        """
        try:
            if not session.get('authenticated'):
                return False
            
            # Check session timeout
            last_activity = session.get('last_activity')
            if not last_activity:
                return False
            
            last_activity_time = datetime.fromisoformat(last_activity)
            if datetime.now() - last_activity_time > self.session_timeout:
                self.logger.info(f"[SESSION] Session expired for user: {session.get('username')}")
                self.destroy_session()
                return False
            
            # Update last activity
            session['last_activity'] = datetime.now().isoformat()
            
            return True
            
        except Exception as e:
            self.logger.error(f"[SESSION] Error validating session: {e}")
            return False
    
    def destroy_session(self):
        """Destroy current session"""
        try:
            username = session.get('username', 'unknown')
            self.logger.info(f"[SESSION] Destroying session for user: {username}")
            
            # Clear all session data
            session.clear()
            
        except Exception as e:
            self.logger.error(f"[SESSION] Error destroying session: {e}")
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current user information from session
        
        Returns:
            User information dictionary or None if not authenticated
        """
        if not self.validate_session():
            return None
        
        return {
            'username': session.get('username'),
            'display_name': session.get('display_name'),
            'email': session.get('email'),
            'groups': session.get('groups', []),
            'domain': session.get('domain'),
            'login_time': session.get('login_time'),
            'last_activity': session.get('last_activity'),
            'client_ip': session.get('client_ip'),
            'user_agent': session.get('user_agent')
        }
    
    def refresh_session(self):
        """Refresh session activity timestamp"""
        if session.get('authenticated'):
            session['last_activity'] = datetime.now().isoformat()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get detailed session information"""
        if not self.validate_session():
            return {'authenticated': False}
        
        login_time = datetime.fromisoformat(session.get('login_time', datetime.now().isoformat()))
        last_activity = datetime.fromisoformat(session.get('last_activity', datetime.now().isoformat()))
        session_duration = datetime.now() - login_time
        idle_time = datetime.now() - last_activity
        
        return {
            'authenticated': True,
            'username': session.get('username'),
            'display_name': session.get('display_name'),
            'domain': session.get('domain'),
            'login_time': session.get('login_time'),
            'session_duration_minutes': int(session_duration.total_seconds() / 60),
            'idle_time_minutes': int(idle_time.total_seconds() / 60),
            'timeout_minutes': int(self.session_timeout.total_seconds() / 60),
            'client_ip': session.get('client_ip'),
            'groups': session.get('groups', [])
        }
    
    def has_group(self, group_name: str) -> bool:
        """Check if current user is member of specified group"""
        if not self.validate_session():
            return False
        
        user_groups = session.get('groups', [])
        return group_name in user_groups
    
    def has_any_group(self, group_names: list) -> bool:
        """Check if current user is member of any of the specified groups"""
        if not self.validate_session():
            return False
        
        user_groups = session.get('groups', [])
        return any(group in user_groups for group in group_names)
    
    def is_admin(self) -> bool:
        """Check if current user has admin privileges"""
        admin_groups = [
            'Domain Admins',
            'Administrators', 
            'Job Scheduler Admins',
            'IT Admins'
        ]
        return self.has_any_group(admin_groups)
    
    def update_user_activity(self, activity: str):
        """Log user activity"""
        if self.validate_session():
            self.logger.info(f"[SESSION] User {session.get('username')} activity: {activity}")
            self.refresh_session()


# Global session manager instance
session_manager = SessionManager()


def login_required(f):
    """Decorator to require authentication for routes"""
    from functools import wraps
    from flask import redirect, url_for, request as flask_request
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session_manager.validate_session():
            # Store the original URL for redirect after login
            session['next_url'] = flask_request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require admin privileges for routes"""
    from functools import wraps
    from flask import redirect, url_for, flash
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session_manager.validate_session():
            session['next_url'] = flask_request.url
            return redirect(url_for('login'))
        
        if not session_manager.is_admin():
            flash('Admin privileges required', 'error')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function