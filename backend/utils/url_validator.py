"""
URL safety validator to prevent Server-Side Request Forgery (SSRF) attacks.
Ensures URLs use http/https schemes and do not resolve to local, private,
link-local, or Cloud metadata server IP addresses.
"""
from __future__ import annotations
import socket
import ipaddress
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


class InvalidURLException(Exception):
    """Exception raised when the URL syntax is invalid or scheme is unsupported."""
    pass


class UnsafeURLException(Exception):
    """Exception raised when the URL resolves to a forbidden (private/loopback/SSRF-prone) address."""
    pass


def is_safe_ip(ip_str: str) -> bool:
    """Check if an IP address string belongs to a safe public range.
    
    Blocks:
    - Loopback addresses (127.0.0.0/8, ::1)
    - Private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fd00::/8)
    - Link-local/Cloud Metadata (169.254.0.0/16, fe80::/10)
    - Unspecified/Wildcard (0.0.0.0, ::)
    - Reserved ranges
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        # Block private, loopback, link-local, unspecified, or reserved ranges
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_unspecified
            or ip.is_reserved
        ):
            return False
        return True
    except ValueError:
        # Invalid IP format is treated as unsafe
        return False


def validate_url_safety(url: str) -> str:
    """Validate URL syntax and resolve the hostname to verify SSRF safety.
    
    Args:
        url: The absolute target URL to validate.
        
    Returns:
        str: The validated URL if it is safe.
        
    Raises:
        InvalidURLException: If scheme is unsupported or host is missing.
        UnsafeURLException: If host resolves to a loopback or private range.
    """
    if not url:
        raise InvalidURLException("URL cannot be empty.")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise InvalidURLException(f"Malformed URL syntax: {e}")

    # Validate scheme
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise InvalidURLException(
            f"Unsupported scheme '{scheme}'. Only 'http' and 'https' are allowed."
        )

    # Reject embedded credentials
    if parsed.username is not None or parsed.password is not None:
        raise InvalidURLException(
            "URLs containing embedded credentials are not allowed."
        )

    # Validate host
    hostname = parsed.hostname
    if not hostname:
        raise InvalidURLException("URL must contain a valid hostname.")

    # Resolve hostname to all associated IP addresses (handles both IPv4 and IPv6)
    try:
        # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        # If hostname cannot be resolved, block it to prevent dns-resolution errors later
        raise InvalidURLException(f"Failed to resolve host '{hostname}': {e}")
    except Exception as e:
        raise InvalidURLException(f"Resolution error for host '{hostname}': {e}")

    # Validate every resolved IP address
    for info in addr_info:
        ip_str = info[4][0]
        if not is_safe_ip(ip_str):
            logger.warning(
                "SSRF attempt blocked: host '%s' resolved to unsafe IP '%s'",
                hostname,
                ip_str
            )
            raise UnsafeURLException(
                f"Connection to unsafe host IP '{ip_str}' is forbidden."
            )

    # Reconstruct normalized URL without fragments or credentials
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"

    normalized_url = urlunparse((
        scheme,
        netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        ""
    ))

    return normalized_url
