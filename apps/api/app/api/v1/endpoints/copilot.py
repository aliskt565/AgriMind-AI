import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_farmer
from app.db.session import get_db
from app.models.user import Farmer
from app.models.copilot import CopilotConversation, CopilotMessage
from app.schemas.copilot import ConversationCreate, ConversationOut, ConversationDetailOut, SendMessageRequest, MessageOut
from app.services.copilot_service import send_message

router = APIRouter(prefix="/copilot/conversations", tags=["AI Farm Copilot"])


def _get_owned_conversation_or_404(conversation_id: uuid.UUID, farmer: Farmer, db: Session) -> CopilotConversation:
    """
    Ownership enforcement, identical pattern to every other resource in this
    codebase: a conversation is only returned if it belongs to the
    authenticated farmer -- never trusts a client-supplied conversation_id
    alone.
    """
    conversation = (
        db.query(CopilotConversation)
        .options(joinedload(CopilotConversation.messages))
        .filter(CopilotConversation.id == conversation_id, CopilotConversation.farmer_id == farmer.id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(payload: ConversationCreate, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    conversation = CopilotConversation(farmer_id=farmer.id, title=payload.title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationOut])
def list_conversations(farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    return (
        db.query(CopilotConversation)
        .filter(CopilotConversation.farmer_id == farmer.id)
        .order_by(CopilotConversation.updated_at.desc())
        .all()
    )


@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(conversation_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    return _get_owned_conversation_or_404(conversation_id, farmer, db)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: uuid.UUID, farmer: Farmer = Depends(require_farmer), db: Session = Depends(get_db)):
    conversation = _get_owned_conversation_or_404(conversation_id, farmer, db)
    db.delete(conversation)
    db.commit()
    return None


@router.post("/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def post_message(
    conversation_id: uuid.UUID,
    payload: SendMessageRequest,
    farmer: Farmer = Depends(require_farmer),
    db: Session = Depends(get_db),
):
    conversation = _get_owned_conversation_or_404(conversation_id, farmer, db)
    assistant_message = send_message(conversation, payload.content, farmer, db)
    return assistant_message
