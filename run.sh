#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
pkill -f "streamlit run" || true
streamlit run photo_agent_app.py --server.port 8501 --server.headless true
