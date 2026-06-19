import os

from mcp.server.fastmcp import FastMCP

from tools.import_connections import import_linkedin_connections
from tools.find_warm_path import find_warm_path
from tools.score_relationship import score_relationship_strength
from tools.search_graph import search_by_company_or_role
from tools.top_contacts import get_top_contacts
from tools.stale_relationships import get_stale_relationships
from tools.team_stats import get_team_coverage_stats
from tools.network_summary import get_network_summary
from tools.mutual_connections import get_mutual_connections
from tools.recent_additions import get_recent_additions

mcp_port = int(os.environ.get("PORT", "8001"))
mcp = FastMCP("Network Intelligence", host="0.0.0.0", port=mcp_port)

expected_api_key = os.environ.get("API_KEY", "")


@mcp.tool()
async def import_connections(member_name: str, csv_content: str) -> str:
    """Import LinkedIn connections CSV for a team member.

    Args:
        member_name: Full name of the TSI team member whose connections are being imported
        csv_content: Raw CSV text content from LinkedIn data export
    """
    result = await import_linkedin_connections(member_name, csv_content)
    return (
        f"Imported {result.get('imported', 0)} new contacts, "
        f"merged {result.get('merged', 0)} existing. "
        f"{result.get('message', '')}"
    )


@mcp.tool()
async def warm_path(
    source_member: str, target_name: str, target_company: str = ""
) -> str:
    """Find the shortest warm introduction path from a team member to a target contact.

    Args:
        source_member: Full name of the TSI team member starting the path
        target_name: Name of the target person to reach
        target_company: Company the target works at (optional but helps narrow results)
    """
    options = await find_warm_path(source_member, target_name, target_company)
    if not options:
        return f"No warm path found to {target_name}" + (
            f" at {target_company}" if target_company else ""
        )

    blocks: list[str] = []
    for opt in options:
        label = opt.get("label", opt.get("id", "Path"))
        desc = opt.get("description", "")
        header = f"=== {label} ===" + (f"\n{desc}" if desc else "")
        blocks.append(header)
        for step in opt.get("path") or []:
            strength = step.get("strength")
            badge = f" (strength: {strength:.2f})" if strength else ""
            member_tag = " [TSI]" if step.get("is_member") else ""
            blocks.append(
                f"  Step {step['step']}: {step['name']}{member_tag} — "
                f"{step.get('role', 'N/A')} at {step.get('company', 'N/A')}{badge}"
            )
        blocks.append("")
    return "\n".join(blocks).strip()


@mcp.tool()
async def score_relationship(person_id: str) -> str:
    """Get detailed relationship strength score breakdown for a specific contact.

    Args:
        person_id: The unique person ID slug (e.g., john_smith_barclays)
    """
    details = await score_relationship_strength(person_id)
    return (
        f"Contact: {details.get('name', 'Unknown')} at {details.get('company', 'Unknown')}\n"
        f"Role: {details.get('role', 'N/A')}\n"
        f"Overall Strength: {details.get('overall', 0):.2f}\n"
        f"  Recency: {details.get('recency', 0):.2f}\n"
        f"  Seniority: {details.get('seniority', 0):.2f}\n"
        f"  Shared Connections: {details.get('shared_connections', 0)}\n"
        f"  Source Diversity: {'Yes' if details.get('source_diversity') else 'No'}\n"
        f"Known by: {', '.join(details.get('known_by', []))}"
    )


@mcp.tool()
async def search_network(company: str = "", role: str = "") -> str:
    """Search the network for contacts by company name and/or role/title.

    Args:
        company: Company name to search for (optional)
        role: Role or title to search for (optional)
    """
    results = await search_by_company_or_role(company, role)
    if not results:
        return "No contacts found matching your criteria."

    lines = [f"Found {len(results)} contacts:\n"]
    for r in results:
        known = ", ".join(r.get("known_by", []))
        lines.append(
            f"- {r['name']} — {r.get('role', 'N/A')} at {r.get('company', 'N/A')} "
            f"(strength: {r.get('strength', 0):.2f}, known by: {known})"
        )
    return "\n".join(lines)


