from pydantic import BaseModel, EmailStr, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class WorkspaceUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class KnowledgeBaseCreate(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class KnowledgeBaseUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None


class MemberUpsert(BaseModel):
    user_id: str
    role: str = Field(pattern="^(admin|editor|viewer)$")


class MemberByEmail(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(admin|editor|viewer)$")


class ChatSessionCreate(BaseModel):
    workspace_id: str
    title: str | None = None
    knowledge_base_ids: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


class CredentialSave(BaseModel):
    workspace_id: str
    provider: str = Field(pattern="^gemini$")
    secret: str = Field(min_length=8, max_length=500)
