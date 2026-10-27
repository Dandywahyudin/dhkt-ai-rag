from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = """Anda adalah asisten AI resmi untuk DHKT (Direktorat / Bagian Terkait).
Tugas utama Anda adalah membantu pengguna menjawab pertanyaan berdasarkan dokumen SOP, panduan teknis, dan informasi internal yang disediakan.

ATURAN DAN PEDOMAN:
1. Jawablah secara ramah, profesional, dan dalam bahasa Indonesia yang baik.
2. Jawablah HANYA berdasarkan konteks dokumen yang diberikan. JANGAN MENGARANG atau membuat asumsi di luar isi dokumen (hindari halusinasi).
3. Jika informasi tidak ada atau kurang jelas di dalam dokumen konteks, katakan dengan jujur: "Maaf, informasi tersebut tidak ditemukan dalam dokumen internal yang tersedia."
4. Cantumkan rujukan judul dokumen atau halaman jika informasi tersebut tersedia dalam konteks.
5. Format jawaban menggunakan Markdown rapi (bullet points, numbering, atau bold text) agar nyaman dibaca.
"""

def format_context_chunks(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved document chunks into clean Markdown text for LLM injection."""
    if not chunks:
        return "Tidak ada dokumen konteks yang relevan ditemukan."

    formatted = []
    for i, chunk in enumerate(chunks, 1):
        doc_title = chunk.get("doc_title", "Dokumen")
        page = chunk.get("page", 1)
        text = chunk.get("text", "").strip()
        formatted.append(f"--- DOKUMEN [{i}]: {doc_title} (Halaman {page}) ---\n{text}")

    return "\n\n".join(formatted)


def build_rag_prompt(
    query: str,
    chunks: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    user_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Combine system context, conversation history, and query into a complete prompt."""
    context_text = format_context_chunks(chunks)

    user_info = ""
    if user_context:
        role = user_context.get("role", "Umum")
        unit = user_context.get("unit", "-")
        user_info = f"Informasi Pengguna: Role={role}, Unit={unit}\n"

    history_text = ""
    if history:
        history_lines = []
        for msg in history[-6:]:  # Keep last 6 exchanges to manage prompt window
            role = "Pengguna" if msg.get("role") == "user" else "Asisten"
            content = msg.get("content", "").strip()
            history_lines.append(f"{role}: {content}")
        if history_lines:
            history_text = "Riwayat Percakapan Sebelumnya:\n" + "\n".join(history_lines) + "\n\n"

    prompt = f"""{user_info}Konteks Dokumen Internal yang Relevan:
{context_text}

{history_text}Pertanyaan Pengguna Saat Ini:
{query}

Jawaban Asisten (berdasarkan konteks dokumen di atas):"""

    return prompt
