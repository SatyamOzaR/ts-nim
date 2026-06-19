import httpx
from tools._config import backend_url, api_key


async def get_top_contacts(source_member: str = "", limit: int = 10) -> list[dict]:
    """Return the strongest relationships in the network ranked by score."""
    params: dict = {"limit": limit}
    if source_member:
        params["source_member"] = source_member
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/top-contacts",
            params=params,
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json().get("results", [])
