"""
FastAPI web app for NetScan.

Run locally:
  uvicorn app.main:app --host 0.0.0.0 --port 8765
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.health import get_health
from app.models import HostScanRequest, PortScanRequest
from app.scanner import discover_hosts, resolve_hostname, scan_ports

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(
    title="NetScan",
    description="Simple IP discovery, port scanner, and system health",
    version="1.0.0",
)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/healthz")
async def healthz() -> dict:
    # Tiny probe for Docker / Kubernetes
    return {"status": "ok"}


@app.get("/api/health")
async def api_health() -> dict:
    return get_health()


@app.post("/api/scan/hosts")
async def api_scan_hosts(body: HostScanRequest) -> dict:
    try:
        results = await discover_hosts(
            body.target,
            timeout=body.timeout,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "target": body.target,
        "alive_count": len(results),
        "hosts": results,
    }


@app.post("/api/scan/ports")
async def api_scan_ports(body: PortScanRequest) -> dict:
    try:
        ip = resolve_hostname(body.host)
        results = await scan_ports(
            ip,
            body.ports,
            timeout=body.timeout,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    open_ports = [r for r in results if r["open"]]
    return {
        "host": body.host,
        "resolved_ip": ip,
        "open_count": len(open_ports),
        "checked": len(results),
        "ports": results,
    }
