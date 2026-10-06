import enum
import uuid

from sqlalchemy import String, Text, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"  # internal only -- never rendered to the farmer


class CopilotConversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    A Copilot conversation belongs to exactly one farmer. All authorization
    for every message and context lookup within a conversation traces back
    to this ownership relationship.
    """
    __tablename__ = "copilot_conversations"

    farmer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("farmers.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=True)

    messages: Mapped[list["CopilotMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="CopilotMessage.created_at"
    )


class CopilotMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    One message in a conversation. `referenced_entities` and
    `context_snapshot` are stored as JSON since their shape is defined by
    the Copilot contract (app/ai/contracts.py), not a rigid relational
    schema -- consistent with how AIPrediction/AIRisk already store
    AI-contract-shaped data elsewhere in this codebase.
    """
    __tablename__ = "copilot_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="copilot_message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Only populated on ASSISTANT messages
    provider_name: Mapped[str] = mapped_column(String(120), nullable=True)
    is_mock: Mapped[bool] = mapped_column(nullable=True)
    referenced_entities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    context_freshness_warnings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    conversation: Mapped["CopilotConversation"] = relationship(back_populates="messages")
