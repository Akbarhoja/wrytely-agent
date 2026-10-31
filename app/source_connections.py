"""Bounded HTTP assembly for the existing Canvas credential lifecycle."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.exceptions import HTTPException as StarletteHTTPException

from contracts.models import Identity
from shared.db import Store
from shared.source_connections import PairingLimited, PairingRejected, SourceCredentialRejected

BODY_LIMIT = 16 * 1024


class CanvasRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            try:
                body = bytearray()
                async for chunk in request.stream():
                    if len(body) + len(chunk) > BODY_LIMIT:
                        raise HTTPException(413, "Canvas request too large")
                    body.extend(chunk)
                if (
                    body
                    and request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    raise HTTPException(415, "Use application/json")
                replayed = False

                async def receive():
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await request.receive()

                response = await handler(Request(request.scope, receive=receive))
            except RequestValidationError:
                response = JSONResponse(
                    status_code=422, content={"detail": "Invalid Canvas request"}
                )
            except StarletteHTTPException as exc:
                response = JSONResponse(
                    status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return bounded


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class PairingIn(StrictBody):
    origin: str = Field(min_length=1, max_length=2048)


class RedeemIn(StrictBody):
    code: SecretStr
    device_public_id: str = Field(min_length=1, max_length=128)


class BindIn(PairingIn):
    provider_subject: str = Field(min_length=1, max_length=1024)


def register_source_connections(api, *, identity_dependency, database_dependency, canvas_origins):
    router = APIRouter(prefix="/v1/source-connections", route_class=CanvasRoute)
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]
    Credential = Annotated[
        HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))
    ]

    def enabled():
        if not canvas_origins:
            raise HTTPException(503, "Canvas pairing is not configured")

    @router.post("/canvas/pairing")
    def pairing(body: PairingIn, user: User, db: DB):
        enabled()
        try:
            return db.create_pairing(user.user_id, body.origin)
        except PairingLimited:
            raise HTTPException(429, "Pairing rate limited") from None
        except ValueError:
            raise HTTPException(422, "Canvas origin unavailable") from None
        except LookupError:
            raise HTTPException(409, "Complete setup first") from None

    @router.post("/canvas/redeem")
    def redeem(body: RedeemIn, db: DB):
        enabled()
        try:
            return db.redeem_pairing(body.code.get_secret_value(), body.device_public_id)
        except PairingLimited:
            raise HTTPException(429, "Pairing rate limited") from None
        except PairingRejected:
            raise HTTPException(400, "Invalid pairing") from None

    @router.post("/canvas/bind")
    def bind(body: BindIn, credentials: Credential, db: DB):
        enabled()
        try:
            if credentials is None:
                raise SourceCredentialRejected()
            return db.bind_canvas_identity(
                credentials.credentials, body.origin, body.provider_subject
            )
        except SourceCredentialRejected:
            raise HTTPException(
                401, "Reconnect Canvas", headers={"WWW-Authenticate": "Bearer"}
            ) from None
        except ValueError:
            raise HTTPException(422, "Invalid Canvas request") from None

    @router.get("/{connection_id}")
    def read(connection_id: str, user: User, db: DB):
        result = db.source_connection(user.user_id, connection_id)
        if result is None:
            raise HTTPException(404, "Not found")
        return result

    @router.post("/{connection_id}/revoke")
    def revoke(connection_id: str, user: User, db: DB, body: StrictBody | None = None):
        try:
            return db.rotate_or_revoke(user.user_id, connection_id)
        except LookupError:
            raise HTTPException(404, "Not found") from None

    api.include_router(router)
