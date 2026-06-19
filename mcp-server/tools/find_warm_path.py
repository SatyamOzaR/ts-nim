import httpx

from tools._config import backend_url, api_key


async def find_warm_path(
    source_member: str, target_name: str, target_company: str = ""
) -> list[dict]:
    """Find warm introduction paths (multiple strategies) to a target contact."""
    params = {"source_member": source_member, "target_name": target_name}
    if target_company:
        params["target_company"] = target_company

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{backend_url}/api/graph/path",
            params=params,
            headers={"X-API-Key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("options", [])
