"""Outbound HTTP validation for tenant-configurable connectors."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


class UnsafeOutboundURLError(ValueError):
    """Raised when an outbound URL can reach an unsafe network target."""


def _host_allowed(hostname: str, allowed_hosts: set[str] | None) -> bool:
    if not allowed_hosts:
        return True
    return any(hostname == allowed or hostname.endswith(f".{allowed}") for allowed in allowed_hosts)


def validate_outbound_https_url(
    url: str,
    *,
    allowed_hosts: set[str] | None = None,
) -> str:
    """Require a public HTTPS target and reject private/reserved DNS results."""
    candidate = str(url or "").strip()
    if len(candidate) > 2048:
        raise UnsafeOutboundURLError("Bağlantı adresi çok uzun")

    parsed = urlsplit(candidate)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise UnsafeOutboundURLError("Yalnızca geçerli HTTPS bağlantıları kullanılabilir")
    if parsed.username or parsed.password:
        raise UnsafeOutboundURLError("Bağlantı adresinde kullanıcı bilgisi kullanılamaz")
    if parsed.port not in {None, 443}:
        raise UnsafeOutboundURLError("Yalnızca standart HTTPS portu kullanılabilir")

    hostname = parsed.hostname.rstrip(".").lower()
    normalized_allowlist = (
        {item.lower().rstrip(".") for item in allowed_hosts}
        if allowed_hosts
        else None
    )
    if not _host_allowed(hostname, normalized_allowlist):
        raise UnsafeOutboundURLError("Bağlantı sağlayıcısı izin verilen listede değil")

    try:
        literal_ip = ipaddress.ip_address(hostname)
        addresses = {literal_ip}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(item[4][0])
                for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
            }
        except (OSError, ValueError) as exc:
            raise UnsafeOutboundURLError("Bağlantı adresi çözümlenemedi") from exc

    if not addresses or any(not address.is_global for address in addresses):
        raise UnsafeOutboundURLError("Özel veya ayrılmış ağ adreslerine bağlantı kurulamaz")
    return candidate
