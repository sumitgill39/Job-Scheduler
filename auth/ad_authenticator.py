"""
Active Directory Authentication Module for Windows Job Scheduler
Authenticates users against local AD domain
"""

import ldap3
from ldap3 import Server, Connection, ALL, NTLM
from ldap3.core.exceptions import LDAPException, LDAPBindError
from typing import Dict, Optional, List
import socket
import dns.resolver
from utils.logger import get_logger


class ADAuthenticator:
    """Active Directory Authentication Handler"""
    
    def __init__(self, domain: str = "mgo.mersh.com"):
        self.domain = domain
        self.logger = get_logger(__name__)
        self.domain_controllers = []
        self.logger.info(f"[AD_AUTH] Initializing AD authenticator for domain: {domain}")
        
        # Discover domain controllers
        self._discover_domain_controllers()
    
    def _discover_domain_controllers(self):
        """Discover domain controllers for the domain"""
        try:
            # Try DNS SRV record lookup for domain controllers
            srv_query = f"_ldap._tcp.{self.domain}"
            
            try:
                answers = dns.resolver.resolve(srv_query, 'SRV')
                for rdata in answers:
                    dc_host = str(rdata.target).rstrip('.')
                    dc_port = rdata.port
                    self.domain_controllers.append((dc_host, dc_port))
                    self.logger.info(f"[AD_AUTH] Discovered DC: {dc_host}:{dc_port}")
            except Exception as dns_error:
                self.logger.warning(f"[AD_AUTH] DNS SRV lookup failed: {dns_error}")
                
                # Fallback: try common DC names
                common_dc_names = [
                    f"dc.{self.domain}",
                    f"dc1.{self.domain}",
                    f"dc01.{self.domain}",
                    f"ad.{self.domain}",
                    f"ldap.{self.domain}"
                ]
                
                for dc_name in common_dc_names:
                    try:
                        # Test if host is reachable
                        socket.gethostbyname(dc_name)
                        self.domain_controllers.append((dc_name, 389))
                        self.logger.info(f"[AD_AUTH] Found fallback DC: {dc_name}:389")
                        break
                    except socket.gaierror:
                        continue
            
            if not self.domain_controllers:
                self.logger.error(f"[AD_AUTH] No domain controllers found for {self.domain}")
                # Add localhost as last resort for testing
                self.domain_controllers.append(("localhost", 389))
                
        except Exception as e:
            self.logger.error(f"[AD_AUTH] Error discovering domain controllers: {e}")
            self.domain_controllers.append(("localhost", 389))
    
    def authenticate(self, username: str, password: str) -> Dict[str, any]:
        """
        Authenticate user against Active Directory
        
        Args:
            username: Username (can be with or without domain)
            password: User password
            
        Returns:
            Dict with authentication result and user information
        """
        try:
            self.logger.info(f"[AD_AUTH] Attempting authentication for user: {username}")
            
            # Normalize username
            if '\\' not in username and '@' not in username:
                # Add domain if not present
                full_username = f"{self.domain}\\{username}"
                upn_username = f"{username}@{self.domain}"
            else:
                full_username = username
                if '@' in username:
                    upn_username = username
                else:
                    upn_username = username.replace('\\', '@')
            
            # Try authentication with each discovered domain controller
            for dc_host, dc_port in self.domain_controllers:
                try:
                    self.logger.debug(f"[AD_AUTH] Trying DC: {dc_host}:{dc_port}")
                    
                    # Create server connection
                    server = Server(
                        host=dc_host,
                        port=dc_port,
                        get_info=ALL,
                        connect_timeout=10
                    )
                    
                    # Try different username formats
                    usernames_to_try = [full_username, upn_username, username]
                    
                    for user_format in usernames_to_try:
                        try:
                            self.logger.debug(f"[AD_AUTH] Trying username format: {user_format}")
                            
                            # Attempt LDAP bind
                            conn = Connection(
                                server=server,
                                user=user_format,
                                password=password,
                                authentication=NTLM,
                                auto_bind=True,
                                raise_exceptions=True
                            )
                            
                            # Authentication successful - get user information
                            user_info = self._get_user_info(conn, username.split('\\')[-1].split('@')[0])
                            
                            conn.unbind()
                            
                            self.logger.info(f"[AD_AUTH] Authentication successful for {username}")
                            
                            return {
                                'success': True,
                                'username': user_info.get('username', username),
                                'display_name': user_info.get('display_name', username),
                                'email': user_info.get('email', ''),
                                'groups': user_info.get('groups', []),
                                'domain': self.domain,
                                'domain_controller': f"{dc_host}:{dc_port}"
                            }
                            
                        except LDAPBindError as bind_error:
                            self.logger.debug(f"[AD_AUTH] Bind failed for {user_format}: {bind_error}")
                            continue
                        
                        except Exception as conn_error:
                            self.logger.debug(f"[AD_AUTH] Connection error for {user_format}: {conn_error}")
                            continue
                    
                except Exception as dc_error:
                    self.logger.warning(f"[AD_AUTH] DC {dc_host}:{dc_port} failed: {dc_error}")
                    continue
            
            # All authentication attempts failed
            self.logger.warning(f"[AD_AUTH] Authentication failed for user: {username}")
            
            return {
                'success': False,
                'error': 'Invalid username or password',
                'domain': self.domain,
                'attempted_controllers': self.domain_controllers
            }
            
        except Exception as e:
            self.logger.error(f"[AD_AUTH] Authentication error: {e}")
            return {
                'success': False,
                'error': f'Authentication system error: {str(e)}',
                'domain': self.domain
            }
    
    def _get_user_info(self, connection: Connection, username: str) -> Dict[str, any]:
        """Get detailed user information from AD"""
        try:
            # Search for user in AD
            search_base = self._get_search_base()
            search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
            
            attributes = [
                'sAMAccountName',
                'displayName', 
                'mail',
                'memberOf',
                'userPrincipalName',
                'department',
                'title',
                'telephoneNumber'
            ]
            
            success = connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes
            )
            
            if success and connection.entries:
                entry = connection.entries[0]
                
                # Extract group memberships
                groups = []
                if hasattr(entry, 'memberOf') and entry.memberOf:
                    for group_dn in entry.memberOf:
                        # Extract group name from DN
                        if 'CN=' in str(group_dn):
                            group_name = str(group_dn).split('CN=')[1].split(',')[0]
                            groups.append(group_name)
                
                user_info = {
                    'username': str(entry.sAMAccountName) if hasattr(entry, 'sAMAccountName') else username,
                    'display_name': str(entry.displayName) if hasattr(entry, 'displayName') else username,
                    'email': str(entry.mail) if hasattr(entry, 'mail') else '',
                    'upn': str(entry.userPrincipalName) if hasattr(entry, 'userPrincipalName') else '',
                    'department': str(entry.department) if hasattr(entry, 'department') else '',
                    'title': str(entry.title) if hasattr(entry, 'title') else '',
                    'phone': str(entry.telephoneNumber) if hasattr(entry, 'telephoneNumber') else '',
                    'groups': groups
                }
                
                self.logger.info(f"[AD_AUTH] Retrieved user info for {username}: {user_info['display_name']}")
                return user_info
                
            else:
                self.logger.warning(f"[AD_AUTH] User {username} not found in directory")
                return {'username': username, 'display_name': username, 'email': '', 'groups': []}
                
        except Exception as e:
            self.logger.error(f"[AD_AUTH] Error retrieving user info: {e}")
            return {'username': username, 'display_name': username, 'email': '', 'groups': []}
    
    def _get_search_base(self) -> str:
        """Generate LDAP search base from domain name"""
        # Convert domain.com to DC=domain,DC=com
        domain_parts = self.domain.split('.')
        search_base = ','.join([f"DC={part}" for part in domain_parts])
        return search_base
    
    def validate_group_membership(self, username: str, required_groups: List[str]) -> bool:
        """Check if user is member of required groups"""
        # This would require re-authentication or cached user info
        # For now, return True - implement based on your security requirements
        return True
    
    def test_connection(self) -> Dict[str, any]:
        """Test connection to domain controllers"""
        results = []
        
        for dc_host, dc_port in self.domain_controllers:
            try:
                server = Server(
                    host=dc_host,
                    port=dc_port,
                    get_info=ALL,
                    connect_timeout=5
                )
                
                # Anonymous bind to test connectivity
                conn = Connection(server=server)
                if conn.bind():
                    results.append({
                        'dc': f"{dc_host}:{dc_port}",
                        'status': 'reachable',
                        'info': str(server.info) if server.info else 'Connected'
                    })
                    conn.unbind()
                else:
                    results.append({
                        'dc': f"{dc_host}:{dc_port}",
                        'status': 'unreachable',
                        'error': 'Bind failed'
                    })
                    
            except Exception as e:
                results.append({
                    'dc': f"{dc_host}:{dc_port}",
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'domain': self.domain,
            'domain_controllers': results,
            'total_controllers': len(results),
            'reachable_controllers': len([r for r in results if r['status'] == 'reachable'])
        }


# Singleton instance for application use
_ad_auth_instance = None

def get_ad_authenticator(domain: str = "mgo.mersh.com") -> ADAuthenticator:
    """Get singleton AD authenticator instance"""
    global _ad_auth_instance
    if _ad_auth_instance is None:
        _ad_auth_instance = ADAuthenticator(domain)
    return _ad_auth_instance