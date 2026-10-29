from typing import Any, Dict, List, Optional
from .config import settings

SYSTEM_PROMPT = """Anda adalah asisten data & SOP DHKT ITB.
Tugas: Jawab pertanyaan secara faktual, akurat, dan SANGAT SINGKAT.

ATURAN OUTPUT (WAJIB DIIKUTI):
1. SANGAT RINGKAS: Maksimal 2–3 kalimat langsung ke inti fakta atau data.
2. DILARANG KERAS menggunakan kalimat pembuka/salam (contoh dilarang: "Halo!", "Tentu,", "Berdasarkan data...", "Berdasarkan dokumen...", "Berikut adalah...").
3. DILARANG KERAS menggunakan kalimat penutup/saran (contoh dilarang: "Semoga membantu", "Saran: ajukan ke...", "Ada yang perlu ditanyakan lagi?", "Catatan:").
4. Langsung jawab fakta atau status data intinya.
5. Jika data tidak ditemukan, jawab HANYA 1 kalimat: "Data tidak ditemukan dalam sistem."
6. Jangan mengulang pertanyaan pengguna.
7. DILARANG KERAS MENGGUNAKAN TANDA BINTANG MARKDOWN (** atau *) untuk penekanan (bold/italic) maupun daftar. Gunakan teks polos (plain text).
8. DILARANG KERAS MENAMBAHKAN CATATAN KAKI atau disclaimer sumber seperti "*(Sumber:...)*" di dalam teks jawaban. Informasi rujukan sudah dikelola oleh sistem secara terpisah.
9. JIKA PENGGUNA BERMAKSUD MEMINJAM RUANGAN ATAU MENGISI FORM:
   - Anda ADALAH bagian dari sistem resmi operasional DHKT ITB. DILARANG KERAS menolak atau menyuruh pengguna "mengajukan melalui kanal/prosedur resmi".
   - Periksa DATA SISTEM APLIKASI DHKT TERKINI apakah ada benturan jadwal.
   - Jika tidak ada benturan jadwal, jawab dengan ramah dan lugas bahwa ruangan tersedia pada jadwal yang diminta dan form peminjaman telah disiapkan.
   - Ekstrak seluruh parameter form peminjaman ke dalam blok JSON di akhir respons:
   ```json:form_data
   {
     "form_type": "room_booking",
     "activity_name": "...",
     "place_name": "...",
     "room_name": "...",
     "date_range": "DD-MM-YYYY HH:mm - DD-MM-YYYY HH:mm",
     "participant_count": 0,
     "unit": "...",
     "description": "...",
     "category": "internal_dhkt"
   }
   ```
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
