import re
from datetime import datetime, date

WEIGHTS = {
    "recency":            0.25,
    "seniority":          0.25,
    "shared_connections": 0.20,
    "interaction_freq":   0.10,
    "source_diversity":   0.20,
}

_CSUITE_RE = re.compile(
    r"\b(ceo|cfo|coo|cto|cio|cmo|chief|partner|managing director|md)\b", re.I
)
_VP_RE = re.compile(r"\b(vp|vice president|director|head of)\b", re.I)
_MGR_RE = re.compile(r"\b(manager|senior|sr\.?|lead)\b", re.I)


def _to_date(d) -> date | None:
    if d is None:
        return None
    if hasattr(d, "to_native"):
        return d.to_native()
    if isinstance(d, date):
        return d
    return None


def recency_score(connected_on: date | None, last_touch: date | None = None) -> float:
    reference = last_touch or connected_on
    if reference is None:
        return 0.3
    reference = _to_date(reference) or reference
    days = (datetime.now().date() - reference).days
    if days <= 365:
        return 1.0
    if days <= 365 * 3:
        return 0.6
    return 0.3


def seniority_score(title: str | None) -> float:
    if not title:
        return 0.2
    if _CSUITE_RE.search(title):
        return 1.0
    if _VP_RE.search(title):
        return 0.7
    if _MGR_RE.search(title):
        return 0.4
    return 0.2


def shared_connections_score(count: int) -> float:
    if count >= 3:
        return 1.0
    if count == 2:
        return 0.6
    return 0.2


def interaction_frequency_score(count: int) -> float:
    if count >= 5:
        return 1.0
    if count >= 2:
        return 0.5
    return 0.0


def source_diversity_score(source_count: int) -> float:
    return 1.0 if source_count > 1 else 0.0


def compute_strength(
    connected_on: date | None,
    title: str | None,
    shared_count: int,
    source_count: int,
    interaction_count: int = 0,
    last_touch: date | None = None,
) -> float:
    connected_on = _to_date(connected_on)
    last_touch = _to_date(last_touch)
    return round(
        recency_score(connected_on, last_touch) * WEIGHTS["recency"]
        + seniority_score(title) * WEIGHTS["seniority"]
        + shared_connections_score(shared_count) * WEIGHTS["shared_connections"]
        + interaction_frequency_score(interaction_count) * WEIGHTS["interaction_freq"]
        + source_diversity_score(source_count) * WEIGHTS["source_diversity"],
        3,
    )


def score_breakdown(
    connected_on: date | None,
    title: str | None,
    shared_count: int,
    source_count: int,
    interaction_count: int = 0,
    last_touch: date | None = None,
) -> dict:
    connected_on = _to_date(connected_on)
    last_touch = _to_date(last_touch)
    return {
        "overall": compute_strength(
            connected_on, title, shared_count, source_count,
            interaction_count, last_touch,
        ),
        "recency": recency_score(connected_on, last_touch),
        "seniority": seniority_score(title),
        "shared_connections": shared_count,
        "interaction_frequency": interaction_frequency_score(interaction_count),
        "source_diversity": source_count > 1,
    }
