"""
IP discovery and TCP port scanning.

We use plain TCP connect checks (no root / no ICMP) so this runs
fine inside Docker and Kubernetes.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time


# Ports we poke during host discovery to see if a machine is up.
PROBE_PORTS = (22, 80, 443, 135, 139, 445, 3389, 8080, 8765)

# Only scan these by default — keeps people from accidentally scanning the internet.
PRIVATE_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
)


def parse_ports(ports_text: str) -> list[int]:
    """Turn '22,80,443' or '1-100' into a sorted list of port numbers."""
    ports: set[int] = set()

    for part in ports_text.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start > end:
                start, end = end, start
            if start < 1 or end > 65535:
                raise ValueError("Ports must be between 1 and 65535")
            # Cap huge ranges so a typo doesn't melt the machine
            if end - start > 5000:
                raise ValueError("Port range too large (max 5000 ports at once)")
            ports.update(range(start, end + 1))
        else:
            port = int(part)
            if port < 1 or port > 65535:
                raise ValueError("Ports must be between 1 and 65535")
            ports.add(port)

    if not ports:
        raise ValueError("No ports to scan")

    return sorted(ports)


def expand_targets(target: str) -> list[str]:
    """Expand a single IP or CIDR into a list of IP strings."""
    target = target.strip()

    try:
        if "/" in target:
            network = ipaddress.ip_network(target, strict=False)
            # Skip network/broadcast for IPv4 sized nets; keep it simple for /32
            hosts = list(network.hosts()) if network.num_addresses > 2 else list(network)
            if len(hosts) > 1024:
                raise ValueError("CIDR too large (max 1024 hosts). Try a smaller range like /24.")
            return [str(ip) for ip in hosts]

        # Single host
        ip = ipaddress.ip_address(target)
        return [str(ip)]
    except ValueError as exc:
        # Re-raise our own messages; wrap weird input
        if "too large" in str(exc) or "Ports" in str(exc):
            raise
        raise ValueError(f"Invalid IP or CIDR: {target}") from exc


def is_private_ip(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return any(ip in net for net in PRIVATE_NETWORKS)


def assert_targets_allowed(ips: list[str]) -> None:
    """Only private / local ranges are allowed — no public internet scanning."""
    public = [ip for ip in ips if not is_private_ip(ip)]
    if public:
        raise ValueError(
            "Only private/local IPs are allowed "
            "(10.x, 172.16–31.x, 192.168.x, 127.x). "
            "Public internet scanning is disabled."
        )


async def check_port(ip: str, port: int, timeout: float) -> tuple[bool, float | None]:
    """Try to TCP-connect. Returns (is_open, latency_ms)."""
    start = time.perf_counter()
    try:
        # open_connection is the async version of a TCP handshake
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=timeout,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        ms = (time.perf_counter() - start) * 1000
        return True, round(ms, 2)
    except Exception:
        return False, None


async def is_host_alive(ip: str, timeout: float) -> tuple[bool, float | None]:
    """Host is 'alive' if any common probe port answers."""
    # Kick off probes together; first success wins
    tasks = [asyncio.create_task(check_port(ip, port, timeout)) for port in PROBE_PORTS]

    try:
        for coro in asyncio.as_completed(tasks):
            open_, latency = await coro
            if open_:
                for t in tasks:
                    t.cancel()
                return True, latency
        return False, None
    finally:
        for t in tasks:
            if not t.done():
                t.cancel()


async def discover_hosts(
    target: str,
    timeout: float = 0.5,
    concurrency: int = 100,
) -> list[dict]:
    """Scan a CIDR / IP and return which hosts look alive."""
    ips = expand_targets(target)
    assert_targets_allowed(ips)

    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def one(ip: str) -> None:
        async with sem:
            alive, latency = await is_host_alive(ip, timeout)
            if alive:
                results.append({"ip": ip, "alive": True, "latency_ms": latency})

    await asyncio.gather(*(one(ip) for ip in ips))
    results.sort(key=lambda r: ipaddress.ip_address(r["ip"]))
    return results


async def scan_ports(
    host: str,
    ports_text: str,
    timeout: float = 0.5,
    concurrency: int = 200,
) -> list[dict]:
    """Scan ports on one host. Returns open/closed for each port."""
    ips = expand_targets(host)
    if len(ips) != 1:
        raise ValueError("Port scan needs a single host IP, not a CIDR range")
    ip = ips[0]
    assert_targets_allowed([ip])

    ports = parse_ports(ports_text)
    sem = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def one(port: int) -> None:
        async with sem:
            open_, latency = await check_port(ip, port, timeout)
            results.append(
                {
                    "port": port,
                    "open": open_,
                    "latency_ms": latency,
                }
            )

    await asyncio.gather(*(one(p) for p in ports))
    results.sort(key=lambda r: r["port"])
    return results


def resolve_hostname(host: str) -> str:
    """If someone types a hostname, turn it into an IP when we can."""
    host = host.strip()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass

    try:
        return socket.gethostbyname(host)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {host}") from exc
