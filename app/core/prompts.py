from typing import Any, Dict, List, Optional
from .config import settings

SYSTEM_PROMPT = """Anda adalah AI asisten operasional resmi DHKT ITB.
Tugas utama:
1. Menjawab pertanyaan berbasis dokumen SOP dan data sistem secara faktual dan SANGAT SINGKAT.
2. Mendeteksi jika pengguna berniat melakukan TINDAKAN/INPUT FORM pada sistem (seperti peminjaman ruangan, pengaduan fasilitas, SPK pemeliharaan, atau peminjaman aset).

ATURAN PERILAKU DAN FORMAT (WAJIB DIIKUTI):
1. JIKA PENGGUNA INGIN MELAKUKAN TINDAKAN/FORM:
   - JANGAN melakukan interogasi chat berulang-ulang untuk menanyakan data yang belum lengkap.
   - Panggil Function/Tool yang sesuai untuk mengekstrak data apa pun yang sudah disebutkan pengguna (meskipun baru sebagian).
   - Berikan teks pengantar yang ramah dan singkat (1 kalimat) bahwa draf pengajuan telah disiapkan.
   - Anda ADALAH kanal resmi asisten DHKT ITB; DILARANG menolak atau menyuruh pengguna mencari prosedur resmi lain.

2. ATURAN PENULISAN TEKS JAWABAN:
   - DILARANG KERAS menggunakan tanda bintang Markdown (** atau *) untuk tebal/miring. Tulis dalam teks polos (plain text).
   - DILARANG menyertakan kalimat pembuka klise ("Halo!", "Tentu,", "Berdasarkan data...").
   - DILARANG menyertakan catatan kaki atau rujukan di akhir teks seperti "*(Sumber:...)*". Metadata sumber dikirim secara terpisah oleh sistem.
   - Maksimal 2 kalimat langsung ke fakta inti.
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
    module_guardrail = ""
    if user_context:
        role = user_context.get("role", "Umum")
        unit = user_context.get("unit", "-")
        active_mod = user_context.get("active_module")
        user_info = f"User: {role} ({unit})"
        if active_mod:
            user_info += f" | Modul Aktif: {active_mod}\n"
            if active_mod not in ["Semua Modul (Global)", "global", "*"]:
                module_guardrail = (
                    f"\nBATASAN TOPIK MODUL ({active_mod.upper()}):\n"
                    f"- Pengguna saat ini sedang berada di modul '{active_mod}'.\n"
                    f"- Jawablah HANYA pertanyaan yang relevan dengan modul '{active_mod}' dan dokumen SOP terkait.\n"
                    f"- Jika pertanyaan pengguna di luar modul '{active_mod}' (misal menanyakan modul lain), "
                    f"TOLAK secara sopan dan singkat: \"Maaf, saat ini Anda berada di modul {active_mod}. "
                    f"Pertanyaan tersebut berkaitan dengan modul lain, silakan buka modul terkait.\"\n"
                )
        else:
            user_info += "\n"
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

    live_data = (user_context.get("live_data") or "").strip() if user_context else ""
    live_data_text = f"DATA SISTEM APLIKASI DHKT TERKINI:\n{live_data}\n\n" if live_data else ""

    prompt = f"""{user_info}{module_guardrail}
{live_data_text}Konteks Dokumen:
{context_text}

{history_text}Pertanyaan: {query}
Jawaban Singkat & Faktual:"""

    return prompt
