from fastapi import APIRouter
from ....core.config import settings
from ....services.gemini_service import gemini_service
from ....services.llm_service import get_llm_service
from ....services.vector_store import get_vector_store

router = APIRouter()


@router.get("/health", summary="Health check service status")
async def health_check():
    vector_store = get_vector_store()
    docs = vector_store.list_documents()

    llm = get_llm_service()
    current_model = settings.SUMOPOD_MODEL if settings.LLM_PROVIDER.lower() == "sumopod" else settings.GEMINI_MODEL

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "llm_provider": settings.LLM_PROVIDER,
        "model": current_model,
        "api_configured": llm.is_configured,
        "gemini_api_configured": llm.is_configured,
        "gemini_model": current_model,
        "vector_backend": settings.VECTOR_STORE_BACKEND,
        "indexed_documents_count": len(docs),
        "require_hmac": settings.REQUIRE_HMAC,
    }