@mcp.tool()
async def top_relationships(source_member: str = "", limit: int = 10) -> str:
    """List the strongest relationships in the network ranked by score.

    Args:
        source_member: Filter to one TSI team member's relationships (optional)
        limit: Number of contacts to return (default 10)
    """
    results = await get_top_contacts(source_member, limit)
    if not results:
        return "No contacts found."
    lines = [f"Top {len(results)} relationships:\n"]
    for r in results:
        known = ", ".join(r.get("known_by", []))
        interactions = r.get("interaction_count", 0)
        last = r.get("last_touch") or "—"
        lines.append(
            f"- {r['name']} ({r.get('role','N/A')} @ {r.get('company','N/A')}) "
            f"strength: {r.get('strength', 0):.2f}, interactions: {interactions}, "
            f"last touch: {last}, known by: {known}"
        )
    return "\n".join(lines)


@mcp.tool()
async def cold_relationships(months: int = 12, source_member: str = "") -> str:
    """Find relationships that have gone cold — no interaction in the last N months.

    Args:
        months: Months of inactivity to flag as stale (default 12)
        source_member: Filter to one team member (optional)
    """
    results = await get_stale_relationships(months, source_member)
    if not results:
        return f"No stale relationships found (>{months} months inactive). Great coverage!"
    lines = [f"{len(results)} relationships inactive for >{months} months:\n"]
    for r in results:
        known = ", ".join(r.get("known_by", []))
        last = r.get("last_touch") or "never"
        lines.append(
            f"- {r['name']} ({r.get('role','N/A')} @ {r.get('company','N/A')}) "
            f"strength: {r.get('strength', 0):.2f}, last touch: {last}, known by: {known}"
        )
    return "\n".join(lines)


@mcp.tool()
async def team_coverage() -> str:
    """Show per-team-member network stats: connection count, avg strength, total interactions."""
    results = await get_team_coverage_stats()
    if not results:
        return "No team member data found."
    lines = ["Team coverage breakdown:\n"]
    for r in results:
        companies = ", ".join(r.get("top_companies", []))
        lines.append(
            f"- {r['member_name']}: {r.get('total_contacts', 0)} contacts, "
            f"avg strength: {r.get('avg_strength', 0):.2f}, "
            f"interactions: {r.get('total_interactions', 0)}, "
            f"top companies: {companies or '—'}"
        )
    return "\n".join(lines)


@mcp.tool()
async def network_health() -> str:
    """Overall network health dashboard: totals, company coverage, strong vs cold relationships."""
    d = await get_network_summary()
    if not d:
        return "No network data available."
    top = "\n".join(
        f"  {r['company']}: {r['depth']} contacts"
        for r in d.get("top_companies", [])
    )
    return (
        f"Network Summary\n"
        f"  Total contacts: {d.get('contacts', 0)}\n"
        f"  TSI members: {d.get('members', 0)}\n"
        f"  Companies covered: {d.get('companies_covered', 0)}\n"
        f"  Total relationship edges: {d.get('total_edges', 0)}\n"
        f"  Avg relationship strength: {d.get('avg_strength', 0):.2f}\n"
        f"  Strong relationships (≥0.7): {d.get('strong_relationships', 0)}\n"
        f"  Cold relationships (>12mo): {d.get('cold_relationships', 0)}\n"
        f"  Total recorded interactions: {d.get('total_interactions', 0)}\n"
        f"\nDeepest company coverage:\n{top}"
    )


@mcp.tool()
async def bridges_between(target_a: str, target_b: str) -> str:
    """Find people connected to both of two targets — useful to bridge two companies or people.

    Args:
        target_a: First person name or company fragment
        target_b: Second person name or company fragment
    """
    results = await get_mutual_connections(target_a, target_b)
    if not results:
        return f"No mutual connections found between '{target_a}' and '{target_b}'."
    lines = [f"People connected to both '{target_a}' and '{target_b}':\n"]
    for r in results:
        member_tag = " [TSI]" if r.get("is_member") else ""
        lines.append(
            f"- {r['name']}{member_tag} — {r.get('role','N/A')} @ {r.get('company','N/A')}"
        )
    return "\n".join(lines)


@mcp.tool()
async def recent_activity(days: int = 30, source_member: str = "") -> str:
    """List contacts added or interacted with in the last N days.

    Args:
        days: Lookback window in days (default 30)
        source_member: Filter to one team member (optional)
    """
    results = await get_recent_additions(days, source_member)
    if not results:
        return f"No recent activity in the last {days} days."
    lines = [f"{len(results)} contacts active in the last {days} days:\n"]
    for r in results:
        known = ", ".join(r.get("known_by", []))
        touch = r.get("last_touch") or r.get("connected_on") or "—"
        lines.append(
            f"- {r['name']} ({r.get('role','N/A')} @ {r.get('company','N/A')}) "
            f"last touch: {touch}, known by: {known}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run(transport="sse")
