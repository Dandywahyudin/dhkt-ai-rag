import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Base Directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    INDEX_DIR: Path = STORAGE_DIR / "index"

    # Application
    APP_NAME: str = "DHKT AI RAG Service"
    APP_ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # LLM Provider ("sumopod" or "gemini")
    LLM_PROVIDER: str = "sumopod"

    # Sumopod AI (OpenAI Compatible - https://ai.sumopod.com)
    SUMOPOD_API_KEY: str = ""
    SUMOPOD_BASE_URL: str = "https://ai.sumopod.com/v1"
    SUMOPOD_MODEL: str = "deepseek-v4-flash"
    SUMOPOD_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # Security & HMAC (CodeIgniter 4 integration)
    AI_INTERNAL_HMAC_SECRET: str = "dhkt_internal_secret_key_2026"
    REQUIRE_HMAC: bool = False
    HMAC_MAX_SKEW_SECONDS: int = 300

    # CodeIgniter 4 Internal Tool Calling
    ENABLE_TOOL_CALLING: bool = True
    CI4_BASE_URL: str = "http://127.0.0.1:8080"
    CI4_TOOL_TIMEOUT_SECONDS: int = 10

    # Vector Store ("local" or "qdrant")
    VECTOR_STORE_BACKEND: str = "local"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "dhkt_knowledge"

    # RAG Parameters & Token Optimization (Hemat Kuota Token)
    CHUNK_SIZE: int = 600
    CHUNK_OVERLAP: int = 100
    TOP_K_RESULTS: int = 2
    MIN_SIMILARITY_SCORE: float = 0.35
    MAX_OUTPUT_TOKENS: int = 512
    MAX_HISTORY_MESSAGES: int = 3
    ENABLE_COMPACT_PROMPT: bool = True

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def init_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        self.INDEX_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.init_directories()
