#!/bin/bash
# Ensure ChromaDB directory is writable by appuser
if [ -d "/app/chroma_db" ]; then
    chown -R appuser:appgroup /app/chroma_db 2>/dev/null || true
fi
# Ensure cache directories are writable
if [ -d "/home/appuser/.cache" ]; then
    chown -R appuser:appgroup /home/appuser/.cache 2>/dev/null || true
fi
# Switch to appuser and run the application
exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port 8001
