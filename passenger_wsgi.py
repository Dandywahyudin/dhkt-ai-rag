import os
import sys

# Pastikan root direktori projek terdaftar di sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.main import app

# WSGI Application entry point untuk Phusion Passenger / cPanel
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    application = app
