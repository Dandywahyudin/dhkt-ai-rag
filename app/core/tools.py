from typing import Any, Dict, List
from google.genai import types

# Definisi seluruh tools yang terdaftar dan dapat dipanggil oleh Gemini.
# Setiap nama tool di sini berkorespondensi langsung dengan method di AiToolsController.php CodeIgniter 4.
TOOL_DEFINITIONS = [
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
