from ..core.config import settings
from .gemini_service import gemini_service
from .sumopod_service import sumopod_service


def get_llm_service():
    """
    Mengembalikan instance LLM service sesuai konfigurasi LLM_PROVIDER di .env.
    Pilihan: 'sumopod' (default) atau 'gemini'.
    """
    provider = settings.LLM_PROVIDER.strip().lower()
    if provider == "gemini":
        return gemini_service
    return sumopod_service
