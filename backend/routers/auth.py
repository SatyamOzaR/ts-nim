import os

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, APIKeyQuery

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


async def verify_api_key(
    request: Request,
    header_key: str | None = Security(_api_key_header),
    query_key: str | None = Security(_api_key_query),
) -> str:
    expected = os.environ.get("API_KEY", "")
    if not expected:
        return "no-auth"

    key = header_key or query_key
    if not key or key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return key
