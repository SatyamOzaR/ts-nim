import httpx
from tools._config import backend_url, api_key


async def get_mutual_connections(target_a: str, target_b: str) -> list[dict]:
    """Return people connected to both target_a and target_b."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/mutual",
            params={"target_a": target_a, "target_b": target_b},
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json().get("results", [])
