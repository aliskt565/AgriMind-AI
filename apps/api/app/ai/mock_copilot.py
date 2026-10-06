"""
MOCK IMPLEMENTATION -- NOT A REAL LLM.

This provider never calls an external model. It answers strictly from the
structured `context` dict it's given (built by ContextBuilder from
authorized database rows) using simple keyword-based intent matching. It
never invents farm-specific facts: every concrete number or name in a
response is read directly from `request.context`, and when the relevant
context is empty, the response says so explicitly rather than guessing.

Swapping this for a real LLM later means implementing a new class against
the same `CopilotProvider`/`CopilotRequest`/`CopilotResponse` contract --
the orchestrator, API, and frontend do not change.
"""
from app.ai.base import CopilotProvider
from app.ai.contracts import CopilotRequest, CopilotResponse, ReferencedEntity

PROVIDER_NAME = "mock-copilot"

_GENERAL_GUIDANCE_DISCLAIMER = (
    "This is general agricultural guidance, not a fact about your farm -- "
    "verify with a local agricultural expert before acting on it."
)


def _summarize_risks(context: dict, limit: int = 5) -> tuple[str, list[ReferencedEntity]]:
    risks = context.get("active_risks", [])
    if not risks:
        return "You have no active risks recorded right now.", []
    lines = []
    refs = []
    for r in risks[:limit]:
        where = r.get("field_name") or r.get("crop_type") or "your farm"
        lines.append(f"- {r['risk_level']} {r['risk_type'].replace('_', ' ').lower()} risk on {where}: {r['reason']}")
        refs.append(ReferencedEntity(entity_type="risk", entity_id=r["id"], label=f"{r['risk_type']} risk"))
    more = f" (+{len(risks) - limit} more)" if len(risks) > limit else ""
    return "Here are your active risks:\n" + "\n".join(lines) + more, refs


def _summarize_recommendations(context: dict, limit: int = 5) -> tuple[str, list[ReferencedEntity]]:
    recs = context.get("active_recommendations", [])
    if not recs:
        return "You have no active recommendations right now -- nothing has triggered one.", []
    lines = []
    refs = []
    for r in recs[:limit]:
        lines.append(f"- [{r['priority']}] {r['text']}")
        refs.append(ReferencedEntity(entity_type="recommendation", entity_id=r["id"], label=r["category"]))
    more = f" (+{len(recs) - limit} more)" if len(recs) > limit else ""
    return "Here are your active recommendations:\n" + "\n".join(lines) + more, refs


def _summarize_crops(context: dict, limit: int = 6) -> tuple[str, list[ReferencedEntity]]:
    crops = context.get("crops", [])
    if not crops:
        return "You don't have any crops recorded yet.", []
    lines = []
    refs = []
    for c in crops[:limit]:
        lines.append(f"- {c['crop_type']} in {c['field_name']}: stage {c['stage']}, health {c['health_status']}")
        refs.append(ReferencedEntity(entity_type="crop", entity_id=c["id"], label=c["crop_type"]))
    more = f" (+{len(crops) - limit} more)" if len(crops) > limit else ""
    return "Here's how your crops are doing:\n" + "\n".join(lines) + more, refs


def _summarize_activities(context: dict, limit: int = 5) -> tuple[str, list[ReferencedEntity]]:
    activities = context.get("recent_activities", [])
    if not activities:
        return "No recent activities have been logged.", []
    lines = []
    refs = []
    for a in activities[:limit]:
        lines.append(f"- {a['activity_type']} on {a['crop_type']} ({a['activity_date']})")
        refs.append(ReferencedEntity(entity_type="activity", entity_id=a["id"], label=a["activity_type"]))
    return "Recent activity:\n" + "\n".join(lines), refs


def _weather_freshness_warnings(context: dict) -> list[str]:
    warnings = []
    for w in context.get("weather", []):
        if w.get("is_stale"):
            warnings.append(f"Weather for {w.get('field_name', 'a field')} is stale (last updated {w.get('fetched_at')}).")
    return warnings


