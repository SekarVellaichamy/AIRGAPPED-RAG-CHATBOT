"""
LDAP Authentication Service

Provides optional LDAP authentication with support for:
- LDAP and LDAPS protocols
- STARTTLS for secure connections
- Configurable user search filters
- Graceful degradation when LDAP is unavailable
"""

import ssl
import logging
from typing import Optional, Dict, Any
from ldap3 import Server, Connection, ALL, Tls, SUBTREE
from ldap3.core.exceptions import LDAPException, LDAPBindError, LDAPSocketOpenError

from app.core.config import settings

logger = logging.getLogger(__name__)


class LDAPAuthService:
    """Service for authenticating users against an LDAP directory."""
    
    def __init__(self):
        self.enabled = settings.LDAP_ENABLED
        self.server_address = settings.LDAP_SERVER
        self.port = settings.LDAP_PORT
        self.use_ssl = settings.LDAP_USE_SSL
        self.bind_dn = settings.LDAP_BIND_DN
        self.bind_password = settings.LDAP_BIND_PASSWORD
        self.search_base = settings.LDAP_USER_SEARCH_BASE
        self.search_filter = settings.LDAP_USER_SEARCH_FILTER
        self.start_tls = settings.LDAP_START_TLS
        self.skip_cert_verify = settings.LDAP_SKIP_CERTIFICATE_VERIFY
        
        self._server: Optional[Server] = None
        
        if self.enabled:
            self._init_server()
    
    def _init_server(self) -> None:
        """Initialize the LDAP server connection configuration."""
        if not self.server_address:
            logger.warning("LDAP is enabled but LDAP_SERVER is not configured")
            self.enabled = False
            return
        
        try:
            tls_config = None
            if self.use_ssl or self.start_tls:
                # Configure TLS settings
                validate = ssl.CERT_NONE if self.skip_cert_verify else ssl.CERT_REQUIRED
                tls_config = Tls(validate=validate)
            
            self._server = Server(
                self.server_address,
                port=self.port,
                use_ssl=self.use_ssl,
                tls=tls_config,
                get_info=ALL
            )
            logger.info(f"LDAP server configured: {self.server_address}:{self.port} (SSL: {self.use_ssl})")
        except Exception as e:
            logger.error(f"Failed to initialize LDAP server configuration: {e}")
            self.enabled = False
    
    def is_available(self) -> bool:
        """Check if LDAP authentication is enabled and configured."""
        return self.enabled and self._server is not None
    
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user against the LDAP directory.
        
        Args:
            username: The username to authenticate
            password: The user's password
            
        Returns:
            A dictionary with user info if authentication succeeds, None otherwise.
            User info includes: username, email (if available), display_name (if available)
        """
        if not self.is_available():
            logger.debug("LDAP authentication not available")
            return None
        
        if not password:
            # Never allow empty password authentication
            logger.warning(f"LDAP auth attempt with empty password for user: {username}")
            return None
        
        try:
            # Step 1: Bind with service account to search for user
            user_dn = self._find_user_dn(username)
            if not user_dn:
                logger.info(f"LDAP user not found: {username}")
                return None
            
            # Step 2: Attempt to bind with user's credentials
            user_conn = Connection(
                self._server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True
            )
            
            if self.start_tls and not self.use_ssl:
                user_conn.start_tls()
            
            # Successful bind means valid credentials
            user_info = {
                "username": username,
                "dn": user_dn,
                "email": None,
                "display_name": None
            }
            
            # Try to get additional user attributes
            try:
                search_filter = self.search_filter.replace("{username}", username)
                user_conn.search(
                    self.search_base,
                    search_filter,
                    search_scope=SUBTREE,
                    attributes=["mail", "email", "displayName", "cn", "givenName", "sn"]
                )
                
                if user_conn.entries:
                    entry = user_conn.entries[0]
                    # Try different email attribute names
                    for attr in ["mail", "email"]:
                        if hasattr(entry, attr) and getattr(entry, attr):
                            user_info["email"] = str(getattr(entry, attr))
                            break
                    # Try different display name attribute names
                    for attr in ["displayName", "cn"]:
                        if hasattr(entry, attr) and getattr(entry, attr):
                            user_info["display_name"] = str(getattr(entry, attr))
                            break
            except Exception as e:
                logger.debug(f"Could not fetch additional LDAP attributes: {e}")
            
            user_conn.unbind()
            logger.info(f"LDAP authentication successful for user: {username}")
            return user_info
            
        except LDAPBindError as e:
            logger.info(f"LDAP authentication failed for user {username}: Invalid credentials")
            return None
        except LDAPSocketOpenError as e:
            logger.error(f"LDAP server unreachable: {e}")
            return None
        except LDAPException as e:
            logger.error(f"LDAP error during authentication: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during LDAP authentication: {e}")
            return None
    
    def _find_user_dn(self, username: str) -> Optional[str]:
        """
        Find the user's DN in the LDAP directory.
        
        Uses the service account (bind DN) to search for the user.
        """
        try:
            # If no bind DN is configured, try anonymous bind or direct user DN construction
            if not self.bind_dn:
                # Construct DN directly from search filter pattern
                # This is a simplified approach for simple LDAP setups
                search_filter = self.search_filter.replace("{username}", username)
                # Extract attribute from filter like "(uid={username})" -> "uid"
                if search_filter.startswith("(") and "=" in search_filter:
                    attr = search_filter[1:search_filter.index("=")]
                    return f"{attr}={username},{self.search_base}"
                return None
            
            # Bind with service account
            conn = Connection(
                self._server,
                user=self.bind_dn,
                password=self.bind_password,
                auto_bind=True,
                raise_exceptions=True
            )
            
            if self.start_tls and not self.use_ssl:
                conn.start_tls()
            
            # Search for the user
            search_filter = self.search_filter.replace("{username}", username)
            conn.search(
                self.search_base,
                search_filter,
                search_scope=SUBTREE,
                attributes=[]
            )
            
            if conn.entries:
                user_dn = str(conn.entries[0].entry_dn)
                conn.unbind()
                return user_dn
            
            conn.unbind()
            return None
            
        except LDAPSocketOpenError as e:
            logger.error(f"LDAP server unreachable during user search: {e}")
            return None
        except LDAPException as e:
            logger.error(f"LDAP error during user search: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during LDAP user search: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test the LDAP server connection."""
        if not self.is_available():
            return False
        
        try:
            if self.bind_dn:
                conn = Connection(
                    self._server,
                    user=self.bind_dn,
                    password=self.bind_password,
                    auto_bind=True
                )
            else:
                # Anonymous bind test
                conn = Connection(self._server, auto_bind=True)
            
            if self.start_tls and not self.use_ssl:
                conn.start_tls()
            
            conn.unbind()
            logger.info("LDAP connection test successful")
            return True
        except Exception as e:
            logger.error(f"LDAP connection test failed: {e}")
            return False


# Global singleton instance
ldap_service = LDAPAuthService()
