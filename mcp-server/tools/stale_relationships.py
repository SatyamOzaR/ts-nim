import httpx
from tools._config import backend_url, api_key


async def get_stale_relationships(months: int = 12, source_member: str = "") -> list[dict]:
    """Return contacts with no recorded touch in the last N months."""
    params: dict = {"months": months}
    if source_member:
        params["source_member"] = source_member
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/stale",
            params=params,
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json().get("results", [])
