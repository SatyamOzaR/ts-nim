import csv
import io
import logging
from datetime import datetime

from slugify import slugify

from db.neo4j_client import get_driver

logger = logging.getLogger(__name__)

DATE_FORMATS = ["%d %b %Y", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]


def _parse_date(raw: str) -> str | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _make_id(first: str, last: str, company: str) -> str:
    return slugify(f"{first}_{last}_{company}", separator="_")


async def _ensure_member(session, member_name: str) -> None:
    await session.run(
        "MERGE (m:Person {full_name: $name}) "
        "ON CREATE SET m.id = $id, m.is_tsi_member = true, "
        "m.first_name = $first, m.last_name = $last",
        {
            "name": member_name,
            "id": slugify(member_name, separator="_"),
            "first": member_name.split()[0] if " " in member_name else member_name,
            "last": member_name.split()[-1] if " " in member_name else "",
        },
    )


# ---------------------------------------------------------------------------
# Primitive: upsert a single contact (LLM-callable)
# ---------------------------------------------------------------------------

async def upsert_contact(
    member_name: str,
    first_name: str,
    last_name: str,
    company: str,
    role: str = "",
    connected_on: str = "",
    email: str = "",
) -> str:
    """Add or merge a contact into the graph. Returns 'imported' or 'merged'."""
    if not first_name or not last_name or not company:
        return "skipped"

    parsed_date = _parse_date(connected_on) or "2020-01-01"
    person_id = _make_id(first_name, last_name, company)
    full_name = f"{first_name} {last_name}"

    driver = await get_driver()
    async with driver.session() as session:
        await _ensure_member(session, member_name)

        result = await session.run(
            """
            MERGE (p:Person {id: $id})
            ON CREATE SET
                p.first_name = $first_name,
                p.last_name = $last_name,
                p.full_name = $full_name,
                p.company = $company,
                p.role = $role,
                p.email = $email,
                p.is_tsi_member = false
            ON MATCH SET
                p.role = CASE WHEN $role <> '' THEN $role ELSE p.role END,
                p.email = CASE WHEN $email <> '' THEN $email ELSE p.email END
            WITH p,
                 CASE WHEN p.is_tsi_member IS NULL THEN false ELSE p.is_tsi_member END AS existed
            MERGE (c:Company {name: $company})
            MERGE (p)-[:WORKS_AT {role: $role, is_current: true}]->(c)
            WITH p, existed
            MATCH (m:Person {full_name: $member_name})
            MERGE (m)-[k:KNOWS]->(p)
            ON CREATE SET
                k.source_member = $member_name,
                k.connected_on = date($connected_on),
                k.shared_connection_count = 1,
                k.sources = ['linkedin'],
                k.last_interaction_at = date($connected_on),
                k.interaction_count = 0
            ON MATCH SET
                k.shared_connection_count = k.shared_connection_count + 1,
                k.sources = CASE
                    WHEN NOT 'linkedin' IN coalesce(k.sources, [])
                    THEN coalesce(k.sources, []) + ['linkedin']
                    ELSE k.sources
                END
            RETURN existed
            """,
            {
                "id": person_id,
                "first_name": first_name,
                "last_name": last_name,
                "full_name": full_name,
                "company": company,
                "role": role,
                "email": email,
                "member_name": member_name,
                "connected_on": parsed_date,
            },
        )
        records = [r async for r in result]
        existed = records[0].data().get("existed") if records else False
        await _recompute_scores(session, member_name)

    return "merged" if existed else "imported"


# ---------------------------------------------------------------------------
# Primitive: upsert an interaction (email/meeting/call) (LLM-callable)
# ---------------------------------------------------------------------------

async def upsert_interaction(
    member_name: str,
    contact_name: str,
    contact_company: str,
    interaction_type: str,
    occurred_at: str,
    notes: str = "",
) -> str:
    """Record an interaction between a member and a contact. Returns 'ok' or 'skipped'."""
    if not contact_name or not member_name:
        return "skipped"

    parsed_date = _parse_date(occurred_at) or datetime.now().strftime("%Y-%m-%d")
    source_label = interaction_type.lower() if interaction_type else "other"

    driver = await get_driver()
    async with driver.session() as session:
        await _ensure_member(session, member_name)

        await session.run(
            """
            MATCH (m:Person {full_name: $member_name})
            MATCH (p:Person)
            WHERE toLower(p.full_name) CONTAINS toLower($contact_name)
              AND ($contact_company = '' OR toLower(p.company) CONTAINS toLower($contact_company))
            WITH m, p LIMIT 1
            MERGE (m)-[k:KNOWS]->(p)
            ON CREATE SET
                k.source_member = $member_name,
                k.connected_on = date($occurred_at),
                k.shared_connection_count = 1,
                k.sources = [$source_label],
                k.last_interaction_at = date($occurred_at),
                k.interaction_count = 1
            ON MATCH SET
                k.sources = CASE
                    WHEN NOT $source_label IN coalesce(k.sources, [])
                    THEN coalesce(k.sources, []) + [$source_label]
                    ELSE k.sources
                END,
                k.last_interaction_at = CASE
                    WHEN date($occurred_at) > coalesce(k.last_interaction_at, date('2000-01-01'))
                    THEN date($occurred_at)
                    ELSE k.last_interaction_at
                END,
                k.interaction_count = coalesce(k.interaction_count, 0) + 1
            """,
            {
                "member_name": member_name,
                "contact_name": contact_name,
                "contact_company": contact_company or "",
                "source_label": source_label,
                "occurred_at": parsed_date,
            },
        )
        await _recompute_scores(session, member_name)

    return "ok"


