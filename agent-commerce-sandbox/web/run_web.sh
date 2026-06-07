#!/bin/bash
cd "$(dirname "$0")/.."
pip install -r web/requirements.txt 2>/dev/null
uvicorn web.app:app --host 0.0.0.0 --port 8080 --timeout-keep-alive 600
