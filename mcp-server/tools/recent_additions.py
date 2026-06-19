import httpx
from tools._config import backend_url, api_key


async def get_recent_additions(days: int = 30, source_member: str = "") -> list[dict]:
    """Return contacts connected or interacted with in the last N days."""
    params: dict = {"days": days}
    if source_member:
        params["source_member"] = source_member
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/recent",
            params=params,
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json().get("results", [])
