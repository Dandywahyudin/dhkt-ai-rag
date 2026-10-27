import io
from pathlib import Path
from typing import Any, Dict, List, Union
import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from ..core.config import settings


class PDFService:
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def extract_text_by_pages(self, file_source: Union[str, Path, bytes]) -> List[Dict[str, Any]]:
        """
        Extract text from each page of a PDF document.
        Accepts a file path string, Path object, or raw bytes.
        """
        pages_content: List[Dict[str, Any]] = []

        if isinstance(file_source, bytes):
            doc = pymupdf.open(stream=file_source, filetype="pdf")
        else:
            file_path = Path(file_source)
            if not file_path.exists():
                raise FileNotFoundError(f"File PDF tidak ditemukan: {file_path}")
            doc = pymupdf.open(str(file_path))

        try:
            for page_index in range(len(doc)):
                page = doc[page_index]
                text = page.get_text("text") or ""
                # Clean up excessive blank lines while preserving paragraphs
                clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
                if clean_text:
                    pages_content.append({
                        "page_number": page_index + 1,
                        "text": clean_text,
                    })
        finally:
            doc.close()

        return pages_content

    def process_pdf(
        self,
        file_source: Union[str, Path, bytes],
        document_id: Union[int, str],
        doc_title: str,
        allowed_roles: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts pages from PDF, splits into semantic chunks, and assigns metadata.
        Returns a list of chunk dictionaries ready for embedding and indexing.
        """
        if allowed_roles is None:
            allowed_roles = ["*"]

        pages = self.extract_text_by_pages(file_source)
        chunks: List[Dict[str, Any]] = []
        global_chunk_idx = 0

        for page_data in pages:
            page_num = page_data["page_number"]
            page_text = page_data["text"]

            page_chunks = self.splitter.split_text(page_text)
            for chunk_text in page_chunks:
                chunk_text = chunk_text.strip()
                if not chunk_text:
                    continue

                chunks.append({
                    "id": f"doc_{document_id}_p{page_num}_c{global_chunk_idx}",
                    "document_id": str(document_id),
                    "doc_title": doc_title,
                    "page": page_num,
                    "chunk_index": global_chunk_idx,
                    "text": chunk_text,
                    "allowed_roles": allowed_roles,
                })
                global_chunk_idx += 1

        return chunks


pdf_service = PDFService()
