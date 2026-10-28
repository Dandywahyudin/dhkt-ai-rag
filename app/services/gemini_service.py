import hashlib
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from ..core.config import settings
from ..core.prompts import SYSTEM_PROMPT
from ..core.tools import get_gemini_tools
from .ci4_tool_client import ci4_tool_client

logger = logging.getLogger("dhkt.gemini")


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY.strip()
        self.chat_model = settings.GEMINI_MODEL
        self.embedding_model = settings.GEMINI_EMBEDDING_MODEL
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("Google GenAI client initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize Google GenAI client: {e}")
                self.client = None
        else:
            logger.warning(
                "GEMINI_API_KEY is not set. Service will use mock embeddings and return setup notice for chats."
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.client)

    def _mock_embedding(self, text: str, dimension: int = 768) -> List[float]:
        """
        Deterministic mock embedding based on SHA256 hash for offline testing
        when GEMINI_API_KEY has not yet been set.
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
        """Generate embedding vector for a single string."""
        if not self.is_configured:
            return self._mock_embedding(text)

        try:
            response = self.client.models.embed_content(
                model=self.embedding_model,
                contents=text,
            )
            if response.embeddings and len(response.embeddings) > 0:
                return response.embeddings[0].values
            raise ValueError("No embeddings returned by Gemini API")
        except Exception as e:
            logger.error(f"Error calling Gemini embed_content: {e}")
            return self._mock_embedding(text)

    async def generate_embeddings_batch(self, texts: List[str], batch_size: int = 20) -> List[List[float]]:
        """Generate embeddings in batches to stay within API rate limits."""
        if not texts:
            return []

        if not self.is_configured:
            return [self._mock_embedding(t) for t in texts]

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = self.client.models.embed_content(
                    model=self.embedding_model,
                    contents=batch,
                )
                if response.embeddings:
                    for emb in response.embeddings:
                        all_embeddings.append(emb.values)
                else:
                    for t in batch:
                        all_embeddings.append(self._mock_embedding(t))
            except Exception as e:
                logger.error(f"Error in batch embed_content: {e}")
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
    ) -> Tuple[str, List[str]]:
        """
        Generate chat answer using Gemini LLM with integrated Tool Calling support.
        Returns: (reply_text, list_of_tools_called)
        """
        tools_called: List[str] = []

        # Handler saat API Key belum diisi (Offline / Development Mock)
        if not self.is_configured:
            prompt_lower = prompt.lower()
            if enable_tools and any(kw in prompt_lower for kw in ["statistik", "total", "summary", "rekap"]):
                tools_called.append("get_dhkt_summary_stats")
                sim_data = await ci4_tool_client.execute_tool("get_dhkt_summary_stats", {}, user_context)
                reply = (
                    f"Berdasarkan data statistik dari sistem CodeIgniter, "
                    f"total pengajuan yang tercatat saat ini berjumlah: **{sim_data.get('total', 42)} pengajuan**."
                )
                return reply, tools_called

            elif enable_tools and any(kw in prompt_lower for kw in ["status", "pengajuan", "laporan", "tiket", "submission"]):
                tools_called.append("get_my_submission_status")
                sim_data = await ci4_tool_client.execute_tool("get_my_submission_status", {}, user_context)
                sub = sim_data.get("submission", {})
                reply = (
                    f"Berdasarkan pengecekan data internal ke sistem CodeIgniter, pengajuan Anda "
                    f"(ID: #{sub.get('id', 101)}) bertajuk **'{sub.get('title', 'Pengajuan')}'** "
                    f"saat ini berstatus: **{sub.get('status', 'DALAM_PROSES')}** "
                    f"(terakhir diperbarui: {sub.get('updated_at', '-')})."
                )
                return reply, tools_called

            return (
                "⚠️ **Perhatian**: Kunci `GEMINI_API_KEY` belum dikonfigurasi di file `.env`.\n\n"
                "Silakan ikuti langkah berikut untuk mengaktifkan AI:\n"
                "1. Dapatkan API Key gratis di [Google AI Studio](https://aistudio.google.com/)\n"
                "2. Masukkan ke file `.env`: `GEMINI_API_KEY=AIzaSy...`\n"
                "3. Restart server FastAPI ini.",
                tools_called,
            )

        try:
            from google.genai import types

            sys_inst = system_instruction or SYSTEM_PROMPT
            tools = get_gemini_tools() if (enable_tools and settings.ENABLE_TOOL_CALLING) else None

            config = types.GenerateContentConfig(
                system_instruction=sys_inst,
                temperature=temperature,
                tools=tools,
                max_output_tokens=getattr(settings, "MAX_OUTPUT_TOKENS", 512),
            )

            # Round 1: Model evaluates prompt & decides whether to call a tool
            response = self.client.models.generate_content(
                model=self.chat_model,
                contents=prompt,
                config=config,
            )

            # Jika model memutuskan memanggil satu atau lebih Tools
            if response.function_calls:
                tool_parts = []
                for fc in response.function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}
                    tools_called.append(tool_name)
                    logger.info(f"Gemini triggered tool call: '{tool_name}' with arguments: {tool_args}")

                    # Eksekusi fungsi ke CodeIgniter 4
                    tool_result = await ci4_tool_client.execute_tool(
                        tool_name=tool_name,
                        arguments=tool_args,
                        user_context=user_context,
                    )

                    tool_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )

                # Round 2: Kirim hasil data mentah ke Gemini untuk dirangkai menjadi jawaban natural
                second_turn_contents = [
                    prompt,
                    response.candidates[0].content,
                    types.Content(role="user", parts=tool_parts),
                ]
                final_response = self.client.models.generate_content(
                    model=self.chat_model,
                    contents=second_turn_contents,
                    config=config,
                )
                reply = final_response.text.strip() if final_response.text else "Panggilan tool selesai dijalankan."
                return reply, tools_called

            reply = response.text.strip() if response.text else "Maaf, tidak ada tanggapan teks yang dihasilkan."
            return reply, tools_called

        except Exception as e:
            logger.error(f"Error calling Gemini generate_content: {e}")
            return f"Terjadi kendala saat menghubungi Gemini API: {str(e)}", tools_called


gemini_service = GeminiService()
