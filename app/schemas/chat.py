from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    id: Optional[Union[int, str]] = None
    role: Optional[str] = "staff"
    unit: Optional[str] = None


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' atau 'assistant'")
    content: str


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(default="default-session", description="ID sesi chat")
    message: str = Field(..., min_length=1, description="Pesan pertanyaan dari user")
    user_context: Optional[UserContext] = Field(default_factory=UserContext)
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="Riwayat chat sebelumnya")


class SourceItem(BaseModel):
    document_id: Union[int, str]
    doc_title: str
    page: int
    chunk_index: int
    snippet: str
    score: float


class ChatResponse(BaseModel):
    status: str = "success"
    session_id: str
    reply: str
    sources: List[SourceItem] = Field(default_factory=list)
    tools_used: List[str] = Field(default_factory=list, description="Daftar nama tool internal yang dipanggil oleh AI")
    form_data: Optional[Dict[str, Any]] = Field(default=None, description="Data form terstruktur yang diekstrak jika ada instruksi pengisian form")
