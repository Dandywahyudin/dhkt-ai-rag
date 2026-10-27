import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from ..core.config import settings
from ..core.prompts import build_rag_prompt
from ..schemas.chat import ChatResponse, SourceItem, UserContext
from .gemini_service import gemini_service
from .pdf_service import pdf_service
from .vector_store import get_vector_store

logger = logging.getLogger("dhkt.rag")


class RAGService:
    def __init__(self):
        self.vector_store = get_vector_store()
        self.pdf_service = pdf_service
        self.gemini_service = gemini_service

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
        embeddings = await self.gemini_service.generate_embeddings_batch(texts)

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
        query_embedding = await self.gemini_service.generate_embedding(message)

        # 2. Retrieve top matching chunks
        min_score = settings.MIN_SIMILARITY_SCORE if self.gemini_service.is_configured else 0.0
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

        reply, tools_called = await self.gemini_service.generate_response(
            prompt=prompt,
            user_context=user_dict,
            enable_tools=settings.ENABLE_TOOL_CALLING,
        )

        return ChatResponse(
            status="success",
            session_id=session_id,
            reply=reply,
            sources=sources,
            tools_used=tools_called,
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
