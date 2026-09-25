from __future__ import annotations

import asyncio
import time
from typing import Optional

from app.pinger import PingOutcome, validate_host


def _status_name(value: int) -> str:
    return {0: "UNKNOWN", 1: "SERVING", 2: "NOT_SERVING", 3: "SERVICE_UNKNOWN"}.get(value, str(value))


def _check_sync(target: str, service: str, timeout: float) -> PingOutcome:
    try:
        import grpc
        from grpc_health.v1 import health_pb2, health_pb2_grpc
    except ImportError:
        return PingOutcome(False, None, "gRPC support is not installed")
    started = time.perf_counter()
    channel = grpc.insecure_channel(target)
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        stub = health_pb2_grpc.HealthStub(channel)
        response = stub.Check(
            health_pb2.HealthCheckRequest(service=service or ""),
            timeout=timeout,
        )
        rtt = round((time.perf_counter() - started) * 1000.0, 2)
        if response.status == health_pb2.HealthCheckResponse.SERVING:
            return PingOutcome(True, rtt, None)
        return PingOutcome(False, None, "gRPC health is %s" % _status_name(int(response.status)))
    except Exception as exc:
        return PingOutcome(False, None, str(exc)[:200] or "gRPC health check failed")
    finally:
        channel.close()


async def check_grpc(
    host: str,
    port: int,
    *,
    service: Optional[str] = None,
    timeout: float = 2.0,
) -> PingOutcome:
    host = validate_host(host)
    target = "%s:%s" % (host, port)
    name = (service or "").strip()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _check_sync, target, name, timeout)
