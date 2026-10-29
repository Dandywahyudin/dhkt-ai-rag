import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from ..core.config import settings
from ..core.prompts import build_rag_prompt
from ..schemas.chat import ChatResponse, SourceItem, UserContext
from .llm_service import get_llm_service
from .pdf_service import pdf_service
from .vector_store import get_vector_store

logger = logging.getLogger("dhkt.rag")


def clean_markdown_and_footnotes(text: str) -> str:
    """
    Membersihkan output LLM agar bebas dari karakter markdown asterisks (**) dan catatan kaki.
    """
    if not text:
        return ""
    # 1. Hapus tanda tebal/miring markdown: **kata** -> kata, *kata* -> kata
    cleaned = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
    # 2. Hapus catatan kaki sumber seperti: *(Sumber:...)* atau (Sumber:...)
    cleaned = re.sub(r'\s*\(?\*?Sumber:[^)]*\)?\*?', '', cleaned, flags=re.IGNORECASE)
    # 3. Hapus sisa-sisa tanda bintang liar
    cleaned = cleaned.replace('**', '').replace('*', '')
    # 4. Hapus tanda strip/dash orphan di awal kalimat (misal: "—hanya dapat ...")
    cleaned = re.sub(r'^[—–\-\s:\.]+', '', cleaned)
    return cleaned.strip()


def extract_room_booking_heuristics(message: str) -> Optional[Dict[str, Any]]:
    """
    Ekstraksi data form peminjaman ruangan dari teks kalimat pengguna
    jika terdeteksi adanya perintah input/booking ruangan.
    """
    msg_lower = message.lower()
    if not any(k in msg_lower for k in ["pinjam", "minjam", "booking", "reservasi", "isi form", "buat jadwal", "ajukan"]):
        return None

    form: Dict[str, Any] = {
        "form_type": "room_booking",
        "category": "internal_dhkt",
    }

    # Nama Kegiatan
    act_match = re.search(r'(?:untuk|acara|kegiatan|buat|agenda)\s+([^,.\n]+?)(?:\s+(?:di|pada|tanggal|tgl|\d{1,2}[-\/]|jam|dengan|pukul)|$)', message, re.IGNORECASE)
    if act_match:
        form["activity_name"] = act_match.group(1).strip()
    else:
        form["activity_name"] = "Peminjaman Ruangan"

    # Ruangan & Tempat
    room_match = re.search(r'(?:ruang(?:an)?|meeting|miting|aula)\s+([a-zA-Z0-9_\-]+(?:\s+[a-zA-Z0-9_\-]+){0,2})', message, re.IGNORECASE)
    if room_match:
        raw_room = room_match.group(0).strip()
        form["room_name"] = raw_room if raw_room.lower().startswith("ruang") else "Ruang " + raw_room
    if "gedebage" in msg_lower or "stp" in msg_lower:
        form["place_name"] = "STP Gedebage"
    elif "crcs" in msg_lower:
        form["place_name"] = "Gedung CRCS"

    # Jumlah Peserta
    peserta_match = re.search(r'(\d+)\s*(?:orang|peserta)', message, re.IGNORECASE)
    if peserta_match:
        form["participant_count"] = int(peserta_match.group(1))

    # Unit Peminjam
    unit_match = re.search(r'(?:unit|dari)\s+([^,.\n]+)', message, re.IGNORECASE)
    if unit_match:
        form["unit"] = unit_match.group(1).strip()

    # Tanggal dan Jam
    date_match = re.search(r'(\d{1,2}[-\/]\d{1,2}[-\/]\d{4}|\d{4}[-\/]\d{1,2}[-\/]\d{1,2}|\d{1,2}\s+[a-zA-Z]+\s+\d{4})', message)
    time_match = re.search(r'(\d{1,2}[:.]\d{2})\s*(?:s\/d|sampai|-)\s*(\d{1,2}[:.]\d{2})', message)
    if date_match and time_match:
        tgl = date_match.group(1).replace('/', '-')
        t_start = time_match.group(1).replace('.', ':')
        t_end = time_match.group(2).replace('.', ':')
        form["date_range"] = f"{tgl} {t_start} - {tgl} {t_end}"
    elif date_match:
        form["date_range"] = f"{date_match.group(1)} 08:00 - {date_match.group(1)} 16:00"

    return form if len(form) > 2 else None


