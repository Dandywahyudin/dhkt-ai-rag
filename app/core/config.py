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

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
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

    # RAG Parameters
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RESULTS: int = 4
    MIN_SIMILARITY_SCORE: float = 0.3

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
