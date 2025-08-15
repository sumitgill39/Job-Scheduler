# Active Directory Authentication Setup Guide

## Overview
The Windows Job Scheduler now includes integrated Active Directory authentication for secure domain-based login.

## Features
- **Domain Authentication**: Login with domain credentials (username/password)
- **Auto-Discovery**: Automatically discovers domain controllers via DNS SRV records
- **Session Management**: Secure session handling with configurable timeout
- **Group Support**: Retrieves user group memberships from AD
- **Role-Based Access**: Admin role detection based on group membership
- **Connection Testing**: Built-in domain connectivity testing

## Prerequisites

### 1. Install Dependencies
```bash
pip install ldap3 dnspython cryptography
```

### 2. Network Requirements
- **DNS Resolution**: Application server must resolve domain controller names
- **LDAP Access**: Port 389 (LDAP) or 636 (LDAPS) access to domain controllers
- **Domain Membership**: Not required, but recommended for seamless integration

### 3. Domain Controller Access
- **Service Account** (recommended): Create dedicated service account for LDAP queries
- **User Authentication**: Standard domain user authentication via LDAP bind

## Configuration

### Environment Variables
Set these environment variables or update `web_ui/app.py`:

```bash
# Active Directory Domain
export AD_DOMAIN="mgo.mersh.com"

# Session Configuration
export SESSION_TIMEOUT_MINUTES="480"  # 8 hours default

# Flask Security
export SECRET_KEY="your-secure-secret-key-here"
```

### Flask Configuration
In `web_ui/app.py`:
```python
app.config['AD_DOMAIN'] = 'mgo.mersh.com'
app.config['SESSION_TIMEOUT_MINUTES'] = 480  # 8 hours
```

## Authentication System Components

### 1. AD Authenticator (`auth/ad_authenticator.py`)
- **Domain Controller Discovery**: Uses DNS SRV records to find DCs
- **LDAP Authentication**: NTLM authentication against AD
- **User Information**: Retrieves display name, email, group memberships
- **Connection Testing**: Tests connectivity to domain controllers

### 2. Session Manager (`auth/session_manager.py`)
- **Session Creation**: Creates secure user sessions
- **Session Validation**: Validates sessions with timeout
- **Role Management**: Admin role detection
- **Activity Tracking**: Logs user activities

### 3. Web Interface
- **Login Page**: `/login` - Domain credential login
- **Profile Page**: `/profile` - User information and session details
- **Logout**: `/logout` - Session termination

## Usage

### 1. Start the Application
```bash
python main.py
```

### 2. Access Login Page
Navigate to: `http://localhost:5000/login`

### 3. Login Formats
Users can login with any of these formats:
- `username` (domain will be added automatically)
- `domain\username`
- `username@domain.com`

### 4. Test Domain Connection
Click "Test" on login page to verify domain controller connectivity.

## Admin Role Configuration

### Default Admin Groups
Users in these AD groups will have admin privileges:
- `Domain Admins`
- `Administrators`
- `Job Scheduler Admins`
- `IT Admins`

### Custom Admin Groups
Modify `auth/session_manager.py`, `is_admin()` method:
```python
def is_admin(self) -> bool:
    admin_groups = [
        'Domain Admins',
        'Your Custom Admin Group',
        # Add more groups as needed
    ]
    return self.has_any_group(admin_groups)
```

## Security Features

### 1. Session Security
- **Secure Tokens**: 32-byte URL-safe tokens
- **Session Timeout**: Configurable timeout (default 8 hours)
- **IP Tracking**: Tracks client IP addresses
- **Activity Refresh**: Updates last activity timestamp

### 2. Authentication Security
- **Password Protection**: Passwords never logged or stored
- **Connection Encryption**: Supports LDAPS (SSL/TLS)
- **Multiple DC Support**: Failover to multiple domain controllers

### 3. Route Protection
All application routes are protected by authentication middleware:
```python
@app.before_request
def check_authentication():
    # Automatically protects all routes except public ones
```

## API Endpoints

### Authentication APIs
- `POST /login` - User login
- `GET /logout` - User logout
- `POST /api/auth/test-domain` - Test domain connectivity
- `GET /api/auth/session-info` - Get session information

## Troubleshooting

### 1. Cannot Connect to Domain
**Symptoms**: "No domain controllers reachable"
**Solutions**:
- Verify DNS resolution: `nslookup _ldap._tcp.mgo.mersh.com`
- Check firewall: Port 389/636 access
- Test manual connection: `telnet dc.mgo.mersh.com 389`

### 2. Authentication Fails
**Symptoms**: "Invalid username or password"
**Solutions**:
- Verify credentials in Active Directory Users and Computers
- Check account lockout status
- Try different username formats
- Review application logs for detailed errors

### 3. Group Memberships Not Loading
**Symptoms**: User has no groups or missing admin privileges
**Solutions**:
- Verify user has group memberships in AD
- Check LDAP query permissions
- Review group name matching in `is_admin()` method

### 4. Session Timeout Issues
**Symptoms**: Frequent logouts or session expires too quickly
**Solutions**:
- Increase `SESSION_TIMEOUT_MINUTES`
- Check for multiple browser tabs/sessions
- Verify system clock synchronization

## Deployment Considerations

### 1. Production Settings
```python
# Use strong secret key
app.config['SECRET_KEY'] = 'very-long-random-secret-key'

# Enable HTTPS
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
```

### 2. Load Balancing
- Use shared session storage (Redis/Database) for multiple app instances
- Configure sticky sessions for simple deployments

### 3. Monitoring
- Monitor failed login attempts
- Track session duration and user activity
- Alert on domain controller connectivity issues

## Testing

### 1. Test Domain Connection
```bash
python -c "
from auth.ad_authenticator import get_ad_authenticator
auth = get_ad_authenticator('mgo.mersh.com')
print(auth.test_connection())
"
```

### 2. Test User Authentication
```bash
python -c "
from auth.ad_authenticator import get_ad_authenticator
auth = get_ad_authenticator('mgo.mersh.com')
result = auth.authenticate('testuser', 'password')
print(result)
"
```

## Support
For issues or questions about the authentication system:
1. Check application logs in `logs/` directory
2. Test domain connectivity using built-in tools
3. Review AD group memberships and permissions
4. Verify network connectivity to domain controllers