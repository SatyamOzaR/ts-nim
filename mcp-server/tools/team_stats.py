import httpx
from tools._config import backend_url, api_key


async def get_team_coverage_stats() -> list[dict]:
    """Return per-team-member network stats: contact count, avg strength, interactions."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/team-stats",
            headers={"X-API-Key": api_key},
        )
    resp.raise_for_status()
    return resp.json().get("results", [])
