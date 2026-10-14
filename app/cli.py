"""
Command-line entrypoint.

Examples:
  python -m app.cli hosts --target 127.0.0.1
  python -m app.cli ports --host 127.0.0.1 --ports 22,80,443,8765
  python -m app.cli health
"""

from __future__ import annotations

import asyncio
import json

import click

from app.health import get_health
from app.scanner import discover_hosts, resolve_hostname, scan_ports


@click.group()
def cli() -> None:
    """NetScan — IP discovery, port scan, and system health."""


@cli.command("hosts")
@click.option("--target", required=True, help="IP or CIDR, e.g. 192.168.1.0/24")
@click.option("--timeout", default=0.5, show_default=True, type=float)
@click.option("--allow-public", is_flag=True, help="Allow non-private IPs (use carefully)")
def hosts_cmd(target: str, timeout: float, allow_public: bool) -> None:
    """Find live hosts on a network range."""
    try:
        results = asyncio.run(
            discover_hosts(target, timeout=timeout, allow_public=allow_public)
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    if not results:
        click.echo("No live hosts found.")
        return

    click.echo(f"Found {len(results)} live host(s):")
    for row in results:
        ms = f"{row['latency_ms']} ms" if row["latency_ms"] is not None else "?"
        click.echo(f"  {row['ip']:15}  alive  ({ms})")


@cli.command("ports")
@click.option("--host", required=True, help="Single IP or hostname")
@click.option("--ports", default="22,80,443,8080,8765", show_default=True)
@click.option("--timeout", default=0.5, show_default=True, type=float)
@click.option("--allow-public", is_flag=True)
@click.option("--show-closed", is_flag=True, help="Also print closed ports")
def ports_cmd(
    host: str,
    ports: str,
    timeout: float,
    allow_public: bool,
    show_closed: bool,
) -> None:
    """Scan TCP ports on one host."""
    try:
        ip = resolve_hostname(host)
        results = asyncio.run(
            scan_ports(ip, ports, timeout=timeout, allow_public=allow_public)
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    open_ports = [r for r in results if r["open"]]
    click.echo(f"Scan of {ip} — {len(open_ports)} open / {len(results)} checked")

    for row in results:
        if row["open"]:
            ms = f"{row['latency_ms']} ms" if row["latency_ms"] is not None else "?"
            click.echo(f"  port {row['port']:<5}  OPEN   ({ms})")
        elif show_closed:
            click.echo(f"  port {row['port']:<5}  closed")


@cli.command("health")
@click.option("--json-out", is_flag=True, help="Print raw JSON")
def health_cmd(json_out: bool) -> None:
    """Show CPU, memory, disk, and uptime."""
    data = get_health()
    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    click.echo(f"Host:     {data['hostname']}")
    click.echo(f"Platform: {data['platform']}")
    click.echo(f"CPU:      {data['cpu_percent']}%  ({data['cpu_count']} cores)")
    mem = data["memory"]
    click.echo(f"Memory:   {mem['used_gb']} / {mem['total_gb']} GB  ({mem['percent']}%)")
    disk = data["disk"]
    click.echo(f"Disk:     {disk['used_gb']} / {disk['total_gb']} GB  ({disk['percent']}%)")
    if data["load_average"]:
        click.echo(f"Load:     {data['load_average']}")
    click.echo(f"Uptime:   {data['uptime_human']}")


if __name__ == "__main__":
    cli()
