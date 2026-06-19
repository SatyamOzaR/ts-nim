import httpx

from tools._config import backend_url, api_key


async def score_relationship_strength(person_id: str) -> dict:
    """Get detailed relationship strength score for a contact."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/score",
            params={"person_id": person_id},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()
