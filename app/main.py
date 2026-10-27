from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api.v1.router import api_router
from .core.config import settings
from .services.vector_store import get_vector_store

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("dhkt.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories and vector store initialized
    logger.info("Starting DHKT AI RAG Service...")
    settings.init_directories()
    vs = get_vector_store()
    logger.info(f"Vector store initialized ({settings.VECTOR_STORE_BACKEND}). Current documents: {len(vs.list_documents())}")
    yield
    # Shutdown
    logger.info("Shutting down DHKT AI RAG Service...")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "Microservice RAG (Retrieval-Augmented Generation) berbasis Python FastAPI & Google Gemini API, "
        "terintegrasi dengan CodeIgniter 4 dan mendukung ekstraksi & pencarian dokumen PDF internal."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "detail": f"Terjadi kesalahan internal pada AI service: {str(exc)}",
        },
    )


# Root Endpoint
@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs_url": "/docs",
        "api_v1": "/v1",
        "description": "Layanan AI RAG Dokumen PDF siap digunakan & terintegrasi dengan CodeIgniter 4.",
    }


# Mount API V1 Router
app.include_router(api_router, prefix="/v1")
