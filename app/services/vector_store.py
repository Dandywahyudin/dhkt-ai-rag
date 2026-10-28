from abc import ABC, abstractmethod
from datetime import datetime
import json
import logging
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import numpy as np
from ..core.config import settings

logger = logging.getLogger("dhkt.vector_store")


class BaseVectorStore(ABC):
    @abstractmethod
    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        """Add chunks and their embeddings into the store. Returns added count."""
        pass

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        role: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search top-K most similar chunks, optionally filtered by user role."""
        pass

    @abstractmethod
    def delete_document(self, document_id: str) -> int:
        """Delete all chunks belonging to a document_id. Returns deleted count."""
        pass

    @abstractmethod
    def list_documents(self) -> List[Dict[str, Any]]:
        """List summary of ingested documents."""
        pass


class LocalVectorStore(BaseVectorStore):
    """
    Lightweight, persistent local vector store using NumPy for cosine similarity
    and JSON for metadata storage. Requires zero external dependencies.
    """

    def __init__(self, index_dir: Optional[Path] = None):
        self.index_dir = index_dir or settings.INDEX_DIR
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.index_dir / "metadata.json"
        self.vectors_file = self.index_dir / "vectors.npy"
        self.lock = threading.Lock()

        self.chunks: List[Dict[str, Any]] = []
        self.vectors: np.ndarray = np.empty((0, 768), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        with self.lock:
            if self.meta_file.exists() and self.vectors_file.exists():
                try:
                    with open(self.meta_file, "r", encoding="utf-8") as f:
                        self.chunks = json.load(f)
                    self.vectors = np.load(self.vectors_file)
                    logger.info(f"Loaded {len(self.chunks)} chunks from local vector store.")
                except Exception as e:
                    logger.error(f"Failed to load local index, resetting: {e}")
                    self.chunks = []
                    self.vectors = np.empty((0, 768), dtype=np.float32)

    def _save(self) -> None:
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False, indent=2)
        np.save(self.vectors_file, self.vectors)

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        if not chunks or not embeddings:
            return 0

        with self.lock:
            now_iso = datetime.now().isoformat()
            new_vectors = np.array(embeddings, dtype=np.float32)

            # Normalize vectors for fast cosine similarity via dot product
            norms = np.linalg.norm(new_vectors, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            new_vectors = new_vectors / norms

            for chunk in chunks:
                chunk["indexed_at"] = now_iso
                self.chunks.append(chunk)

            if len(self.vectors) == 0:
                self.vectors = new_vectors
            elif self.vectors.ndim == 2 and self.vectors.shape[1] != new_vectors.shape[1]:
                logger.warning(
                    f"Vector dimension changed from {self.vectors.shape[1]} to {new_vectors.shape[1]}. Resetting vector store index."
                )
                self.chunks = list(chunks)
                self.vectors = new_vectors
            else:
                self.vectors = np.vstack([self.vectors, new_vectors])

            self._save()
            logger.info(f"Added {len(chunks)} chunks to local vector store. Total: {len(self.chunks)}")
            return len(chunks)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        role: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        with self.lock:
            if len(self.chunks) == 0 or len(self.vectors) == 0:
                return []

            q_vec = np.array(query_embedding, dtype=np.float32)
            if self.vectors.ndim == 2 and self.vectors.shape[1] != q_vec.shape[0]:
                logger.warning(
                    f"Dimension mismatch in vector search: stored={self.vectors.shape[1]}, query={q_vec.shape[0]}. "
                    "Dokumen di-index dengan model embedding berbeda. Kembalikan pencarian kosong."
                )
                return []

            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            # Cosine similarity via dot product on normalized vectors
            scores = np.dot(self.vectors, q_vec)

            # Sort descending
            sorted_indices = np.argsort(scores)[::-1]

            results = []
            for idx in sorted_indices:
                score = float(scores[idx])
                if score < min_score:
                    continue

                chunk = self.chunks[idx]
                allowed_roles = chunk.get("allowed_roles", ["*"])

                # RBAC Filter: admin or "*" matches everything; otherwise user's role must match
                if role and role.lower() != "admin":
                    if "*" not in allowed_roles and role.lower() not in [r.lower() for r in allowed_roles]:
                        continue

                results.append({
                    "id": chunk.get("id"),
                    "document_id": chunk.get("document_id"),
                    "doc_title": chunk.get("doc_title"),
                    "page": chunk.get("page", 1),
                    "chunk_index": chunk.get("chunk_index", 0),
                    "text": chunk.get("text", ""),
                    "score": round(score, 4),
                    "allowed_roles": allowed_roles,
                })

                if len(results) >= top_k:
                    break

            return results

    def delete_document(self, document_id: str) -> int:
        with self.lock:
            doc_id_str = str(document_id)
            keep_indices = [
                i for i, chunk in enumerate(self.chunks)
                if str(chunk.get("document_id")) != doc_id_str
            ]
            deleted_count = len(self.chunks) - len(keep_indices)

            if deleted_count > 0:
                self.chunks = [self.chunks[i] for i in keep_indices]
                if len(keep_indices) > 0:
                    self.vectors = self.vectors[keep_indices]
                else:
                    self.vectors = np.empty((0, 768), dtype=np.float32)
                self._save()
                logger.info(f"Deleted document {document_id} ({deleted_count} chunks removed).")

            return deleted_count

    def list_documents(self) -> List[Dict[str, Any]]:
        with self.lock:
            docs_summary: Dict[str, Dict[str, Any]] = {}
            for chunk in self.chunks:
                doc_id = str(chunk.get("document_id"))
                if doc_id not in docs_summary:
                    docs_summary[doc_id] = {
                        "document_id": doc_id,
                        "doc_title": chunk.get("doc_title", "Dokumen"),
                        "filename": chunk.get("filename", f"{chunk.get('doc_title', 'doc')}.pdf"),
                        "chunks_count": 0,
                        "allowed_roles": chunk.get("allowed_roles", ["*"]),
                        "created_at": chunk.get("indexed_at", datetime.now().isoformat()),
                    }
                docs_summary[doc_id]["chunks_count"] += 1

            return list(docs_summary.values())


class QdrantVectorStore(BaseVectorStore):
    """
    Qdrant vector store backend for scalable production deployments.
    """

    def __init__(self):
        try:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
            )
            self.collection_name = settings.QDRANT_COLLECTION

            # Ensure collection exists
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}: {e}")
            raise

    def add_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        from qdrant_client.models import PointStruct
        import uuid

        points = []
        for chunk, emb in zip(chunks, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.get("id", str(uuid.uuid4()))))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=emb,
                    payload=chunk,
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        role: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        query_filter = None
        if role and role.lower() != "admin":
            query_filter = Filter(
                should=[
                    FieldCondition(key="allowed_roles", match=MatchValue(value="*")),
                    FieldCondition(key="allowed_roles", match=MatchValue(value=role.lower())),
                ]
            )

        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
            query_filter=query_filter,
            score_threshold=min_score if min_score > 0 else None,
        )

        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append({
                "id": payload.get("id"),
                "document_id": payload.get("document_id"),
                "doc_title": payload.get("doc_title"),
                "page": payload.get("page", 1),
                "chunk_index": payload.get("chunk_index", 0),
                "text": payload.get("text", ""),
                "score": round(hit.score, 4),
                "allowed_roles": payload.get("allowed_roles", ["*"]),
            })
        return results

    def delete_document(self, document_id: str) -> int:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        res = self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=str(document_id)))]
            ),
        )
        return 1

    def list_documents(self) -> List[Dict[str, Any]]:
        # In Qdrant, scroll collection to aggregate document metadata
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            limit=1000,
            with_payload=True,
            with_vectors=False,
        )
        docs_summary: Dict[str, Dict[str, Any]] = {}
        for p in points:
            payload = p.payload or {}
            doc_id = str(payload.get("document_id"))
            if doc_id not in docs_summary:
                docs_summary[doc_id] = {
                    "document_id": doc_id,
                    "doc_title": payload.get("doc_title", "Dokumen"),
                    "filename": payload.get("filename", f"{payload.get('doc_title', 'doc')}.pdf"),
                    "chunks_count": 0,
                    "allowed_roles": payload.get("allowed_roles", ["*"]),
                    "created_at": payload.get("indexed_at", datetime.now().isoformat()),
                }
            docs_summary[doc_id]["chunks_count"] += 1
        return list(docs_summary.values())


_vector_store_instance: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """Singleton getter for vector store based on configured backend."""
    global _vector_store_instance
    if _vector_store_instance is None:
        if settings.VECTOR_STORE_BACKEND.lower() == "qdrant":
            try:
                _vector_store_instance = QdrantVectorStore()
                logger.info("Using Qdrant vector store backend.")
            except Exception as e:
                logger.warning(f"Could not connect to Qdrant ({e}), falling back to LocalVectorStore.")
                _vector_store_instance = LocalVectorStore()
        else:
            _vector_store_instance = LocalVectorStore()
            logger.info("Using Local persistent vector store backend.")
    return _vector_store_instance
