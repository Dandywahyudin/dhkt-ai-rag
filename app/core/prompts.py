from typing import Any, Dict, List, Optional
from .config import settings

SYSTEM_PROMPT = """Anda adalah asisten AI DHKT ITB.
Tugas: Jawab pertanyaan pengguna berdasarkan dokumen konteks internal yang diberikan.

PEDOMAN JAWABAN:
1. Jawab langsung ke inti (to-the-point), padat, jelas, dan profesional. Hindari basa-basi panjang.
2. Jawab HANYA berdasarkan dokumen yang relevan. Jika tidak ada di dokumen, nyatakan secara ringkas.
3. Sertakan rujukan dokumen/halaman singkat jika tersedia.
4. Gunakan poin ringkas (bullet points) jika menjelaskan langkah/syarat.
"""

def format_context_chunks(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved document chunks into clean, token-efficient text."""
    if not chunks:
        return "Tidak ada dokumen relevan."

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        doc_title = chunk.get("doc_title", "Dokumen")
        page = chunk.get("page", 1)
        text = chunk.get("text", "").strip()
        formatted.append(f"[{i}] {doc_title} (Hal {page}):\n{text}")

    return "\n\n".join(formatted)


def build_rag_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Combine system context, conversation history, and query into a token-efficient prompt."""
    context_text = format_context_chunks(chunks)

    user_info = ""
    if user_context:
        role = user_context.get("role", "Umum")
        unit = user_context.get("unit", "-")
        user_info = f"User: {role} ({unit})\n"

    history_text = ""
    if history:
        history_lines = []
        max_hist = getattr(settings, "MAX_HISTORY_MESSAGES", 3)
        for msg in history[-max_hist:]:
            role = "U" if msg.get("role") == "user" else "A"
            content = msg.get("content", "").strip()
            if len(content) > 180:
                content = content[:180] + "..."
            history_lines.append(f"{role}: {content}")
        if history_lines:
            history_text = "Riwayat:\n" + "\n".join(history_lines) + "\n\n"

    prompt = f"""{user_info}Konteks Dokumen:
{context_text}

{history_text}Pertanyaan: {query}
Jawaban:"""

    return prompt
