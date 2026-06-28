#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
# Production auth API. Client also falls back here if an old URL is configured.
export API_SERVER_URL=https://project-user-dashboard-api.vercel.app
python ssmaker.py
