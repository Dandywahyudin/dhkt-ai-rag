import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx
import numpy as np

from ..core.config import settings
from ..core.prompts import SYSTEM_PROMPT
from ..core.tools import get_openai_tools
from .ci4_tool_client import ci4_tool_client

logger = logging.getLogger("dhkt.sumopod")


class SumopodService:
    def __init__(self):
        self.api_key = settings.SUMOPOD_API_KEY.strip()
        self.base_url = settings.SUMOPOD_BASE_URL.rstrip("/")
        self.chat_model = settings.SUMOPOD_MODEL
        self.embedding_model = settings.SUMOPOD_EMBEDDING_MODEL
        self.timeout = 60.0

        if self.api_key:
            logger.info(f"Sumopod AI service initialized with model: {self.chat_model} ({self.base_url})")
        else:
            logger.warning(
                "SUMOPOD_API_KEY is not set. Service will use mock embeddings and return setup instructions."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "DHKT-AI-RAG/1.0",
        }

    def _mock_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """
        Deterministic mock embedding based on SHA256 hash for offline testing
        when SUMOPOD_API_KEY has not yet been set.
        """
        hash_digest = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(hash_digest[:4], "little")
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector using Sumopod OpenAI-compatible /v1/embeddings endpoint."""
        if not self.is_configured:
            return self._mock_embedding(text)

        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.embedding_model,
            "input": text,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                if res.status_code == 200:
                    data = res.json()
                    emb_list = data.get("data", [])
                    if emb_list and "embedding" in emb_list[0]:
                        return emb_list[0]["embedding"]
                logger.warning(f"Sumopod embedding returned status {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.error(f"Error calling Sumopod embeddings: {e}")

        return self._mock_embedding(text)

    async def generate_embeddings_batch(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """Generate embeddings in batches."""
        if not texts:
            return []

        if not self.is_configured:
            return [self._mock_embedding(t) for t in texts]

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            url = f"{self.base_url}/embeddings"
            payload = {
                "model": self.embedding_model,
                "input": batch,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(url, headers=self._get_headers(), json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))
                        for item in items:
                            all_embeddings.append(item["embedding"])
                        continue
                    logger.warning(f"Sumopod batch embeddings error {res.status_code}: {res.text[:200]}")
            except Exception as e:
                logger.error(f"Error in batch embeddings: {e}")

            # Fallback for this batch if failed
            for t in batch:
                all_embeddings.append(self._mock_embedding(t))

        return all_embeddings

    async def generate_response(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        enable_tools: bool = True,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, List[str], Optional[Dict[str, Any]]]:
        """
        Generate chat answer using Sumopod DeepSeek LLM with Tool Calling support.
        Returns: (reply_text, list_of_tools_called, extracted_tool_data)
        """
        tools_called: List[str] = []
        tool_data: Optional[Dict[str, Any]] = None

        # Handler saat API Key belum diisi (Offline / Development Mock)
        if not self.is_configured:
            prompt_lower = prompt.lower()
            if enable_tools and any(kw in prompt_lower for kw in ["statistik", "total", "summary", "rekap"]):
                tools_called.append("get_dhkt_summary_stats")
                sim_data = await ci4_tool_client.execute_tool("get_dhkt_summary_stats", {}, user_context)
                reply = (
                    f"Berdasarkan data statistik dari sistem CodeIgniter, "
                    f"total pengajuan yang tercatat saat ini berjumlah: {sim_data.get('total', 42)} pengajuan."
                )
                return reply, tools_called, None

            elif enable_tools and any(kw in prompt_lower for kw in ["status", "pengajuan", "laporan", "tiket", "submission"]):
                tools_called.append("get_my_submission_status")
                sim_data = await ci4_tool_client.execute_tool("get_my_submission_status", {}, user_context)
                sub = sim_data.get("submission", {})
                reply = (
                    f"Berdasarkan pengecekan data internal ke sistem CodeIgniter, pengajuan Anda "
                    f"(ID: #{sub.get('id', 101)}) bertajuk '{sub.get('title', 'Pengajuan')}' "
                    f"saat ini berstatus: {sub.get('status', 'DALAM_PROSES')} "
                    f"(terakhir diperbarui: {sub.get('updated_at', '-')})."
                )
                return reply, tools_called, None

            return (
                "Perhatian: Kunci SUMOPOD_API_KEY belum dikonfigurasi di file .env.",
                tools_called,
                None,
            )
        url = f"{self.base_url}/chat/completions"
        sys_inst = system_instruction or SYSTEM_PROMPT

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": sys_inst},
            {"role": "user", "content": prompt},
        ]

        # Live data from CI4 replaces the get_* tools; draft tools stay so forms can still be prepared.
        has_live_data = bool(user_context and user_context.get("live_data"))
        tools = get_openai_tools(drafts_only=has_live_data) if (enable_tools and settings.ENABLE_TOOL_CALLING) else None

        payload: Dict[str, Any] = {
            "model": self.chat_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": getattr(settings, "MAX_OUTPUT_TOKENS", 512),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                if res.status_code != 200:
                    err_msg = res.text[:300]
                    logger.error(f"Sumopod chat error ({res.status_code}): {err_msg}")
                    return f"Terjadi kendala saat menghubungi Sumopod DeepSeek API ({res.status_code}): {err_msg}", tools_called, None

                resp_data = res.json()
                choices = resp_data.get("choices", [])
                if not choices:
                    return "Maaf, tidak ada tanggapan teks yang dihasilkan oleh model DeepSeek.", tools_called, None

                choice_msg = choices[0].get("message", {})
                tool_calls = choice_msg.get("tool_calls")

                # Jika model memutuskan memanggil tools
                if tool_calls:
                    # Tambahkan pesan assistant ke riwayat
                    messages.append(choice_msg)

                    for tc in tool_calls:
                        func = tc.get("function", {})
                        t_name = func.get("name")
                        try:
                            t_args = json.loads(func.get("arguments", "{}"))
                        except Exception:
                            t_args = {}

                        tools_called.append(t_name)
                        if t_name.startswith("draft_"):
                            tool_data = {"form_type": t_name, **t_args}
                        logger.info(f"Sumopod DeepSeek triggered tool call: '{t_name}' with args: {t_args}")
                        tool_result = await ci4_tool_client.execute_tool(
                            tool_name=t_name,
                            arguments=t_args,
                            user_context=user_context,
                        )

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id"),
                            "content": json.dumps({"result": tool_result}),
                        })

                    # Round 2: Kirim data hasil tool ke Sumopod DeepSeek
                    payload_turn2 = {
                        "model": self.chat_model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": getattr(settings, "MAX_OUTPUT_TOKENS", 512),
                    }

                    res2 = await client.post(url, headers=self._get_headers(), json=payload_turn2)
                    if res2.status_code == 200:
                        data2 = res2.json()
                        msg2 = data2.get("choices", [{}])[0].get("message", {})
                        reply2 = msg2.get("content") or msg2.get("reasoning_content") or ""
                        return reply2.strip() if reply2 else "Draf form berhasil disiapkan.", tools_called, tool_data
                    else:
                        logger.warning(f"Sumopod round 2 returned HTTP {res2.status_code}: {res2.text[:200]}")
                        return "Draf pengajuan form telah berhasil disiapkan.", tools_called, tool_data

                reply_content = choice_msg.get("content") or choice_msg.get("reasoning_content") or ""
                return reply_content.strip() if reply_content else "Maaf, tidak ada teks jawaban yang dikembalikan.", tools_called, None
        except Exception as e:
            logger.error(f"Error calling Sumopod DeepSeek chat/completions: {e}")
            return f"Terjadi kendala saat menghubungi Sumopod API: {str(e)}", tools_called, None

sumopod_service = SumopodService()
