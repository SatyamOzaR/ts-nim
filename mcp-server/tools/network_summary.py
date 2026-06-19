import httpx
from tools._config import backend_url, api_key


async def get_network_summary() -> dict:
    """Return overall network health stats: totals, coverage, strong vs cold relationships."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/summary",
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json()
