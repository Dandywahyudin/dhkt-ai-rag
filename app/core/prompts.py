from typing import Any, Dict, List, Optional
from .config import settings

# Long assistant replies are cut; the details users give (object, place, date) fit well within this.
HISTORY_MESSAGE_CHARS = 500

SYSTEM_PROMPT = """Anda adalah asisten AI operasional resmi DHKT ITB.

PEDOMAN UTAMA:
1. GAYA BAHASA ALAMI & PROFESIONAL:
   - Gunakan bahasa Indonesia yang santun, ramah, natural, dan komunikatif layaknya staf profesional DHKT ITB.
   - Jawablah secara padat, lugas, dan langsung menjawab pertanyaan pengguna secara tuntas.

2. PERBEDAAN PERTANYAAN INFORMASI (INQUIRY) VS AKSI INPUT FORM (ACTION):
   - JIKA PENGGUNA HANYA BERTANYA / MENGECEK DATA (contoh: "apakah ada pemeliharaan yang terlambat?", "jadwal ruangan besok apa saja?", "bagaimana SOP pengaduan?", "siapa yang memakai aula?"):
     -> Jawablah murni sebagai percakapan chat biasa yang informatif. DILARANG memanggil tool form atau membuat draf form.
   - JIKA PENGGUNA SECARA EKSPLISIT MEMINTA INPUT / PENGAJUAN (contoh: "saya mau pinjam ruang 08 besok...", "tolong buatkan pengaduan AC rusak...", "ajukan pemeliharaan proyektor..."):
     -> Panggil Function/Tool yang relevan untuk mengekstrak data yang disebutkan.
     -> Berikan respons ramah bahwa draf pengajuan telah disiapkan.

3. KONTEKS PERCAKAPAN:
   - Bagian "Riwayat" adalah percakapan sebelumnya dengan pengguna yang sama. Selalu baca Riwayat sebelum menjawab.
   - Jawaban singkat seperti "iya", "ya", "boleh", "lanjut", atau tambahan data seperti "lokasinya di gedung X, tanggal Y" adalah kelanjutan permintaan sebelumnya. Jangan memulai percakapan baru atau menyapa ulang.
   - Saat memanggil tool draf, isi argumennya dari SELURUH percakapan (Riwayat + pertanyaan terakhir), bukan hanya pesan terakhir. Jangan menanyakan ulang data yang sudah disebutkan.
   - Jangan mengatakan draf telah disiapkan kecuali Anda benar-benar memanggil tool draf.

4. ATURAN FORMAT TEKS:
   - DILARANG KERAS menggunakan tanda bintang Markdown (** atau *) untuk tebal/miring. Tulis dalam teks polos (plain text).
   - DILARANG menyertakan catatan kaki atau rujukan seperti "*(Sumber:...)*" di akhir teks. Metadata sumber dikelola oleh sistem secara terpisah.
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
        max_hist = getattr(settings, "MAX_HISTORY_MESSAGES", 12)
        for msg in history[-max_hist:]:
            role = "U" if msg.get("role") == "user" else "A"
            content = msg.get("content", "").strip()
            if len(content) > HISTORY_MESSAGE_CHARS:
                content = content[:HISTORY_MESSAGE_CHARS] + "..."
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
