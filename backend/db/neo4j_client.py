import asyncio
import logging
import os

from neo4j import AsyncGraphDatabase, AsyncDriver

logger = logging.getLogger(__name__)

_driver: AsyncDriver | None = None


async def get_driver() -> AsyncDriver:
    global _driver
    if _driver is None:
        raise RuntimeError("Neo4j driver not initialized – call connect() first")
    return _driver


async def connect() -> None:
    global _driver
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "password")

    for attempt in range(1, 6):
        try:
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
            await driver.verify_connectivity()
            _driver = driver
            logger.info("Connected to Neo4j at %s (attempt %d)", uri, attempt)
            break
        except Exception as exc:
            logger.warning("Neo4j connection attempt %d failed: %s", attempt, exc)
            if attempt == 5:
                raise
            await asyncio.sleep(2)

    await _ensure_constraints()


async def _ensure_constraints() -> None:
    driver = await get_driver()
    async with driver.session() as session:
        await session.run(
            "CREATE CONSTRAINT person_id IF NOT EXISTS "
            "FOR (p:Person) REQUIRE p.id IS UNIQUE"
        )
        await session.run(
            "CREATE CONSTRAINT company_name IF NOT EXISTS "
            "FOR (c:Company) REQUIRE c.name IS UNIQUE"
        )
    logger.info("Neo4j constraints ensured")


def _coerce(value):
    """Recursively convert Neo4j temporal/spatial types to JSON-safe primitives."""
    if value is None:
        return None
    # Neo4j Date/DateTime/Time/Duration all expose to_native()
    if hasattr(value, "to_native"):
        return str(value.to_native())
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    return value


async def run_query(cypher: str, params: dict | None = None) -> list[dict]:
    driver = await get_driver()
    async with driver.session() as session:
        result = await session.run(cypher, params or {})
        return [
            {k: _coerce(v) for k, v in record.data().items()}
            async for record in result
        ]


async def close() -> None:
    global _driver
    if _driver:
        await _driver.close()
        _driver = None
        logger.info("Neo4j connection closed")
