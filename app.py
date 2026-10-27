import os
import sys

# Pastikan root direktori projek terdaftar di sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app
from app.core.config import settings

# WSGI Application Adapter (untuk cPanel / Phusion Passenger / WSGI Server)
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    # Fallback jika a2wsgi belum terinstall
    application = app

# Entrypoint saat dijalankan langsung: python app.py
if __name__ == "__main__":
    import uvicorn
    print(f"Starting {settings.APP_NAME} on http://{settings.HOST}:{settings.PORT} ...")
    print(f"Interactive Swagger Documentation: http://localhost:{settings.PORT}/docs")
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
