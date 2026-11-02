"""Maintenance gate: an exclusive operation (a restore) runs only with no other request in flight.

New requests get 503 while it runs, so nobody observes a half-restored database or folder.
"""

import threading
from contextlib import contextmanager

from fastapi import HTTPException
from fastapi.responses import JSONResponse

MESSAGE = "Sistema em manutenção (restauração em andamento). Tente novamente em instantes."


class MaintenanceGate:
    def __init__(self, timeout: float = 30):
        self.condition = threading.Condition()
        self.active = 0
        self.maintenance = False
        self.timeout = timeout

    def enter(self) -> bool:
        with self.condition:
            if self.maintenance:
                return False
            self.active += 1
            return True

    def leave(self):
        with self.condition:
            self.active -= 1
            self.condition.notify_all()

    @contextmanager
    def exclusive(self, held: int = 0):
        """`held` is how many in-flight requests belong to the caller (its own request)."""
        with self.condition:
            if self.maintenance:
                raise HTTPException(409, "Já existe uma restauração em andamento.")
            self.maintenance = True
            if not self.condition.wait_for(lambda: self.active <= held, self.timeout):
                self.maintenance = False
                raise HTTPException(
                    409,
                    "Há operações em andamento no sistema. Nada foi alterado; "
                    "tente restaurar novamente em instantes.",
                )
        try:
            yield
        finally:
            with self.condition:
                self.maintenance = False


class MaintenanceMiddleware:
    """Pure ASGI so a request counts as in flight until its whole body has been sent."""

    def __init__(self, app, gate: MaintenanceGate):
        self.app = app
        self.gate = gate

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        admitted = self.gate.enter()
        if not admitted and scope["path"] != "/health":
            response = JSONResponse(
                {"detail": MESSAGE}, status_code=503, headers={"Retry-After": "5"}
            )
            return await response(scope, receive, send)
        try:
            await self.app(scope, receive, send)
        finally:
            if admitted:
                self.gate.leave()
