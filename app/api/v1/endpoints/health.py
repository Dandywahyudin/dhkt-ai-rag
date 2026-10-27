from fastapi import APIRouter
from ....core.config import settings
from ....services.gemini_service import gemini_service
from ....services.vector_store import get_vector_store

router = APIRouter()


@router.get("/health", summary="Health check service status")
async def health_check():
    vector_store = get_vector_store()
    docs = vector_store.list_documents()

    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "gemini_api_configured": gemini_service.is_configured,
        "gemini_model": settings.GEMINI_MODEL,
        "vector_backend": settings.VECTOR_STORE_BACKEND,
        "indexed_documents_count": len(docs),
        "require_hmac": settings.REQUIRE_HMAC,
    }
