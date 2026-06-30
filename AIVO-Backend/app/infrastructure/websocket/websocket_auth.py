"""WebSocket 认证"""

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import WebSocket

from app.core.security import decode_token

logger = logging.getLogger(__name__)


@dataclass
class AuthResult:
    ok: bool
    close_code: Optional[int] = 1008
    reason: str = "Unauthorized"


async def authorize_websocket(websocket: WebSocket, path_user_id: str, token: Optional[str]) -> AuthResult:
    """校验 WebSocket 连接"""
    raw_token = token or _first_query_param(websocket) or _first_header_token(websocket)
    if raw_token is None:
        return AuthResult(ok=False, close_code=1008, reason="Token required")

    normalized = raw_token.replace("Bearer ", "").replace("bearer ", "").strip()
    if not normalized:
        return AuthResult(ok=False, close_code=1008, reason="Token required")

    payload = decode_token(normalized)
    if payload is None:
        return AuthResult(ok=False, close_code=1008, reason="Invalid token")

    token_user_id = payload.get("sub")
    if token_user_id is None or str(token_user_id) != str(path_user_id):
        return AuthResult(ok=False, close_code=1008, reason="Token does not match user")

    return AuthResult(ok=True)


def _first_query_param(websocket: WebSocket) -> Optional[str]:
    try:
        query = websocket.query_params
        for key in ("token", "access_token", "authorization", "satoken"):
            value = query.get(key)
            if value:
                return value
    except Exception:
        pass
    return None


def _first_header_token(websocket: WebSocket) -> Optional[str]:
    try:
        for key in ("authorization", "Authorization", "token", "access_token"):
            value = websocket.headers.get(key)
            if value:
                return value
    except Exception:
        pass
    return None