def _focus_today(context: dict) -> tuple[str, list[ReferencedEntity]]:
    risks = context.get("active_risks", [])
    high_priority_recs = [r for r in context.get("active_recommendations", []) if r.get("priority") == "HIGH"]

    if not risks and not high_priority_recs:
        return (
            "Nothing urgent stands out right now -- no active risks and no high-priority recommendations. "
            "Routine monitoring is a good use of your time today."
        ), []

    lines = []
    refs = []
    if risks:
        top_risk = risks[0]
        where = top_risk.get("field_name") or top_risk.get("crop_type") or "your farm"
        lines.append(f"- {top_risk['risk_level']} risk on {where}: {top_risk['reason']}")
        refs.append(ReferencedEntity(entity_type="risk", entity_id=top_risk["id"], label=f"{top_risk['risk_type']} risk"))
    for rec in high_priority_recs[:2]:
        lines.append(f"- High priority: {rec['text']}")
        refs.append(ReferencedEntity(entity_type="recommendation", entity_id=rec["id"], label=rec["category"]))

    return "Here's what I'd focus on today:\n" + "\n".join(lines), refs


def _full_summary(context: dict) -> tuple[str, list[ReferencedEntity]]:
    farmer = context.get("farmer", {})
    farms = context.get("farms", [])
    if not farms:
        return "You haven't added any farms yet -- once you do, I can summarize what's happening across them.", []

    refs: list[ReferencedEntity] = []
    parts = [
        f"You have {len(farms)} farm(s) with {len(context.get('fields', []))} field(s) and "
        f"{len(context.get('crops', []))} crop(s) tracked."
    ]
    for f in farms[:3]:
        refs.append(ReferencedEntity(entity_type="farm", entity_id=f["id"], label=f["name"]))

    risks = context.get("active_risks", [])
    recs = context.get("active_recommendations", [])
    parts.append(f"{len(risks)} active risk(s) and {len(recs)} active recommendation(s) right now.")

    return " ".join(parts), refs


class MockCopilotProvider(CopilotProvider):
    def respond(self, request: CopilotRequest) -> CopilotResponse:
        context = request.context
        message = request.user_message.lower()

        warnings = _weather_freshness_warnings(context)

        if not context.get("farms"):
            return CopilotResponse(
                content=(
                    "I don't have any farm data for your account yet -- once you add a farm, field, and crop, "
                    "I'll be able to answer questions about them."
                ),
                referenced_entities=[], context_freshness_warnings=warnings,
                provider_name=PROVIDER_NAME, is_mock=True,
            )

        if any(kw in message for kw in ["focus today", "attention today", "what should i focus", "today"]):
            content, refs = _focus_today(context)
        elif any(kw in message for kw in ["which field", "field needs", "field is at risk", "at risk"]):
            content, refs = _summarize_risks(context)
        elif any(kw in message for kw in ["risk"]):
            content, refs = _summarize_risks(context)
        elif any(kw in message for kw in ["recommend"]):
            content, refs = _summarize_recommendations(context)
        elif any(kw in message for kw in ["crop", "how are my crops", "progress"]):
            content, refs = _summarize_crops(context)
        elif any(kw in message for kw in ["activity", "activities", "overdue", "this week"]):
            content, refs = _summarize_activities(context)
        elif any(kw in message for kw in ["summarize", "summary", "situation", "overview"]):
            content, refs = _full_summary(context)
        else:
            content, refs = _full_summary(context)
            content += (
                "\n\nYou can ask me things like \"which field needs attention\", \"how are my crops doing\", "
                "or \"what are my active recommendations\"."
            )

        return CopilotResponse(
            content=content,
            referenced_entities=refs,
            context_freshness_warnings=warnings,
            provider_name=PROVIDER_NAME,
            is_mock=True,
        )