# ---------------------------------------------------------------------------
# Batch CSV ingestion (existing, unchanged public API)
# ---------------------------------------------------------------------------

async def ingest_csv(member_name: str, csv_text: str) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))

    rows = []
    for raw_row in reader:
        row = {k.strip(): v.strip() if v else "" for k, v in raw_row.items()}
        first = row.get("First Name", "")
        last = row.get("Last Name", "")
        company = row.get("Company", "")
        if not first or not last or not company:
            continue
        rows.append(
            {
                "id": _make_id(first, last, company),
                "first_name": first,
                "last_name": last,
                "full_name": f"{first} {last}",
                "company": company,
                "role": row.get("Position", ""),
                "connected_on": _parse_date(row.get("Connected On", "")),
            }
        )

    if not rows:
        return {"imported": 0, "merged": 0, "message": "No valid rows found"}

    driver = await get_driver()
    imported = 0
    merged = 0

    async with driver.session() as session:
        await _ensure_member(session, member_name)

        for row in rows:
            result = await session.run(
                """
                MERGE (p:Person {id: $id})
                ON CREATE SET
                    p.first_name = $first_name,
                    p.last_name = $last_name,
                    p.full_name = $full_name,
                    p.company = $company,
                    p.role = $role,
                    p.is_tsi_member = false
                ON MATCH SET
                    p.role = CASE WHEN $role <> '' THEN $role ELSE p.role END
                WITH p,
                     CASE WHEN p.is_tsi_member IS NULL THEN false ELSE p.is_tsi_member END AS existed
                MERGE (c:Company {name: $company})
                MERGE (p)-[:WORKS_AT {role: $role, is_current: true}]->(c)
                WITH p, existed
                MATCH (m:Person {full_name: $member_name})
                MERGE (m)-[k:KNOWS]->(p)
                ON CREATE SET
                    k.source_member = $member_name,
                    k.connected_on = date($connected_on),
                    k.shared_connection_count = 1,
                    k.sources = ['linkedin'],
                    k.last_interaction_at = date($connected_on),
                    k.interaction_count = 0
                ON MATCH SET
                    k.shared_connection_count = k.shared_connection_count + 1,
                    k.sources = CASE
                        WHEN NOT 'linkedin' IN coalesce(k.sources, [])
                        THEN coalesce(k.sources, []) + ['linkedin']
                        ELSE k.sources
                    END
                RETURN existed
                """,
                {
                    **row,
                    "member_name": member_name,
                    "connected_on": row["connected_on"] or "2020-01-01",
                },
            )
            records = [r async for r in result]
            if records and records[0].data().get("existed"):
                merged += 1
            else:
                imported += 1

        await _recompute_scores(session, member_name)

    return {
        "imported": imported,
        "merged": merged,
        "message": f"Processed {imported + merged} contacts for {member_name}",
    }


async def _recompute_scores(session, member_name: str) -> None:
    """Recompute strength on every KNOWS edge originating from this member."""
    from services.scoring_service import compute_strength

    records = await session.run(
        """
        MATCH (m:Person {full_name: $member_name})-[k:KNOWS]->(p:Person)
        OPTIONAL MATCH (other:Person {is_tsi_member: true})-[:KNOWS]->(p)
        WITH m, k, p,
             k.connected_on AS conn_date,
             k.last_interaction_at AS last_touch,
             k.interaction_count AS interaction_count,
             p.role AS role,
             count(DISTINCT other) AS shared_count
        OPTIONAL MATCH (:Person {is_tsi_member: true})-[k2:KNOWS]->(p)
        WITH k, conn_date, last_touch, interaction_count, role, shared_count,
             count(DISTINCT k2.source_member) AS source_count
        RETURN id(k) AS rel_id, conn_date, last_touch, interaction_count,
               role, shared_count, source_count
        """,
        {"member_name": member_name},
    )

    async for record in records:
        data = record.data()
        strength = compute_strength(
            data["conn_date"],
            data["role"],
            data["shared_count"],
            data["source_count"],
            interaction_count=data.get("interaction_count") or 0,
            last_touch=data.get("last_touch"),
        )
        await session.run(
            "MATCH ()-[k:KNOWS]->() WHERE id(k) = $rel_id SET k.strength = $strength",
            {"rel_id": data["rel_id"], "strength": strength},
        )
