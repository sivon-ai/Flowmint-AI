"""
SSRF Protection utility for outbound HTTP requests (e.g., WooCommerce, Webhooks).

Validates store URLs, checks DNS resolution, and rejects private, loopback,
link-local, and reserved IP ranges to protect against Server-Side Request Forgery.
"""

import ipaddress
import socket
from urllib.parse import urlparse

from app.config import get_settings
from app.core.exceptions import ValidationError


def validate_outbound_url(url: str, allow_localhost_dev: bool = False) -> str:
    """
    Validate that an external store URL is safe for outbound requests.
    
    Rejects:
    - Non-HTTP(S) schemes
    - Private IP addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Loopback addresses (127.0.0.0/8, ::1)
    - Link-local addresses (169.254.0.0/16, fe80::/10)
    - Cloud metadata endpoints (e.g. 169.254.169.254)
    """
    if not url or not isinstance(url, str):
        raise ValidationError("Store URL is required")

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
    except Exception:
        raise ValidationError("Invalid URL format")

    settings = get_settings()
    is_prod = settings.is_production

    if is_prod and parsed.scheme != "https":
        raise ValidationError("Production store connections must use HTTPS")

    hostname = parsed.hostname
    if not hostname:
        raise ValidationError("Invalid hostname in store URL")

    # In dev/test mode only, optionally permit localhost if explicitly requested
    if allow_localhost_dev and not is_prod:
        if hostname in ("localhost", "127.0.0.1", "::1", "test"):
            return url.rstrip("/")

    # Resolve IP address to check against private/reserved ranges
    try:
        ip_str = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        # If hostname does not resolve, it's either an invalid domain or mock test domain
        if is_prod:
            raise ValidationError(f"Could not resolve domain: {hostname}")
        return url.rstrip("/")

    # Check for private, loopback, multicast, reserved ranges
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    ):
        raise ValidationError(
            f"Access to private, loopback, or internal address ({ip_str}) is blocked for security."
        )

    return url.rstrip("/")
