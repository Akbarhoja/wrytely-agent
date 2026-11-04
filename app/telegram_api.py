"""Private Telegram setup and secret-authenticated bounded inbound assembly."""

import json
import re
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.course_supervision_api import SupervisionRoute
from app.private_artifact_api import _queries
from app.source_connections import StrictBody
from contracts.models import Identity
from integrations.telegram import bot_id_for_token, parse_update, verify_webhook
from shared.db import QueueFull, RequestConflict, Store


class TelegramPreferences(StrictBody):
    consent: bool
    notification_consent: bool
    timezone: str = Field(min_length=1, max_length=100)
    quiet_start: int = Field(ge=0, le=23)
    quiet_end: int = Field(ge=0, le=23)

    @field_validator("timezone")
    @classmethod
    def timezone_valid(cls, value):
        try:
            ZoneInfo(value)
        except (KeyError, ValueError):
            raise ValueError("Invalid timezone") from None
        return value


def register_telegram(api, *, settings, identity_dependency, database_dependency):
    User = Annotated[Identity, Depends(identity_dependency)]
    DB = Annotated[Store, Depends(database_dependency)]
    router = APIRouter(prefix="/v1/telegram", route_class=SupervisionRoute)

    def configured_bot():
        try:
            return bot_id_for_token(settings.telegram_bot_token.get_secret_value())
        except (AttributeError, ValueError):
            raise HTTPException(503, "Telegram is not configured") from None

    def username():
        name = settings.telegram_bot_username
        return name if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_]{5,32}", name) else None

    @router.get("")
    def status(request: Request, user: User, db: DB):
        _queries(request, set())
        return {
            **db.telegram_connection(user.user_id, configured_bot()),
            "bot_username": username(),
        }

    @router.post("/link")
    async def link(request: Request, user: User, db: DB):
        _queries(request, set())
        if await request.body():
            raise ValueError("No link parameters")
        row = await run_in_threadpool(db.create_telegram_challenge, user.user_id, configured_bot())
        return {**row, "bot_username": username()}

    @router.post("/preferences")
    def preferences(body: TelegramPreferences, request: Request, user: User, db: DB):
        _queries(request, set())
        return db.set_telegram_preferences(user.user_id, configured_bot(), **body.model_dump())

    @router.post("/unlink")
    async def unlink(request: Request, user: User, db: DB):
        _queries(request, set())
        if await request.body():
            raise ValueError("No unlink parameters")
        await run_in_threadpool(db.unlink_telegram, user.user_id, configured_bot())
        return {"linked": False}

    api.include_router(router)

    @api.post("/webhooks/telegram")
    async def callback(request: Request):
        def result(status, body):
            return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})

        supplied = request.headers.getlist("x-telegram-bot-api-secret-token")
        secret = settings.telegram_webhook_secret
        if not secret:
            return result(503, {"detail": "Telegram is not configured"})
        if len(supplied) != 1 or not verify_webhook(secret.get_secret_value(), supplied[0]):
            return result(401, {"detail": "Invalid Telegram authentication"})
        try:
            bot = configured_bot()
            if request.query_params:
                return result(400, {"detail": "Invalid callback"})
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > 65536:
                    return result(413, {"detail": "Callback too large"})
                body.extend(chunk)
            if (
                request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                != "application/json"
            ):
                return result(415, {"detail": "Use application/json"})
            event = parse_update(json.loads(body))
            state = (
                "ignored"
                if event is None
                else await run_in_threadpool(database_dependency().ingest_telegram, bot, event)
            )
            return result(200, {"state": state})
        except RequestConflict:
            return result(409, {"detail": "Update conflict"})
        except QueueFull:
            return result(409, {"detail": "Queue full"})
        except (ValueError, UnicodeError):
            return result(400, {"detail": "Invalid callback"})
        except HTTPException as exc:
            return result(exc.status_code, {"detail": "Telegram unavailable"})
        except Exception:
            return result(503, {"detail": "Telegram unavailable"})
