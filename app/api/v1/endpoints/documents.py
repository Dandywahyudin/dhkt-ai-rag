import json
from pathlib import Path
import shutil
import uuid
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from ....core.config import settings
from ....core.security import verify_ci4_signature
from ....schemas.document import (
    DeleteResponse,
    DocumentInfo,
    DocumentIngestRequest,
    DocumentIngestResponse,
    DocumentListResponse,
)
from ....services.rag_service import rag_service

router = APIRouter()


@router.post(
    "/documents/ingest",
    response_model=DocumentIngestResponse,
    summary="Ingest file PDF dari path file lokal di server",
    dependencies=[Depends(verify_ci4_signature)],
)
async def ingest_document_by_path(payload: DocumentIngestRequest) -> DocumentIngestResponse:
    """
    Dipanggil oleh CodeIgniter 4 DhktAiClient saat mengindeks file PDF yang sudah tersimpan di server.
    """
    file_path = Path(payload.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File PDF tidak ditemukan pada path: {payload.file_path}",
        )

    if not file_path.suffix.lower() == ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hanya file dengan ekstensi .pdf yang didukung.",
        )

    try:
        result = await rag_service.ingest_pdf(
            file_source=file_path,
            document_id=payload.document_id,
            doc_title=payload.doc_title,
            allowed_roles=payload.allowed_roles,
            filename=file_path.name,
        )
        return DocumentIngestResponse(**result)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengindeks dokumen PDF: {str(e)}",
        )


@router.post(
    "/documents/upload",
    response_model=DocumentIngestResponse,
    summary="Upload file PDF langsung via multipart form-data",
    dependencies=[Depends(verify_ci4_signature)],
)
async def upload_and_ingest_pdf(
    file: UploadFile = File(..., description="File PDF yang ingin diindeks"),
    document_id: Optional[str] = Form(None, description="ID dokumen opsional (jika kosong, auto-generate)"),
    doc_title: Optional[str] = Form(None, description="Judul dokumen opsional (jika kosong, menggunakan nama file)"),
    allowed_roles: Optional[str] = Form(None, description="Daftar role JSON atau comma-separated, misal: admin,staff"),
) -> DocumentIngestResponse:
    """
    Endpoint upload PDF langsung via multipart/form-data.
    Menyimpan file ke folder storage/uploads lalu langsung mengekstrak teks,
    membuat chunking, embedding, dan menyimpannya di Vector Store.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hanya file berekstensi .pdf yang diperbolehkan.",
        )

    doc_id = document_id or str(uuid.uuid4())[:8]
    title = doc_title or Path(file.filename).stem

    roles_list = ["*"]
    if allowed_roles:
        try:
            parsed = json.loads(allowed_roles)
            if isinstance(parsed, list):
                roles_list = parsed
        except Exception:
            roles_list = [r.strip() for r in allowed_roles.split(",") if r.strip()]

    # Simpan file ke storage/uploads/
    target_path = settings.UPLOADS_DIR / f"{doc_id}_{file.filename}"
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await rag_service.ingest_pdf(
            file_source=target_path,
            document_id=doc_id,
            doc_title=title,
            allowed_roles=roles_list,
            filename=file.filename,
        )
        return DocumentIngestResponse(**result)

    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengunggah dan mengindeks file PDF: {str(e)}",
        )


@router.get(
    "/documents",
    response_model=DocumentListResponse,
    summary="Daftar seluruh dokumen yang telah diindeks ke dalam Vector Store",
    dependencies=[Depends(verify_ci4_signature)],
)
async def list_documents() -> DocumentListResponse:
    """Mengembalikan daftar semua dokumen yang tersimpan dalam vector store."""
    docs = rag_service.list_documents()
    formatted = [DocumentInfo(**d) for d in docs]
    return DocumentListResponse(status="success", total=len(formatted), documents=formatted)


@router.delete(
    "/documents/{document_id}",
    response_model=DeleteResponse,
    summary="Hapus dokumen dari Vector Store berdasarkan document_id",
    dependencies=[Depends(verify_ci4_signature)],
)
async def delete_document(document_id: str) -> DeleteResponse:
    """Menghapus semua potongan vektor dokumen berdasarkan document_id."""
    res = rag_service.delete_document(document_id)
    return DeleteResponse(
        status="success",
        document_id=document_id,
        message=res["message"],
    )
