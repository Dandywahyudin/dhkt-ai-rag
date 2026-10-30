from typing import Any, Dict, List
from google.genai import types

# Definisi seluruh tools yang terdaftar dan dapat dipanggil oleh LLM.
# Tool draft_* tidak dieksekusi di CodeIgniter: argumennya dikembalikan sebagai `tool_call` dan
# AssistantFormTools.php di CI4 mengubahnya menjadi link form terisi. Nama argumen harus sama dengan
# yang dibaca AssistantFormTools. Tool get_* berkorespondensi dengan endpoint internal CI4.
TOOL_DEFINITIONS = [
    # 1. Modul Peminjaman Ruangan
    {
        "name": "draft_room_booking",
        "description": "Dipanggil saat pengguna berniat meminjam ruangan, aula, atau gedung pertemuan.",
        "parameters": {
            "type": "object",
            "properties": {
                "activity_name": {"type": "string", "description": "Nama kegiatan atau acara"},
                "description": {"type": "string", "description": "Deskripsi singkat kegiatan"},
                "category": {"type": "string", "enum": ["internal_dhkt", "eksternal"], "description": "Kategori peminjam"},
                "unit": {"type": "string", "description": "Unit atau bagian peminjam"},
                "participant_count": {"type": "integer", "description": "Jumlah peserta"},
                "place_name": {"type": "string", "description": "Gedung/Lokasi, misal: STP Gedebage, CRCS"},
                "room_name": {"type": "string", "description": "Nama ruangan, misal: Ruang Meeting 08, Aula Barat"},
                "date": {"type": "string", "description": "Tanggal format YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "Jam mulai format HH:mm"},
                "end_time": {"type": "string", "description": "Jam selesai format HH:mm"},
                "duration_minutes": {"type": "integer", "description": "Durasi dalam menit bila jam selesai tidak disebut"},
            },
            "required": [],
        },
    },
    # 2. Modul Pengaduan Fasilitas
    {
        "name": "draft_facility_complaint",
        "description": "Dipanggil saat pengguna melaporkan keluhan, kerusakan fasilitas, atau kendala sarana.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Judul keluhan singkat"},
                "location": {"type": "string", "description": "Lokasi kejadian atau ruangan"},
                "description": {"type": "string", "description": "Rincian kerusakan atau keluhan"},
            },
            "required": ["title", "location"],
        },
    },
    # 3. Modul Pemeliharaan Fasilitas / SPK
    {
        "name": "draft_maintenance_spk",
        "description": "Dipanggil saat membuat order/jadwal pemeliharaan, servis rutin, atau perbaikan aset, fasilitas, atau ruangan.",
        "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["pemeliharaan", "perbaikan"], "description": "pemeliharaan = terjadwal/rutin, perbaikan = kerusakan"},
                "title": {"type": "string", "description": "Nama pekerjaan, misal: Servis AC rutin"},
                "description": {"type": "string", "description": "Rincian pekerjaan atau uraian kerusakan, termasuk lokasi/gedung"},
                "frequency": {"type": "string", "enum": ["once", "monthly", "quarterly", "yearly"], "description": "Pengulangan untuk pemeliharaan: sekali, bulanan, triwulanan, tahunan"},
                "target": {"type": "string", "enum": ["asset", "facility", "room"], "description": "Kategori objek: aset inventaris, fasilitas gedung (AC, lift, genset), atau ruangan"},
                "object_name": {"type": "string", "description": "Nama aset/fasilitas/ruangan yang dikerjakan"},
                "due_date": {"type": "string", "description": "Tanggal target format YYYY-MM-DD"},
                "planned_start": {"type": "string", "description": "Rencana mulai format YYYY-MM-DD"},
            },
            "required": [],
        },
    },
    # 4. Modul Peminjaman Barang / Aset
    {
        "name": "draft_asset_loan",
        "description": "Dipanggil saat pengguna meminjam aset bergerak (alat, proyektor, laptop, mobil dinas).",
        "parameters": {
            "type": "object",
            "properties": {
                "purpose": {"type": "string", "description": "Tujuan peminjaman"},
                "items": {"type": "array", "items": {"type": "string"}, "description": "Nama barang yang dipinjam"},
                "start_date": {"type": "string", "description": "Tanggal mulai format YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "Jam mulai format HH:mm"},
                "end_date": {"type": "string", "description": "Tanggal kembali format YYYY-MM-DD"},
                "end_time": {"type": "string", "description": "Jam kembali format HH:mm"},
            },
            "required": [],
        },
    },
    # 5. Tools Query Status & Statistik
    {
        "name": "get_my_submission_status",
        "description": "Mengambil status permohonan atau laporan layanan terbaru milik pengguna saat ini.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_submission_detail",
        "description": "Mengambil rincian detail suatu permohonan/laporan spesifik berdasarkan nomor/ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "submission_id": {
                    "type": "string",
                    "description": "ID atau nomor permohonan/laporan, contoh: '12', '104'",
                }
            },
            "required": ["submission_id"],
        },
    },
    {
        "name": "get_dhkt_summary_stats",
        "description": "Mengambil ringkasan statistik layanan internal di sistem DHKT.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


def _definitions(drafts_only: bool) -> List[Dict[str, Any]]:
    return [t for t in TOOL_DEFINITIONS if not drafts_only or t["name"].startswith("draft_")]


def get_gemini_tools(drafts_only: bool = False) -> List[types.Tool]:
    """Mengubah definisi tool menjadi objek types.Tool yang dikenali oleh Gemini SDK."""
    declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
        )
        for tool in _definitions(drafts_only)
    ]
    return [types.Tool(function_declarations=declarations)]

def get_openai_tools(drafts_only: bool = False) -> List[Dict[str, Any]]:
    """Mengubah definisi tool menjadi format OpenAI Function Calling (digunakan oleh Sumopod / DeepSeek)."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in _definitions(drafts_only)
    ]
