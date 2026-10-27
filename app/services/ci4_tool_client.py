import json
import logging
import time
from typing import Any, Dict, Optional
import httpx
from ..core.config import settings
from ..core.security import generate_hmac_signature

logger = logging.getLogger("dhkt.ci4_tool")


class Ci4ToolClient:
    def __init__(self):
        self.base_url = settings.CI4_BASE_URL.rstrip("/")
        self.secret = settings.AI_INTERNAL_HMAC_SECRET
        self.timeout = settings.CI4_TOOL_TIMEOUT_SECONDS

    async def execute_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Kirim HTTP POST ke endpoint internal CodeIgniter 4:
        POST /internal/ai/tools/{tool_name}
        Dilengkapi dengan header otentikasi HMAC-SHA256.
        """
        context = {
            "id": user_context.get("id") if user_context else 1,
            "role": user_context.get("role") if user_context else "staff",
            "unit": user_context.get("unit") if user_context else None,
        }

        payload = {
            "user_context": context,
            "arguments": arguments or {},
        }

        body_str = json.dumps(payload, separators=(",", ":"))
        body_bytes = body_str.encode("utf-8")
        timestamp = str(int(time.time()))
        signature = generate_hmac_signature(timestamp, body_bytes, self.secret)

        url = f"{self.base_url}/internal/ai/tools/{tool_name}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Timestamp": timestamp,
            "X-CI4-Signature": signature,
        }

        logger.info(f"Executing CI4 Tool '{tool_name}' for user_id={context['id']} role={context['role']}")

        try:
            timeout_cfg = httpx.Timeout(self.timeout, connect=1.5)
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(url, headers=headers, content=body_bytes)

            if response.status_code == 200:
                data = response.json()
                logger.info(f"CI4 Tool '{tool_name}' succeeded.")
                return data
            else:
                logger.warning(f"CI4 Tool '{tool_name}' returned HTTP {response.status_code}: {response.text}")
                return {
                    "error": f"Gagal mengeksekusi tool di CodeIgniter (HTTP {response.status_code})",
                    "detail": response.text,
                }

        except (httpx.ConnectError, httpx.ConnectTimeout):
            logger.warning(f"Tidak dapat terhubung ke CodeIgniter di {url} (Koneksi offline/timeout). Mengembalikan simulasi.")
            return self._mock_fallback(tool_name, arguments, context)
        except Exception as e:
            logger.error(f"Error saat memanggil tool '{tool_name}': {e}")
            return {
                "error": f"Terjadi kesalahan saat memanggil fungsi internal: {str(e)}",
            }

    def _mock_fallback(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Fallback simulasi lokal ketika server CodeIgniter belum aktif / sedang dalam tahap pengujian.
        """
        if tool_name == "get_my_submission_status":
            return {
                "submission": {
                    "id": 101,
                    "status": "DALAM_PROSES_REVIEW",
                    "title": "Pengajuan Pemeliharaan Proyektor Lab A",
                    "updated_at": "2026-10-27 10:15:00",
                    "note": "[Data Simulasi - Server CI4 Offline]",
                }
            }
        elif tool_name == "get_submission_detail":
            sub_id = arguments.get("submission_id", "101")
            return {
                "submission": {
                    "id": sub_id,
                    "status": "DISETUJUI",
                    "title": f"Pengajuan #{sub_id}",
                    "description": "Pengajuan telah diverifikasi oleh koordinator fasilitas.",
                    "updated_at": "2026-10-26 14:00:00",
                    "note": "[Data Simulasi - Server CI4 Offline]",
                }
            }
        elif tool_name == "get_dhkt_summary_stats":
            return {
                "total": 42,
                "role": context.get("role", "staff"),
                "note": "[Data Simulasi - Server CI4 Offline]",
            }
        return {"note": "Tool dieksekusi dalam mode simulasi"}


ci4_tool_client = Ci4ToolClient()
