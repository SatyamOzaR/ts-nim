from fastapi import APIRouter, Depends, HTTPException

from routers.auth import verify_api_key
from services.graph_service import (
    find_path_options,
    get_full_graph,
    get_score_details,
    mutual_connections,
    network_summary,
    recent_additions,
    search_graph,
    stale_relationships,
    team_coverage_stats,
    top_contacts,
)

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/path")
async def graph_path(
    source_member: str,
    target_name: str,
    target_company: str | None = None,
    _key: str = Depends(verify_api_key),
):
    options = await find_path_options(source_member, target_name, target_company)
    if not options:
        raise HTTPException(status_code=404, detail="No path found")
    return {"options": options, "path": options[0]["path"]}


@router.get("/search")
async def graph_search(
    company: str | None = None,
    role: str | None = None,
    _key: str = Depends(verify_api_key),
):
    results = await search_graph(company, role)
    return {"results": results}


@router.get("/score")
async def graph_score(
    person_id: str,
    _key: str = Depends(verify_api_key),
):
    details = await get_score_details(person_id)
    if not details:
        raise HTTPException(status_code=404, detail="Person not found")
    return details


@router.get("/top-contacts")
async def graph_top_contacts(
    source_member: str | None = None,
    limit: int = 10,
    _key: str = Depends(verify_api_key),
):
    return {"results": await top_contacts(source_member, limit)}


@router.get("/stale")
async def graph_stale(
    months: int = 12,
    source_member: str | None = None,
    _key: str = Depends(verify_api_key),
):
    return {"results": await stale_relationships(months, source_member)}


@router.get("/team-stats")
async def graph_team_stats(_key: str = Depends(verify_api_key)):
    return {"results": await team_coverage_stats()}


@router.get("/summary")
async def graph_summary(_key: str = Depends(verify_api_key)):
    return await network_summary()


@router.get("/mutual")
async def graph_mutual(
    target_a: str,
    target_b: str,
    _key: str = Depends(verify_api_key),
):
    return {"results": await mutual_connections(target_a, target_b)}


@router.get("/recent")
async def graph_recent(
    days: int = 30,
    source_member: str | None = None,
    _key: str = Depends(verify_api_key),
):
    return {"results": await recent_additions(days, source_member)}


@router.get("/all")
async def graph_all(_key: str = Depends(verify_api_key)):
    return await get_full_graph()
