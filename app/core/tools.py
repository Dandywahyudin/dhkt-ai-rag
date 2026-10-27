from typing import Any, Dict, List
from google.genai import types

# Definisi seluruh tools yang terdaftar dan dapat dipanggil oleh Gemini.
# Setiap nama tool di sini berkorespondensi langsung dengan method di AiToolsController.php CodeIgniter 4.
TOOL_DEFINITIONS = [
    {
        "name": "get_my_submission_status",
        "description": "Mengambil status pengajuan proposal, HKI, permohonan, atau komplain terbaru milik pengguna yang sedang login saat ini.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_submission_detail",
        "description": "Mengambil rincian detail suatu pengajuan/laporan spesifik berdasarkan nomor/ID pengajuan (submission_id).",
        "parameters": {
            "type": "object",
            "properties": {
                "submission_id": {
                    "type": "string",
                    "description": "ID atau nomor pengajuan/laporan yang ingin diperiksa, contoh: '12', '104'",
                }
            },
            "required": ["submission_id"],
        },
    },
    {
        "name": "get_dhkt_summary_stats",
        "description": "Mengambil ringkasan statistik total pengajuan atau laporan yang ada pada sistem DHKT (khusus admin melihat semua, user melihat miliknya).",
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