class RAGService:
    def __init__(self):
        self.vector_store = get_vector_store()
        self.pdf_service = pdf_service
        self.llm_service = get_llm_service()

    async def ingest_pdf(
        self,
        file_source: Union[str, Path, bytes],
        document_id: Union[int, str],
        doc_title: str,
        allowed_roles: Optional[List[str]] = None,
        filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a PDF file: extract pages, split into chunks, compute embeddings,
        and store in vector database.
        """
        roles = allowed_roles or ["*"]

        # 1. Extract & chunk text
        chunks = self.pdf_service.process_pdf(
            file_source=file_source,
            document_id=document_id,
            doc_title=doc_title,
            allowed_roles=roles,
        )

        if not chunks:
            raise ValueError(f"Dokumen '{doc_title}' tidak mengandung teks yang dapat diekstrak.")

        if filename:
            for c in chunks:
                c["filename"] = filename

        # 2. Generate embeddings
        texts = [c["text"] for c in chunks]
        embeddings = await self.llm_service.generate_embeddings_batch(texts)

        # 3. Save into vector store
        # First remove any previous chunks with same document_id (upsert behavior)
        self.vector_store.delete_document(str(document_id))
        added_count = self.vector_store.add_chunks(chunks, embeddings)

        logger.info(f"Ingested document '{doc_title}' (id={document_id}) with {added_count} chunks.")

        return {
            "status": "success",
            "document_id": document_id,
            "doc_title": doc_title,
            "chunks_count": added_count,
            "message": f"Berhasil mengindeks {added_count} potongan teks dari '{doc_title}'.",
        }

    async def answer_chat(
        self,
        session_id: str,
        message: str,
        user_context: Optional[UserContext] = None,
        history: Optional[List[Dict[str, str]]] = None,
        top_k: Optional[int] = None,
    ) -> ChatResponse:
        """
        Retrieve relevant document snippets and synthesize an answer using Gemini.
        """
        k = top_k or settings.TOP_K_RESULTS
        user_dict = user_context.model_dump() if user_context else {}
        user_role = user_dict.get("role")

        # 1. Embed user query
        query_embedding = await self.llm_service.generate_embedding(message)

        # 2. Retrieve top matching chunks
        min_score = settings.MIN_SIMILARITY_SCORE if self.llm_service.is_configured else 0.0
        raw_chunks = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            role=user_role,
            min_score=min_score,
        )

        # 3. Format sources
        sources: List[SourceItem] = []
        for c in raw_chunks:
            snippet = c.get("text", "")
            # Truncate snippet preview if long
            preview = snippet[:250] + "..." if len(snippet) > 250 else snippet
            sources.append(
                SourceItem(
                    document_id=c.get("document_id"),
                    doc_title=c.get("doc_title", "Dokumen"),
                    page=c.get("page", 1),
                    chunk_index=c.get("chunk_index", 0),
                    snippet=preview,
                    score=c.get("score", 0.0),
                )
            )

        # 4. Synthesize answer with Gemini
        prompt = build_rag_prompt(
            query=message,
            chunks=raw_chunks,
            history=history,
            user_context=user_dict,
        )
        reply, tools_called, tool_data = await self.llm_service.generate_response(
            prompt=prompt,
            user_context=user_dict,
            enable_tools=settings.ENABLE_TOOL_CALLING,
        )

        # 5. Ekstraksi form_data dan sanitasi output (Hapus ** dan footnote sumber)
        form_data = tool_data
        json_match = re.search(r'```(?:json:form_data|json)?\s*(\{.*?\})\s*```', reply, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict):
                    form_data = parsed
                    # Potong blok JSON dari reply teks
                    reply = reply[:json_match.start()] + reply[json_match.end():]
            except Exception as e:
                logger.warning(f"Gagal mem-parsing blok JSON form_data dari reply: {e}")

        if not form_data:
            form_data = extract_room_booking_heuristics(message)

        clean_reply = clean_markdown_and_footnotes(reply)

        return ChatResponse(
            status="success",
            session_id=session_id,
            reply=clean_reply,
            sources=sources,
            tools_used=tools_called,
            form_data=form_data,
        )

    def delete_document(self, document_id: Union[int, str]) -> Dict[str, Any]:
        """Delete document from vector store."""
        deleted_count = self.vector_store.delete_document(str(document_id))
        return {
            "status": "success",
            "document_id": document_id,
            "deleted_chunks": deleted_count,
            "message": f"Dokumen {document_id} berhasil dihapus ({deleted_count} chunks dihapus).",
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        """List all indexed documents."""
        return self.vector_store.list_documents()


rag_service = RAGService()
