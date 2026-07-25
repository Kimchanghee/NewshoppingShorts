"""Vercel ASGI entrypoint for the SSMaker authentication API."""

import sys
from pathlib import Path


# vercel.json bundles backend/** with this function. Import the application
# directly so deployments do not depend on a cached Git branch dependency.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
