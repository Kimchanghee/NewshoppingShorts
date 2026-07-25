"""Vercel ASGI entrypoint for the SSMaker authentication API."""

# `app` is installed from the repository through api/requirements.txt.
# This keeps the Vercel function self-contained even when a direct deployment
# tool uploads only files below `api/`.
from app.main import app
