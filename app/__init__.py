"""DHKT AI RAG Application Package"""
__version__ = "1.0.0"

def __getattr__(name):
    if name == "application":
        from .main import app as fastapi_app
        try:
            from a2wsgi import ASGIMiddleware
            return ASGIMiddleware(fastapi_app)
        except ImportError:
            return fastapi_app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
