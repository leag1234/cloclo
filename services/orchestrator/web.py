"""Public-only HTTP transport: validation happens at the connector DNS boundary."""

import asyncio
import ipaddress
import socket
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import aiohttp
from aiohttp.abc import ResolveResult
from aiohttp.resolver import ThreadedResolver

USER_AGENT = "ATLAS-0/0.1 (+https://github.com/leag1234/cloclo)"
MAX_BYTES = 2_000_000


def public_ip(address: str) -> None:
    ip = ipaddress.ip_address(address)
    if not ip.is_global or ip.is_multicast or "%" in address:
        raise ValueError("ssrf_denied")
    if isinstance(ip, ipaddress.IPv6Address):
        if (
            ip.ipv4_mapped is not None
            or ip.sixtofour is not None
            or ip.teredo is not None
        ):
            raise ValueError("ssrf_denied")


def validate_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        len(url) > 4096
        or parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 80, 443)
        or "\\" in url
        or any(ord(c) <= 32 for c in url)
        or "%" in parsed.hostname
    ):
        raise ValueError("invalid_url")
    host = parsed.hostname.rstrip(".").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("ssrf_denied")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return
    public_ip(host)


class PublicResolver(ThreadedResolver):
    async def resolve(
        self, host: str, port: int = 0, family: int = socket.AF_INET
    ) -> list[ResolveResult]:
        results = await super().resolve(host, port, socket.AddressFamily(family))
        if not results:
            raise ValueError("dns_empty")
        for result in results:
            public_ip(result["host"])
        return results


class Web:
    async def _request(self, url: str, timeout: float) -> tuple[int, str, bytes]:
        validate_url(url)
        connector = aiohttp.TCPConnector(
            resolver=PublicResolver(), use_dns_cache=False, force_close=True
        )
        async with aiohttp.ClientSession(
            connector=connector,
            trust_env=False,
            auto_decompress=False,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as session:
            async with session.get(url, allow_redirects=False) as response:
                if response.headers.get("Content-Encoding", "identity") != "identity":
                    raise ValueError("unsupported_encoding")
                if (
                    response.content_length is not None
                    and response.content_length > MAX_BYTES
                ):
                    raise ValueError("response_too_large")
                body = bytearray()
                async for piece in response.content.iter_chunked(16384):
                    body.extend(piece)
                    if len(body) > MAX_BYTES:
                        raise ValueError("response_too_large")
                return (
                    response.status,
                    response.headers.get("Location", ""),
                    bytes(body),
                )

    async def _robots(self, url: str, timeout: float) -> None:
        parsed = urlsplit(url)
        target = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        for _ in range(5):
            status, location, body = await self._request(target, timeout)
            if status in (301, 302, 303, 307, 308):
                target = urljoin(target, location)
                continue
            if status == 404:
                return
            if status != 200:
                raise ValueError("robots_unavailable")
            parser = RobotFileParser()
            parser.parse(body.decode("utf-8", errors="replace").splitlines())
            if not parser.can_fetch(USER_AGENT, url):
                raise ValueError("robots_denied")
            return
        raise ValueError("robots_redirect_limit")

    async def fetch(self, url: str, timeout: float = 15) -> tuple[str, bytes]:
        async with asyncio.timeout(min(15, timeout)):
            for _ in range(5):
                validate_url(url)
                await self._robots(url, timeout)
                status, location, body = await self._request(url, timeout)
                if status in (301, 302, 303, 307, 308):
                    url = urljoin(url, location)
                    continue
                if status != 200:
                    raise ValueError(f"http_{status}")
                return url, body
        raise ValueError("redirect_limit")
