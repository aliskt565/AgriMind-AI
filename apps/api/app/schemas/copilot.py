import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = None


class ReferencedEntityOut(BaseModel):
    entity_type: str
    entity_id: str
    label: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    provider_name: str | None
    is_mock: bool | None
    referenced_entities: list[ReferencedEntityOut] = Field(default_factory=list)
    context_freshness_warnings: list[str] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
