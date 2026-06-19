from db.neo4j_client import run_query

# (id, label, description)
PATH_STRATEGIES: tuple[tuple[str, str, str], ...] = (
    (
        "shortest_hops",
        "Fewest introductions",
        "Minimizes the number of hops between you and the target.",
    ),
    (
        "strongest",
        "Strongest combined ties",
        "Maximizes the sum of relationship strength scores (up to 5 hops).",
    ),
    (
        "team_preferred",
        "Most teammate handoffs",
        "Prioritizes paths with more teammates as intermediaries.",
    ),
)

_PATH_RETURN = """
UNWIND range(0, length(path)) AS idx
WITH nodes(path)[idx] AS node,
     CASE WHEN idx > 0 THEN relationships(path)[idx - 1].strength ELSE null END AS edge_strength,
     idx AS step
RETURN step,
       node.full_name AS name,
       node.company AS company,
       node.role AS role,
       node.is_tsi_member AS is_member,
       edge_strength AS strength
"""


def _target_match(target_company: str | None) -> str:
    if target_company:
        return "(target:Person {full_name: $target_name, company: $target_company})"
    return "(target:Person {full_name: $target_name})"


def _base_params(
    source_member: str, target_name: str, target_company: str | None
) -> dict:
    p: dict = {"source_member": source_member, "target_name": target_name}
    if target_company:
        p["target_company"] = target_company
    return p


async def _run_path_query(cypher: str, params: dict) -> list[dict]:
    return await run_query(cypher, params)


async def _path_shortest_hops(
    target_match: str, params: dict, fuzzy: bool
) -> list[dict]:
    if fuzzy:
        cypher = f"""
        MATCH (target:Person)
        WHERE target.company = $target_company
          AND (toLower(target.full_name) CONTAINS toLower($target_name)
               OR toLower(target.role) CONTAINS toLower($target_name))
        WITH target LIMIT 1
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH path = shortestPath((source)-[:KNOWS*..5]-(target))
        WITH path,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength
        ORDER BY total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    else:
        cypher = f"""
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH {target_match}
        MATCH path = shortestPath((source)-[:KNOWS*..5]-(target))
        WITH path,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength
        ORDER BY total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    return await _run_path_query(cypher, params)


async def _path_strongest(
    target_match: str, params: dict, fuzzy: bool
) -> list[dict]:
    if fuzzy:
        cypher = f"""
        MATCH (target:Person)
        WHERE target.company = $target_company
          AND (toLower(target.full_name) CONTAINS toLower($target_name)
               OR toLower(target.role) CONTAINS toLower($target_name))
        WITH target LIMIT 1
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH path = (source)-[:KNOWS*1..5]-(target)
        WITH path, source, target,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength
        ORDER BY total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    else:
        cypher = f"""
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH {target_match}
        MATCH path = (source)-[:KNOWS*1..5]-(target)
        WITH path, source, target,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength
        ORDER BY total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    return await _run_path_query(cypher, params)


