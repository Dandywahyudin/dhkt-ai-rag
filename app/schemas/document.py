from datetime import datetime
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    document_id: Union[int, str] = Field(..., description="ID unik dokumen di database CodeIgniter")
    doc_title: str = Field(..., description="Judul dokumen SOP / berkas")
    file_path: str = Field(..., description="Lokasi file PDF di sistem / server")
    allowed_roles: Optional[List[str]] = Field(
        default_factory=lambda: ["*"],
        description="Daftar role yang diizinkan mengakses (misal ['admin', 'staff'] atau ['*'])",
    )


class DocumentIngestResponse(BaseModel):
    status: str = "success"
    document_id: Union[int, str]
    doc_title: str
    chunks_count: int
    message: str


class DocumentInfo(BaseModel):
    document_id: Union[int, str]
    doc_title: str
    filename: str
    chunks_count: int
    allowed_roles: List[str]
    created_at: str


class DocumentListResponse(BaseModel):
    status: str = "success"
    total: int
    documents: List[DocumentInfo]


class DeleteResponse(BaseModel):
    status: str = "success"
    document_id: Union[int, str]
    message: str
