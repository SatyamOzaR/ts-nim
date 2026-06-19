import httpx

from tools._config import backend_url, api_key


async def search_by_company_or_role(
    company: str = "", role: str = ""
) -> list[dict]:
    """Search the network for contacts by company and/or role."""
    params = {}
    if company:
        params["company"] = company
    if role:
        params["role"] = role

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/search",
            params=params,
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