async def _path_team_preferred(
    target_match: str, params: dict, fuzzy: bool
) -> list[dict]:
    if fuzzy:
        cypher = f"""
        MATCH (target:Person)
        WHERE target.company = $target_company
          AND (toLower(target.full_name) CONTAINS toLower($target_name)
               OR toLower(target.role) CONTAINS toLower($target_name))
        WITH target LIMIT 1
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH path = (source)-[:KNOWS*1..5]-(target)
        WITH path, source, target,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength,
             size([n IN nodes(path)
                   WHERE n <> source AND n <> target AND coalesce(n.is_tsi_member, false) = true]) AS team_intermediates
        ORDER BY team_intermediates DESC, total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    else:
        cypher = f"""
        MATCH (source:Person {{is_tsi_member: true, full_name: $source_member}})
        MATCH {target_match}
        MATCH path = (source)-[:KNOWS*1..5]-(target)
        WITH path, source, target,
             reduce(s = 0.0, r IN relationships(path) | s + coalesce(r.strength, 0.0)) AS total_strength,
             size([n IN nodes(path)
                   WHERE n <> source AND n <> target AND coalesce(n.is_tsi_member, false) = true]) AS team_intermediates
        ORDER BY team_intermediates DESC, total_strength DESC
        LIMIT 1
        {_PATH_RETURN}
        """
    return await _run_path_query(cypher, params)


async def find_path_options(
    source_member: str, target_name: str, target_company: str | None = None
) -> list[dict]:
    """Return strategies that found a path: {id, label, description, path: [...]}."""
    if not source_member or not target_name:
        return []

    tm = _target_match(target_company)
    params = _base_params(source_member, target_name, target_company)

    runners = {
        "shortest_hops": _path_shortest_hops,
        "strongest": _path_strongest,
        "team_preferred": _path_team_preferred,
    }

    async def collect(fuzzy: bool) -> list[dict]:
        options: list[dict] = []
        for sid, label, desc in PATH_STRATEGIES:
            rows = await runners[sid](tm, params, fuzzy)
            if rows:
                options.append({"id": sid, "label": label, "description": desc, "path": rows})
        return options

    options = await collect(fuzzy=False)
    if not options and target_company:
        options = await collect(fuzzy=True)

    # Do not dedupe by route: the same nodes may be best for several strategies;
    # users still want to see "Most teammate handoffs" vs "Strongest ties" labels.
    return options


async def find_shortest_path(
    source_member: str, target_name: str, target_company: str | None = None
) -> list[dict]:
    """Backward compatible: first strategy path, or []."""
    opts = await find_path_options(source_member, target_name, target_company)
    if not opts:
        return []
    return opts[0]["path"]


async def search_graph(company: str | None = None, role: str | None = None) -> list[dict]:
    conditions = ["NOT p.is_tsi_member OR p.is_tsi_member = false"]
    params: dict = {}

    if company:
        conditions.append("toLower(p.company) CONTAINS toLower($company)")
        params["company"] = company
    if role:
        conditions.append("toLower(p.role) CONTAINS toLower($role)")
        params["role"] = role

    where = " AND ".join(conditions) if conditions else "true"

    cypher = f"""
    MATCH (p:Person)
    WHERE {where}
    OPTIONAL MATCH (member:Person {{is_tsi_member: true}})-[k:KNOWS]->(p)
    WITH p,
         collect(DISTINCT member.full_name) AS known_by,
         max(k.strength) AS best_strength
    RETURN p.full_name AS name,
           p.company AS company,
           p.role AS role,
           p.id AS person_id,
           coalesce(best_strength, 0.0) AS strength,
           known_by
    ORDER BY strength DESC
    LIMIT 50
    """
    return await run_query(cypher, params)


async def get_score_details(person_id: str) -> dict | None:
    from services.scoring_service import score_breakdown

    records = await run_query(
        """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p)
        WITH p, k, member
        ORDER BY k.strength DESC
        WITH p,
             collect(DISTINCT member.full_name) AS known_by,
             head(collect(k.connected_on)) AS connected_on,
             head(collect(k.last_interaction_at)) AS last_touch,
             sum(coalesce(k.interaction_count, 0)) AS interaction_count,
             count(DISTINCT member) AS shared_count,
             count(DISTINCT k.source_member) AS source_count
        RETURN p.full_name AS name,
               p.company AS company,
               p.role AS role,
               connected_on,
               last_touch,
               interaction_count,
               shared_count,
               source_count,
               known_by
        """,
        {"person_id": person_id},
    )
    if not records:
        return None

    r = records[0]
    breakdown = score_breakdown(
        r["connected_on"], r["role"], r["shared_count"], r["source_count"],
        interaction_count=r.get("interaction_count") or 0,
        last_touch=r.get("last_touch"),
    )
    def _fmt_date(d) -> str | None:
        if d is None:
            return None
        if hasattr(d, "to_native"):
            d = d.to_native()
        return str(d)

    return {
        "name": r["name"],
        "company": r["company"],
        "role": r["role"],
        "known_by": r["known_by"],
        "interaction_count": r.get("interaction_count") or 0,
        "last_touch": _fmt_date(r.get("last_touch")),
        **breakdown,
    }


async def top_contacts(
    source_member: str | None = None, limit: int = 10
) -> list[dict]:
    """Top contacts ranked by relationship strength, optionally filtered to one member."""
    conditions = ["NOT coalesce(p.is_tsi_member, false)"]
    params: dict = {"limit": limit}
    if source_member:
        conditions.append("member.full_name = $source_member")
        params["source_member"] = source_member
    where = " AND ".join(conditions)
    cypher = f"""
    MATCH (member:Person {{is_tsi_member: true}})-[k:KNOWS]->(p:Person)
    WHERE {where}
    WITH p,
         collect(DISTINCT member.full_name) AS known_by,
         max(coalesce(k.strength, 0.0)) AS best_strength,
         sum(coalesce(k.interaction_count, 0)) AS total_interactions,
         max(k.last_interaction_at) AS last_touch
    ORDER BY best_strength DESC
    LIMIT $limit
    RETURN p.full_name AS name, p.company AS company, p.role AS role, p.id AS person_id,
           best_strength AS strength, total_interactions AS interaction_count,
           last_touch, known_by
    """
    return await run_query(cypher, params)


async def stale_relationships(
    months: int = 12, source_member: str | None = None
) -> list[dict]:
    """Contacts with no recorded touch in the last N months (relationship gone cold)."""
    params: dict = {"cutoff_days": months * 30}
    member_filter = ""
    if source_member:
        member_filter = "AND member.full_name = $source_member"
        params["source_member"] = source_member
    cypher = f"""
    MATCH (member:Person {{is_tsi_member: true}})-[k:KNOWS]->(p:Person)
    WHERE NOT coalesce(p.is_tsi_member, false) {member_filter}
    WITH p,
         collect(DISTINCT member.full_name) AS known_by,
         max(coalesce(k.strength, 0.0)) AS best_strength,
         max(k.last_interaction_at) AS last_touch,
         max(k.connected_on) AS connected_on
    WHERE last_touch IS NULL
       OR duration.between(date(last_touch), date()).days > $cutoff_days
    ORDER BY best_strength DESC
    RETURN p.full_name AS name, p.company AS company, p.role AS role, p.id AS person_id,
           best_strength AS strength, known_by,
           toString(last_touch) AS last_touch, toString(connected_on) AS connected_on
    """
    return await run_query(cypher, params)


async def team_coverage_stats() -> list[dict]:
    """Per-member stats: connection count, avg strength, top companies."""
    cypher = """
    MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p:Person)
    WHERE NOT coalesce(p.is_tsi_member, false)
    WITH member,
         count(DISTINCT p) AS total_contacts,
         round(avg(coalesce(k.strength, 0.0)) * 1000) / 1000 AS avg_strength,
         sum(coalesce(k.interaction_count, 0)) AS total_interactions,
         collect(DISTINCT p.company)[0..5] AS top_companies
    RETURN member.full_name AS member_name,
           total_contacts, avg_strength, total_interactions, top_companies
    ORDER BY total_contacts DESC
    """
    return await run_query(cypher, {})


async def network_summary() -> dict:
    """High-level network health stats."""
    rows = await run_query(
        """
        MATCH (p:Person)
        WITH count(p) AS total_people,
             sum(CASE WHEN coalesce(p.is_tsi_member, false) THEN 1 ELSE 0 END) AS members,
             sum(CASE WHEN NOT coalesce(p.is_tsi_member, false) THEN 1 ELSE 0 END) AS contacts
        MATCH (a:Person {is_tsi_member: true})-[k:KNOWS]->(b:Person)
        RETURN total_people, members, contacts,
               count(k) AS total_edges,
               round(avg(coalesce(k.strength, 0.0)) * 1000) / 1000 AS avg_strength,
               sum(coalesce(k.interaction_count, 0)) AS total_interactions,
               count(DISTINCT b.company) AS companies_covered
        """,
        {},
    )

    strong_rows = await run_query(
        """
        MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p:Person)
        WHERE NOT coalesce(p.is_tsi_member, false)
        WITH p, max(coalesce(k.strength, 0.0)) AS s
        WHERE s >= 0.7
        RETURN count(p) AS strong_count
        """,
        {},
    )

    cold_rows = await run_query(
        """
        MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p:Person)
        WHERE NOT coalesce(p.is_tsi_member, false)
          AND (k.last_interaction_at IS NULL OR
               duration.between(date(k.last_interaction_at), date()).days > 365)
        RETURN count(DISTINCT p) AS cold_count
        """,
        {},
    )

    top_companies = await run_query(
        """
        MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p:Person)
        WHERE NOT coalesce(p.is_tsi_member, false) AND p.company IS NOT NULL
        WITH p.company AS company, count(DISTINCT p) AS depth
        ORDER BY depth DESC LIMIT 8
        RETURN company, depth
        """,
        {},
    )

    if not rows:
        return {}
    r = rows[0]
    return {
        **r,
        "strong_relationships": strong_rows[0]["strong_count"] if strong_rows else 0,
        "cold_relationships": cold_rows[0]["cold_count"] if cold_rows else 0,
        "top_companies": top_companies,
    }


async def mutual_connections(
    target_a: str, target_b: str
) -> list[dict]:
    """People who are connected to BOTH target_a and target_b (by name/company fragment)."""
    cypher = """
    MATCH (a:Person)
    WHERE toLower(a.full_name) CONTAINS toLower($target_a)
       OR toLower(a.company) CONTAINS toLower($target_a)
    WITH a LIMIT 3
    MATCH (b:Person)
    WHERE toLower(b.full_name) CONTAINS toLower($target_b)
       OR toLower(b.company) CONTAINS toLower($target_b)
    WITH a, b LIMIT 3
    MATCH (bridge:Person)-[:KNOWS]-(a)
    MATCH (bridge)-[:KNOWS]-(b)
    WHERE bridge <> a AND bridge <> b
    RETURN DISTINCT bridge.full_name AS name, bridge.company AS company,
           bridge.role AS role, bridge.id AS person_id,
           coalesce(bridge.is_tsi_member, false) AS is_member
    ORDER BY is_member DESC
    LIMIT 10
    """
    return await run_query(cypher, {"target_a": target_a, "target_b": target_b})


async def recent_additions(
    days: int = 30, source_member: str | None = None
) -> list[dict]:
    """Contacts connected or interacted with in the last N days."""
    params: dict = {"cutoff_days": days}
    member_filter = ""
    if source_member:
        member_filter = "AND member.full_name = $source_member"
        params["source_member"] = source_member
    cypher = f"""
    MATCH (member:Person {{is_tsi_member: true}})-[k:KNOWS]->(p:Person)
    WHERE NOT coalesce(p.is_tsi_member, false) {member_filter}
      AND (
        (k.last_interaction_at IS NOT NULL AND
         duration.between(date(k.last_interaction_at), date()).days <= $cutoff_days)
        OR
        (k.connected_on IS NOT NULL AND
         duration.between(date(k.connected_on), date()).days <= $cutoff_days)
      )
    WITH p,
         collect(DISTINCT member.full_name) AS known_by,
         max(coalesce(k.strength, 0.0)) AS strength,
         max(k.last_interaction_at) AS last_touch,
         max(k.connected_on) AS connected_on
    RETURN p.full_name AS name, p.company AS company, p.role AS role, p.id AS person_id,
           strength, known_by,
           toString(last_touch) AS last_touch, toString(connected_on) AS connected_on
    ORDER BY last_touch DESC, connected_on DESC
    """
    return await run_query(cypher, params)


async def get_full_graph() -> dict:
    nodes = await run_query(
        """
        MATCH (p:Person)
        OPTIONAL MATCH (member:Person {is_tsi_member: true})-[k:KNOWS]->(p)
        WITH p, max(coalesce(k.strength, 0)) AS strength
        RETURN p.id AS id,
               p.full_name AS label,
               p.company AS company,
               p.role AS role,
               coalesce(p.is_tsi_member, false) AS is_member,
               strength
        ORDER BY strength DESC
        LIMIT 500
        """
    )

    edges = await run_query(
        """
        MATCH (a:Person)-[k:KNOWS]->(b:Person)
        WHERE a.id IN $ids AND b.id IN $ids
        RETURN a.id AS source,
               b.id AS target,
               coalesce(k.strength, 0.0) AS strength,
               k.source_member AS source_member,
               coalesce(k.interaction_count, 0) AS interaction_count,
               coalesce(k.sources, []) AS sources
        """,
        {"ids": [n["id"] for n in nodes]},
    )

    return {"nodes": nodes, "edges": edges}
