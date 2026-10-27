from fastapi import APIRouter
from .endpoints import chat, documents, health

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(chat.router, tags=["Chat RAG"])
api_router.include_router(documents.router, tags=["Documents & Ingestion"])
