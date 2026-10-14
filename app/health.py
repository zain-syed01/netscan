"""
Quick system health snapshot.

Shows how the machine (or container) running NetScan is doing —
CPU, memory, disk, uptime. Nothing fancy, just useful numbers.
"""

from __future__ import annotations

import platform
import socket
import time
from datetime import timedelta

import psutil


def _bytes_to_gb(num: int) -> float:
    return round(num / (1024**3), 2)


def get_health() -> dict:
    """Gather a one-shot health report."""
    # First call to cpu_percent can return 0.0; a tiny sleep makes it real.
    psutil.cpu_percent(interval=None)
    time.sleep(0.15)
    cpu = psutil.cpu_percent(interval=None)

    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    boot = psutil.boot_time()
    uptime_seconds = int(time.time() - boot)

    load = None
    try:
        # loadavg is a Linux/mac thing; Windows will skip it
        load = [round(x, 2) for x in psutil.getloadavg()]
    except (AttributeError, OSError):
        load = None

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "cpu_percent": cpu,
        "cpu_count": psutil.cpu_count(logical=True),
        "memory": {
            "used_gb": _bytes_to_gb(mem.used),
            "total_gb": _bytes_to_gb(mem.total),
            "percent": mem.percent,
        },
        "disk": {
            "used_gb": _bytes_to_gb(disk.used),
            "total_gb": _bytes_to_gb(disk.total),
            "percent": disk.percent,
        },
        "load_average": load,
        "uptime_seconds": uptime_seconds,
        "uptime_human": str(timedelta(seconds=uptime_seconds)),
    }
