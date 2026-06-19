import httpx

from tools._config import backend_url, api_key


async def import_linkedin_connections(member_name: str, csv_content: str) -> dict:
    """Import LinkedIn connections CSV for a team member."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{backend_url}/api/connections/import",
            data={"member_name": member_name},
            files={"file": ("connections.csv", csv_content.encode(), "text/csv")},
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        return resp.json()
