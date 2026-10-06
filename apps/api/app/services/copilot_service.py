"""
CopilotService -- the orchestrator layer described in the roadmap:

    Authorized Farm Context Retrieval -> Prompt/Message Builder -> AIProvider -> Response Formatter

This is the only module that ties context building, provider invocation,
and persistence together. Endpoints call into this, never into
ContextBuilder or the provider directly, so the orchestration flow can't be
bypassed or reordered incorrectly from the API layer.

Responsibilities that belong HERE, not in the provider:
  1. Conversation ownership is already verified by the caller (API layer)
     before this function is invoked.
  2. Context retrieval is delegated to ContextBuilder (farmer-scoped only).
  3. Context size control lives in ContextBuilder's caps (MAX_* constants).
  4. Provider invocation and failure handling (see try/except below).
  5. Response validation (see _validate_provider_response) -- a future real
     provider could return malformed data, and that must never crash the
     API or silently pass corrupt data to the frontend.
  6. Persistence.

The provider itself never sees a farmer_id, a database session, or
performs any authorization -- see app/ai/contracts.py::CopilotRequest.
"""
import logging

from sqlalchemy.orm import Session

from app.models.user import Farmer
from app.models.copilot import CopilotConversation, CopilotMessage, MessageRole
from app.ai.contracts import CopilotRequest, CopilotMessageInput, CopilotResponse
from app.ai.factory import get_copilot_provider
from app.services.copilot_context import build_farmer_context

logger = logging.getLogger("agrimind.copilot")

MAX_HISTORY_TURNS = 10
FALLBACK_MESSAGE = "I couldn't process that just now -- please try again in a moment."


def _validate_provider_response(result: object) -> CopilotResponse | None:
    """
    Defends against a provider (mock today, a real LLM integration later)
    returning something malformed: wrong type, missing fields, empty
    content, non-list referenced_entities, etc. Returns a valid
    CopilotResponse, or None if the result cannot be trusted -- callers
    must treat None the same as a provider exception, never render it.
    """
    if not isinstance(result, CopilotResponse):
        logger.warning("Copilot provider returned an unexpected type: %s", type(result).__name__)
        return None
    if not isinstance(result.content, str) or not result.content.strip():
        logger.warning("Copilot provider returned empty or non-string content")
        return None
    if not isinstance(result.referenced_entities, list):
        logger.warning("Copilot provider returned non-list referenced_entities")
        return None
    if not isinstance(result.context_freshness_warnings, list):
        logger.warning("Copilot provider returned non-list context_freshness_warnings")
        return None
    if not isinstance(result.provider_name, str) or not result.provider_name:
        logger.warning("Copilot provider returned an empty provider_name")
        return None
    if not isinstance(result.is_mock, bool):
        logger.warning("Copilot provider returned a non-bool is_mock flag")
        return None
    # Validate each referenced entity individually -- a malformed single
    # entry must not corrupt the whole response.
    for entity in result.referenced_entities:
        if not (hasattr(entity, "entity_type") and hasattr(entity, "entity_id") and hasattr(entity, "label")):
            logger.warning("Copilot provider returned a malformed referenced entity")
            return None
    return result


def _persist_fallback(conversation_id, db: Session) -> CopilotMessage:
    assistant_msg = CopilotMessage(
        conversation_id=conversation_id, role=MessageRole.ASSISTANT,
        content=FALLBACK_MESSAGE,
        provider_name="unavailable", is_mock=True, referenced_entities=[], context_freshness_warnings=[],
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)
    return assistant_msg


def send_message(conversation: CopilotConversation, user_message: str, farmer: Farmer, db: Session) -> CopilotMessage:
    """
    Persists the user's message, builds authorized context, invokes the
    (currently mock) Copilot provider, and persists + returns the assistant
    reply. `conversation` must already be verified as owned by `farmer` by
    the caller (the API layer) before this is invoked.
    """
    user_msg = CopilotMessage(conversation_id=conversation.id, role=MessageRole.USER, content=user_message)
    db.add(user_msg)
    db.flush()

    # Bounded history: only the last MAX_HISTORY_TURNS*2 messages (user+assistant
    # pairs) for THIS conversation -- conversation_id is already scoped to the
    # authenticated farmer's own conversation, so no cross-user history can
    # enter this query.
    history = (
        db.query(CopilotMessage)
        .filter(CopilotMessage.conversation_id == conversation.id, CopilotMessage.role != MessageRole.SYSTEM)
        .order_by(CopilotMessage.created_at.desc())
        .limit(MAX_HISTORY_TURNS * 2)
        .all()
    )
    history.reverse()
    history_input = [
        CopilotMessageInput(role=m.role.value, content=m.content) for m in history if m.id != user_msg.id
    ]

    try:
        context = build_farmer_context(farmer, db)
    except Exception:
        logger.exception("Copilot context build failed for conversation_id=%s", conversation.id)
        return _persist_fallback(conversation.id, db)

    provider = get_copilot_provider()
    request = CopilotRequest(conversation_history=history_input, user_message=user_message, context=context)

    try:
        raw_result = provider.respond(request)
    except Exception:
        # Provider failure (including timeouts a real provider might raise)
        # must never become a fabricated response.
        logger.warning("Copilot provider raised an exception for conversation_id=%s", conversation.id)
        return _persist_fallback(conversation.id, db)

    result = _validate_provider_response(raw_result)
    if result is None:
        return _persist_fallback(conversation.id, db)

    assistant_msg = CopilotMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.content,
        provider_name=result.provider_name,
        is_mock=result.is_mock,
        referenced_entities=[
            {"entity_type": e.entity_type, "entity_id": e.entity_id, "label": e.label} for e in result.referenced_entities
        ],
        context_freshness_warnings=result.context_freshness_warnings,
    )
    db.add(assistant_msg)

    if conversation.title is None:
        conversation.title = user_message[:80]

    db.commit()
    db.refresh(assistant_msg)
    logger.info(
        "Copilot response generated conversation_id=%s provider=%s is_mock=%s referenced_entity_count=%d",
        conversation.id, result.provider_name, result.is_mock, len(result.referenced_entities),
    )
    return assistant_msg
