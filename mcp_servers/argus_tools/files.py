import ipaddress
from urllib.parse import urlparse

BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "localhost"}


class UrlError(ValueError):
    pass


def guard_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlError(f"esquema não permitido: {parsed.scheme}")
    host = (parsed.hostname or "").lower()
    if not host:
        raise UrlError("host vazio")
    if host in BLOCKED_HOSTS:
        raise UrlError(f"host bloqueado: {host}")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        raise UrlError(f"ip privado: {host}")
