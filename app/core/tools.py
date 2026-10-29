from typing import Any, Dict, List
from google.genai import types

# Definisi seluruh tools yang terdaftar dan dapat dipanggil oleh Gemini.
# Setiap nama tool di sini berkorespondensi langsung dengan method di AiToolsController.php CodeIgniter 4.
TOOL_DEFINITIONS = [
    # 1. Modul Peminjaman Ruangan
    {
        "name": "draft_room_booking",
        "description": "Dipanggil saat pengguna berniat meminjam ruangan, aula, atau gedung pertemuan.",
        "parameters": {
            "type": "object",
            "properties": {
                "room_name": {"type": "string", "description": "Nama ruangan, misal: Ruang Meeting 08, Aula Barat"},
                "place_name": {"type": "string", "description": "Gedung/Lokasi, misal: STP Gedebage, CRCS"},
                "date": {"type": "string", "description": "Tanggal format YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "Jam mulai format HH:mm"},
                "end_time": {"type": "string", "description": "Jam selesai format HH:mm"},
                "activity_name": {"type": "string", "description": "Nama kegiatan atau acara"},
                "participant_count": {"type": "integer", "description": "Jumlah peserta"},
                "unit": {"type": "string", "description": "Unit atau bagian peminjam"},
            },
            "required": ["room_name"],
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
        "description": "Dipanggil saat membuat order pemeliharaan, jadwal servis rutin, atau perbaikan aset.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Nama pekerjaan SPK"},
                "target_facility": {"type": "string", "description": "Aset atau fasilitas yang akan diservis"},
                "due_date": {"type": "string", "description": "Tenggat pengerjaan format YYYY-MM-DD"},
                "executor": {"type": "string", "description": "Nama teknisi atau vendor pelaksana"},
            },
            "required": ["title"],
        },
    },
    # 4. Modul Peminjaman Barang / Aset
    {
        "name": "draft_asset_loan",
        "description": "Dipanggil saat pengguna meminjam aset bergerak (alat, proyektor, laptop, mobil dinas).",
        "parameters": {
            "type": "object",
            "properties": {
                "asset_name": {"type": "string", "description": "Nama aset atau barang yang dipinjam"},
                "quantity": {"type": "integer", "description": "Jumlah barang"},
                "loan_date": {"type": "string", "description": "Tanggal peminjaman"},
                "return_date": {"type": "string", "description": "Tanggal perkiraan kembali"},
                "unit": {"type": "string", "description": "Unit peminjam"},
            },
            "required": ["asset_name"],
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


def get_gemini_tools() -> List[types.Tool]:
    """Mengubah definisi tool menjadi objek types.Tool yang dikenali oleh Gemini SDK."""
    declarations = [
        types.FunctionDeclaration(
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
        )
        for tool in TOOL_DEFINITIONS
    ]
    return [types.Tool(function_declarations=declarations)]

def get_openai_tools() -> List[Dict[str, Any]]:
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
        for tool in TOOL_DEFINITIONS
    ]
