from __future__ import annotations

from statistics import mean

from app.core.config import settings
from app.graph.states import StudentWritingState


def route_after_evaluate(state: StudentWritingState) -> str:
    scores = state.get("critique_scores", {})
    revision_count = int(state.get("revision_count", 0))
    if revision_count >= settings.MAX_REVISIONS:
        return "render"
    if scores and mean(scores.values()) >= settings.PASS_SCORE:
        return "render"
    return "revise_draft"
