"""Request and response shapes used by the API and CLI."""

from pydantic import BaseModel, Field


class HostScanRequest(BaseModel):
    # Example: 192.168.1.0/24 or 127.0.0.1
    target: str = Field(..., min_length=1)
    timeout: float = Field(0.5, ge=0.1, le=10.0)
    allow_public: bool = False


class PortScanRequest(BaseModel):
    host: str = Field(..., min_length=1)
    # "22,80,443" or "1-1024"
    ports: str = Field("22,80,443,8080,8765")
    timeout: float = Field(0.5, ge=0.1, le=10.0)
    allow_public: bool = False


class HostResult(BaseModel):
    ip: str
    alive: bool
    latency_ms: float | None = None


class PortResult(BaseModel):
    port: int
    open: bool
    latency_ms: float | None = None
